"""
Construtor de tabelas a partir de palavras OCR.

Contem a logica de construcao de tabelas baseada em layout de palavras OCR.
"""

from typing import Any, Dict, List, Optional, Tuple


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
    Constroi tabela a partir de palavras OCR baseado em layout.

    Agrupa palavras em linhas e colunas usando tolerancias baseadas
    nas dimensoes medianas das palavras.

    Args:
        words: Lista de palavras OCR com coordenadas (x_center, y_center, etc.)
        row_tol_factor: Fator de tolerancia para agrupamento de linhas
        col_tol_factor: Fator de tolerancia para agrupamento de colunas
        min_row_tol: Tolerancia minima para linhas
        min_col_tol: Tolerancia minima para colunas

    Returns:
        Tupla (table_rows, col_centers) onde:
        - table_rows: Lista de linhas, cada uma com lista de celulas
        - col_centers: Lista de centros das colunas detectadas
    """
    if not words:
        return [], []

    # Calcular tolerancias baseadas nas dimensoes medianas
    heights = [w["height"] for w in words if w.get("height")]
    widths = [w["width"] for w in words if w.get("width")]
    median_height = median(heights) or 12.0
    median_width = median(widths) or 40.0
    row_tol = max(min_row_tol, median_height * row_tol_factor)
    col_tol = max(min_col_tol, median_width * col_tol_factor)

    # Agrupar palavras em linhas
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

    # Detectar colunas via clustering de centros X
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

    # Construir linhas da tabela
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
