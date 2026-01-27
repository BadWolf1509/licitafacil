"""
Funções de similaridade para comparação de serviços.

Fornece funções para comparar quantidades, descrições e itens
para detecção de duplicatas e mesclagem de dados.
"""

from typing import Optional

from .text_normalizer import (
    normalize_description,
    normalize_unit,
    extract_keywords,
)
from .table_processor import parse_quantity


def quantities_similar(qty_a: Optional[float], qty_b: Optional[float]) -> bool:
    """
    Verifica se duas quantidades são similares (20% tolerância).

    Args:
        qty_a: Primeira quantidade
        qty_b: Segunda quantidade

    Returns:
        True se similares
    """
    if qty_a is None or qty_b is None:
        return True
    if qty_a == 0 or qty_b == 0:
        return False
    diff = abs(qty_a - qty_b)
    if diff <= 1.0:
        return True
    base = max(abs(qty_a), abs(qty_b))
    if base > 0 and diff / base <= 0.2:
        return True
    return False


def descriptions_similar(desc_a: str, desc_b: str) -> bool:
    """
    Verifica se duas descrições são similares.

    Args:
        desc_a: Primeira descrição
        desc_b: Segunda descrição

    Returns:
        True se similares
    """
    if not desc_a or not desc_b:
        return False
    norm_a = normalize_description(desc_a)
    norm_b = normalize_description(desc_b)
    if norm_a == norm_b:
        return True
    if norm_a in norm_b or norm_b in norm_a:
        return True
    kw_a = extract_keywords(desc_a)
    kw_b = extract_keywords(desc_b)
    if not kw_a or not kw_b:
        return False
    common = len(kw_a & kw_b)
    min_len = min(len(kw_a), len(kw_b))
    return common >= max(1, min_len // 2)


def items_similar(item_a: dict, item_b: dict) -> bool:
    """
    Verifica se dois itens são similares.

    Args:
        item_a: Primeiro item
        item_b: Segundo item

    Returns:
        True se similares
    """
    desc_a = (item_a.get("descricao") or "").strip()
    desc_b = (item_b.get("descricao") or "").strip()
    if not descriptions_similar(desc_a, desc_b):
        return False
    unit_a = normalize_unit(item_a.get("unidade") or "")
    unit_b = normalize_unit(item_b.get("unidade") or "")
    if unit_a and unit_b and unit_a != unit_b:
        return False
    qty_a = parse_quantity(item_a.get("quantidade"))
    qty_b = parse_quantity(item_b.get("quantidade"))
    return quantities_similar(qty_a, qty_b)


def servico_key(servico: dict) -> tuple:
    """
    Cria chave única para um serviço baseado em item e descrição normalizada.

    Args:
        servico: Dicionário do serviço

    Returns:
        Tupla (item, descrição_normalizada)
    """
    item = servico.get("item") or ""
    desc = normalize_description(servico.get("descricao", ""))
    return (item, desc[:50])
