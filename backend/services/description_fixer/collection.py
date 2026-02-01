"""
Funções de coleta de linhas para o corretor de descrições.
"""
import re
from typing import List

from services.extraction.patterns import Patterns
from .constants import STOP_PREFIXES, FOOTER_DATE_PATTERN, TECHNICAL_NOUNS
from .validation import looks_like_reversed_footer_line


def collect_continuation_lines(
    lines: List[str],
    start_idx: int,
    max_lines: int = 5
) -> str:
    """
    Coleta linhas de continuação após uma linha de item.

    Args:
        lines: Lista de todas as linhas do texto
        start_idx: Índice da próxima linha após o item
        max_lines: Máximo de linhas de continuação a coletar

    Returns:
        Texto concatenado das linhas de continuação
    """
    continuation_parts: List[str] = []
    j = start_idx

    while j < len(lines) and len(continuation_parts) < max_lines:
        cont_line = lines[j].strip()

        # Parar se linha vazia
        if not cont_line:
            break

        # Ignorar linhas muito curtas
        if len(cont_line) < 4:
            j += 1
            continue

        # Ignorar linhas de rodapé invertidas
        if looks_like_reversed_footer_line(cont_line):
            j += 1
            continue

        # Verificar se é lixo de OCR
        has_af = bool(Patterns.AF_CODE_ANYWHERE.search(cont_line))
        if not has_af:
            cont_lower = cont_line.lower()
            vowels_count = sum(1 for c in cont_lower if c in 'aeiouáéíóúàâêô')
            if len(cont_line) > 3 and vowels_count < len(cont_line) * 0.15:
                j += 1
                continue

            if len(cont_line) < 25:
                # Permitir fechamento de parênteses
                if ')' in cont_line:
                    prev_line = lines[j - 1].strip() if j - 1 >= 0 else ""
                    if prev_line.count('(') > prev_line.count(')'):
                        continuation_parts.append(cont_line)
                        j += 1
                        break

                words = cont_line.split()
                if cont_line[0].islower():
                    valid_starters = {'de', 'da', 'do', 'das', 'dos', 'e', 'ou', 'a', 'o',
                                      'para', 'com', 'em', 'no', 'na', 'nos', 'nas',
                                      'por', 'pelo', 'pela', 'ao', 'aos', 'as'}
                    continuation_starters = {'inclusive', 'incluindo', 'conforme', 'segundo',
                                             'tipo', 'como', 'sendo', 'sem', 'ref', 'exceto',
                                             'excetuando', 'exclusive', 'exclusivo'}
                    first_word = words[0].lower() if words else ""

                    if first_word in continuation_starters:
                        pass
                    elif first_word in valid_starters and len(words) > 1:
                        has_valid_word = any(
                            (len(w) >= 4 and w[0].isupper()) or
                            (len(w) >= 5 and w.isalpha())
                            for w in words[1:]
                        )
                        if not has_valid_word:
                            j += 1
                            continue
                    else:
                        j += 1
                        continue
                elif ' ' not in cont_line and not cont_line.isupper() and not cont_line.isdigit():
                    if not cont_line[0].isupper():
                        j += 1
                        continue

            if cont_line[0] in ',:;.!?-':
                j += 1
                continue

        # Parar se é outro item
        if Patterns.ITEM_PATTERN.match(cont_line):
            break

        # Parar se contém código de item no meio
        if Patterns.ITEM_CODE_MID.search(cont_line):
            break

        # Verificar próxima linha
        if j + 1 < len(lines):
            next_line = lines[j + 1].strip()
            if Patterns.ITEM_PATTERN.match(next_line):
                prev_line = lines[j - 1].strip() if j - 1 >= 0 else ""
                prev_ends_with_continuation = (
                    prev_line.endswith(('-', '–', '—')) or
                    Patterns.CONTINUATION_WORDS_END.search(prev_line)
                )
                if prev_ends_with_continuation:
                    continuation_parts.append(cont_line)
                    break

                prev_has_dash_unit_qty = bool(re.search(
                    r'\s-\s*(UN|M|M2|M3|M²|M³|KG|L|VB|CJ|PC|GL|PAR|JG|SC)\s+[\d.,]+\s*$',
                    prev_line,
                    re.IGNORECASE
                ))
                cont_upper = cont_line.upper()
                tail_starters = (
                    "FORNECIMENTO", "EXECUÇÃO", "EXECUCAO",
                    "INSTALAÇÃO", "INSTALACAO", "ASSENTAMENTO"
                )
                if prev_has_dash_unit_qty and cont_upper.startswith(tail_starters):
                    continuation_parts.append(cont_line)
                    break

                prev_has_unit_qty_end = bool(re.search(
                    r'(UN|M|M2|M3|M²|M³|KG|L|VB|CJ|PC|GL|PAR|JG|SC)\s+[\d.,]+\s*$',
                    prev_line,
                    re.IGNORECASE
                ))
                if prev_has_unit_qty_end and cont_upper.startswith(('E ', 'OU ', 'COM ', 'SEM ', 'INCLUSIVE', 'INCLUINDO')):
                    continuation_parts.append(cont_line)
                    break

                if Patterns.UNIT_FIRST.match(next_line):
                    break

                first_word = cont_line.split()[0] if cont_line.split() else ""
                first_word_upper = first_word.upper() if first_word else ""

                if first_word_upper in TECHNICAL_NOUNS:
                    break

                if Patterns.SECTION_HEADER_BROAD.match(cont_line):
                    break

                if Patterns.CONTINUATION_WORDS_END.search(cont_line):
                    continuation_parts.append(cont_line)
                    break

                is_new_desc_start = (
                    (len(first_word) >= 4 and first_word[0].isupper() and
                     not first_word.isupper()) or
                    (cont_line.endswith('.') and len(cont_line) > 20)
                )
                if not is_new_desc_start:
                    continuation_parts.append(cont_line)
                break

        # Parar se é cabeçalho de seção
        if Patterns.SECTION_HEADER_BROAD.match(cont_line):
            break

        # Parar se é rodapé/cabeçalho
        cont_upper = cont_line.upper()
        if any(cont_upper.startswith(prefix) for prefix in STOP_PREFIXES):
            break

        if FOOTER_DATE_PATTERN.search(cont_line):
            break

        if Patterns.PAGE_BARE.match(cont_line):
            break

        continuation_parts.append(cont_line)
        j += 1

        if Patterns.AF_CODE_ANYWHERE.search(cont_line):
            break

    return " ".join(continuation_parts)


