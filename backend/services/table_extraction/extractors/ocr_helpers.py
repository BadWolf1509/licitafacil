"""
Helpers para extração baseada em OCR.

Funções auxiliares para processamento de palavras OCR e construção de tabelas.
"""

from typing import Any, Dict, List, Optional, Tuple

from services.extraction import parse_item_tuple
from config import AtestadoProcessingConfig as APC


def median(values: List[float]) -> float:
    """Calcula a mediana de uma lista de valores."""
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    mid = len(sorted_vals) // 2
    if len(sorted_vals) % 2 == 1:
        return float(sorted_vals[mid])
    return float(sorted_vals[mid - 1] + sorted_vals[mid]) / 2


def build_table_from_ocr_words(
    words: List[Dict[str, Any]],
    row_tol_factor: float = 0.6,
    col_tol_factor: float = 0.7,
    min_row_tol: float = 6.0,
    min_col_tol: float = 18.0
) -> Tuple[List[List[str]], List[float]]:
    """
    Constrói tabela a partir de palavras OCR baseado em layout.

    Args:
        words: Lista de palavras OCR com coordenadas
        row_tol_factor: Fator de tolerância para agrupamento de linhas
        col_tol_factor: Fator de tolerância para agrupamento de colunas
        min_row_tol: Tolerância mínima para linhas
        min_col_tol: Tolerância mínima para colunas

    Returns:
        Tupla (table_rows, col_centers)
    """
    if not words:
        return [], []

    heights = [w["height"] for w in words if w.get("height")]
    widths = [w["width"] for w in words if w.get("width")]
    median_height = median(heights) or 12.0
    median_width = median(widths) or 40.0
    row_tol = max(min_row_tol, median_height * row_tol_factor)
    col_tol = max(min_col_tol, median_width * col_tol_factor)

    words_sorted = sorted(words, key=lambda w: (w["y_center"], w["x_center"]))
    rows: List[List[Dict]] = []
    current: List[Dict] = []
    current_y: Optional[float] = None

    for word in words_sorted:
        if current_y is None:
            current_y = word["y_center"]
            current = [word]
            continue
        if abs(word["y_center"] - current_y) > row_tol:
            rows.append(current)
            current = [word]
            current_y = word["y_center"]
        else:
            current.append(word)
            current_y = (current_y + word["y_center"]) / 2
    if current:
        rows.append(current)

    centers = sorted(w["x_center"] for w in words)
    clusters: List[Dict[str, Any]] = []
    for center in centers:
        if not clusters:
            clusters.append({"center": center, "values": [center]})
            continue
        if abs(center - clusters[-1]["center"]) > col_tol:
            clusters.append({"center": center, "values": [center]})
        else:
            clusters[-1]["values"].append(center)
            clusters[-1]["center"] = sum(clusters[-1]["values"]) / len(clusters[-1]["values"])

    col_centers = [c["center"] for c in clusters]
    col_centers.sort()

    table_rows: List[List[str]] = []
    for row in rows:
        cells = [""] * len(col_centers)
        for word in sorted(row, key=lambda w: w["x_center"]):
            distances = [abs(word["x_center"] - c) for c in col_centers]
            if not distances:
                continue
            col_idx = distances.index(min(distances))
            if cells[col_idx]:
                cells[col_idx] = f"{cells[col_idx]} {word['text']}".strip()
            else:
                cells[col_idx] = word["text"]
        if any(cells):
            table_rows.append(cells)

    return table_rows, col_centers


