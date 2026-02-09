"""
Extrator de servicos usando OCR com analise de layout.

Extrai servicos de imagens usando OCR com deteccao de colunas e linhas.
"""

from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from config import AtestadoProcessingConfig as APC
from exceptions import OCRError
from logging_config import get_logger

logger = get_logger('services.table_extraction.extractors.ocr_layout')

ProgressCallback = Optional[Callable[[int, int, str, str], None]]
CancelCheck = Optional[Callable[[], bool]]


def extract_servicos_from_ocr_layout(
    service: Any,
    file_path: str,
    progress_callback: ProgressCallback = None,
    cancel_check: CancelCheck = None
) -> Tuple[List[Dict], float, Dict]:
    """
    Extrai servicos usando OCR com analise de layout.

    Args:
        service: Instancia do TableExtractionService para delegar operacoes
        file_path: Caminho para o arquivo
        progress_callback: Callback para progresso
        cancel_check: Funcao para verificar cancelamento

    Returns:
        Tupla (servicos, confidence, debug)
    """
    # Importar aqui para evitar import circular
    from services.ocr_service import ocr_service
    from services.pdf_extraction_service import pdf_extraction_service

    min_conf = APC.OCR_LAYOUT_CONFIDENCE
    dpi = APC.OCR_LAYOUT_DPI
    page_min_items = APC.OCR_LAYOUT_PAGE_MIN_ITEMS
    retry_dpi = APC.OCR_LAYOUT_RETRY_DPI
    retry_dpi_hard = APC.OCR_LAYOUT_RETRY_DPI_HARD
    retry_conf = APC.OCR_LAYOUT_RETRY_CONFIDENCE
    retry_min_words = APC.OCR_LAYOUT_RETRY_MIN_WORDS
    retry_min_items = APC.OCR_LAYOUT_RETRY_MIN_ITEMS
    retry_min_qty_ratio = APC.OCR_LAYOUT_RETRY_MIN_QTY_RATIO

    images: List[bytes] = []
    file_ext = Path(file_path).suffix.lower()

    if file_ext == ".pdf":
        images = pdf_extraction_service.pdf_to_images(
            file_path,
            dpi=dpi,
            progress_callback=progress_callback,
            cancel_check=cancel_check,
            stage="ocr"
        )
    else:
        with open(file_path, "rb") as f:
            images = [f.read()]

    if not images:
        return [], 0.0, {"pages": 0}

    table_pages = pdf_extraction_service.detect_table_pages(images)
    if table_pages:
        page_queue = list(dict.fromkeys(table_pages))
        page_seen = set(page_queue)
    else:
        page_queue = list(range(len(images)))
        page_seen = set(page_queue)
    processed_pages: List[int] = []

    total_items = 0
    weighted_conf = 0.0
    all_servicos: List[Dict] = []
    page_debug: List[Dict] = []

    while page_queue:
        page_index = page_queue.pop(0)
        pdf_extraction_service._check_cancel(cancel_check)
        image_bytes = images[page_index]
        cropped = service._crop_page_image(file_path, file_ext, page_index, image_bytes)

        try:
            words = ocr_service.extract_words_from_bytes(cropped, min_confidence=min_conf)
        except OCRError as exc:
            logger.debug(f"Erro OCR na pagina {page_index + 1}: {exc}")
            page_debug.append({"page": page_index + 1, "error": str(exc)})
            continue

        servicos, confidence, debug, metrics = service._extract_from_ocr_words(words)
        base_metrics = metrics

        retry_info: Dict[str, Any] = {
            "attempted": False,
            "used": False,
            "base": {
                "word_count": base_metrics.get("word_count", 0),
                "items": len(servicos),
                "qty_ratio": round(base_metrics.get("qty_ratio", 0.0), 3)
            }
        }

        should_retry = (
            base_metrics.get("word_count", 0) < retry_min_words
            or base_metrics.get("total_page_items", 0) < retry_min_items
            or base_metrics.get("qty_ratio", 0.0) < retry_min_qty_ratio
        )

        if should_retry:
            servicos, confidence, debug, metrics, retry_info = _perform_retry(
                service=service,
                file_path=file_path,
                file_ext=file_ext,
                page_index=page_index,
                image_bytes=image_bytes,
                dpi=dpi,
                retry_dpi=retry_dpi,
                retry_dpi_hard=retry_dpi_hard,
                retry_conf=retry_conf,
                retry_min_words=retry_min_words,
                retry_min_items=retry_min_items,
                retry_min_qty_ratio=retry_min_qty_ratio,
                servicos=servicos,
                confidence=confidence,
                debug=debug,
                metrics=metrics,
                base_metrics=base_metrics,
                retry_info=retry_info,
                ocr_service=ocr_service,
            )

        total_page_items = metrics.get("total_page_items", 0)
        item_ratio = metrics.get("item_ratio", 0.0)
        unit_ratio = metrics.get("unit_ratio", 0.0)
        dominant_len = metrics.get("dominant_len", 0) or 0
        qty_ratio = metrics.get("qty_ratio", 0.0)

        primary_accept = (
            total_page_items > 0
            and dominant_len >= APC.OCR_PAGE_MIN_DOMINANT_LEN
            and item_ratio >= APC.OCR_PAGE_MIN_ITEM_RATIO
            and unit_ratio >= APC.OCR_PAGE_MIN_UNIT_RATIO
        )
        fallback_accept = (
            total_page_items >= APC.OCR_PAGE_MIN_ITEMS
            and dominant_len == 1
            and item_ratio >= APC.OCR_PAGE_FALLBACK_ITEM_RATIO
            and unit_ratio >= APC.OCR_PAGE_FALLBACK_UNIT_RATIO
        )
        itemless_accept = (
            (debug.get("itemless_mode") or debug.get("itemless_forced"))
            and total_page_items >= APC.OCR_PAGE_MIN_ITEMS
            and unit_ratio >= APC.OCR_PAGE_FALLBACK_UNIT_RATIO
            and qty_ratio >= APC.OCR_PAGE_FALLBACK_UNIT_RATIO
        )
        page_accept = primary_accept or fallback_accept or itemless_accept

        if page_accept and servicos and (debug.get("itemless_mode") or debug.get("itemless_forced")):
            service._assign_itemless_items(servicos, page_index + 1)
            debug["itemless_assigned"] = True

        debug.update({
            "page": page_index + 1,
            "row_count": metrics.get("row_count", 0),
            "word_count": metrics.get("word_count", 0),
            "item_col": metrics.get("item_col", {}),
            "page_accept": page_accept,
            "qty_ratio": round(qty_ratio, 3),
            "ocr_retry": retry_info
        })
        page_debug.append(debug)
        processed_pages.append(page_index)

        if not page_accept:
            continue

        if servicos:
            page_num = page_index + 1
            for s in servicos:
                s["_page"] = page_num
            all_servicos.extend(servicos)
            total_items += len(servicos)
            weighted_conf += confidence * len(servicos)

            if table_pages and len(servicos) >= page_min_items:
                for neighbor in (page_index - 1, page_index + 1):
                    if 0 <= neighbor < len(images) and neighbor not in page_seen:
                        page_seen.add(neighbor)
                        page_queue.append(neighbor)

    overall_conf = (weighted_conf / total_items) if total_items else 0.0
    return all_servicos, round(overall_conf, 3), {
        "pages": len(processed_pages),
        "pages_used": sorted(set(processed_pages)),
        "page_debug": page_debug
    }


