"""
Utilitários para detecção de grid em imagens.

Funções para detectar linhas horizontais e segmentar tabelas.
"""

from typing import Any, Dict, List, Sequence, Tuple, Union
import numpy as np
import cv2



def _median(values: Sequence[Union[int, float]]) -> float:
    """Calcula a mediana de uma lista de valores."""
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    mid = len(sorted_vals) // 2
    if len(sorted_vals) % 2 == 1:
        return float(sorted_vals[mid])
    return float(sorted_vals[mid - 1] + sorted_vals[mid]) / 2


def detect_grid_rows(image_bytes: bytes) -> Tuple[List[Tuple[int, int]], Dict[str, Any]]:
    """
    Detecta linhas de uma tabela em uma imagem.

    Args:
        image_bytes: Bytes da imagem PNG

    Returns:
        Tupla (rows, debug_info) onde rows é lista de (top, bottom)
    """
    if not image_bytes:
        return [], {"error": "empty_image"}

    img_array = np.frombuffer(image_bytes, np.uint8)
    gray = cv2.imdecode(img_array, cv2.IMREAD_GRAYSCALE)

    if gray is None:
        return [], {"error": "decode_failed"}

    height, width = gray.shape[:2]
    blur = cv2.GaussianBlur(gray, (3, 3), 0)
    _, bw = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    def detect_rows_by_projection() -> Tuple[List[Tuple[int, int]], Dict[str, Any]]:
        row_sum = (bw > 0).sum(axis=1)
        threshold = max(10, int(width * 0.02))
        segments: List[Tuple[int, int]] = []
        in_row = False
        start = 0

        for idx, value in enumerate(row_sum):
            if value >= threshold and not in_row:
                start = idx
                in_row = True
            elif value < threshold and in_row:
                end = idx - 1
                segments.append((start, end))
                in_row = False
        if in_row:
            segments.append((start, height - 1))

        if not segments:
            return [], {"segments": 0, "threshold": threshold}

        heights = [end - start + 1 for start, end in segments]
        median_height = _median(heights) or max(12, int(height * 0.015))
        merge_gap = max(4, int(median_height * 0.6))

        merged: List[List[int]] = []
        for start, end in segments:
            if not merged:
                merged.append([start, end])
                continue
            if start - merged[-1][1] <= merge_gap:
                merged[-1][1] = end
            else:
                merged.append([start, end])

        rows: List[Tuple[int, int]] = []
        min_row_height = max(12, int(height * 0.015))
        for start, end in merged:
            if end - start + 1 < min_row_height:
                continue
            top = max(0, start - 1)
            bottom = min(height - 1, end + 1)
            rows.append((top, bottom))

        debug = {
            "segments": len(segments),
            "rows_detected": len(rows),
            "threshold": threshold,
            "merge_gap": merge_gap,
            "method": "projection"
        }
        return rows, debug

    def extract_rows(min_width_ratio: float, max_height_ratio: float) -> Tuple[List[Tuple[int, int]], Dict[str, Any]]:
        horizontal_kernel = cv2.getStructuringElement(
            cv2.MORPH_RECT,
            (max(10, int(width * 0.03)), 1)
        )
        horizontal = cv2.erode(bw, horizontal_kernel, iterations=1)
        horizontal = cv2.dilate(horizontal, horizontal_kernel, iterations=1)

        contours, _ = cv2.findContours(horizontal, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        lines_y: List[int] = []
        min_width = int(width * min_width_ratio)
        max_height = max(6, int(height * max_height_ratio))

        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            if w < min_width or h > max_height:
                continue
            lines_y.append(y)
            lines_y.append(y + h)

        lines_y = sorted(lines_y)
        merged: List[int] = []
        for y in lines_y:
            if not merged or y - merged[-1] > 4:
                merged.append(y)

        rows: List[Tuple[int, int]] = []
        min_row_height = max(12, int(height * 0.015))
        for idx in range(len(merged) - 1):
            top = merged[idx] + 1
            bottom = merged[idx + 1] - 1
            if bottom - top < min_row_height:
                continue
            rows.append((top, bottom))

        return rows, {
            "lines_detected": len(merged),
            "rows_detected": len(rows),
            "width": width,
            "height": height
        }

    rows, debug = extract_rows(0.6, 0.03)

    if len(rows) < 8:
        fallback_rows, fallback_debug = extract_rows(0.4, 0.05)
        if len(fallback_rows) > len(rows):
            fallback_debug["fallback"] = True
            rows, debug = fallback_rows, fallback_debug

    if len(rows) < 8:
        proj_rows, proj_debug = detect_rows_by_projection()
        if len(proj_rows) > len(rows):
            proj_debug["fallback"] = True
            return proj_rows, proj_debug

    return rows, debug
