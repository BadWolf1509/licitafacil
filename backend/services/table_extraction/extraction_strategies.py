"""
Estratégias de extração de serviços.

Implementa o Strategy Pattern para diferentes métodos de extração:
- PdfPlumber (gratuito)
- Document AI (pago)
- OCR Layout
- Grid OCR
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from logging_config import get_logger

logger = get_logger('services.table_extraction.extraction_strategies')

ProgressCallback = Optional[Callable[[str, int], None]]
CancelCheck = Optional[Callable[[], bool]]


@dataclass
class ExtractionResult:
    """Resultado de uma estratégia de extração."""
    servicos: List[Dict]
    confidence: float
    debug: Dict[str, Any]
    qty_ratio: float
    complete_ratio: float
    source: str


class ExtractionStrategy(ABC):
    """Interface base para estratégias de extração."""

    def __init__(self, service: Any):
        """
        Args:
            service: Instância do TableExtractionService
        """
        self._service = service

    @property
    @abstractmethod
    def name(self) -> str:
        """Nome da estratégia."""
        pass

    @abstractmethod
    def should_execute(self, context: Dict[str, Any]) -> bool:
        """
        Verifica se a estratégia deve ser executada.

        Args:
            context: Contexto com informações sobre o documento

        Returns:
            True se deve executar
        """
        pass

    @abstractmethod
    def execute(
        self,
        file_path: str,
        context: Dict[str, Any],
        progress_callback: ProgressCallback = None,
        cancel_check: CancelCheck = None,
    ) -> ExtractionResult:
        """
        Executa a estratégia de extração.

        Args:
            file_path: Caminho do arquivo
            context: Contexto com informações sobre o documento
            progress_callback: Callback de progresso
            cancel_check: Função para verificar cancelamento

        Returns:
            Resultado da extração
        """
        pass

    def _empty_result(self) -> ExtractionResult:
        """Retorna um resultado vazio."""
        return ExtractionResult(
            servicos=[],
            confidence=0.0,
            debug={},
            qty_ratio=0.0,
            complete_ratio=0.0,
            source=self.name
        )


class PdfPlumberStrategy(ExtractionStrategy):
    """Estratégia de extração usando pdfplumber."""

    @property
    def name(self) -> str:
        return "pdfplumber"

    def should_execute(self, context: Dict[str, Any]) -> bool:
        """Não executa para documentos escaneados."""
        return not context.get("is_scanned", False)

    def execute(
        self,
        file_path: str,
        context: Dict[str, Any],
        progress_callback: ProgressCallback = None,
        cancel_check: CancelCheck = None,
    ) -> ExtractionResult:
        if not self.should_execute(context):
            logger.info("Cascata: pulando pdfplumber (documento escaneado)")
            return self._empty_result()

        logger.info("Cascata Etapa 1: Tentando pdfplumber...")

        servicos, confidence, debug = self._service.extract_servicos_from_tables(file_path)
        debug["source"] = self.name
        qty_ratio = self._service.calc_qty_ratio(servicos)
        complete_ratio = self._service.calc_complete_ratio(servicos)

        return ExtractionResult(
            servicos=servicos,
            confidence=confidence,
            debug=debug,
            qty_ratio=qty_ratio,
            complete_ratio=complete_ratio,
            source=self.name
        )


class DocumentAIStrategy(ExtractionStrategy):
    """Estratégia de extração usando Document AI."""

    @property
    def name(self) -> str:
        return "document_ai"

    def should_execute(self, context: Dict[str, Any]) -> bool:
        """Verifica se Document AI está disponível e não é só fallback."""
        return (
            context.get("document_ai_ready", False)
            and not context.get("document_ai_fallback_only", False)
        )

    def execute(
        self,
        file_path: str,
        context: Dict[str, Any],
        progress_callback: ProgressCallback = None,
        cancel_check: CancelCheck = None,
    ) -> ExtractionResult:
        if not self.should_execute(context):
            if context.get("document_ai_ready"):
                logger.info("Cascata: Document AI aguardando fallback pos-OCR")
            else:
                logger.info("Cascata: Document AI nao disponivel")
            return self._empty_result()

        logger.info("Cascata Etapa 2: Tentando Document AI...")

        try:
            allow_itemless = context.get("allow_itemless", False)
            text_useful = context.get("text_useful", True)

            servicos, confidence, debug = self._service.extract_servicos_from_document_ai(
                file_path,
                allow_itemless=allow_itemless
            )
            debug["source"] = self.name

            # Retry se page limit excedido
            if (
                debug.get("error")
                and "PAGE_LIMIT_EXCEEDED" in str(debug.get("error"))
                and not text_useful
            ):
                logger.info("Cascata: Document AI page limit, tentando imageless...")
                servicos, confidence, debug = self._service.extract_servicos_from_document_ai(
                    file_path,
                    use_native_pdf_parsing=True,
                    allow_itemless=allow_itemless
                )
                debug["source"] = self.name
                debug["retry_reason"] = "page_limit_exceeded"

            # Merge com pdfplumber se disponível
            pdf_servicos = context.get("pdf_servicos", [])
            if servicos and pdf_servicos:
                servicos, merge_debug = self._service._merge_table_sources(servicos, pdf_servicos)
                debug["merge"] = merge_debug

            qty_ratio = self._service.calc_qty_ratio(servicos)
            complete_ratio = self._service.calc_complete_ratio(servicos)

            return ExtractionResult(
                servicos=servicos,
                confidence=confidence,
                debug=debug,
                qty_ratio=qty_ratio,
                complete_ratio=complete_ratio,
                source=self.name
            )

        except Exception as e:
            logger.warning(f"Cascata: Document AI falhou - {e}")
            result = self._empty_result()
            result.debug = {"error": str(e)}
            return result


class OCRLayoutStrategy(ExtractionStrategy):
    """Estratégia de extração usando OCR layout."""

    @property
    def name(self) -> str:
        return "ocr_layout"

    def should_execute(self, context: Dict[str, Any]) -> bool:
        """Executa se tem imagens grandes e outros métodos falharam."""
        large_images = context.get("large_images", 0)
        pdf_servicos = context.get("pdf_servicos", [])
        doc_servicos = context.get("doc_servicos", [])
        doc_qty_ratio = context.get("doc_qty_ratio", 0.0)
        stage2_threshold = context.get("stage2_threshold", 0.6)

        return (
            large_images > 0
            and not pdf_servicos
            and (not doc_servicos or doc_qty_ratio < stage2_threshold)
        )

    def execute(
        self,
        file_path: str,
        context: Dict[str, Any],
        progress_callback: ProgressCallback = None,
        cancel_check: CancelCheck = None,
    ) -> ExtractionResult:
        if not self.should_execute(context):
            return self._empty_result()

        logger.info("Cascata Etapa 2.5: Tentando OCR layout (tabela em imagem)...")

        try:
            servicos, confidence, debug = self._service.extract_servicos_from_ocr_layout(
                file_path,
                progress_callback=progress_callback,
                cancel_check=cancel_check
            )
            debug["source"] = self.name
            qty_ratio = self._service.calc_qty_ratio(servicos)
            complete_ratio = self._service.calc_complete_ratio(servicos)

            return ExtractionResult(
                servicos=servicos,
                confidence=confidence,
                debug=debug,
                qty_ratio=qty_ratio,
                complete_ratio=complete_ratio,
                source=self.name
            )

        except Exception as exc:
            logger.warning(f"Cascata: OCR layout falhou - {exc}")
            result = self._empty_result()
            result.debug = {"error": str(exc)}
            return result


class GridOCRStrategy(ExtractionStrategy):
    """Estratégia de extração usando Grid OCR (OpenCV)."""

    @property
    def name(self) -> str:
        return "grid_ocr"

    def should_execute(self, context: Dict[str, Any]) -> bool:
        """Executa se tem imagens grandes e OCR layout não teve resultados suficientes."""
        large_images = context.get("large_images", 0)
        best_ocr_count = context.get("best_ocr_count", 0)
        min_items = context.get("min_items_for_confidence", 3)

        return large_images > 0 and best_ocr_count < min_items

    def execute(
        self,
        file_path: str,
        context: Dict[str, Any],
        progress_callback: ProgressCallback = None,
        cancel_check: CancelCheck = None,
    ) -> ExtractionResult:
        if not self.should_execute(context):
            return self._empty_result()

        logger.info("Cascata Etapa 2.6: Tentando Grid OCR (OpenCV)...")

        try:
            servicos, confidence, debug = self._service.extract_servicos_from_grid_ocr(
                file_path,
                progress_callback=progress_callback,
                cancel_check=cancel_check
            )
            debug["source"] = self.name
            qty_ratio = self._service.calc_qty_ratio(servicos)
            complete_ratio = self._service.calc_complete_ratio(servicos)

            return ExtractionResult(
                servicos=servicos,
                confidence=confidence,
                debug=debug,
                qty_ratio=qty_ratio,
                complete_ratio=complete_ratio,
                source=self.name
            )

        except Exception as exc:
            logger.warning(f"Cascata: Grid OCR falhou - {exc}")
            result = self._empty_result()
            result.debug = {"error": str(exc)}
            return result


class DocumentAIFallbackStrategy(ExtractionStrategy):
    """Estratégia de Document AI como fallback após OCR."""

    @property
    def name(self) -> str:
        return "document_ai_fallback"

    def should_execute(self, context: Dict[str, Any]) -> bool:
        """Executa se OCR teve poucos resultados e Document AI está em modo fallback."""
        document_ai_ready = context.get("document_ai_ready", False)
        fallback_only = context.get("document_ai_fallback_only", False)
        ocr_count = context.get("best_ocr_count", 0)
        current_count = context.get("current_count", 0)
        min_items = context.get("min_items_for_confidence", 3)
        grid_low_quality = context.get("grid_low_quality", False)

        return (
            document_ai_ready
            and fallback_only
            and (
                (ocr_count < min_items and current_count < min_items)
                or grid_low_quality
            )
        )

    def execute(
        self,
        file_path: str,
        context: Dict[str, Any],
        progress_callback: ProgressCallback = None,
        cancel_check: CancelCheck = None,
    ) -> ExtractionResult:
        if not self.should_execute(context):
            return self._empty_result()

        grid_low_quality = context.get("grid_low_quality", False)
        if grid_low_quality:
            logger.info("Cascata Etapa 2.7: Grid OCR com baixa qualidade, tentando Document AI...")
        else:
            logger.info("Cascata Etapa 2.7: Tentando Document AI como fallback...")

        try:
            allow_itemless = context.get("allow_itemless", False)
            text_useful = context.get("text_useful", True)

            servicos, confidence, debug = self._service.extract_servicos_from_document_ai(
                file_path,
                allow_itemless=allow_itemless
            )
            debug["source"] = "document_ai"
            debug["fallback_only"] = True
            if grid_low_quality:
                debug["fallback_reason"] = "grid_ocr_low_quality"

            # Retry se page limit excedido
            if (
                debug.get("error")
                and "PAGE_LIMIT_EXCEEDED" in str(debug.get("error"))
                and not text_useful
            ):
                logger.info("Cascata: Document AI page limit, tentando imageless...")
                servicos, confidence, debug = self._service.extract_servicos_from_document_ai(
                    file_path,
                    use_native_pdf_parsing=True,
                    allow_itemless=allow_itemless
                )
                debug["source"] = "document_ai"
                debug["retry_reason"] = "page_limit_exceeded"

            # Merge com pdfplumber se disponível
            pdf_servicos = context.get("pdf_servicos", [])
            if servicos and pdf_servicos:
                servicos, merge_debug = self._service._merge_table_sources(servicos, pdf_servicos)
                debug["merge"] = merge_debug

            qty_ratio = self._service.calc_qty_ratio(servicos)
            complete_ratio = self._service.calc_complete_ratio(servicos)

            return ExtractionResult(
                servicos=servicos,
                confidence=confidence,
                debug=debug,
                qty_ratio=qty_ratio,
                complete_ratio=complete_ratio,
                source="document_ai"
            )

        except Exception as e:
            logger.warning(f"Cascata: Document AI fallback falhou - {e}")
            result = self._empty_result()
            result.debug = {"error": str(e)}
            return result
