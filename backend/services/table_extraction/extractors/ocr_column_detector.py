"""
Detector de colunas de item em dados OCR.

Contem a logica de inferencia da coluna de item a partir de palavras OCR.
"""

from typing import Any, Dict, List, Optional, Tuple

from services.extraction import parse_item_tuple
from config import AtestadoProcessingConfig as APC


def infer_item_column_from_words(
    words: List[Dict[str, Any]],
    col_centers: List[float]
) -> Tuple[Optional[int], Dict[str, Any]]:
    """
    Infere a coluna de item a partir das palavras OCR.

    Analisa as palavras que contem codigos de item validos e determina
    qual coluna tem a maior concentracao desses codigos.

    Args:
        words: Lista de palavras OCR com coordenadas
        col_centers: Centros das colunas detectadas

    Returns:
        Tupla (item_col_index, debug_info) onde:
        - item_col_index: Indice da coluna de item ou None
        - debug_info: Informacoes de debug para analise
    """
    if not words or not col_centers:
        return None, {}

    min_ratio = APC.ITEM_COL_RATIO
    max_x_ratio = APC.ITEM_COL_MAX_X_RATIO
    max_index = APC.ITEM_COL_MAX_INDEX
    min_count = APC.ITEM_COL_MIN_COUNT

    # Calcular span horizontal
    min_x = min(w["x0"] for w in words)
    max_x = max(w["x1"] for w in words)
    span = max(1.0, max_x - min_x)

    # Contar codigos de item por coluna
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

    # Encontrar coluna com mais codigos de item
    best_idx = counts.index(max(counts))
    ratio = counts[best_idx] / max(1, total_candidates)
    x_ratio = (col_centers[best_idx] - min_x) / span

    debug = {
        "item_col_counts": counts,
        "item_col_ratio": round(ratio, 3),
        "item_col_x_ratio": round(x_ratio, 3),
        "item_col_best": best_idx
    }

    # Validar coluna candidata
    if best_idx > max_index or x_ratio > max_x_ratio:
        return None, debug
    if ratio < min_ratio and counts[best_idx] < min_count:
        return None, debug

    return best_idx, debug
