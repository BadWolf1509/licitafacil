"""
Extrator OCR na nuvem usando Azure Document Intelligence.

Utiliza o Azure Document Intelligence para OCR de alta qualidade.
Custo aproximado: R$ 0.01/página.
"""

from typing import Optional, List

from .base_extractor import BaseExtractor, ExtractionMethod, ExtractionResult
from exceptions import AzureNotConfiguredError

from logging_config import get_logger
logger = get_logger('services.extraction.cloud_ocr')


class CloudOCRExtractor(BaseExtractor):
    """
    Extrator OCR usando Azure Document Intelligence.

    Oferece alta precisão para documentos escaneados complexos,
    com melhor suporte a tabelas e layouts estruturados.
    """

    def _get_service(self):
        """Obtém azure_document_service (lazy import)."""
        from services.azure_document_service import azure_document_service
        return azure_document_service

    @property
    def method(self) -> ExtractionMethod:
        return ExtractionMethod.CLOUD_OCR

    @property
    def is_available(self) -> bool:
        """Verifica se Azure está configurado."""
        return self._get_service().is_configured

    @property
    def cost_per_page(self) -> float:
        """Custo aproximado por página em R$."""
        return 0.01

    def extract(
        self,
        file_path: str,
        progress_callback: Optional[callable] = None,
        cancel_check: Optional[callable] = None
    ) -> ExtractionResult:
        """
        Extrai texto usando Azure Document Intelligence.

        Args:
            file_path: Caminho para o arquivo
            progress_callback: Callback para progresso
            cancel_check: Função de cancelamento

        Returns:
            ExtractionResult com texto e metadados
        """
        if not self.is_available:
            return ExtractionResult(
                text="",
                confidence=0.0,
                method=self.method,
                success=False,
                errors=["Azure Document Intelligence não está configurado"]
            )

        try:
            # Verificar cancelamento antes de iniciar
            if cancel_check and cancel_check():
                return ExtractionResult(
                    text="",
                    confidence=0.0,
                    method=self.method,
                    success=False,
                    errors=["Processamento cancelado pelo usuário"]
                )

            # Notificar início
            if progress_callback:
                progress_callback(1, 3, "Enviando documento para Azure...")

            # Extrair texto
            result = self._get_service().extract_text_from_file(file_path)

            # Notificar conclusão
            if progress_callback:
                progress_callback(3, 3, "Processamento Azure concluído")

            # Estimar número de páginas pelo tamanho do texto
            estimated_pages = max(1, len(result.text) // 2000)
            cost_estimate = estimated_pages * self.cost_per_page

            return ExtractionResult(
                text=result.text,
                confidence=result.confidence,
                method=self.method,
                success=True,
                pages_processed=estimated_pages,
                cost_estimate=cost_estimate,
                metadata={
                    "azure_confidence": result.confidence,
                    "text_length": len(result.text)
                }
            )

        except AzureNotConfiguredError:
            return ExtractionResult(
                text="",
                confidence=0.0,
                method=self.method,
                success=False,
                errors=["Azure Document Intelligence não está configurado"]
            )
        except Exception as e:
            logger.error(f"Erro no Azure OCR: {e}")
            return ExtractionResult(
                text="",
                confidence=0.0,
                method=self.method,
                success=False,
                errors=[f"Erro no Azure OCR: {str(e)}"]
            )

    def extract_from_images(
        self,
        images: List[bytes],
        progress_callback: Optional[callable] = None,
        cancel_check: Optional[callable] = None
    ) -> ExtractionResult:
        """
        Extrai texto de lista de imagens usando Azure.

        Args:
            images: Lista de imagens em bytes
            progress_callback: Callback para progresso
            cancel_check: Função de cancelamento

        Returns:
            ExtractionResult com texto e metadados
        """
        if not self.is_available:
            return ExtractionResult(
                text="",
                confidence=0.0,
                method=self.method,
                success=False,
                errors=["Azure Document Intelligence não está configurado"]
            )

        try:
            text_parts = []
            total_confidence = 0.0

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
                    progress_callback(i + 1, len(images), f"Azure OCR imagem {i+1}/{len(images)}")

                result = self._get_service().extract_text_from_bytes(img_bytes)
                if result.text.strip():
                    text_parts.append(result.text)
                    total_confidence += result.confidence

            text = "\n\n".join(text_parts)
            avg_confidence = total_confidence / len(images) if images else 0
            cost_estimate = len(images) * self.cost_per_page

            return ExtractionResult(
                text=text,
                confidence=avg_confidence,
                method=self.method,
                success=len(text.strip()) > 100,
                pages_processed=len(images),
                cost_estimate=cost_estimate
            )

        except Exception as e:
            logger.error(f"Erro no Azure OCR de imagens: {e}")
            return ExtractionResult(
                text="",
                confidence=0.0,
                method=self.method,
                success=False,
                errors=[f"Erro no Azure OCR: {str(e)}"]
            )
