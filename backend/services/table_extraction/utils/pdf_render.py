"""
Utilitários para renderização de PDFs.

Funções para renderizar páginas de PDF como imagens e recortar regiões.
"""

from typing import Optional

import fitz
import pdfplumber

from logging_config import get_logger
from services.pdf_extraction_service import pdf_extraction_service

logger = get_logger('services.table_extraction.utils.pdf_render')


def render_pdf_page(file_path: str, page_index: int, dpi: int) -> Optional[bytes]:
    """
    Renderiza uma página do PDF como imagem PNG.

    Args:
        file_path: Caminho do arquivo PDF
        page_index: Índice da página (0-based)
        dpi: Resolução em DPI

    Returns:
        Bytes da imagem PNG ou None em caso de erro
    """
    try:
        doc = fitz.open(file_path)
        page = doc[page_index]
        zoom = dpi / 72
        matrix = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=matrix)
        img_bytes = pix.tobytes("png")
        doc.close()
        return img_bytes
    except Exception as exc:
        logger.debug(f"OCR layout: erro ao renderizar pagina {page_index + 1}: {exc}")
        return None


def crop_page_image(
    file_path: str,
    file_ext: str,
    page_index: int,
    image_bytes: bytes
) -> bytes:
    """
    Recorta a área mais provável da tabela para OCR.

    Args:
        file_path: Caminho do arquivo
        file_ext: Extensão do arquivo
        page_index: Índice da página
        image_bytes: Bytes da imagem original

    Returns:
        Bytes da imagem recortada
    """
    cropped = None

    if file_ext == ".pdf":
        try:
            with pdfplumber.open(file_path) as pdf:
                page = pdf.pages[page_index]
                large_images = [
                    img for img in (page.images or [])
                    if img.get("width", 0) > 400 and img.get("height", 0) > 400
                ]
                if large_images:
                    biggest = max(
                        large_images,
                        key=lambda img: img.get("width", 0) * img.get("height", 0)
                    )
                    page_width = page.width or 1
                    page_height = page.height or 1
                    left = biggest["x0"] / page_width
                    right = biggest["x1"] / page_width
                    top = biggest["top"] / page_height
                    bottom = biggest["bottom"] / page_height
                    cropped = pdf_extraction_service.crop_region(
                        image_bytes, left, top, right, bottom
                    )
        except Exception as exc:
            logger.debug(
                f"OCR layout: erro ao localizar imagem grande na pagina {page_index + 1}: {exc}"
            )

    if cropped is None:
        cropped = pdf_extraction_service.crop_region(image_bytes, 0.05, 0.15, 0.95, 0.92)

    return cropped
