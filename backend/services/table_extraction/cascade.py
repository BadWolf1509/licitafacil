"""
Estrategia de extracao em cascata.

Implementa o fluxo de extracao que tenta multiplas fontes em sequencia:
1. pdfplumber (gratuito)
2. Document AI
3. OCR layout
4. Grid OCR
"""

from typing import Any, Callable, Dict, List, Optional, Tuple

from config import AtestadoProcessingConfig as APC
from logging_config import get_logger

from .extraction_strategies import (
    ExtractionResult,
    PdfPlumberStrategy,
    DocumentAIStrategy,
    OCRLayoutStrategy,
    GridOCRStrategy,
    DocumentAIFallbackStrategy,
)

logger = get_logger('services.table_extraction.cascade')

ProgressCallback = Optional[Callable[[str, int], None]]
CancelCheck = Optional[Callable[[], bool]]


class CascadeStrategy:
    """
    Estrategia de extracao em cascata.

    Tenta multiplas fontes de extracao em sequencia ate encontrar
    um resultado satisfatorio com base em thresholds de qualidade.

    Usa o Strategy Pattern para encapsular cada método de extração.
    """

    def __init__(self, service: Any):
        """
        Args:
            service: Instancia do TableExtractionService para delegar extracoes
        """
        self._service = service

        # Inicializar estratégias
        self._pdfplumber_strategy = PdfPlumberStrategy(service)
        self._document_ai_strategy = DocumentAIStrategy(service)
        self._ocr_layout_strategy = OCRLayoutStrategy(service)
        self._grid_ocr_strategy = GridOCRStrategy(service)
        self._document_ai_fallback_strategy = DocumentAIFallbackStrategy(service)

    def execute(
        self,
        file_path: str,
        file_ext: str,
        progress_callback: ProgressCallback = None,
        cancel_check: CancelCheck = None,
        doc_analysis: Optional[dict] = None
    ) -> Tuple[List[Dict], float, Dict, Dict]:
        """
        Executa extracao em cascata.

        Fluxo:
        1. pdfplumber (gratuito) - se qty_ratio >= 70%: SUCESSO
        2. Document AI (~R$0.008/pag) - se qty_ratio >= 60%: SUCESSO
        3. Fallback para melhor resultado disponivel

        Args:
            file_path: Caminho para o arquivo
            file_ext: Extensao do arquivo
            progress_callback: Callback para progresso
            cancel_check: Funcao para verificar cancelamento
            doc_analysis: Analise previa do documento (opcional)

        Returns:
            Tupla (servicos, confidence, debug, attempts)
        """
        # Importar aqui para evitar import circular
        from ..document_ai_service import document_ai_service

        servicos_table: List[Dict] = []
        table_confidence = 0.0
        table_debug: Dict[str, Any] = {}
        table_attempts: Dict[str, Any] = {}

        stage1_threshold = APC.STAGE1_QTY_THRESHOLD
        stage2_threshold = APC.STAGE2_QTY_THRESHOLD
        min_items_for_confidence = APC.MIN_ITEMS_FOR_CONFIDENCE

        document_ai_enabled = APC.DOCUMENT_AI_ENABLED
        document_ai_ready = document_ai_enabled and document_ai_service.is_configured
        document_ai_fallback_only = APC.DOCUMENT_AI_FALLBACK_ONLY

        if file_ext == ".pdf":
            return self._extract_from_pdf(
                file_path=file_path,
                doc_analysis=doc_analysis,
                progress_callback=progress_callback,
                cancel_check=cancel_check,
                stage1_threshold=stage1_threshold,
                stage2_threshold=stage2_threshold,
                min_items_for_confidence=min_items_for_confidence,
                document_ai_ready=document_ai_ready,
                document_ai_fallback_only=document_ai_fallback_only,
                table_debug=table_debug,
                table_attempts=table_attempts,
            )
        elif file_ext in [".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif"]:
            return self._extract_from_image(
                file_path=file_path,
                stage2_threshold=stage2_threshold,
                document_ai_ready=document_ai_ready,
                table_debug=table_debug,
                table_attempts=table_attempts,
            )

        # Nenhum formato reconhecido
        table_debug["cascade_summary"] = {
            "final_source": "none",
            "final_stage": 0,
            "attempts": list(table_attempts.keys())
        }
        return servicos_table, table_confidence, table_debug, table_attempts

    def _extract_from_pdf(
        self,
        file_path: str,
        doc_analysis: Optional[dict],
        progress_callback: ProgressCallback,
        cancel_check: CancelCheck,
        stage1_threshold: float,
        stage2_threshold: float,
        min_items_for_confidence: int,
        document_ai_ready: bool,
        document_ai_fallback_only: bool,
        table_debug: Dict[str, Any],
        table_attempts: Dict[str, Any],
    ) -> Tuple[List[Dict], float, Dict, Dict]:
        """Extrai de arquivo PDF usando cascata de estratégias."""
        servicos_table: List[Dict] = []
        table_confidence = 0.0

        if doc_analysis is None:
            doc_analysis = self._service.analyze_document_type(file_path)
        table_debug["doc_analysis"] = doc_analysis

        _da = doc_analysis if isinstance(doc_analysis, dict) else {}
        is_scanned = bool(_da.get("is_scanned"))
        has_image_tables = bool(_da.get("has_image_tables"))
        text_useful = (not is_scanned) and (not has_image_tables)
        large_images = int(_da.get("large_images_count") or 0)
        allow_itemless_doc = bool(is_scanned or has_image_tables)

        # Contexto compartilhado entre estratégias
        context: Dict[str, Any] = {
            "is_scanned": is_scanned,
            "text_useful": text_useful,
            "large_images": large_images,
            "allow_itemless": allow_itemless_doc,
            "document_ai_ready": document_ai_ready,
            "document_ai_fallback_only": document_ai_fallback_only,
            "stage2_threshold": stage2_threshold,
            "min_items_for_confidence": min_items_for_confidence,
        }

        # ETAPA 1: pdfplumber (usando estratégia)
        pdf_result = self._pdfplumber_strategy.execute(file_path, context)
        self._record_attempt(table_attempts, pdf_result)

        # Sucesso se qty_ratio >= threshold E complete_ratio > 0
        pdf_ok = pdf_result.servicos and pdf_result.qty_ratio >= stage1_threshold
        if pdf_ok and pdf_result.complete_ratio > 0:
            logger.info(
                f"Cascata: pdfplumber SUCESSO - {len(pdf_result.servicos)} servicos, "
                f"qty_ratio={pdf_result.qty_ratio:.0%}, complete_ratio={pdf_result.complete_ratio:.0%}"
            )
            table_debug.update(pdf_result.debug)
            table_debug["cascade_stage"] = 1
            table_debug["cascade_reason"] = "pdfplumber_success"
            self._add_cascade_summary(table_debug, table_attempts)
            return pdf_result.servicos, pdf_result.confidence, table_debug, table_attempts

        logger.info(
            f"Cascata: pdfplumber insuficiente - {len(pdf_result.servicos)} servicos, "
            f"qty_ratio={pdf_result.qty_ratio:.0%}, complete_ratio={pdf_result.complete_ratio:.0%}"
        )

        # Atualizar contexto com resultados do pdfplumber
        context["pdf_servicos"] = pdf_result.servicos

        # ETAPA 2: Document AI (usando estratégia)
        doc_result = self._document_ai_strategy.execute(file_path, context)
        if doc_result.servicos or doc_result.debug.get("error"):
            self._record_attempt(table_attempts, doc_result)

        if doc_result.servicos and doc_result.qty_ratio >= stage2_threshold:
            logger.info(
                f"Cascata: Document AI SUCESSO - {len(doc_result.servicos)} servicos, "
                f"qty_ratio={doc_result.qty_ratio:.0%}, complete_ratio={doc_result.complete_ratio:.0%}"
            )
            table_debug.update(doc_result.debug)
            table_debug["cascade_stage"] = 2
            table_debug["cascade_reason"] = "document_ai_success"
            self._add_cascade_summary(table_debug, table_attempts)
            return doc_result.servicos, doc_result.confidence, table_debug, table_attempts

        if doc_result.servicos:
            logger.info(
                f"Cascata: Document AI insuficiente - {len(doc_result.servicos)} servicos, "
                f"qty_ratio={doc_result.qty_ratio:.0%}, complete_ratio={doc_result.complete_ratio:.0%}"
            )

            # Usar Document AI se tiver melhor qualidade
            if doc_result.qty_ratio > pdf_result.qty_ratio or doc_result.complete_ratio > pdf_result.complete_ratio:
                servicos_table = doc_result.servicos
                table_confidence = doc_result.confidence
                table_debug.update(doc_result.debug)
                table_debug["cascade_stage"] = 2
                table_debug["cascade_reason"] = "document_ai_better"

        # Atualizar contexto para OCR
        context["doc_servicos"] = doc_result.servicos
        context["doc_qty_ratio"] = doc_result.qty_ratio

        # ETAPA 2.5: OCR Layout (usando estratégia)
        ocr_result = self._ocr_layout_strategy.execute(
            file_path, context, progress_callback, cancel_check
        )
        if ocr_result.servicos or ocr_result.debug.get("error"):
            self._record_attempt(table_attempts, ocr_result)

        best_ocr_result = ocr_result
        best_ocr_label = "ocr_layout"

        # ETAPA 2.6: Grid OCR (usando estratégia)
        context["best_ocr_count"] = len(ocr_result.servicos)
        grid_result = self._grid_ocr_strategy.execute(
            file_path, context, progress_callback, cancel_check
        )
        if grid_result.servicos or grid_result.debug.get("error"):
            self._record_attempt(table_attempts, grid_result)

        # Selecionar melhor resultado OCR
        if grid_result.servicos and (
            grid_result.qty_ratio > best_ocr_result.qty_ratio
            or grid_result.complete_ratio > best_ocr_result.complete_ratio
            or len(grid_result.servicos) >= len(best_ocr_result.servicos) + 2
        ):
            best_ocr_result = grid_result
            best_ocr_label = "grid_ocr"

        # Usar o melhor OCR se superar Document AI
        if (
            best_ocr_result.servicos
            and (best_ocr_result.qty_ratio > doc_result.qty_ratio or best_ocr_result.complete_ratio > doc_result.complete_ratio)
        ):
            servicos_table = best_ocr_result.servicos
            table_confidence = best_ocr_result.confidence
            table_debug.update(best_ocr_result.debug)
            table_debug["cascade_stage"] = 3
            table_debug["cascade_reason"] = f"{best_ocr_label}_better"

        # ETAPA 2.7: Document AI fallback (usando estratégia)
        context["best_ocr_count"] = len(best_ocr_result.servicos)
        context["current_count"] = len(servicos_table)
        context["grid_low_quality"] = self._check_grid_low_quality(table_attempts)

        fallback_result = self._document_ai_fallback_strategy.execute(file_path, context)
        if fallback_result.servicos or fallback_result.debug.get("error"):
            self._record_attempt(table_attempts, fallback_result, key="document_ai")

            if fallback_result.servicos and fallback_result.qty_ratio >= stage2_threshold:
                table_debug.update(fallback_result.debug)
                table_debug["cascade_stage"] = 2
                table_debug["cascade_reason"] = "document_ai_fallback"
                self._add_cascade_summary(table_debug, table_attempts)
                return fallback_result.servicos, fallback_result.confidence, table_debug, table_attempts

            if fallback_result.servicos and (
                fallback_result.qty_ratio > best_ocr_result.qty_ratio
                or fallback_result.complete_ratio > best_ocr_result.complete_ratio
            ):
                servicos_table = fallback_result.servicos
                table_confidence = fallback_result.confidence
                table_debug.update(fallback_result.debug)
                table_debug["cascade_stage"] = 2
                table_debug["cascade_reason"] = "document_ai_fallback_better"

        # FALLBACK
        if not servicos_table and pdf_result.servicos:
            servicos_table = pdf_result.servicos
            table_confidence = pdf_result.confidence
            table_debug.update(pdf_result.debug)
            table_debug["cascade_stage"] = 1
            table_debug["cascade_reason"] = "pdfplumber_fallback"
            logger.info(f"Cascata: Usando pdfplumber como fallback ({len(pdf_result.servicos)} servicos)")

        self._add_cascade_summary(table_debug, table_attempts)
        return servicos_table, table_confidence, table_debug, table_attempts

    def _record_attempt(
        self,
        table_attempts: Dict[str, Any],
        result: ExtractionResult,
        key: Optional[str] = None
    ) -> None:
        """Registra uma tentativa de extração no dict de attempts."""
        attempt_key = key or result.source
        if result.debug.get("error"):
            table_attempts[attempt_key] = {"error": str(result.debug.get("error"))}
        elif not result.servicos and not result.debug:
            table_attempts[attempt_key] = {"skipped": True, "reason": "not_applicable"}
        else:
            table_attempts[attempt_key] = {
                "count": len(result.servicos),
                "confidence": result.confidence,
                "qty_ratio": result.qty_ratio,
                "complete_ratio": result.complete_ratio,
                "debug": self._service._summarize_table_debug(result.debug)
            }

    def _check_grid_low_quality(self, table_attempts: Dict[str, Any]) -> bool:
        """Verifica se Grid OCR teve baixa qualidade."""
        grid_debug_raw = table_attempts.get("grid_ocr", {})
        if not isinstance(grid_debug_raw, dict):
            return False

        grid_servicos = grid_debug_raw.get("count", 0)
        _raw_stats = grid_debug_raw.get("debug", {}).get("stats") if isinstance(grid_debug_raw.get("debug"), dict) else None
        grid_stats: Dict[str, Any] = _raw_stats if isinstance(_raw_stats, dict) else {}
        grid_dup_ratio = float(grid_stats.get("duplicate_ratio") or 0.0)
        grid_has_items = int(grid_stats.get("with_item") or 0) > 0

        return bool(grid_servicos) and (not grid_has_items) and grid_dup_ratio >= 0.25

    def _extract_from_image(
        self,
        file_path: str,
        stage2_threshold: float,
        document_ai_ready: bool,
        table_debug: Dict[str, Any],
        table_attempts: Dict[str, Any],
    ) -> Tuple[List[Dict], float, Dict, Dict]:
        """Extrai de arquivo de imagem usando Document AI."""
        servicos_table: List[Dict] = []
        table_confidence = 0.0

        logger.info("Imagem detectada: Usando Document AI diretamente")

        if document_ai_ready:
            try:
                doc_servicos, doc_conf, doc_debug = self._service.extract_servicos_from_document_ai(
                    file_path,
                    allow_itemless=True
                )
                doc_debug["source"] = "document_ai"
                doc_qty_ratio = self._service.calc_qty_ratio(doc_servicos)
                table_attempts["document_ai"] = {
                    "count": len(doc_servicos),
                    "confidence": doc_conf,
                    "qty_ratio": doc_qty_ratio,
                    "debug": self._service._summarize_table_debug(doc_debug)
                }

                if doc_servicos and doc_qty_ratio >= stage2_threshold:
                    servicos_table = doc_servicos
                    table_confidence = doc_conf
                    table_debug.update(doc_debug)
                    table_debug["cascade_stage"] = 2
                    table_debug["cascade_reason"] = "document_ai_image"
                    logger.info(
                        f"Imagem: Document AI SUCESSO - {len(doc_servicos)} servicos, "
                        f"qty_ratio={doc_qty_ratio:.0%}"
                    )

            except Exception as e:
                logger.warning(f"Imagem: Document AI falhou - {e}")
                table_attempts["document_ai"] = {"error": str(e)}
        else:
            logger.warning("Imagem: Document AI nao disponivel")

        self._add_cascade_summary(table_debug, table_attempts)
        return servicos_table, table_confidence, table_debug, table_attempts

    def _add_cascade_summary(
        self,
        table_debug: Dict[str, Any],
        table_attempts: Dict[str, Any]
    ) -> None:
        """Adiciona resumo da cascata ao debug."""
        table_debug["cascade_summary"] = {
            "final_source": table_debug.get("source", "none"),
            "final_stage": table_debug.get("cascade_stage", 0),
            "attempts": list(table_attempts.keys())
        }