def infer_item_column_from_words(
    words: List[Dict[str, Any]],
    col_centers: List[float]
) -> Tuple[Optional[int], Dict[str, Any]]:
    """
    Infere a coluna de item a partir das palavras OCR.

    Args:
        words: Lista de palavras OCR
        col_centers: Centros das colunas detectadas

    Returns:
        Tupla (item_col_index, debug_info)
    """
    if not words or not col_centers:
        return None, {}

    min_ratio = APC.ITEM_COL_RATIO
    max_x_ratio = APC.ITEM_COL_MAX_X_RATIO
    max_index = APC.ITEM_COL_MAX_INDEX
    min_count = APC.ITEM_COL_MIN_COUNT

    min_x = min(w["x0"] for w in words)
    max_x = max(w["x1"] for w in words)
    span = max(1.0, max_x - min_x)

    counts = [0] * len(col_centers)
    total_candidates = 0

    for word in words:
        item_tuple = parse_item_tuple(word.get("text"))
        if not item_tuple:
            continue
        total_candidates += 1
        distances = [abs(word["x_center"] - c) for c in col_centers]
        if not distances:
            continue
        col_idx = distances.index(min(distances))
        counts[col_idx] += 1

    if total_candidates == 0:
        return None, {"item_col_counts": counts}

    best_idx = counts.index(max(counts))
    ratio = counts[best_idx] / max(1, total_candidates)
    x_ratio = (col_centers[best_idx] - min_x) / span

    debug = {
        "item_col_counts": counts,
        "item_col_ratio": round(ratio, 3),
        "item_col_x_ratio": round(x_ratio, 3),
        "item_col_best": best_idx
    }

    if best_idx > max_index or x_ratio > max_x_ratio:
        return None, debug
    if ratio < min_ratio and counts[best_idx] < min_count:
        return None, debug

    return best_idx, debug


