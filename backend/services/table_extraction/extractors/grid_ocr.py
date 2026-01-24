"""
Extrator de servicos usando Grid OCR com OpenCV.

Detecta linhas de grade em imagens e extrai servicos usando OCR.
"""

from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from services.extraction.quality_assessor import compute_servicos_stats, compute_quality_score
from config import AtestadoProcessingConfig as APC
from exceptions import OCRError
from logging_config import get_logger

logger = get_logger('services.table_extraction.extractors.grid_ocr')

ProgressCallback = Optional[Callable[[int, int, str, str], None]]
CancelCheck = Optional[Callable[[], bool]]


def extract_servicos_from_grid_ocr(
    service: Any,
    file_path: str,
    progress_callback: ProgressCallback = None,
    cancel_check: CancelCheck = None
) -> Tuple[List[Dict], float, Dict]:
    """
    Extrai servicos usando deteccao de grade com OpenCV e OCR.

    Args:
        service: Instancia do TableExtractionService para delegar operacoes
        file_path: Caminho para o arquivo
        progress_callback: Callback para progresso
        cancel_check: Funcao para verificar cancelamento

    Returns:
        Tupla (servicos, confidence, debug)
    """
    # Importar aqui para evitar import circular
    from services.pdf_extraction_service import pdf_extraction_service
    from services.ocr_service import ocr_service

    min_conf = APC.OCR_LAYOUT_CONFIDENCE
    dpi = APC.OCR_LAYOUT_DPI

    images: List[bytes] = []
    file_ext = Path(file_path).suffix.lower()

    if file_ext == ".pdf":
        images = pdf_extraction_service.pdf_to_images(
            file_path,
            dpi=dpi,
            progress_callback=progress_callback,
            cancel_check=cancel_check,
            stage="ocr_grid"
        )
    else:
        with open(file_path, "rb") as f:
            images = [f.read()]

    if not images:
        return [], 0.0, {"pages": 0}

    all_servicos: List[Dict] = []
    page_debug: List[Dict] = []

    for page_index, image_bytes in enumerate(images):
        pdf_extraction_service._check_cancel(cancel_check)
        cropped = service._crop_page_image(file_path, file_ext, page_index, image_bytes)
        row_boxes, row_debug = service._detect_grid_rows(cropped)

        if not row_boxes:
            page_debug.append({
                "page": page_index + 1,
                "rows": 0,
                "grid": row_debug,
                "reason": "no_rows"
            })
            continue

        try:
            words = ocr_service.extract_words_from_bytes(cropped, min_confidence=min_conf)
        except OCRError as exc:
            page_debug.append({
                "page": page_index + 1,
                "rows": len(row_boxes),
                "grid": row_debug,
                "error": str(exc)
            })
            continue

        row_count = 0
        for top, bottom in row_boxes:
            row_words = [
                w for w in words
                if w.get("y_center") is not None
                and top <= w["y_center"] <= bottom
            ]
            if not row_words:
                continue
            row_words_sorted = sorted(row_words, key=lambda w: w.get("x_center", 0))
            row_text = " ".join(w.get("text", "") for w in row_words_sorted).strip()
            if not row_text:
                continue
            row_servicos = service._parse_row_text_to_servicos(row_text)
            if row_servicos:
                row_count += 1
                all_servicos.extend(row_servicos)

        page_debug.append({
            "page": page_index + 1,
            "rows": row_count,
            "grid": row_debug,
            "word_count": len(words)
        })

    stats = compute_servicos_stats(all_servicos)
    confidence = compute_quality_score(stats)
    confidence = max(0.0, min(1.0, round(confidence, 3)))

    debug = {
        "pages": len(images),
        "page_debug": page_debug,
        "stats": stats,
        "confidence": confidence
    }

    return all_servicos, confidence, debug
