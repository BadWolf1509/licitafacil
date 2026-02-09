"""
Filtros para detecção de ruído e headers em linhas de tabela.

Funções para identificar linhas que não são serviços válidos:
- Ruído (metadados, cabeçalhos institucionais)
- Headers de seção
- Metadados de página
"""

import re

from services.extraction import normalize_description
from services.extraction.patterns import Patterns

# Tokens que indicam ruído (não são serviços)
NOISE_TOKENS = (
    "RUA PROJETADA",
    "SERVICOS PRELIMINARES",
    "SERVICOS COMPLEMENTARES",
    "SERVICOS EXECUTADOS",
    "PAGINA",
    "IMPRESSO EM",
    "EMITIDO EM",
    "DATA DE EMISSAO",
    "CHAVE DE IMPRESSAO",
    "CERTIDAO N",
    "CNPJ",
    "CPF",
    "CREA",
    "CONSELHO REGIONAL",
    "PREFEITURA",
    "MUNICIPIO",
    "ESTADO",
    "ART",
)

# Headers de seção conhecidos (não devem ser concatenados com descrições)
SECTION_HEADERS = (
    "SERVICOS PRELIMINARES",
    "SERVICOS COMPLEMENTARES",
    "SERVICOS FINAIS",
    "INSTALACOES ELETRICAS",
    "INSTALACOES HIDROSSANITARIAS",
    "INSTALACOES HIDROSANITARIAS",
    "INSTALACOES HIDRAULICAS",
    "INSTALACOES SANITARIAS",
    "FUNDACOES E ESTRUTURAS",
    "ALVENARIA E VEDACOES",
    "MOVIMENTACAO DE TERRA",
)

# Palavras de continuação (indicam descrição técnica, não novo item)
CONTINUATION_WORDS = (
    "DE", "DA", "DO", "DOS", "DAS",
    "COM", "SEM", "PARA", "EM", "NO", "NA", "NOS", "NAS",
    "E", "OU",
    "TIPO", "CONF", "CONFORME", "SEGUNDO", "REF",
)

# Tokens de header de tabela
HEADER_TOKENS = ("ITEM", "DESCRICAO", "UND", "UNID", "QUANT")


def is_row_noise(text: str) -> bool:
    """
    Detecta se o texto é ruído (não é um serviço válido).

    Args:
        text: Texto da linha

    Returns:
        True se a linha é ruído

    Examples:
        >>> is_row_noise("CNPJ 12.345.678/0001-90")
        True
        >>> is_row_noise("Instalação de piso cerâmico")
        False
    """
    if not text:
        return True

    normalized = normalize_description(text)
    if not normalized:
        return True

    normalized_compact = normalized.replace(" ", "")

    for token in NOISE_TOKENS:
        if token in normalized:
            return True
        if token.replace(" ", "") in normalized_compact:
            return True

    # Detectar padrão de página "X/Y" ou "X de Y" usando Patterns centralizados
    normalized_stripped = normalized.strip()
    if Patterns.PAGE_BARE.match(normalized_stripped):
        return True
    if Patterns.PAGE_NUMBER.match(normalized_stripped):
        return True
    if Patterns.PAGE_DE.match(normalized_stripped):
        return True

    return False