def collect_previous_lines(
    lines: List[str],
    start_idx: int,
    max_lines: int = 3
) -> str:
    """
    Coleta linhas ANTERIORES para formar descrição completa.

    Args:
        lines: Lista de todas as linhas do texto
        start_idx: Índice da linha atual (com o item)
        max_lines: Máximo de linhas anteriores a coletar

    Returns:
        Texto concatenado das linhas anteriores (ordem correta)
    """
    prev_parts: List[str] = []
    j = start_idx - 1

    while j >= 0 and len(prev_parts) < max_lines:
        prev_line = lines[j].strip()

        if not prev_line:
            break

        if Patterns.ITEM_PATTERN.match(prev_line):
            break

        if Patterns.SECTION_HEADER_BROAD.match(prev_line):
            break

        prev_upper = prev_line.upper()
        if any(prev_upper.startswith(prefix) for prefix in STOP_PREFIXES):
            break

        if Patterns.AF_CODE_ANYWHERE.search(prev_line):
            break

        if Patterns.ITEM_CODE_MID.search(prev_line):
            break

        prev_parts.insert(0, prev_line)
        j -= 1

        if prev_line and prev_line[0].isupper():
            first_word = prev_line.split()[0] if prev_line.split() else ""
            if len(first_word) >= 4 and first_word[0].isupper():
                break

    return " ".join(prev_parts)
