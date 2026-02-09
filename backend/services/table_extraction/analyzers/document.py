"""
Analisador de tipo de documento.

Funcoes para analisar documentos PDF e determinar suas caracteristicas
para otimizar o fluxo de extracao.
"""

from typing import Any, Dict

import pdfplumber

from config import AtestadoProcessingConfig as APC
from logging_config import get_logger

logger = get_logger('services.table_extraction.analyzers.document')


def analyze_document_type(file_path: str) -> Dict[str, Any]:
    """
    Analisa o tipo de documento para otimizar o fluxo de extracao.

    Args:
        file_path: Caminho do arquivo PDF

    Returns:
        dict com:
            - is_scanned: bool - documento e escaneado
            - has_image_tables: bool - tem tabelas dentro de imagens
            - total_pages: int
            - avg_chars_per_page: float
            - large_images_count: int
    """
    result = {
        "is_scanned": False,
        "has_image_tables": False,
        "total_pages": 0,
        "avg_chars_per_page": 0.0,
        "large_images_count": 0,
        "dominant_image_pages": 0,
        "dominant_image_page_indexes": [],
        "max_image_ratio": 0.0
    }

    try:
        with pdfplumber.open(file_path) as pdf:
            total_pages = len(pdf.pages)
            total_chars = 0
            total_large_images = 0
            pages_with_tables_in_images = 0
            dominant_image_pages = 0
            dominant_image_page_indexes = []
            max_image_ratio = 0.0

            for page_index, page in enumerate(pdf.pages):
                text = page.extract_text() or ""
                chars = len(text.strip())
                total_chars += chars

                large_images = 0
                page_area = (page.width or 1) * (page.height or 1)
                page_max_ratio = 0.0
                for img in page.images or []:
                    width = img.get("width", 0) or 0
                    height = img.get("height", 0) or 0
                    if width > 400 and height > 400:
                        large_images += 1
                    area = width * height
                    if page_area > 0:
                        ratio = area / page_area
                        if ratio > page_max_ratio:
                            page_max_ratio = ratio
                if page_max_ratio > max_image_ratio:
                    max_image_ratio = page_max_ratio
                total_large_images += large_images

                if page_max_ratio >= APC.DOMINANT_IMAGE_RATIO:
                    dominant_image_pages += 1
                    dominant_image_page_indexes.append(page_index)

                if chars < APC.SCANNED_MIN_CHARS_PER_PAGE and large_images > 0:
                    pages_with_tables_in_images += 1

            avg_chars = total_chars / total_pages if total_pages > 0 else 0
            image_ratio = total_large_images / total_pages if total_pages > 0 else 0

            result["total_pages"] = total_pages
            result["avg_chars_per_page"] = avg_chars
            result["large_images_count"] = total_large_images
            result["dominant_image_pages"] = dominant_image_pages
            result["dominant_image_page_indexes"] = dominant_image_page_indexes
            result["max_image_ratio"] = max_image_ratio

            result["is_scanned"] = (
                avg_chars < APC.SCANNED_MIN_CHARS_PER_PAGE
                or (avg_chars < 500 and image_ratio >= APC.SCANNED_IMAGE_PAGE_RATIO)
            )

            result["has_image_tables"] = (
                pages_with_tables_in_images > 0
                or dominant_image_pages >= APC.DOMINANT_IMAGE_MIN_PAGES
            )

            logger.info(
                f"Analise do documento: {total_pages} paginas, "
                f"media {avg_chars:.0f} chars/pagina, "
                f"{total_large_images} imagens grandes, "
                f"dominant_pages={dominant_image_pages}, max_img_ratio={max_image_ratio:.2f}, "
                f"escaneado={result['is_scanned']}, "
                f"tabelas_em_imagens={result['has_image_tables']}"
            )

    except Exception as e:
        logger.warning(f"Erro ao analisar documento: {e}")

    return result