def _perform_retry(
    service: Any,
    file_path: str,
    file_ext: str,
    page_index: int,
    image_bytes: bytes,
    dpi: int,
    retry_dpi: int,
    retry_dpi_hard: int,
    retry_conf: float,
    retry_min_words: int,
    retry_min_items: int,
    retry_min_qty_ratio: float,
    servicos: List[Dict],
    confidence: float,
    debug: Dict,
    metrics: Dict,
    base_metrics: Dict,
    retry_info: Dict,
    ocr_service: Any,
) -> Tuple[List[Dict], float, Dict, Dict, Dict]:
    """Executa retry com DPI mais alto se necessario."""
    retry_info["attempted"] = True
    retry_image_bytes = image_bytes
    rendered_dpi = dpi

    if file_ext == ".pdf" and retry_dpi > dpi:
        rerendered = service._render_pdf_page(file_path, page_index, retry_dpi)
        if rerendered:
            retry_image_bytes = rerendered
            rendered_dpi = retry_dpi

    retry_cropped = service._crop_page_image(file_path, file_ext, page_index, retry_image_bytes)

    try:
        words_retry = ocr_service.extract_words_from_bytes(
            retry_cropped,
            min_confidence=retry_conf,
            use_binarization=True
        )
        servicos_retry, conf_retry, debug_retry, metrics_retry = service._extract_from_ocr_words(words_retry)
        retry_info["retry"] = {
            "rendered_dpi": rendered_dpi,
            "min_confidence": retry_conf,
            "word_count": metrics_retry.get("word_count", 0),
            "items": len(servicos_retry),
            "qty_ratio": round(metrics_retry.get("qty_ratio", 0.0), 3)
        }

        if service._is_retry_result_better(servicos_retry, servicos, metrics_retry, base_metrics):
            servicos = servicos_retry
            confidence = conf_retry
            debug = debug_retry
            metrics = metrics_retry
            retry_info["used"] = True

    except OCRError as exc:
        retry_info["error"] = str(exc)

    # Hard retry se ainda nao satisfatorio
    needs_hard_retry = (
        retry_dpi_hard
        and retry_dpi_hard > retry_dpi
        and (
            metrics.get("word_count", 0) < retry_min_words
            or metrics.get("total_page_items", 0) < retry_min_items
            or metrics.get("qty_ratio", 0.0) < retry_min_qty_ratio
        )
    )

    if needs_hard_retry:
        retry_info["hard_attempted"] = True
        hard_image_bytes = image_bytes
        hard_rendered_dpi = dpi

        if file_ext == ".pdf" and retry_dpi_hard > dpi:
            rerendered = service._render_pdf_page(file_path, page_index, retry_dpi_hard)
            if rerendered:
                hard_image_bytes = rerendered
                hard_rendered_dpi = retry_dpi_hard

        hard_cropped = service._crop_page_image(file_path, file_ext, page_index, hard_image_bytes)

        try:
            words_hard = ocr_service.extract_words_from_bytes(
                hard_cropped,
                min_confidence=retry_conf,
                use_binarization=True
            )
            servicos_hard, conf_hard, debug_hard, metrics_hard = service._extract_from_ocr_words(words_hard)
            retry_info["hard"] = {
                "rendered_dpi": hard_rendered_dpi,
                "min_confidence": retry_conf,
                "word_count": metrics_hard.get("word_count", 0),
                "items": len(servicos_hard),
                "qty_ratio": round(metrics_hard.get("qty_ratio", 0.0), 3)
            }

            if service._is_retry_result_better(servicos_hard, servicos, metrics_hard, metrics):
                servicos = servicos_hard
                confidence = conf_hard
                debug = debug_hard
                metrics = metrics_hard
                retry_info["used"] = True
                retry_info["hard_used"] = True

        except OCRError as exc:
            retry_info["hard_error"] = str(exc)

    return servicos, confidence, debug, metrics, retry_info
