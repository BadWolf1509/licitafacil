"""
Funções de validação de linhas para o corretor de descrições.
"""
import re
from typing import List, Optional

from services.extraction import normalize_accents
from services.extraction.patterns import Patterns

from .constants import COMPOUND_PAIRS, REVERSED_FOOTER_TOKENS, TECHNICAL_NOUNS


def is_valid_prefix_line(prev_line: str) -> bool:
    """
    Verifica se uma linha anterior é válida para ser prefixada à descrição.

    Args:
        prev_line: Linha anterior (já stripped)

    Returns:
        True se a linha pode ser usada como prefixo
    """
    if not prev_line or len(prev_line) < 10:
        return False

    # Rejeitar se é outro item
    if Patterns.ITEM_PATTERN.match(prev_line):
        return False

    # Rejeitar se é cabeçalho de seção
    if Patterns.SECTION_HEADER_BROAD.match(prev_line):
        return False

    return True


def is_description_fragment(desc: str, prev_line: str) -> bool:
    """
    Verifica se uma descrição parece ser um fragmento que precisa da linha anterior.

    Args:
        desc: Texto da descrição (entre código e unidade/quantidade)
        prev_line: Linha anterior para verificar continuação

    Returns:
        True se a descrição parece ser um fragmento
    """
    if not desc:
        return True

    first_word = desc.split()[0] if desc.split() else ""

    # Começa com parêntese ou colchete
    if re.match(r'^[(\[]', desc):
        return True

    # Começa com letra minúscula
    if desc[0].islower():
        return True

    # Começa com preposição/conjunção
    if re.match(r'^(DE|DA|DO|E|OU|COM|PARA|EM|NO|NA)\s', desc, re.I):
        return True

    # Palavra muito curta (MM, CM, etc.)
    if re.match(r'^[A-Z]{1,3}[,\s]', desc):
        return True

    # Começa com especificação técnica (número + unidade)
    if re.match(r'^\d+[A-Z/,]', desc):
        return True

    # Começa com traço de argamassa (ex: "1:2:8", "1:3")
    if re.match(r'^\d+(?::\d+){1,3}\b', desc):
        return True

    # Linha anterior termina com palavra de continuação
    if prev_line and Patterns.CONTINUATION_WORDS_END.search(prev_line):
        return True

    # Verificar se linha anterior termina com palavra incompleta
    if prev_line:
        prev_last_word = prev_line.split()[-1] if prev_line.split() else ""
        prev_ends_clean = bool(
            prev_last_word and
            not prev_last_word.endswith(('.', ',', ';', ':')) and
            'AF_' not in prev_last_word
        )

        first_word_clean = first_word.rstrip(',.;:')
        first_word_upper = first_word_clean.upper() if first_word_clean else ""

        # Evitar tratar substantivos técnicos como adjetivos
        is_noun_starter = (
            first_word_upper in TECHNICAL_NOUNS or
            (first_word_upper.endswith('S') and first_word_upper[:-1] in TECHNICAL_NOUNS)
        )

        first_word_is_adjective = bool(
            first_word_clean and not is_noun_starter and
            (re.match(r'^[A-ZÁÉÍÓÚÀÂÊÔ]{4,}[AOEIAS]$', first_word_clean) or
             re.match(r'^[A-ZÁÉÍÓÚÀÂÊÔ]{4,}(AL|AR|ER|OR|VEL|AIS|EIS|OS)$', first_word_clean, re.I))
        )

        if prev_ends_clean and first_word_is_adjective:
            return True

        # Verificar pares comuns de substantivo + adjetivo
        prev_last_upper = prev_last_word.upper() if prev_last_word else ""
        first_upper = first_word_clean.upper() if first_word_clean else ""

        if prev_last_upper in COMPOUND_PAIRS:
            if first_upper in COMPOUND_PAIRS[prev_last_upper]:
                return True

        # Verificar se linha anterior termina com vírgula (lista)
        if prev_line.rstrip().endswith(','):
            return True

    return False


def prev_line_is_continuation(
    prev_line: str,
    lines: Optional[List[str]] = None,
    line_idx: int = 0
) -> bool:
    """
    Verifica se a linha anterior parece ser continuação de OUTRO item.

    Args:
        prev_line: Linha anterior
        lines: Lista completa de linhas (para busca recursiva)
        line_idx: Índice da linha atual

    Returns:
        True se a linha parece ser continuação de outro item
    """
    if not prev_line:
        return False

    # Termina com código AF
    if Patterns.AF_CODE_END.search(prev_line):
        return True

    # Fecha parêntese seguido de texto
    if re.match(r'^[)}\]]\s*[A-Z]', prev_line):
        return True

    # Termina com ponto final e contém AF
    if prev_line.endswith('.') and 'AF_' in prev_line:
        return True

    # Busca recursiva para trás
    if lines and line_idx >= 2:
        prev_line_is_item = bool(Patterns.ITEM_PATTERN.match(prev_line))
        if not prev_line_is_item:
            prev_upper = prev_line.upper() if prev_line else ""
            if any(prev_upper.startswith(starter) for starter in TECHNICAL_NOUNS):
                return False

            for j in range(line_idx - 2, max(line_idx - 7, -1), -1):
                check_line = lines[j].strip()
                if not check_line:
                    break
                if Patterns.SECTION_HEADER_BROAD.match(check_line):
                    break
                if Patterns.AF_CODE_ANYWHERE.search(check_line):
                    break
                if Patterns.ITEM_PATTERN.match(check_line):
                    return True

    return False


def should_prefix_with_previous(
    desc_in_line: str,
    prev_line: str,
    lines: Optional[List[str]] = None,
    line_idx: int = 0
) -> bool:
    """
    Determina se deve prefixar a descrição com a linha anterior.

    Args:
        desc_in_line: Texto entre código e unidade/quantidade
        prev_line: Linha anterior (já stripped)
        lines: Lista completa de linhas
        line_idx: Índice da linha atual

    Returns:
        True se deve prefixar com a linha anterior
    """
    is_fragment = is_description_fragment(desc_in_line, prev_line)
    should_prefix = is_fragment or len(desc_in_line) < 25

    if not should_prefix:
        return False

    if not is_valid_prefix_line(prev_line):
        return False

    if Patterns.AF_ONLY.match(prev_line):
        return False

    if Patterns.PAGINATION_SIMPLE.match(prev_line):
        return False

    if prev_line_is_continuation(prev_line, lines, line_idx):
        return False

    return True


def looks_like_reversed_footer_line(line: str) -> bool:
    """
    Detecta linhas de rodapé invertidas pelo OCR.

    Ex.: "ohlesnoC" -> "Conselho", "a rirefnoc" -> "a conferir"
    """
    if not line or len(line) < 6:
        return False

    words = line.split()
    if not words:
        return False

    reversed_line = " ".join(word[::-1] for word in words)
    normalized = normalize_accents(reversed_line).upper()

    return any(token in normalized for token in REVERSED_FOOTER_TOKENS)