def item_sequence_suspicious(servicos: List[Dict[str, Any]]) -> Tuple[bool, Dict[str, Any]]:
    """
    Verifica se a sequência de itens é suspeita.

    Args:
        servicos: Lista de serviços extraídos

    Returns:
        Tupla (is_suspicious, debug_info)
    """
    items = [str(s.get("item")).strip() for s in servicos if s.get("item")]
    count = len(items)

    if count < 4:
        return False, {"count": count, "large_segment_ratio": 0.0, "duplicate_ratio": 0.0}

    tuples = [parse_item_tuple(item) for item in items]
    large_segment = 0
    for item_tuple in tuples:
        if not item_tuple:
            continue
        if any(seg >= 100 for seg in item_tuple):
            large_segment += 1

    unique_ratio = len(set(items)) / max(1, count)
    duplicate_ratio = 1 - unique_ratio
    large_segment_ratio = large_segment / max(1, count)

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
    Atribui códigos de item para serviços sem item.

    Args:
        servicos: Lista de serviços (modificada in-place)
        page_number: Número da página para prefixo
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
    Verifica se o resultado do retry é melhor que o atual.

    Args:
        servicos_retry: Serviços do retry
        servicos_current: Serviços atuais
        metrics_retry: Métricas do retry
        metrics_current: Métricas atuais

    Returns:
        True se o retry for melhor
    """
    if not servicos_retry:
        return False
    if not servicos_current:
        return True
    if len(servicos_retry) >= len(servicos_current) + 2:
        return True
    if metrics_retry.get("qty_ratio", 0.0) >= metrics_current.get("qty_ratio", 0.0) + 0.1:
        return True
    if (
        len(servicos_retry) > len(servicos_current)
        and metrics_retry.get("unit_ratio", 0.0) >= metrics_current.get("unit_ratio", 0.0)
    ):
        return True
    return False


def extract_from_ocr_words(
    service: Any,
    words: List[Dict[str, Any]],
    row_tol_factor: float = 0.6,
    col_tol_factor: float = 0.7,
    enable_refine: bool = True
) -> Tuple[List[Dict], float, Dict[str, Any], Dict[str, Any]]:
    """
    Extrai serviços a partir de palavras OCR.

    Args:
        service: Instância do TableExtractionService
        words: Lista de palavras OCR com coordenadas
        row_tol_factor: Fator de tolerância para agrupamento de linhas
        col_tol_factor: Fator de tolerância para agrupamento de colunas
        enable_refine: Habilita refinamento com tolerância menor

    Returns:
        Tupla (servicos, confidence, debug, metrics)
    """
    table_rows, col_centers = build_table_from_ocr_words(
        words,
        row_tol_factor=row_tol_factor,
        col_tol_factor=col_tol_factor
    )
    preferred_item_col, item_col_debug = infer_item_column_from_words(words, col_centers)

    servicos, confidence, debug = service.extract_servicos_from_table(
        table_rows,
        preferred_item_col=preferred_item_col
    )

    servicos_itemless, conf_itemless, debug_itemless = service.extract_servicos_from_table(
        table_rows,
        preferred_item_col=None,
        allow_itemless=True,
        ignore_item_numbers=True
    )

    item_suspicious, item_suspicious_info = item_sequence_suspicious(servicos)

    if servicos_itemless:
        qty_ratio_itemless = service.calc_qty_ratio(servicos_itemless)
        qty_ratio_regular = service.calc_qty_ratio(servicos)
        prefer_itemless = (
            len(servicos_itemless) >= len(servicos) + 3
            and qty_ratio_itemless >= max(0.6, qty_ratio_regular)
        )
        if qty_ratio_itemless >= max(0.9, qty_ratio_regular + 0.4):
            prefer_itemless = True

        if item_suspicious:
            servicos = servicos_itemless
            confidence = conf_itemless
            debug = debug_itemless
            debug["itemless_forced"] = True
        elif prefer_itemless:
            servicos = servicos_itemless
            confidence = conf_itemless
            debug = debug_itemless
            debug["itemless_mode"] = True

    debug["item_suspicious"] = item_suspicious_info

    stats = debug.get("stats") or {}
    dominant = debug.get("dominant_item") or {}
    total_page_items = stats.get("total", 0)
    item_ratio = stats.get("with_item", 0) / max(1, total_page_items)
    unit_ratio = stats.get("with_unit", 0) / max(1, total_page_items)
    dominant_len = dominant.get("dominant_len", 0) or 0
    qty_ratio = service.calc_qty_ratio(servicos)

    metrics = {
        "row_count": len(table_rows),
        "word_count": len(words),
        "item_col": item_col_debug,
        "total_page_items": total_page_items,
        "item_ratio": item_ratio,
        "unit_ratio": unit_ratio,
        "dominant_len": dominant_len,
        "qty_ratio": qty_ratio
    }

    if enable_refine and row_tol_factor >= 0.6:
        refine_min_words = max(40, int(APC.OCR_LAYOUT_RETRY_MIN_WORDS * 0.6))
        needs_refine = (
            metrics.get("total_page_items", 0) < APC.OCR_LAYOUT_RETRY_MIN_ITEMS
            and metrics.get("word_count", 0) >= refine_min_words
        )
        if needs_refine:
            refined_servicos, refined_conf, refined_debug, refined_metrics = extract_from_ocr_words(
                service,
                words,
                row_tol_factor=0.45,
                col_tol_factor=col_tol_factor,
                enable_refine=False
            )
            refine_info = {
                "attempted": True,
                "used": False,
                "base": {
                    "items": len(servicos),
                    "row_count": metrics.get("row_count", 0),
                    "qty_ratio": round(metrics.get("qty_ratio", 0.0), 3)
                },
                "refined": {
                    "items": len(refined_servicos),
                    "row_count": refined_metrics.get("row_count", 0),
                    "qty_ratio": round(refined_metrics.get("qty_ratio", 0.0), 3)
                }
            }
            use_refine = False
            if refined_servicos:
                if len(refined_servicos) >= len(servicos) + 2:
                    use_refine = True
                elif refined_metrics.get("qty_ratio", 0.0) >= metrics.get("qty_ratio", 0.0) + 0.1:
                    use_refine = True
                elif (
                    len(refined_servicos) > len(servicos)
                    and refined_metrics.get("unit_ratio", 0.0) >= metrics.get("unit_ratio", 0.0)
                ):
                    use_refine = True

            if use_refine:
                refine_info["used"] = True
                refined_debug["row_refine"] = refine_info
                return refined_servicos, refined_conf, refined_debug, refined_metrics

            debug["row_refine"] = refine_info

    return servicos, confidence, debug, metrics
