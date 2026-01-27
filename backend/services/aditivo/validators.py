"""
Validadores para processamento de aditivos.

Contém funções para detectar linhas contaminadas e validar descrições.
"""

import re
from ..extraction.constants import KNOWN_CATEGORIES
from ..extraction.patterns import Patterns
from ..extraction.text_normalizer import normalize_accents


def is_contaminated_line(line: str) -> bool:
    """
    Detecta se uma linha contém contaminação que não deve ser usada como descrição.

    Tipos de contaminação detectados:
    1. Caracteres Unicode especiais (ex: U+2796 HEAVY MINUS SIGN)
    2. Metadados de página (Impresso em, Página X/Y)
    3. Headers de categoria numerados (4 IMPERMEABILIZAÇÃO, 8 INSTALAÇÕES)
    4. Linhas de CNPJ, CREA, datas

    Args:
        line: Linha de texto a verificar

    Returns:
        True se a linha está contaminada e não deve ser usada
    """
    if not line:
        return True

    line_stripped = line.strip()

    # 0. Detectar caracteres Unicode especiais (garbage chars como U+2796)
    # Permitir apenas ASCII e acentos latinos (Latin-1 Supplement: À-ÿ)
    for char in line_stripped[:50]:  # Verificar apenas início da linha
        code = ord(char)
        if code > 127:
            # Permitir apenas acentos latinos comuns (À-ÿ = 0x00C0 a 0x00FF)
            if not (0x00C0 <= code <= 0x00FF):
                # Caractere Unicode incomum detectado (ex: ➖, ▪, etc.)
                return True

    line_upper = line_stripped.upper()

    # 1. Metadados de página usando Patterns centralizados
    if Patterns.PRINT_HEADER.match(line_upper):
        return True
    if re.match(r'^EMITIDO\s+EM\s*:?', line_upper):
        return True
    if Patterns.PAGE_NUMBER.match(line_upper):
        return True
    if Patterns.PAGE_ABBREV.match(line_upper):
        return True
    if Patterns.PRINT_DATETIME.match(line_upper):
        return True
    if Patterns.CERTIDAO.match(line_upper):
        return True
    if Patterns.CHAVE_IMPRESSAO.match(line_upper):
        return True

    # Verificar se contém "Página X/Y" em qualquer posição
    if Patterns.PAGE_ANYWHERE.search(line_upper):
        return True

    # 2. Headers de categoria numerados (ex: "4 IMPERMEABILIZAÇÃO", "8 INSTALAÇÕES")
    # Verificar se linha inteira é um header de categoria
    category_match = Patterns.SECTION_HEADER.match(line_upper)
    if category_match:
        category_name = category_match.group(2).strip()
        # Normalizar acentos para comparação
        category_normalized = normalize_accents(category_name)
        for known in KNOWN_CATEGORIES:
            known_normalized = normalize_accents(known)
            if category_normalized.startswith(known_normalized):
                return True

    # 3. Linhas de dados institucionais usando Patterns centralizados
    if "CNPJ" in line_upper or Patterns.CNPJ.search(line_stripped):
        return True
    if "CREA" in line_upper or Patterns.CREA.search(line_stripped):
        return True
    if "CPF" in line_upper or Patterns.CPF.search(line_stripped):
        return True

    # 4. Spillovers - linhas que começam com continuação de item anterior
    spillover_patterns = [
        r'^MM,\s*INCLUSIVE',       # "MM, INCLUSIVE ACESSÓRIOS" - spillover claro
        r'^M[²³2³],?\s+[A-Z]',     # "M² FORNECIMENTO" - unidade seguida de texto
        r'^REFER[ÊE]NCIA\s+SBC',   # "REFERÊNCIA SBC" específico
        r'^REF\.\s*\d+',           # "REF. 12345"
        r'^E\s*=\s*\d+\s*MM',      # "E = 10 MM" (espessura isolada)
        r'^E\s+CANOPLA',           # Continuação específica
    ]
    for pattern in spillover_patterns:
        if re.match(pattern, line_upper):
            return True

    return False


def is_good_description(desc: str) -> bool:
    """
    Verifica se uma descrição extraída tem qualidade suficiente.

    Args:
        desc: Descrição a verificar

    Returns:
        True se a descrição tem qualidade suficiente
    """
    if not desc:
        return False

    # Mínimo de caracteres
    if len(desc) < 10:
        return False

    desc_stripped = desc.strip()

    # Rejeitar descrições que terminam com número de item (spillover)
    if re.search(r'\s\d+\.\d+\s*$', desc_stripped):
        return False

    # Rejeitar descrições que são só sufixo (FORNECIMENTO E INSTALAÇÃO. AF_XX/XXXX)
    if re.match(
        r'^(FORNECIMENTO\s+E\s+)?INSTALA[CÇ][AÃ]O\.?\s*AF_\d+/\d+$',
        desc_stripped,
        re.IGNORECASE
    ):
        return False

    # Deve ter palavras reais (não só números/códigos) - usando padrão centralizado
    words = Patterns.WORD_3PLUS.findall(desc)
    if len(words) < 2:
        return False

    # Não deve ser só código de referência (AF_XX/XXXX) - usando padrão centralizado
    if Patterns.AF_CODE.match(desc_stripped):
        return False

    return True
