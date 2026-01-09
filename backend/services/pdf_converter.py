"""
Utilitários para conversão de PDF para imagens.
"""
import io
from typing import List, Optional, Callable

import fitz  # PyMuPDF
from PIL import Image

from config import OCRConfig
from logging_config import get_logger

logger = get_logger('services.pdf_converter')


class PDFConverter:
    """Conversor de PDF para imagens."""

    def pdf_to_images(
        self,
        file_path: str,
        dpi: Optional[int] = None,
        progress_callback: Optional[Callable] = None,
        cancel_check: Optional[Callable] = None,
        stage: str = "vision"
    ) -> List[bytes]:
        """
        Converte páginas de PDF em imagens PNG.

        Args:
            file_path: Caminho para o arquivo PDF
            dpi: Resolução em DPI (300 para melhor qualidade de OCR)
            progress_callback: Callback para progresso
            cancel_check: Callback para verificar cancelamento
            stage: Nome do estágio para progresso

        Returns:
            Lista de imagens em bytes (PNG)
        """
        if dpi is None:
            dpi = OCRConfig.DPI

        images = []
        doc = fitz.open(file_path)
        zoom = dpi / 72
        matrix = fitz.Matrix(zoom, zoom)

        total_pages = doc.page_count
        for page_index, page in enumerate(doc):
            if cancel_check and cancel_check():
                doc.close()
                raise InterruptedError("Processamento cancelado")

            if progress_callback:
                progress_callback(
                    page_index + 1,
                    total_pages,
                    stage,
                    f"Convertendo pagina {page_index + 1} de {total_pages}"
                )

            pix = page.get_pixmap(matrix=matrix)
            img_bytes = pix.tobytes("png")
            images.append(img_bytes)

        doc.close()
        return images

    def crop_region(
        self,
        image_bytes: bytes,
        left: float,
        top: float,
        right: float,
        bottom: float
    ) -> bytes:
        """
        Recorta uma região de uma imagem.

        Args:
            image_bytes: Imagem em bytes
            left: Posição esquerda (0-1)
            top: Posição superior (0-1)
            right: Posição direita (0-1)
            bottom: Posição inferior (0-1)

        Returns:
            Imagem recortada em bytes
        """
        try:
            img = Image.open(io.BytesIO(image_bytes))
            width, height = img.size
            crop = img.crop((
                int(width * left),
                int(height * top),
                int(width * right),
                int(height * bottom)
            ))
            buffer = io.BytesIO()
            crop.save(buffer, format="PNG")
            return buffer.getvalue()
        except Exception:
            return image_bytes

    def resize_image(self, image_bytes: bytes, scale: float = 0.5) -> bytes:
        """
        Redimensiona uma imagem por um fator de escala.

        Args:
            image_bytes: Imagem em bytes
            scale: Fator de escala (0.5 = metade do tamanho)

        Returns:
            Imagem redimensionada em bytes
        """
        try:
            img = Image.open(io.BytesIO(image_bytes))
            width, height = img.size
            resized = img.resize((
                max(1, int(width * scale)),
                max(1, int(height * scale))
            ))
            buffer = io.BytesIO()
            resized.save(buffer, format="PNG")
            return buffer.getvalue()
        except Exception:
            return image_bytes


# Instância singleton
pdf_converter = PDFConverter()
