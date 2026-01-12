"""
Extrator de texto nativo de PDFs.

Utiliza pdfplumber para extrair texto de PDFs com camada de texto incorporada.
Este é o método mais rápido e barato (gratuito).
"""

import pdfplumber
from typing import Optional

from .base_extractor import BaseExtractor, ExtractionMethod, ExtractionResult
from config import OCRConfig

from logging_config import get_logger
logger = get_logger('services.extraction.native_text')


class NativeTextExtractor(BaseExtractor):
    """
    Extrator de texto nativo de PDFs usando pdfplumber.

    Ideal para PDFs digitais (não escaneados) que já possuem
    camada de texto incorporada.
    """

    MIN_TEXT_LENGTH = OCRConfig.MIN_TEXT_LENGTH

    @property
    def method(self) -> ExtractionMethod:
        return ExtractionMethod.NATIVE_TEXT

    @property
    def is_available(self) -> bool:
        """pdfplumber está sempre disponível."""
        return True

    @property
    def cost_per_page(self) -> float:
        """Extração nativa é gratuita."""
        return 0.0

    def extract(
        self,
        file_path: str,
        progress_callback: Optional[callable] = None,
        cancel_check: Optional[callable] = None
    ) -> ExtractionResult:
        """
        Extrai texto nativo de PDF usando pdfplumber.

        Args:
            file_path: Caminho para o arquivo PDF
            progress_callback: Callback para progresso (current, total, message)
            cancel_check: Função que retorna True para cancelar

        Returns:
            ExtractionResult com texto e metadados
        """
        try:
            text_parts = []
            total_pages = 0
            pages_with_text = 0

            with pdfplumber.open(file_path) as pdf:
                total_pages = len(pdf.pages)

                for i, page in enumerate(pdf.pages):
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
                            total_pages,
                            f"Extraindo texto da página {i+1}/{total_pages}"
                        )

                    page_text = page.extract_text() or ""
                    if page_text.strip():
                        text_parts.append(f"--- Página {i+1} ---\n{page_text}")
                        pages_with_text += 1

            text = "\n\n".join(text_parts)

            # Verificar se texto é válido
            if len(text) < self.MIN_TEXT_LENGTH:
                return ExtractionResult(
                    text=text,
                    confidence=0.2,
                    method=self.method,
                    success=False,
                    pages_processed=total_pages,
                    errors=["Texto extraído muito curto"],
                    metadata={"pages_with_text": pages_with_text}
                )

            # Lazy import para evitar circular import
            from services.text_utils import is_garbage_text
            if is_garbage_text(text):
                return ExtractionResult(
                    text=text,
                    confidence=0.1,
                    method=self.method,
                    success=False,
                    pages_processed=total_pages,
                    errors=["Texto extraído parece ser lixo/ruído"],
                    metadata={"pages_with_text": pages_with_text}
                )

            # Calcular confiança baseado na proporção de páginas com texto
            confidence = pages_with_text / total_pages if total_pages > 0 else 0

            return ExtractionResult(
                text=text,
                confidence=confidence,
                method=self.method,
                success=True,
                pages_processed=total_pages,
                metadata={
                    "pages_with_text": pages_with_text,
                    "text_length": len(text)
                }
            )

        except Exception as e:
            logger.error(f"Erro na extração nativa: {e}")
            return ExtractionResult(
                text="",
                confidence=0.0,
                method=self.method,
                success=False,
                errors=[f"Erro na extração nativa: {str(e)}"]
            )
