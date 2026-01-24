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

logger = get_logger('services.table_extraction.cascade')

ProgressCallback = Optional[Callable[[str, int], None]]
CancelCheck = Optional[Callable[[], bool]]


class CascadeStrategy:
    """
    Estrategia de extracao em cascata.

    Tenta multiplas fontes de extracao em sequencia ate encontrar
    um resultado satisfatorio com base em thresholds de qualidade.
    """

    def __init__(self, service: Any):
        """
        Args:
            service: Instancia do TableExtractionService para delegar extracoes
        """
        self._service = service

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
        """Extrai de arquivo PDF usando cascata de metodos."""
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

        # ETAPA 1: pdfplumber
        pdf_result = self._try_pdfplumber(
            file_path=file_path,
            is_scanned=is_scanned,
            table_attempts=table_attempts,
        )
        pdf_servicos, pdf_conf, pdf_debug = pdf_result[:3]
        pdf_qty_ratio, pdf_complete_ratio = pdf_result[3], pdf_result[4]

        # Sucesso se qty_ratio >= threshold E complete_ratio > 0
        pdf_ok = pdf_servicos and pdf_qty_ratio >= stage1_threshold
        if pdf_ok and pdf_complete_ratio > 0:
            logger.info(
                f"Cascata: pdfplumber SUCESSO - {len(pdf_servicos)} servicos, "
                f"qty_ratio={pdf_qty_ratio:.0%}, complete_ratio={pdf_complete_ratio:.0%}"
            )
            table_debug.update(pdf_debug)
            table_debug["cascade_stage"] = 1
            table_debug["cascade_reason"] = "pdfplumber_success"
            self._add_cascade_summary(table_debug, table_attempts)
            return pdf_servicos, pdf_conf, table_debug, table_attempts

        logger.info(
            f"Cascata: pdfplumber insuficiente - {len(pdf_servicos)} servicos, "
            f"qty_ratio={pdf_qty_ratio:.0%}, complete_ratio={pdf_complete_ratio:.0%}"
        )

        # ETAPA 2: Document AI
        doc_servicos: List[Dict] = []
        doc_conf = 0.0
        doc_debug: Dict[str, Any] = {}
        doc_qty_ratio = 0.0
        doc_complete_ratio = 0.0

        if document_ai_ready and not document_ai_fallback_only:
            doc_servicos, doc_conf, doc_debug, doc_qty_ratio, doc_complete_ratio = self._try_document_ai(
                file_path=file_path,
                allow_itemless=allow_itemless_doc,
                text_useful=text_useful,
                pdf_servicos=pdf_servicos,
                stage2_threshold=stage2_threshold,
                table_attempts=table_attempts,
            )

            if doc_servicos and doc_qty_ratio >= stage2_threshold:
                logger.info(
                    f"Cascata: Document AI SUCESSO - {len(doc_servicos)} servicos, "
                    f"qty_ratio={doc_qty_ratio:.0%}, complete_ratio={doc_complete_ratio:.0%}"
                )
                table_debug.update(doc_debug)
                table_debug["cascade_stage"] = 2
                table_debug["cascade_reason"] = "document_ai_success"
                self._add_cascade_summary(table_debug, table_attempts)
                return doc_servicos, doc_conf, table_debug, table_attempts

            logger.info(
                f"Cascata: Document AI insuficiente - {len(doc_servicos)} servicos, "
                f"qty_ratio={doc_qty_ratio:.0%}, complete_ratio={doc_complete_ratio:.0%}"
            )

            # Usar Document AI se tiver melhor qualidade
            if doc_qty_ratio > pdf_qty_ratio or doc_complete_ratio > pdf_complete_ratio:
                servicos_table = doc_servicos
                table_confidence = doc_conf
                table_debug.update(doc_debug)
                table_debug["cascade_stage"] = 2
                table_debug["cascade_reason"] = "document_ai_better"

        elif document_ai_ready and document_ai_fallback_only:
            logger.info("Cascata: Document AI aguardando fallback pos-OCR")
            table_attempts["document_ai"] = {"skipped": True, "reason": "fallback_only"}
        else:
            logger.info("Cascata: Document AI nao disponivel")

        # ETAPA 2.5: OCR layout
        best_ocr_servicos, best_ocr_conf, best_ocr_debug, best_ocr_qty_ratio, best_ocr_complete_ratio, best_ocr_label = \
            self._try_ocr_methods(
                file_path=file_path,
                large_images=large_images,
                pdf_servicos=pdf_servicos,
                doc_servicos=doc_servicos,
                doc_qty_ratio=doc_qty_ratio,
                stage2_threshold=stage2_threshold,
                min_items_for_confidence=min_items_for_confidence,
                progress_callback=progress_callback,
                cancel_check=cancel_check,
                table_attempts=table_attempts,
            )

        # Usar o melhor OCR se superar Document AI
        if (
            best_ocr_servicos
            and (best_ocr_qty_ratio > doc_qty_ratio or best_ocr_complete_ratio > doc_complete_ratio)
        ):
            servicos_table = best_ocr_servicos
            table_confidence = best_ocr_conf
            table_debug.update(best_ocr_debug)
            table_debug["cascade_stage"] = 3
            table_debug["cascade_reason"] = f"{best_ocr_label}_better"

        # ETAPA 2.7: Document AI fallback
        if document_ai_ready and document_ai_fallback_only:
            servicos_table, table_confidence, table_debug = self._try_document_ai_fallback(
                file_path=file_path,
                allow_itemless=allow_itemless_doc,
                text_useful=text_useful,
                pdf_servicos=pdf_servicos,
                best_ocr_servicos=best_ocr_servicos,
                best_ocr_qty_ratio=best_ocr_qty_ratio,
                best_ocr_complete_ratio=best_ocr_complete_ratio,
                stage2_threshold=stage2_threshold,
                min_items_for_confidence=min_items_for_confidence,
                servicos_table=servicos_table,
                table_confidence=table_confidence,
                table_debug=table_debug,
                table_attempts=table_attempts,
            )

        # FALLBACK
        if not servicos_table and pdf_servicos:
            servicos_table = pdf_servicos
            table_confidence = pdf_conf
            table_debug.update(pdf_debug)
            table_debug["cascade_stage"] = 1
            table_debug["cascade_reason"] = "pdfplumber_fallback"
            logger.info(f"Cascata: Usando pdfplumber como fallback ({len(pdf_servicos)} servicos)")

        self._add_cascade_summary(table_debug, table_attempts)
        return servicos_table, table_confidence, table_debug, table_attempts

    def _try_pdfplumber(
        self,
        file_path: str,
        is_scanned: bool,
        table_attempts: Dict[str, Any],
    ) -> Tuple[List[Dict], float, Dict, float, float]:
        """Tenta extracao com pdfplumber."""
        if is_scanned:
            logger.info("Cascata: pulando pdfplumber (documento escaneado)")
            table_attempts["pdfplumber"] = {"skipped": True, "reason": "scanned"}
            return [], 0.0, {}, 0.0, 0.0

        logger.info("Cascata Etapa 1: Tentando pdfplumber...")
        pdf_servicos, pdf_conf, pdf_debug = self._service.extract_servicos_from_tables(file_path)
        pdf_debug["source"] = "pdfplumber"
        pdf_qty_ratio = self._service.calc_qty_ratio(pdf_servicos)
        pdf_complete_ratio = self._service.calc_complete_ratio(pdf_servicos)
        table_attempts["pdfplumber"] = {
            "count": len(pdf_servicos),
            "confidence": pdf_conf,
            "qty_ratio": pdf_qty_ratio,
            "complete_ratio": pdf_complete_ratio,
            "debug": self._service._summarize_table_debug(pdf_debug)
        }
        return pdf_servicos, pdf_conf, pdf_debug, pdf_qty_ratio, pdf_complete_ratio

    def _try_document_ai(
        self,
        file_path: str,
        allow_itemless: bool,
        text_useful: bool,
        pdf_servicos: List[Dict],
        stage2_threshold: float,
        table_attempts: Dict[str, Any],
    ) -> Tuple[List[Dict], float, Dict, float, float]:
        """Tenta extracao com Document AI."""
        logger.info("Cascata Etapa 2: Tentando Document AI...")
        try:
            doc_servicos, doc_conf, doc_debug = self._service.extract_servicos_from_document_ai(
                file_path,
                allow_itemless=allow_itemless
            )
            doc_debug["source"] = "document_ai"

            if (
                doc_debug.get("error")
                and "PAGE_LIMIT_EXCEEDED" in str(doc_debug.get("error"))
                and not text_useful
            ):
                logger.info("Cascata: Document AI page limit, tentando imageless...")
                doc_servicos, doc_conf, doc_debug = self._service.extract_servicos_from_document_ai(
                    file_path,
                    use_native_pdf_parsing=True,
                    allow_itemless=allow_itemless
                )
                doc_debug["source"] = "document_ai"
                doc_debug["retry_reason"] = "page_limit_exceeded"

            if doc_servicos and pdf_servicos:
                doc_servicos, merge_debug = self._service._merge_table_sources(doc_servicos, pdf_servicos)
                doc_debug["merge"] = merge_debug

            doc_qty_ratio = self._service.calc_qty_ratio(doc_servicos)
            doc_complete_ratio = self._service.calc_complete_ratio(doc_servicos)
            table_attempts["document_ai"] = {
                "count": len(doc_servicos),
                "confidence": doc_conf,
                "qty_ratio": doc_qty_ratio,
                "complete_ratio": doc_complete_ratio,
                "debug": self._service._summarize_table_debug(doc_debug)
            }
            return doc_servicos, doc_conf, doc_debug, doc_qty_ratio, doc_complete_ratio

        except Exception as e:
            logger.warning(f"Cascata: Document AI falhou - {e}")
            table_attempts["document_ai"] = {"error": str(e)}
            return [], 0.0, {}, 0.0, 0.0

    def _try_ocr_methods(
        self,
        file_path: str,
        large_images: int,
        pdf_servicos: List[Dict],
        doc_servicos: List[Dict],
        doc_qty_ratio: float,
        stage2_threshold: float,
        min_items_for_confidence: int,
        progress_callback: ProgressCallback,
        cancel_check: CancelCheck,
        table_attempts: Dict[str, Any],
    ) -> Tuple[List[Dict], float, Dict, float, float, str]:
        """Tenta extracao com OCR layout e Grid OCR."""
        ocr_servicos: List[Dict] = []
        ocr_conf = 0.0
        ocr_debug: Dict[str, Any] = {}
        ocr_qty_ratio = 0.0
        ocr_complete_ratio = 0.0

        should_try_ocr = (
            large_images > 0
            and not pdf_servicos
            and (not doc_servicos or doc_qty_ratio < stage2_threshold)
        )

        if should_try_ocr:
            logger.info("Cascata Etapa 2.5: Tentando OCR layout (tabela em imagem)...")
            try:
                ocr_servicos, ocr_conf, ocr_debug = self._service.extract_servicos_from_ocr_layout(
                    file_path,
                    progress_callback=progress_callback,
                    cancel_check=cancel_check
                )
                ocr_debug["source"] = "ocr_layout"
                ocr_qty_ratio = self._service.calc_qty_ratio(ocr_servicos)
                ocr_complete_ratio = self._service.calc_complete_ratio(ocr_servicos)
                table_attempts["ocr_layout"] = {
                    "count": len(ocr_servicos),
                    "confidence": ocr_conf,
                    "qty_ratio": ocr_qty_ratio,
                    "complete_ratio": ocr_complete_ratio,
                    "debug": self._service._summarize_table_debug(ocr_debug)
                }
            except Exception as exc:
                logger.warning(f"Cascata: OCR layout falhou - {exc}")
                table_attempts["ocr_layout"] = {"error": str(exc)}

        best_ocr_servicos = ocr_servicos
        best_ocr_conf = ocr_conf
        best_ocr_debug = ocr_debug
        best_ocr_qty_ratio = ocr_qty_ratio
        best_ocr_complete_ratio = ocr_complete_ratio
        best_ocr_label = "ocr_layout"

        # ETAPA 2.6: Grid OCR (OpenCV)
        grid_servicos: List[Dict] = []
        grid_conf = 0.0
        grid_debug: Dict[str, Any] = {}
        grid_qty_ratio = 0.0
        grid_complete_ratio = 0.0
        best_ocr_count = len(best_ocr_servicos) if best_ocr_servicos else 0

        should_try_grid = (
            large_images > 0
            and best_ocr_count < min_items_for_confidence
        )

        if should_try_grid:
            logger.info("Cascata Etapa 2.6: Tentando Grid OCR (OpenCV)...")
            try:
                grid_servicos, grid_conf, grid_debug = self._service.extract_servicos_from_grid_ocr(
                    file_path,
                    progress_callback=progress_callback,
                    cancel_check=cancel_check
                )
                grid_debug["source"] = "grid_ocr"
                grid_qty_ratio = self._service.calc_qty_ratio(grid_servicos)
                grid_complete_ratio = self._service.calc_complete_ratio(grid_servicos)
                table_attempts["grid_ocr"] = {
                    "count": len(grid_servicos),
                    "confidence": grid_conf,
                    "qty_ratio": grid_qty_ratio,
                    "complete_ratio": grid_complete_ratio,
                    "debug": self._service._summarize_table_debug(grid_debug)
                }

                if grid_servicos and (
                    grid_qty_ratio > best_ocr_qty_ratio
                    or grid_complete_ratio > best_ocr_complete_ratio
                    or len(grid_servicos) >= len(best_ocr_servicos) + 2
                ):
                    best_ocr_servicos = grid_servicos
                    best_ocr_conf = grid_conf
                    best_ocr_debug = grid_debug
                    best_ocr_qty_ratio = grid_qty_ratio
                    best_ocr_complete_ratio = grid_complete_ratio
                    best_ocr_label = "grid_ocr"

            except Exception as exc:
                logger.warning(f"Cascata: Grid OCR falhou - {exc}")
                table_attempts["grid_ocr"] = {"error": str(exc)}

        return best_ocr_servicos, best_ocr_conf, best_ocr_debug, best_ocr_qty_ratio, best_ocr_complete_ratio, best_ocr_label

    def _try_document_ai_fallback(
        self,
        file_path: str,
        allow_itemless: bool,
        text_useful: bool,
        pdf_servicos: List[Dict],
        best_ocr_servicos: List[Dict],
        best_ocr_qty_ratio: float,
        best_ocr_complete_ratio: float,
        stage2_threshold: float,
        min_items_for_confidence: int,
        servicos_table: List[Dict],
        table_confidence: float,
        table_debug: Dict[str, Any],
        table_attempts: Dict[str, Any],
    ) -> Tuple[List[Dict], float, Dict]:
        """Tenta Document AI como fallback apos OCR."""
        ocr_count = len(best_ocr_servicos) if best_ocr_servicos else 0
        current_count = len(servicos_table) if servicos_table else 0

        # Verificar qualidade do grid
        grid_debug_raw = table_attempts.get("grid_ocr", {})
        grid_servicos = grid_debug_raw.get("count", 0) if isinstance(grid_debug_raw, dict) else 0
        _raw_stats = grid_debug_raw.get("debug", {}).get("stats") if isinstance(grid_debug_raw, dict) else None
        grid_stats: Dict[str, Any] = _raw_stats if isinstance(_raw_stats, dict) else {}
        grid_dup_ratio = float(grid_stats.get("duplicate_ratio") or 0.0)
        grid_has_items = int(grid_stats.get("with_item") or 0) > 0
        grid_low_quality = bool(grid_servicos) and (not grid_has_items) and grid_dup_ratio >= 0.25

        if (ocr_count < min_items_for_confidence and current_count < min_items_for_confidence) or grid_low_quality:
            if grid_low_quality:
                logger.info("Cascata Etapa 2.7: Grid OCR com baixa qualidade, tentando Document AI...")
            else:
                logger.info("Cascata Etapa 2.7: Tentando Document AI como fallback...")

            try:
                doc_servicos, doc_conf, doc_debug = self._service.extract_servicos_from_document_ai(
                    file_path,
                    allow_itemless=allow_itemless
                )
                doc_debug["source"] = "document_ai"
                doc_debug["fallback_only"] = True
                if grid_low_quality:
                    doc_debug["fallback_reason"] = "grid_ocr_low_quality"

                if (
                    doc_debug.get("error")
                    and "PAGE_LIMIT_EXCEEDED" in str(doc_debug.get("error"))
                    and not text_useful
                ):
                    logger.info("Cascata: Document AI page limit, tentando imageless...")
                    doc_servicos, doc_conf, doc_debug = self._service.extract_servicos_from_document_ai(
                        file_path,
                        use_native_pdf_parsing=True,
                        allow_itemless=allow_itemless
                    )
                    doc_debug["source"] = "document_ai"
                    doc_debug["retry_reason"] = "page_limit_exceeded"

                if doc_servicos and pdf_servicos:
                    doc_servicos, merge_debug = self._service._merge_table_sources(doc_servicos, pdf_servicos)
                    doc_debug["merge"] = merge_debug

                doc_qty_ratio = self._service.calc_qty_ratio(doc_servicos)
                doc_complete_ratio = self._service.calc_complete_ratio(doc_servicos)
                table_attempts["document_ai"] = {
                    "count": len(doc_servicos),
                    "confidence": doc_conf,
                    "qty_ratio": doc_qty_ratio,
                    "complete_ratio": doc_complete_ratio,
                    "debug": self._service._summarize_table_debug(doc_debug)
                }

                if doc_servicos and doc_qty_ratio >= stage2_threshold:
                    table_debug.update(doc_debug)
                    table_debug["cascade_stage"] = 2
                    table_debug["cascade_reason"] = "document_ai_fallback"
                    return doc_servicos, doc_conf, table_debug
                elif doc_servicos and (
                    doc_qty_ratio > best_ocr_qty_ratio or doc_complete_ratio > best_ocr_complete_ratio
                ):
                    table_debug.update(doc_debug)
                    table_debug["cascade_stage"] = 2
                    table_debug["cascade_reason"] = "document_ai_fallback_better"
                    return doc_servicos, doc_conf, table_debug

            except Exception as e:
                logger.warning(f"Cascata: Document AI fallback falhou - {e}")
                table_attempts["document_ai"] = {"error": str(e)}

        return servicos_table, table_confidence, table_debug

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
