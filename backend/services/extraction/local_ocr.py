"""
Extrator OCR local usando EasyOCR.

Utiliza EasyOCR com pré-processamento de imagem para extrair
texto de documentos escaneados. Gratuito mas mais lento.
"""

from pathlib import Path
from typing import Optional, List

import fitz  # PyMuPDF

from .base_extractor import BaseExtractor, ExtractionMethod, ExtractionResult

from logging_config import get_logger
logger = get_logger('services.extraction.local_ocr')


class LocalOCRExtractor(BaseExtractor):
    """
    Extrator OCR local usando EasyOCR.

    Ideal para documentos escaneados quando Azure não está disponível
    ou para economia de custos.
    """

    def __init__(self, enable_preprocessing: bool = True):
        """
        Inicializa o extractor.

        Args:
            enable_preprocessing: Se True, aplica pré-processamento nas imagens
        """
        self._enable_preprocessing = enable_preprocessing

    def _get_ocr_service(self):
        """Obtém ocr_service (lazy import)."""
        from services.ocr_service import ocr_service
        return ocr_service

    def _get_preprocessor(self):
        """Obtém image_preprocessor (lazy import)."""
        from services.image_preprocessor import image_preprocessor
        return image_preprocessor

    @property
    def method(self) -> ExtractionMethod:
        return ExtractionMethod.LOCAL_OCR

    @property
    def is_available(self) -> bool:
        """Verifica se EasyOCR está disponível."""
        ocr = self._get_ocr_service()
        return hasattr(ocr, 'is_available') and ocr.is_available or True

    @property
    def cost_per_page(self) -> float:
        """OCR local é gratuito."""
        return 0.0

    def _convert_pdf_to_images(
        self,
        file_path: str,
        dpi: int = 300
    ) -> List[bytes]:
        """
        Converte PDF para lista de imagens.

        Args:
            file_path: Caminho do PDF
            dpi: Resolução em DPI

        Returns:
            Lista de imagens em bytes (PNG)
        """
        images = []
        doc = fitz.open(file_path)
        zoom = dpi / 72
        matrix = fitz.Matrix(zoom, zoom)

        for page in doc:
            pix = page.get_pixmap(matrix=matrix)
            images.append(pix.tobytes("png"))

        doc.close()
        return images

    def _preprocess_images(self, images: List[bytes]) -> List[bytes]:
        """
        Aplica pré-processamento nas imagens.

        Args:
            images: Lista de imagens em bytes

        Returns:
            Lista de imagens pré-processadas
        """
        preprocessed = []
        for img_bytes in images:
            try:
                processed = self._get_preprocessor().preprocess(
                    img_bytes,
                    deskew=True,
                    denoise=True,
                    enhance_contrast=True
                )
                preprocessed.append(processed)
            except Exception as e:
                logger.warning(f"Erro no pré-processamento: {e}")
                preprocessed.append(img_bytes)
        return preprocessed

    def extract(
        self,
        file_path: str,
        progress_callback: Optional[callable] = None,
        cancel_check: Optional[callable] = None
    ) -> ExtractionResult:
        """
        Extrai texto usando OCR local.

        Args:
            file_path: Caminho para o arquivo
            progress_callback: Callback para progresso
            cancel_check: Função de cancelamento

        Returns:
            ExtractionResult com texto e metadados
        """
        try:
            path = Path(file_path)
            ext = path.suffix.lower()

            # Obter imagens
            if ext == '.pdf':
                images = self._convert_pdf_to_images(file_path)
            else:
                with open(file_path, 'rb') as f:
                    images = [f.read()]

            # Pré-processar se habilitado
            if self._enable_preprocessing:
                images = self._preprocess_images(images)

            # Aplicar OCR
            text_parts = []
            total_confidence = 0.0
            pages_processed = 0

            for i, img_bytes in enumerate(images):
                # Verificar cancelamento
                if cancel_check and cancel_check():
                    return ExtractionResult(
                        text="",
                        confidence=0.0,
                        method=self.method,
                        success=False,
                        errors=["Processamento cancelado pelo usuário"]
                    )

                # Notificar progresso
                if progress_callback:
                    progress_callback(
                        i + 1,
                        len(images),
                        f"OCR página {i+1}/{len(images)}"
                    )

                try:
                    result = self._get_ocr_service().extract_text_from_bytes(img_bytes)

                    if isinstance(result, tuple):
                        page_text, page_confidence = result
                    else:
                        page_text = result
                        page_confidence = 0.8

                    if page_text.strip():
                        text_parts.append(f"--- Página {i+1} ---\n{page_text}")
                        total_confidence += page_confidence
                        pages_processed += 1

                except Exception as e:
                    logger.warning(f"Erro OCR na página {i+1}: {e}")
                    text_parts.append(f"--- Página {i+1} ---\n[Erro OCR: {e}]")

            text = "\n\n".join(text_parts)
            avg_confidence = total_confidence / pages_processed if pages_processed > 0 else 0

            return ExtractionResult(
                text=text,
                confidence=avg_confidence,
                method=self.method,
                success=len(text.strip()) > 100,
                pages_processed=len(images),
                metadata={
                    "preprocessing_enabled": self._enable_preprocessing,
                    "pages_with_text": pages_processed,
                    "text_length": len(text)
                }
            )

        except Exception as e:
            logger.error(f"Erro no OCR local: {e}")
            return ExtractionResult(
                text="",
                confidence=0.0,
                method=self.method,
                success=False,
                errors=[f"Erro no OCR local: {str(e)}"]
            )

    def extract_from_images(
        self,
        images: List[bytes],
        progress_callback: Optional[callable] = None,
        cancel_check: Optional[callable] = None
    ) -> ExtractionResult:
        """
        Extrai texto de lista de imagens.

        Args:
            images: Lista de imagens em bytes
            progress_callback: Callback para progresso
            cancel_check: Função de cancelamento

        Returns:
            ExtractionResult com texto e metadados
        """
        try:
            # Pré-processar se habilitado
            if self._enable_preprocessing:
                images = self._preprocess_images(images)

            text_parts = []
            total_confidence = 0.0
            pages_processed = 0

            for i, img_bytes in enumerate(images):
                if cancel_check and cancel_check():
                    return ExtractionResult(
                        text="",
                        confidence=0.0,
                        method=self.method,
                        success=False,
                        errors=["Processamento cancelado"]
                    )

                if progress_callback:
                    progress_callback(i + 1, len(images), f"OCR imagem {i+1}/{len(images)}")

                try:
                    result = self._get_ocr_service().extract_text_from_bytes(img_bytes)

                    if isinstance(result, tuple):
                        page_text, page_confidence = result
                    else:
                        page_text = result
                        page_confidence = 0.8

                    if page_text.strip():
                        text_parts.append(page_text)
                        total_confidence += page_confidence
                        pages_processed += 1

                except Exception as e:
                    logger.warning(f"Erro OCR na imagem {i+1}: {e}")

            text = "\n\n".join(text_parts)
            avg_confidence = total_confidence / pages_processed if pages_processed > 0 else 0

            return ExtractionResult(
                text=text,
                confidence=avg_confidence,
                method=self.method,
                success=len(text.strip()) > 100,
                pages_processed=len(images),
                metadata={"preprocessing_enabled": self._enable_preprocessing}
            )

        except Exception as e:
            return ExtractionResult(
                text="",
                confidence=0.0,
                method=self.method,
                success=False,
                errors=[f"Erro no OCR de imagens: {str(e)}"]
            )
