"""
Métricas de qualidade para extração de tabelas.

Funções para calcular proporções de dados completos,
usadas para decidir entre diferentes extratores.
"""

from typing import Any, Dict, List

from services.extraction import parse_quantity


def calc_qty_ratio(servicos: List[Dict[str, Any]]) -> float:
    """
    Calcula a proporção de serviços com quantidade válida.

    Args:
        servicos: Lista de serviços

    Returns:
        Proporção de 0.0 a 1.0
    """
    if not servicos:
        return 0.0
    qty_count = sum(
        1 for s in servicos
        if parse_quantity(s.get("quantidade")) not in (None, 0)
    )
    return qty_count / len(servicos)


def calc_complete_ratio(servicos: List[Dict[str, Any]]) -> float:
    """
    Calcula a proporção de serviços completos.

    Um serviço é considerado completo se possui:
    - item (código do item)
    - descricao (com mais de 5 caracteres)
    - unidade
    - quantidade (valor válido)

    Args:
        servicos: Lista de serviços

    Returns:
        Proporção de 0.0 a 1.0
    """
    if not servicos:
        return 0.0

    complete_count = sum(
        1 for s in servicos
        if (
            s.get("item") and
            s.get("descricao") and len(str(s.get("descricao", ""))) > 5 and
            s.get("unidade") and
            parse_quantity(s.get("quantidade")) not in (None, 0)
        )
    )
    return complete_count / len(servicos)


def calc_quality_metrics(servicos: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Calcula métricas de qualidade dos serviços extraídos.

    Args:
        servicos: Lista de serviços

    Returns:
        Dict com métricas: total, qty_ratio, complete_ratio, item_ratio, unit_ratio
    """
    if not servicos:
        return {
            "total": 0,
            "qty_ratio": 0.0,
            "complete_ratio": 0.0,
            "item_ratio": 0.0,
            "unit_ratio": 0.0
        }

    total = len(servicos)
    with_item = sum(1 for s in servicos if s.get("item"))
    with_qty = sum(
        1 for s in servicos
        if parse_quantity(s.get("quantidade")) not in (None, 0)
    )
    with_unit = sum(1 for s in servicos if s.get("unidade"))
    complete = sum(
        1 for s in servicos
        if (
            s.get("item") and
            s.get("descricao") and len(str(s.get("descricao", ""))) > 5 and
            s.get("unidade") and
            parse_quantity(s.get("quantidade")) not in (None, 0)
        )
    )

    return {
        "total": total,
        "qty_ratio": with_qty / total,
        "complete_ratio": complete / total,
        "item_ratio": with_item / total,
        "unit_ratio": with_unit / total
    }
