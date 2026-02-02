"""
Verificacoes de qualidade para extracao OCR.

Contem funcoes para avaliar a qualidade dos resultados de extracao
e decidir se e necessario retry ou ajustes.
"""

from typing import Any, Dict, List, Tuple

from services.extraction import parse_item_tuple


def item_sequence_suspicious(servicos: List[Dict[str, Any]]) -> Tuple[bool, Dict[str, Any]]:
    """
    Verifica se a sequencia de itens e suspeita.

    Uma sequencia e considerada suspeita se tiver muitos numeros
    de segmento grandes (>=100) ou muitas duplicatas, indicando
    possivel erro de extracao.

    Args:
        servicos: Lista de servicos extraidos

    Returns:
        Tupla (is_suspicious, debug_info) onde:
        - is_suspicious: True se a sequencia for suspeita
        - debug_info: Informacoes de debug
    """
    items = [str(s.get("item")).strip() for s in servicos if s.get("item")]
    count = len(items)

    if count < 4:
        return False, {"count": count, "large_segment_ratio": 0.0, "duplicate_ratio": 0.0}

    # Verificar segmentos grandes
    tuples = [parse_item_tuple(item) for item in items]
    large_segment = 0
    for item_tuple in tuples:
        if not item_tuple:
            continue
        if any(seg >= 100 for seg in item_tuple):
            large_segment += 1

    # Calcular ratios
    unique_ratio = len(set(items)) / max(1, count)
    duplicate_ratio = 1 - unique_ratio
    large_segment_ratio = large_segment / max(1, count)

    # Determinar se e suspeito
    suspicious = large_segment_ratio >= 0.3 or duplicate_ratio >= 0.25
    info = {
        "count": count,
        "large_segment_ratio": round(large_segment_ratio, 3),
        "duplicate_ratio": round(duplicate_ratio, 3),
        "large_segment_count": large_segment
    }
    return suspicious, info


def assign_itemless_items(servicos: List[Dict[str, Any]], page_number: int) -> None:
    """
    Atribui codigos de item para servicos sem item.

    Gera codigos no formato "S{page}-{seq}" para servicos que nao
    possuem codigo de item.

    Args:
        servicos: Lista de servicos (modificada in-place)
        page_number: Numero da pagina para prefixo
    """
    prefix = f"S{page_number}-"
    seq = 1
    for servico in servicos:
        if servico.get("item"):
            continue
        servico["item"] = f"{prefix}{seq}"
        seq += 1


def is_retry_result_better(
    servicos_retry: List[Dict],
    servicos_current: List[Dict],
    metrics_retry: Dict[str, Any],
    metrics_current: Dict[str, Any]
) -> bool:
    """
    Verifica se o resultado do retry e melhor que o atual.

    Compara os resultados de uma nova tentativa de extracao com
    os resultados atuais usando metricas de qualidade.

    Args:
        servicos_retry: Servicos do retry
        servicos_current: Servicos atuais
        metrics_retry: Metricas do retry (qty_ratio, unit_ratio, etc.)
        metrics_current: Metricas atuais

    Returns:
        True se o retry for melhor
    """
    if not servicos_retry:
        return False
    if not servicos_current:
        return True

    # Retry melhor se tiver significativamente mais servicos
    if len(servicos_retry) >= len(servicos_current) + 2:
        return True

    # Retry melhor se tiver qty_ratio significativamente maior
    if metrics_retry.get("qty_ratio", 0.0) >= metrics_current.get("qty_ratio", 0.0) + 0.1:
        return True

    # Retry melhor se tiver mais servicos com unit_ratio igual ou melhor
    if (
        len(servicos_retry) > len(servicos_current)
        and metrics_retry.get("unit_ratio", 0.0) >= metrics_current.get("unit_ratio", 0.0)
    ):
        return True

    return False
