"""
Helpers de processamento de documentos.

Contém funções puras que podem ser usadas por múltiplos processadores
(document_processor, atestado_processor) sem criar dependências circulares.

Funções extraídas para evitar duplicação e facilitar testes unitários.
"""

import re
from typing import Any, Optional

from .extraction import (
    normalize_description,
    normalize_unit,
    parse_item_tuple,
    item_tuple_to_str,
    parse_quantity,
    SECTION_HEADERS,
    KNOWN_CATEGORIES,
    NARRATIVE_TOKENS,
    # Item utilities - importados de item_utils.py
    normalize_item_code,
    item_code_in_text,
    split_restart_prefix,
)


def item_qty_matches_code(item_code: str, qty: float) -> bool:
    """
    Verifica se a quantidade é igual aos dígitos do código do item.

    Isso indica que a quantidade foi extraída incorretamente
    (vazamento de coluna no OCR/tabela).

    Args:
        item_code: Código do item (ex: "1.2.3")
        qty: Quantidade

    Returns:
        True se a quantidade corresponde aos dígitos do código
    """
    if not item_code or qty is None:
        return False
    digits = re.sub(r'\D', '', item_code)
    if not digits:
        return False
    try:
        return float(digits) == float(qty)
    except (TypeError, ValueError):
        return False


# Funções importadas de services.extraction.item_utils:
# normalize_item_code, item_code_in_text, split_restart_prefix


def is_section_header_desc(desc: str) -> bool:
    """
    Verifica se a descrição é um cabeçalho de seção.

    Args:
        desc: Descrição a verificar

    Returns:
        True se for cabeçalho de seção
    """
    normalized = normalize_description(desc or "")
    if not normalized:
        return False
    if normalized in SECTION_HEADERS:
        return True
    for token in SECTION_HEADERS:
        if normalized.startswith(token) and len(normalized) <= len(token) + 6:
            return True
    return False


def is_narrative_desc(desc: str) -> bool:
    """
    Verifica se a descrição é um texto narrativo (não um serviço).

    Args:
        desc: Descrição a verificar

    Returns:
        True se for texto narrativo
    """
    normalized = normalize_description(desc or "")
    if not normalized:
        return False
    return any(token in normalized for token in NARRATIVE_TOKENS)


def is_contaminated_desc(desc: str) -> bool:
    """
    Detecta se a descrição está contaminada com metadados de página,
    headers de categoria numerados, ou palavras duplicadas.

    Isso acontece quando o text extraction concatena linhas incorretamente.

    Exemplos de descrições contaminadas:
    - "Impresso em: 10/10/2025... Página 9/11 PORTA PIVOTANTE..."
    - "4 IMPERMEABILIZAÇÃO IMPERMEABILIZAÇÃO DE SUPERFÍCIE..."
    - "8 INSTALAÇÕES HIDROSSANITÁRIAS REGISTRO DE ESFERA..."

    Args:
        desc: Descrição a verificar

    Returns:
        True se estiver contaminada
    """
    if not desc:
        return False

    normalized = normalize_description(desc)
    if not normalized:
        return False

    # 1. Verificar metadados de página no início
    page_metadata_patterns = (
        "IMPRESSO EM",
        "EMITIDO EM",
        "PAGINA",
        "PAG ",
    )
    for pattern in page_metadata_patterns:
        if normalized.startswith(pattern):
            return True

    # 2. Verificar categoria numerada no início (ex: "4 IMPERMEABILIZACAO", "8 INSTALACOES")
    match = re.match(r'^(\d{1,2})\s+([A-Z]+)', normalized)
    if match:
        category_word = match.group(2)
        if category_word in KNOWN_CATEGORIES:
            return True

    # 3. Verificar palavras duplicadas no início (ex: "IMPERMEABILIZACAO IMPERMEABILIZACAO")
    words = normalized.split()
    if len(words) >= 2 and words[0] == words[1] and len(words[0]) >= 5:
        return True

    # 4. Verificar spillover: descrição que contém unidade+quantidade no final
    if re.search(r'\b(UN|M|M2|M3|KG|L|VB|CJ|PC|GL)\s+[\d,.]+\s*$', desc, re.IGNORECASE):
        return True

    return False


def item_key(item: dict) -> Optional[tuple]:
    """
    Gera chave única para um item baseado em código, unidade e quantidade.

    Args:
        item: Dicionário com dados do item

    Returns:
        Tupla (code_key, unit, qty) ou None se inválido
    """
    prefix, core = split_restart_prefix(item.get("item"))
    code = normalize_item_code(core)
    if not code:
        return None
    code_key = f"{prefix}-{code}" if prefix else code
    unit = normalize_unit(item.get("unidade") or "")
    qty = parse_quantity(item.get("quantidade"))
    return (code_key, unit, qty)


def should_replace_desc(current_desc: str, candidate_desc: str) -> bool:
    """
    Decide se deve substituir a descrição atual pela candidata.

    Prefere descrições mais longas e não-contaminadas.

    Args:
        current_desc: Descrição atual
        candidate_desc: Descrição candidata

    Returns:
        True se deve substituir
    """
    if not candidate_desc:
        return False
    if is_section_header_desc(candidate_desc):
        return False
    if is_contaminated_desc(candidate_desc):
        return False
    current = (current_desc or "").strip()
    candidate = candidate_desc.strip()
    if not current:
        return True
    if is_section_header_desc(current):
        return True
    # Preferir descrição mais longa
    return len(candidate) > len(current)


def count_item_codes_in_text(texto: str) -> int:
    """
    Conta quantos códigos de item únicos aparecem no texto.

    Args:
        texto: Texto para busca

    Returns:
        Número de códigos únicos encontrados
    """
    if not texto:
        return 0
    codes = set()
    pattern = re.compile(r'(?<!\d)(\d{1,3}\s*\.\s*\d{1,3}(?:\s*\.\s*\d{1,3}){0,3})(?!\d)')
    for match in pattern.finditer(texto):
        raw = match.group(1)
        raw = re.sub(r'\s+', '', raw)
        item_tuple = parse_item_tuple(raw)
        if item_tuple:
            codes.add(item_tuple_to_str(item_tuple))
    return len(codes)


def clear_item_code_quantities(servicos: list, min_ratio: float = 0.7, min_samples: int = 10) -> int:
    """
    Limpa quantidades que parecem ser códigos de item vazados.

    Quando muitas quantidades correspondem aos dígitos do código do item,
    é provável que seja um erro de extração de tabela.

    Args:
        servicos: Lista de serviços (modificada in-place)
        min_ratio: Proporção mínima de matches para ativar limpeza
        min_samples: Número mínimo de amostras para considerar

    Returns:
        Número de quantidades limpas
    """
    if not servicos:
        return 0

    total = 0
    matches = 0
    for s in servicos:
        item_code = normalize_item_code(s.get("item"))
        qty = parse_quantity(s.get("quantidade"))
        if not item_code or qty is None:
            continue
        total += 1
        if item_qty_matches_code(item_code, qty):
            matches += 1

    ratio = (matches / total) if total else 0.0
    if total < min_samples or ratio < min_ratio:
        return 0

    cleared = 0
    for s in servicos:
        item_code = normalize_item_code(s.get("item"))
        qty = parse_quantity(s.get("quantidade"))
        if item_code and qty is not None and item_qty_matches_code(item_code, qty):
            s["quantidade"] = None
            cleared += 1

    return cleared
