"""
Pipeline de processamento de atestados.

Extrai e orquestra as fases do processamento de atestados de capacidade técnica.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING

from logging_config import get_logger
from config import AtestadoProcessingConfig as APC

if TYPE_CHECKING:
    from services.protocols import DocumentProcessorProtocol

logger = get_logger('services.atestado.pipeline')

# Type aliases - compatível com pdf_extraction_service
ProgressCallback = Optional[Callable[[int, int, str, str], None]]
CancelCheck = Optional[Callable[[], bool]]


class AtestadoPipeline:
    """
    Pipeline para processamento de atestados de capacidade técnica.

    Combina GPT-4o Vision (para precisão) com OCR+texto (para completude).
    """

    def __init__(
        self,
        processor: DocumentProcessorProtocol,
        file_path: str,
        use_vision: bool = True,
        progress_callback: ProgressCallback = None,
        cancel_check: CancelCheck = None
    ):
        """
        Inicializa o pipeline.

        Args:
            processor: Instância de DocumentProcessor para acesso a métodos auxiliares
            file_path: Caminho para o arquivo (PDF ou imagem)
            use_vision: Se True, usa abordagem híbrida Vision+OCR; se False, apenas OCR+texto
            progress_callback: Callback para reportar progresso
            cancel_check: Função para verificar cancelamento
        """
        self._processor = processor
        self._file_path = file_path
        self._file_ext = Path(file_path).suffix.lower()
        self._use_vision = use_vision
        self._progress_callback = progress_callback
        self._cancel_check = cancel_check

        # Estado compartilhado entre fases
        self._texto: Optional[str] = None
        self._doc_analysis: Optional[dict] = None
        self._images: Optional[List[bytes]] = None
        self._servicos_table: List[Dict] = []
        self._table_confidence: float = 0.0
        self._table_debug: Dict[str, Any] = {}
        self._table_attempts: Dict[str, Any] = {}
        self._table_used: bool = False
        self._qty_ratio: float = 0.0
        self._cascade_stage: int = 0
        self._dados: Dict[str, Any] = {}
        self._servicos_raw: List[Dict] = []
        self._text_items: List[Dict] = []
        self._itemless_mode: bool = False
        self._text_section_enabled: bool = True
        self._text_section_reason: Optional[str] = None
        self._strict_item_gate: bool = False

    def run(self) -> Dict[str, Any]:
        """
        Executa o pipeline completo de processamento.

        Returns:
            Dicionário com dados extraídos do atestado
        """
        logger.debug(f"[PIPELINE] Iniciando processamento: {self._file_path}")

        logger.debug("[PIPELINE] Fase 1: Extração de texto")
        self._phase1_extract_text()
        logger.debug(f"[PIPELINE] Fase 1 completa: {len(self._texto or '')} chars extraídos")

        logger.debug("[PIPELINE] Fase 2: Extração de tabelas")
        self._phase2_extract_tables()
        logger.debug(f"[PIPELINE] Fase 2 completa: {len(self._servicos_table)} itens, table_used={self._table_used}")

        logger.debug("[PIPELINE] Fase 3: Análise com IA")
        self._phase3_ai_analysis()
        servicos_count = len(self._dados.get('servicos') or [])
        logger.debug(f"[PIPELINE] Fase 3 completa: {servicos_count} serviços extraídos")

        logger.debug("[PIPELINE] Fase 4: Enriquecimento via texto")
        self._phase4_text_enrichment()
        logger.debug(f"[PIPELINE] Fase 4 completa: {len(self._servicos_raw)} serviços após enriquecimento")

        logger.debug("[PIPELINE] Fase 5: Pós-processamento")
        self._phase5_postprocess()
        final_count = len(self._dados.get('servicos') or [])
        logger.debug(f"[PIPELINE] Fase 5 completa: {final_count} serviços após filtros")

        logger.debug("[PIPELINE] Fase 6: Finalização")
        self._phase6_finalize()
        logger.debug(f"[PIPELINE] Pipeline completo: {len(self._dados.get('servicos') or [])} serviços finais")

        return self._dados

    def _phase1_extract_text(self) -> None:
        """Fase 1: Extração de texto do documento."""
        from ..pdf_extraction_service import pdf_extraction_service
        from ..table_extraction_service import table_extraction_service
        from ..text_extraction_service import text_extraction_service

        pdf_extraction_service._check_cancel(self._cancel_check)

        if self._file_ext == ".pdf":
            self._doc_analysis = table_extraction_service.analyze_document_type(self._file_path)
            if isinstance(self._doc_analysis, dict) and self._doc_analysis.get("is_scanned"):
                self._images = pdf_extraction_service.pdf_to_images(
                    self._file_path,
                    dpi=300,
                    progress_callback=self._progress_callback,
                    cancel_check=self._cancel_check,
                    stage="ocr"
                )
                self._texto = pdf_extraction_service.ocr_image_list(
                    self._images, self._progress_callback, self._cancel_check
                )
            else:
                self._texto = text_extraction_service.extract_text_from_file(
                    self._file_path, self._file_ext, self._progress_callback, self._cancel_check
                )
        else:
            self._texto = text_extraction_service.extract_text_from_file(
                self._file_path, self._file_ext, self._progress_callback, self._cancel_check
            )

    def _phase2_extract_tables(self) -> None:
        """Fase 2: Extração de serviços de tabelas."""
        from ..table_extraction_service import table_extraction_service
        from ..processors.text_processor import text_processor  # noqa: F401
        from ..extraction.table_processor import parse_item_tuple
        from ..ai_provider import ai_provider

        # Extrair serviços via cascata
        if (
            isinstance(self._doc_analysis, dict)
            and self._doc_analysis.get("has_image_tables")
            and ai_provider.is_configured
            and self._use_vision
        ):
            # Skip table extraction for image-based tables
            self._servicos_table = []
            self._table_confidence = 0.0
            self._table_debug = {"skipped": "has_image_tables"}
            self._table_attempts = {}
        else:
            self._servicos_table, self._table_confidence, self._table_debug, self._table_attempts = \
                table_extraction_service.extract_cascade(
                    self._file_path,
                    self._file_ext,
                    self._progress_callback,
                    self._cancel_check,
                    doc_analysis=self._doc_analysis
                )

        # Backfill de quantidades via texto para PDFs digitais
        text_backfill = {}
        if (
            self._servicos_table
            and self._texto
            and isinstance(self._doc_analysis, dict)
            and not self._doc_analysis.get("is_scanned")
            and not self._doc_analysis.get("has_image_tables")
        ):
            from ..extraction import clear_item_code_quantities
            cleared = clear_item_code_quantities(self._servicos_table)
            filled = text_processor.backfill_quantities_from_text(self._servicos_table, self._texto)
            if cleared or filled:
                text_backfill = {"cleared": cleared, "filled": filled}
        if text_backfill and isinstance(self._table_debug, dict):
            self._table_debug["text_backfill"] = text_backfill

        # Validar tabela
        min_qty_ratio = APC.STAGE3_QTY_THRESHOLD
        self._qty_ratio = table_extraction_service.calc_qty_ratio(self._servicos_table)
        self._cascade_stage = self._table_debug.get("cascade_stage", 0) if isinstance(self._table_debug, dict) else 0
        self._table_used = bool(self._servicos_table and self._qty_ratio >= min_qty_ratio)

        if self._servicos_table and not self._table_used:
            logger.info(
                f"Tabela descartada na validação final: {len(self._servicos_table)} itens, "
                f"qty_ratio={self._qty_ratio:.2%} < {min_qty_ratio:.0%}, cascade_stage={self._cascade_stage}"
            )

        # Quality gate: descartar tabela ruim quando há indícios de tabela em imagem
        if self._servicos_table and isinstance(self._doc_analysis, dict):
            has_image_tables = bool(self._doc_analysis.get("has_image_tables"))
            dominant_pages = int(self._doc_analysis.get("dominant_image_pages") or 0)
            if has_image_tables or dominant_pages > 0:
                metrics = table_extraction_service.calc_quality_metrics(self._servicos_table)
                total = metrics.get("total") or 0
                invalid_code_count = 0
                big_component_count = 0
                for s in self._servicos_table:
                    item = str(s.get("item") or "")
                    item_tuple = parse_item_tuple(item)
                    if not item_tuple:
                        invalid_code_count += 1
                        continue
                    if any(part > 50 for part in item_tuple):
                        big_component_count += 1

                invalid_code_ratio = (invalid_code_count / total) if total else 0.0
                big_component_ratio = (big_component_count / total) if total else 0.0

                reasons = []
                if total >= APC.TABLE_QUALITY_MIN_ITEMS:
                    if metrics.get("unit_ratio", 0.0) < APC.TABLE_MIN_UNIT_RATIO:
                        reasons.append("unit_ratio")
                    if metrics.get("item_ratio", 0.0) < APC.TABLE_MIN_ITEM_RATIO:
                        reasons.append("item_ratio")
                    if invalid_code_ratio >= APC.TABLE_BAD_INVALID_CODE_RATIO:
                        reasons.append("invalid_code_ratio")
                    if big_component_ratio >= APC.TABLE_BAD_BIG_COMPONENT_RATIO:
                        reasons.append("big_component_ratio")

                if reasons:
                    self._table_used = False
                    if isinstance(self._table_debug, dict):
                        self._table_debug["quality_gate"] = {
                            "triggered": True,
                            "reasons": reasons,
                            "metrics": metrics,
                            "invalid_code_ratio": invalid_code_ratio,
                            "big_component_ratio": big_component_ratio,
                            "total": total
                        }
                    logger.info(
                        "[TABLE] Tabela descartada por baixa qualidade: "
                        f"reasons={reasons}, total={total}, "
                        f"invalid_code_ratio={invalid_code_ratio:.0%}, "
                        f"big_component_ratio={big_component_ratio:.0%}, "
                        f"unit_ratio={metrics.get('unit_ratio', 0.0):.0%}"
                    )

        if isinstance(self._table_debug, dict):
            self._table_debug.setdefault("attempts", self._table_attempts)

    def _phase3_ai_analysis(self) -> None:
        """Fase 3: Análise com IA/Vision."""
        from ..ai_provider import ai_provider
        from ..document_analysis_service import document_analysis_service
        from ..aditivo_processor import prefix_aditivo_items
        from ..table_extraction_service import table_extraction_service

        use_ai = ai_provider.is_configured
        vision_page_indexes: List[int] = []
        force_pagewise = False
        filter_invalid_codes = False
        vision_provider = None
        pagewise_min_items = None
        if isinstance(self._doc_analysis, dict):
            has_image_tables = bool(self._doc_analysis.get("has_image_tables"))
            dominant_pages_count = int(self._doc_analysis.get("dominant_image_pages") or 0)
            if has_image_tables or dominant_pages_count >= APC.DOMINANT_IMAGE_MIN_PAGES:
                filter_invalid_codes = True
                pagewise_min_items = 30
                if "gemini" in ai_provider.available_providers:
                    vision_provider = "gemini"
                elif "openai" in ai_provider.available_providers:
                    vision_provider = "openai"

        # Se há páginas com imagem dominante, renderizar apenas essas páginas para Vision
        if (
            use_ai
            and self._use_vision
            and not self._table_used
            and not self._images
            and self._file_ext == ".pdf"
            and isinstance(self._doc_analysis, dict)
        ):
            dominant_pages = self._doc_analysis.get("dominant_image_page_indexes") or []
            if dominant_pages:
                vision_images = []
                for page_index in dominant_pages:
                    image_bytes = table_extraction_service._render_pdf_page(
                        self._file_path,
                        page_index,
                        APC.OCR_LAYOUT_DPI
                    )
                    if not image_bytes:
                        continue
                    cropped = table_extraction_service._crop_page_image(
                        self._file_path,
                        self._file_ext,
                        page_index,
                        image_bytes
                    )
                    vision_images.append(cropped)
                if vision_images:
                    self._images = vision_images
                    vision_page_indexes = list(dominant_pages)

        if use_ai:
            self._dados, primary_source, ai_debug_info = document_analysis_service.extract_dados_with_ai(
                self._file_path,
                self._file_ext,
                self._texto or "",
                self._use_vision,
                self._servicos_table,
                self._table_used,
                self._progress_callback,
                self._cancel_check,
                images=self._images,
                doc_analysis=self._doc_analysis,
                force_pagewise=force_pagewise,
                vision_provider=vision_provider,
                pagewise_min_items=pagewise_min_items,
                filter_invalid_codes=filter_invalid_codes
            )

            self._dados["_debug"] = {
                **ai_debug_info,
                "table": {
                    "count": len(self._servicos_table),
                    "confidence": self._table_confidence,
                    "qty_ratio": self._qty_ratio,
                    "used": self._table_used,
                    "cascade_stage": self._cascade_stage,
                    "debug": self._table_debug
                },
                "primary_source": primary_source,
                "provider_config": ai_provider.current_provider,
            }
            if vision_page_indexes:
                self._dados["_debug"]["vision_pages"] = vision_page_indexes
            if force_pagewise or vision_provider or pagewise_min_items:
                self._dados["_debug"]["vision_policy"] = {
                    "force_pagewise": force_pagewise,
                    "provider": vision_provider,
                    "pagewise_min_items": pagewise_min_items,
                }
        else:
            # IA não configurada - usar apenas tabela
            servicos_table_filtered = prefix_aditivo_items(list(self._servicos_table), self._texto or "") if self._table_used else []

            self._dados = {
                "descricao_servico": None,
                "quantidade": None,
                "unidade": None,
                "contratante": None,
                "data_emissao": None,
                "servicos": servicos_table_filtered
            }
            self._dados["_debug"] = {
                "table": {
                    "count": len(self._servicos_table),
                    "confidence": self._table_confidence,
                    "qty_ratio": self._qty_ratio,
                    "used": self._table_used,
                    "cascade_stage": self._cascade_stage,
                    "debug": self._table_debug
                },
                "primary_source": "table" if self._table_used else "none",
                "ai_configured": False,
            }

    def _phase4_text_enrichment(self) -> None:
        """Fase 4: Enriquecimento via texto."""
        from ..pdf_extraction_service import pdf_extraction_service

        pdf_extraction_service._notify_progress(self._progress_callback, 0, 0, "final", "Finalizando processamento")
        pdf_extraction_service._check_cancel(self._cancel_check)

        self._servicos_raw = self._dados.get("servicos") or []
        self._text_items = []

        self._check_text_section_gate()

        can_process_text = (
            self._texto
            and isinstance(self._doc_analysis, dict)
            and not self._doc_analysis.get("is_scanned")
            and self._table_used
        )
        if can_process_text:
            self._enrich_from_text()

        self._update_text_section_debug()

    def _check_text_section_gate(self) -> None:
        """Verifica se text_section deve ser desabilitado por tabela forte."""
        if not (self._table_used and isinstance(self._table_debug, dict)):
            return

        source = (self._table_debug.get("source") or "").lower()
        stats = self._table_debug.get("stats") or {}
        duplicate_ratio = stats.get("duplicate_ratio", 0.0)

        if (
            source == "pdfplumber"
            and self._table_confidence >= APC.TEXT_SECTION_TABLE_CONFIDENCE_MIN
            and self._qty_ratio >= APC.TEXT_SECTION_QTY_RATIO_MIN
            and duplicate_ratio <= APC.TEXT_SECTION_DUP_RATIO_MAX
        ):
            self._text_section_enabled = False
            self._text_section_reason = (
                "strong_table "
                f"source={source} qty_ratio={self._qty_ratio:.2f} "
                f"confidence={self._table_confidence:.2f} duplicate_ratio={duplicate_ratio:.2f}"
            )
            logger.info(f"[TEXTO] text_section desativado: {self._text_section_reason}")

    def _enrich_from_text(self) -> None:
        """Executa o enriquecimento completo via texto nativo do PDF."""
        from ..text_extraction_service import text_extraction_service
        from ..processors.text_processor import text_processor
        from ..processors.item_code_refiner import item_code_refiner
        from ..extraction import parse_item_tuple

        page_segments = text_extraction_service.split_text_by_pages(self._texto or "")
        page_planilha_map, page_planilha_audit = text_extraction_service.build_page_planilha_map(page_segments)

        # Reatribuir planilha por página
        if page_planilha_map:
            remapped = text_extraction_service.apply_page_planilha_map(self._servicos_raw, page_planilha_map)
            if remapped:
                logger.info(f"[TEXTO] Planilha reatribuida por pagina: {remapped} itens")
            if isinstance(self._dados.get("_debug"), dict):
                self._dados["_debug"]["page_planilha"] = {
                    "map": page_planilha_map,
                    "audit": page_planilha_audit
                }

        # Extrair itens do texto
        section_items = self._extract_text_items(page_segments, page_planilha_map, text_processor)

        # Refinar códigos de item
        text_codes = text_processor.extract_item_codes_from_text_lines(self._texto or "")
        updated = item_code_refiner.refine(self._servicos_raw, self._text_items, text_codes)
        if updated:
            logger.info(f"[TEXTO] Codigos refinados do texto: {updated}")

        # Combinar candidatos e enriquecer
        text_candidates = section_items + self._text_items
        if text_candidates:
            self._apply_restart_prefix_mapping(text_candidates)
            self._apply_text_enrichment(text_candidates)
            self._merge_text_candidates(text_candidates)

        # Verificar modo itemless
        self._check_itemless_mode(text_processor, parse_item_tuple)

    def _extract_text_items(
        self,
        page_segments: list,
        page_planilha_map: Optional[Dict],
        text_processor: Any
    ) -> List[Dict]:
        """Extrai itens de texto por página ou do texto completo."""
        from ..processing_helpers import split_restart_prefix

        section_items: List[Dict] = []

        if page_planilha_map:
            for page_num, page_text in page_segments:
                planilha_id = page_planilha_map.get(page_num, 0)
                if not planilha_id:
                    continue
                page_text_items = text_processor.extract_items_from_text_lines(page_text)
                page_section_items = (
                    text_processor.extract_items_from_text_section(page_text) if self._text_section_enabled else []
                )
                for item in page_text_items + page_section_items:
                    prefix, core = split_restart_prefix(item.get("item"))
                    if prefix:
                        item["item"] = core
                        item.pop("_item_prefix", None)
                    item["_page"] = page_num
                    item["_planilha_id"] = planilha_id
                self._text_items.extend(page_text_items)
                section_items.extend(page_section_items)
        else:
            self._text_items = text_processor.extract_items_from_text_lines(self._texto)
            section_items = text_processor.extract_items_from_text_section(self._texto) if self._text_section_enabled else []

        return section_items

    def _apply_restart_prefix_mapping(self, text_candidates: List[Dict]) -> None:
        """Mapeia prefixos de reinício nos candidatos de texto."""
        from ..processing_helpers import (
            split_restart_prefix,
            normalize_item_code as helpers_normalize_item_code,
        )
        from ..extraction import normalize_unit, parse_quantity

        prefix_map, unique_prefix_by_code = self._processor._build_restart_prefix_maps(self._servicos_raw)
        if not (prefix_map or unique_prefix_by_code):
            return

        for item in text_candidates:
            prefix, core = split_restart_prefix(item.get("item"))
            if prefix:
                continue
            code = helpers_normalize_item_code(core)
            if not code:
                continue
            unit = normalize_unit(item.get("unidade") or "")
            qty = parse_quantity(item.get("quantidade"))
            mapped = prefix_map.get((code, unit, qty)) or unique_prefix_by_code.get(code)
            if mapped:
                item["item"] = f"{mapped}-{code}"

    def _apply_text_enrichment(self, text_candidates: List[Dict]) -> None:
        """Aplica descrições de texto aos serviços existentes."""
        text_map = self._processor._build_text_item_map(text_candidates)
        enriched = self._processor._apply_text_descriptions(self._servicos_raw, text_map)
        if enriched:
            logger.info(f"[TEXTO] Descricoes enriquecidas pelo texto: {enriched}")

    def _merge_text_candidates(self, text_candidates: List[Dict]) -> None:
        """Adiciona/atualiza serviços com itens extraídos do texto."""
        from ..processing_helpers import item_key as helpers_item_key

        existing_index: Dict[tuple, dict] = {}
        existing_keys = set()
        for servico in self._servicos_raw:
            key = helpers_item_key(servico)
            if key:
                existing_keys.add(key)
                existing_index[key] = servico

        added = 0
        replaced = 0
        for item in text_candidates:
            key = helpers_item_key(item)
            if not key:
                continue
            existing = existing_index.get(key)
            if existing:
                if self._processor._should_replace_desc(existing.get("descricao") or "", item.get("descricao") or ""):
                    existing["descricao"] = (item.get("descricao") or "").strip()
                    existing["_desc_from_text"] = True
                    replaced += 1
                continue
            self._servicos_raw.append(item)
            existing_keys.add(key)
            existing_index[key] = item
            added += 1

        if added:
            logger.info(f"[TEXTO] Itens adicionados do texto: {added}")
        if replaced:
            logger.info(f"[TEXTO] Itens atualizados pelo texto: {replaced}")

    def _check_itemless_mode(self, text_processor: Any, parse_item_tuple: Any) -> None:
        """Verifica e aplica modo itemless se códigos estruturados são insuficientes."""
        from ..extraction import normalize_unit, normalize_description, parse_quantity

        with_code = [s for s in self._servicos_raw if s.get("item")]
        if not with_code:
            return

        structured = [
            parse_item_tuple(str(s.get("item")))
            for s in with_code
        ]
        structured = [t for t in structured if t and len(t) >= 2]
        structured_ratio = len(structured) / len(with_code)

        if structured_ratio >= 0.4:
            return

        self._itemless_mode = True
        no_code_items = text_processor.extract_items_without_codes_from_text(self._texto)
        if not no_code_items:
            return

        if len(no_code_items) >= len(self._servicos_raw):
            self._servicos_raw = list(no_code_items)
            logger.info(f"[TEXTO] Itens sem codigo substituindo tabela: {len(self._servicos_raw)}")
            return

        # Adicionar itens sem código que não existem
        existing_keys = set()
        for existing in self._servicos_raw:
            desc_key = normalize_description(existing.get("descricao") or "")[:80]
            unit_key = normalize_unit(existing.get("unidade") or "")
            qty_key = parse_quantity(existing.get("quantidade"))
            existing_keys.add((desc_key, unit_key, qty_key))

        added_no_code = 0
        for item in no_code_items:
            desc_key = normalize_description(item.get("descricao") or "")[:80]
            unit_key = normalize_unit(item.get("unidade") or "")
            qty_key = parse_quantity(item.get("quantidade"))
            key = (desc_key, unit_key, qty_key)
            if key in existing_keys:
                continue
            existing_keys.add(key)
            if key:
                self._servicos_raw.append(item)
                added_no_code += 1

        if added_no_code:
            logger.info(f"[TEXTO] Itens sem codigo adicionados do texto: {added_no_code}")

    def _update_text_section_debug(self) -> None:
        """Atualiza informações de debug da seção de texto."""
        if isinstance(self._dados.get("_debug"), dict):
            self._dados["_debug"]["text_section"] = {
                "enabled": self._text_section_enabled,
                "reason": self._text_section_reason,
                "max_desc_len": APC.TEXT_SECTION_MAX_DESC_LEN,
                "table_confidence_min": APC.TEXT_SECTION_TABLE_CONFIDENCE_MIN,
                "qty_ratio_min": APC.TEXT_SECTION_QTY_RATIO_MIN,
                "dup_ratio_max": APC.TEXT_SECTION_DUP_RATIO_MAX
            }

    def _phase5_postprocess(self) -> None:
        """Fase 5: Pós-processamento dos serviços."""
        from ..ai_provider import ai_provider
        from ..processors.text_processor import text_processor
        from ..processing_helpers import count_item_codes_in_text as helpers_count_item_codes_in_text
        from ..extraction import parse_quantity, parse_item_tuple

        # Limpar quantidades baseadas em código
        from ..extraction import clear_item_code_quantities
        cleared = clear_item_code_quantities(self._servicos_raw)
        if self._texto:
            needs_qty = any(parse_quantity(s.get("quantidade")) in (None, 0) for s in self._servicos_raw)
            if cleared or needs_qty:
                text_processor.backfill_quantities_from_text(self._servicos_raw, self._texto)

        # Recuperar descrições
        self._servicos_raw = text_processor.recover_descriptions_from_text(self._servicos_raw, self._texto or "")

        # Determinar strict_item_gate
        text_item_count = helpers_count_item_codes_in_text(self._texto or "")
        self._strict_item_gate = bool(self._texto) and isinstance(self._doc_analysis, dict) and not self._doc_analysis.get("is_scanned") and text_item_count >= 5

        if self._strict_item_gate and isinstance(self._doc_analysis, dict):
            if self._doc_analysis.get("has_image_tables") or int(self._doc_analysis.get("dominant_image_pages") or 0) > 0:
                logger.info("[FILTRO] strict_item_gate desativado: tabela em imagem")
                self._strict_item_gate = False

        if self._strict_item_gate and self._table_used and self._servicos_raw:
            with_code = [s for s in self._servicos_raw if s.get("item")]
            if with_code:
                structured = [
                    parse_item_tuple(str(s.get("item")))
                    for s in with_code
                ]
                structured = [t for t in structured if t and len(t) >= 2]
                structured_ratio = len(structured) / len(with_code)
                if structured_ratio < 0.4:
                    logger.info(
                        f"[FILTRO] strict_item_gate desativado: baixa proporcao de codigos estruturados ({structured_ratio:.0%})"
                    )
                    self._strict_item_gate = False

        if self._strict_item_gate and isinstance(self._table_debug, dict):
            table_source = (self._table_debug.get("source") or "").lower()
            if table_source and table_source != "pdfplumber":
                logger.info(
                    f"[FILTRO] strict_item_gate desativado: tabela veio de {table_source}"
                )
                self._strict_item_gate = False

        # Aplicar filtros finais
        use_ai = ai_provider.is_configured
        servicos = self._processor._postprocess_servicos(
            self._servicos_raw,
            use_ai,
            self._table_used,
            self._servicos_table,
            self._texto or "",
            self._strict_item_gate,
            skip_no_code_dedupe=self._itemless_mode
        )
        self._dados["servicos"] = servicos

    def _phase6_finalize(self) -> None:
        """Fase 6: Finalização e correção de descrições."""
        from ..description_fixer import fix_descriptions

        servicos = self._dados.get("servicos") or []

        # Corrigir descrições usando texto original como fonte da verdade
        if servicos and self._texto:
            logger.info(f"[FIXER] Aplicando fix_descriptions a {len(servicos)} servicos")
            servicos = fix_descriptions(servicos, self._texto)
            fixed_count = sum(1 for s in servicos if s.get('_desc_source') == 'texto_original')
            logger.info(f"[FIXER] Correções aplicadas: {fixed_count}")

        self._dados["servicos"] = servicos
        self._dados["texto_extraido"] = self._texto