def is_section_header_row(
    item_val: str,
    desc_val: str,
    unit_val: str,
    qty_present: bool
) -> bool:
    """
    Detecta se a linha é um cabeçalho de seção.

    Headers de seção não devem ser armazenados em pending_desc para evitar
    concatenação incorreta com o próximo item.

    Características:
    - Número simples (1-9 ou 10+) na coluna de item
    - Descrição curta (< 60 chars) e em maiúsculas
    - Sem unidade e sem quantidade

    Args:
        item_val: Valor da coluna de item
        desc_val: Valor da coluna de descrição
        unit_val: Valor da coluna de unidade
        qty_present: Se quantidade está presente

    Returns:
        True se parece ser header de seção
    """
    # Se tem unidade ou quantidade, não é header
    if unit_val or qty_present:
        return False

    # Caso 1: Item é número simples (ex: item_val="4", desc_val="IMPERMEABILIZAÇÃO")
    if item_val:
        item_stripped = item_val.strip()
        if Patterns.SECTION_NUMBER.match(item_stripped):
            # Descrição deve existir, ser curta e parecer título
            if desc_val:
                desc_stripped = desc_val.strip()
                if len(desc_stripped) <= 60:
                    desc_upper = desc_stripped.upper()
                    if desc_stripped == desc_upper and not re.match(r'^\d', desc_stripped):
                        return True

    # Caso 2: Categoria embutida na descrição (ex: desc_val="4 IMPERMEABILIZAÇÃO")
    if desc_val and not item_val:
        desc_stripped = desc_val.strip()
        match = Patterns.SECTION_HEADER.match(desc_stripped)
        if match:
            category_name = match.group(2).strip()
            if len(category_name) <= 50 and category_name == category_name.upper():
                return True

    return False


def is_page_metadata(text: str) -> bool:
    """
    Detecta se o texto é metadado de página (header/footer de PDF).

    Args:
        text: Texto a verificar

    Returns:
        True se parece ser metadado de página
    """
    if not text:
        return False

    text_stripped = text.strip()
    text_upper = text_stripped.upper()

    # Usar padrões centralizados da classe Patterns
    if Patterns.PAGE_NUMBER.match(text_upper):
        return True
    if Patterns.PAGE_ABBREV.match(text_upper):
        return True
    if Patterns.PAGE_BARE.match(text_upper):
        return True
    if Patterns.PRINT_HEADER.match(text_upper):
        return True
    if Patterns.PRINT_DATETIME.match(text_upper):
        return True
    if Patterns.CERTIDAO.match(text_upper):
        return True
    if Patterns.CHAVE_IMPRESSAO.match(text_upper):
        return True
    if Patterns.DOCUMENTO.match(text_upper):
        return True

    # Padrão adicional: "EMITIDO EM:" (não está em Patterns ainda)
    if re.match(r'^EMITIDO\s+EM\s*:?', text_upper):
        return True

    # Verificar se contém "Página X/Y" em qualquer posição
    if Patterns.PAGE_ANYWHERE.search(text_upper):
        return True

    return False


def is_header_row(text: str) -> bool:
    """
    Detecta se o texto é uma linha de header de tabela.

    Args:
        text: Texto a verificar

    Returns:
        True se parece ser header de tabela
    """
    if not text:
        return False

    normalized = normalize_description(text)
    if not normalized:
        return False

    hits = sum(1 for token in HEADER_TOKENS if token in normalized)
    return hits >= 2


def strip_section_header_prefix(desc: str) -> str:
    """
    Remove prefixos de headers de seção do início das descrições.

    Isso acontece quando o OCR ou o parser concatena erroneamente o nome
    de uma seção/categoria ao início da descrição do serviço.

    Args:
        desc: Descrição do serviço

    Returns:
        Descrição limpa sem o prefixo de header

    Examples:
        >>> strip_section_header_prefix(
        ...     "INSTALAÇÕES HIDROSSANITÁRIAS Chuveiro elétrico"
        ... )
        'Chuveiro elétrico'
    """
    if not desc:
        return desc

    # Normalizar a descrição (remover acentos, converter para maiúsculas)
    desc_normalized = normalize_description(desc)

    for header in SECTION_HEADERS:
        # Verificar se a descrição normalizada começa com o header
        if desc_normalized.startswith(header):
            header_len = len(header)
            # Verificar se há conteúdo após o header
            rest_normalized = desc_normalized[header_len:].strip()
            if rest_normalized:
                # Verificar se a próxima palavra é uma continuação técnica
                first_word = rest_normalized.split()[0] if rest_normalized.split() else ""
                if first_word in CONTINUATION_WORDS:
                    # Parece continuação de descrição, não remover
                    continue
                # É um header seguido de novo conteúdo, remover
                cleaned = desc[header_len:].strip()
                if cleaned:
                    return cleaned
            # Se só tinha o header (sem resto), retornar original
            return desc

    return desc
