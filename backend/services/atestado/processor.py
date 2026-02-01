"""
Processador de atestados de capacidade técnica.
Extrai serviços, quantidades e dados de documentos de atestado.
"""
from typing import Dict, Any, List, Optional
from pathlib import Path

from logging_config import get_logger

logger = get_logger('services.atestado.processor')


class AtestadoProcessor:
    """
    Processador de atestados de capacidade técnica.

    Extrai serviços usando abordagem híbrida:
    - Tabelas (pdfplumber, Document AI)
    - OCR com layout
    - Vision AI (GPT-4o)
    - Texto bruto
    """

    def __init__(self, document_processor=None):
        """
        Inicializa o processador.

        Args:
            document_processor: Referência ao DocumentProcessor para helpers
        """
        self._doc_processor = document_processor

    def set_document_processor(self, document_processor):
        """Define referência ao DocumentProcessor."""
        self._doc_processor = document_processor

    def process(
        self,
        file_path: str,
        use_vision: bool = True,
        progress_callback=None,
        cancel_check=None
    ) -> Dict[str, Any]:
        """
        Processa um atestado de capacidade técnica.

        Args:
            file_path: Caminho para o arquivo (PDF ou imagem)
            use_vision: Se True, usa Vision AI quando disponível
            progress_callback: Callback para progresso
            cancel_check: Função para verificar cancelamento

        Returns:
            Dicionário com dados extraídos do atestado
        """
        from ..pdf_extraction_service import pdf_extraction_service
        from ..table_extraction_service import table_extraction_service
        from ..document_analysis_service import document_analysis_service
        from ..text_extraction_service import text_extraction_service
        from ..ai_provider import ai_provider
        from ..aditivo_processor import prefix_aditivo_items
        from ..description_fixer import fix_descriptions
        from ..processing_helpers import clear_item_code_quantities
        from config import AtestadoProcessingConfig as APC

        # Preferir pipeline completo quando disponível (inclui adição de itens do texto)
        if self._doc_processor:
            return self._doc_processor.process_atestado(
                file_path,
                use_vision=use_vision,
                progress_callback=progress_callback,
                cancel_check=cancel_check
            )

        pdf_extraction_service._check_cancel(cancel_check)
        file_ext = Path(file_path).suffix.lower()

        # 1. Extrair texto do documento
        doc_analysis = None
        images = None
        if file_ext == ".pdf":
            doc_analysis = table_extraction_service.analyze_document_type(file_path)
            if isinstance(doc_analysis, dict) and doc_analysis.get("is_scanned"):
                images = pdf_extraction_service.pdf_to_images(
                    file_path,
                    dpi=300,
                    progress_callback=progress_callback,
                    cancel_check=cancel_check,
                    stage="ocr"
                )
                texto = pdf_extraction_service.ocr_image_list(
                    images, progress_callback, cancel_check
                )
            else:
                texto = text_extraction_service.extract_text_from_file(
                    file_path, file_ext, progress_callback, cancel_check
                )
        else:
            texto = text_extraction_service.extract_text_from_file(
                file_path, file_ext, progress_callback, cancel_check
            )

        # 2. Extrair serviços de tabelas (cascata)
        servicos_table, table_confidence, table_debug, table_attempts = \
            table_extraction_service.extract_cascade(
                file_path,
                file_ext,
                progress_callback,
                cancel_check,
                doc_analysis=doc_analysis
            )

        # Stage 1.5: backfill de quantidades via texto para PDFs digitais
        text_backfill = {}
        if (
            servicos_table
            and texto
            and isinstance(doc_analysis, dict)
            and not doc_analysis.get("is_scanned")
            and not doc_analysis.get("has_image_tables")
        ):
            cleared = self._clear_item_code_quantities(servicos_table)
            filled = self._backfill_quantities_from_text(servicos_table, texto)
            if cleared or filled:
                text_backfill = {"cleared": cleared, "filled": filled}
        if text_backfill and isinstance(table_debug, dict):
            table_debug["text_backfill"] = text_backfill

        # Validação final da tabela
        min_qty_ratio = APC.STAGE3_QTY_THRESHOLD
        qty_ratio = table_extraction_service.calc_qty_ratio(servicos_table)
        cascade_stage = table_debug.get("cascade_stage", 0) if isinstance(table_debug, dict) else 0
        table_used = bool(servicos_table and qty_ratio >= min_qty_ratio)

        if servicos_table and not table_used:
            logger.info(
                f"Tabela descartada: {len(servicos_table)} itens, "
                f"qty_ratio={qty_ratio:.2%} < {min_qty_ratio:.0%}"
            )

        if isinstance(table_debug, dict):
            table_debug.setdefault("attempts", table_attempts)

        # 3. Extrair dados com IA (se configurada)
        use_ai = ai_provider.is_configured
        force_pagewise = False
        filter_invalid_codes = False
        vision_provider = None
        pagewise_min_items = None
        if isinstance(doc_analysis, dict):
            has_image_tables = bool(doc_analysis.get("has_image_tables"))
            dominant_pages_count = int(doc_analysis.get("dominant_image_pages") or 0)
            if has_image_tables or dominant_pages_count >= APC.DOMINANT_IMAGE_MIN_PAGES:
                filter_invalid_codes = True
                pagewise_min_items = 30
                if "gemini" in ai_provider.available_providers:
                    vision_provider = "gemini"
                elif "openai" in ai_provider.available_providers:
                    vision_provider = "openai"

        if use_ai:
            dados, primary_source, ai_debug_info = document_analysis_service.extract_dados_with_ai(
                file_path,
                file_ext,
                texto,
                use_vision,
                servicos_table,
                table_used,
                progress_callback,
                cancel_check,
                images=images,
                doc_analysis=doc_analysis,
                force_pagewise=force_pagewise,
                vision_provider=vision_provider,
                pagewise_min_items=pagewise_min_items,
                filter_invalid_codes=filter_invalid_codes
            )

            dados["_debug"] = {
                **ai_debug_info,
                "table": {
                    "count": len(servicos_table),
                    "confidence": table_confidence,
                    "qty_ratio": qty_ratio,
                    "used": table_used,
                    "cascade_stage": cascade_stage,
                    "debug": table_debug
                },
                "primary_source": primary_source,
                "provider_config": ai_provider.current_provider,
            }
            if (force_pagewise or vision_provider or pagewise_min_items) and isinstance(dados.get("_debug"), dict):
                dados["_debug"]["vision_policy"] = {
                    "force_pagewise": force_pagewise,
                    "provider": vision_provider,
                    "pagewise_min_items": pagewise_min_items,
                }
        else:
            # IA não configurada - usar apenas tabela
            servicos_table_filtered = prefix_aditivo_items(
                list(servicos_table), texto
            ) if table_used else []

            dados = {
                "descricao_servico": None,
                "quantidade": None,
                "unidade": None,
                "contratante": None,
                "data_emissao": None,
                "servicos": servicos_table_filtered
            }
            dados["_debug"] = {
                "table": {
                    "count": len(servicos_table),
                    "confidence": table_confidence,
                    "qty_ratio": qty_ratio,
                    "used": table_used,
                    "cascade_stage": cascade_stage,
                    "debug": table_debug
                },
                "primary_source": "table" if table_used else "none",
                "ai_configured": False,
            }

        # 4. Pós-processamento
        pdf_extraction_service._notify_progress(
            progress_callback, 0, 0, "final", "Finalizando processamento"
        )
        pdf_extraction_service._check_cancel(cancel_check)

        # Enriquecer serviços com texto
        servicos_raw = dados.get("servicos") or []
        if texto and self._doc_processor:
            servicos_raw = self._enrich_servicos_from_text(
                servicos_raw,
                texto,
                doc_analysis,
                table_used,
                table_debug,
                table_confidence,
                qty_ratio,
                dados
            )

        # Pós-processamento final
        if self._doc_processor:
            servicos = self._doc_processor._postprocess_servicos(
                servicos_raw,
                use_ai,
                table_used,
                servicos_table,
                texto,
                strict_item_gate=False,
                skip_no_code_dedupe=False
            )
        else:
            servicos = servicos_raw

        # Corrigir descrições usando texto original como fonte da verdade
        if servicos and texto:
            logger.info(f"[FIXER] Aplicando fix_descriptions a {len(servicos)} servicos, texto={len(texto)} chars")
            servicos = fix_descriptions(servicos, texto)
            fixed_count = sum(1 for s in servicos if s.get('_desc_source') == 'texto_original')
            logger.info(f"[FIXER] Correções aplicadas: {fixed_count}")

        dados["servicos"] = servicos
        dados["texto_extraido"] = texto
        return dados

    def _extract_texto_from_file(
        self,
        file_path: str,
        file_ext: str,
        progress_callback=None,
        cancel_check=None
    ) -> str:
        """Extrai texto do arquivo."""
        from ..text_extraction_service import text_extraction_service
        return text_extraction_service.extract_text_from_file(
            file_path, file_ext, progress_callback, cancel_check
        )

    def _clear_item_code_quantities(self, servicos: list) -> int:
        """Limpa quantidades que parecem ser códigos de item."""
        from ..processing_helpers import clear_item_code_quantities
        return clear_item_code_quantities(servicos)

    def _backfill_quantities_from_text(self, servicos: list, texto: str) -> int:
        """Preenche quantidades faltantes do texto."""
        if self._doc_processor:
            return self._doc_processor._backfill_quantities_from_text(servicos, texto)
        return 0

    def _enrich_servicos_from_text(
        self,
        servicos_raw: list,
        texto: str,
        doc_analysis: Optional[dict],
        table_used: bool,
        table_debug: Optional[dict],
        table_confidence: float,
        qty_ratio: float,
        dados: dict
    ) -> list:
        """Enriquece serviços com dados extraídos do texto."""
        from ..text_extraction_service import text_extraction_service
        from config import AtestadoProcessingConfig as APC

        if not self._doc_processor:
            return servicos_raw

        dp = self._doc_processor

        # Determinar se text_section está habilitado
        text_section_enabled = True
        text_section_reason = None
        if table_used and isinstance(table_debug, dict):
            source = (table_debug.get("source") or "").lower()
            stats = table_debug.get("stats") or {}
            duplicate_ratio = stats.get("duplicate_ratio", 0.0)
            if (
                source == "pdfplumber"
                and table_confidence >= APC.TEXT_SECTION_TABLE_CONFIDENCE_MIN
                and qty_ratio >= APC.TEXT_SECTION_QTY_RATIO_MIN
                and duplicate_ratio <= APC.TEXT_SECTION_DUP_RATIO_MAX
            ):
                text_section_enabled = False
                text_section_reason = f"strong_table source={source}"

        # Processar texto se não for escaneado e tabela foi usada
        if (
            isinstance(doc_analysis, dict)
            and not doc_analysis.get("is_scanned")
            and table_used
        ):
            # Dividir texto por páginas (chamar text_extraction_service diretamente)
            page_segments = text_extraction_service.split_text_by_pages(texto)
            page_planilha_map, _ = text_extraction_service.build_page_planilha_map(page_segments)

            if page_planilha_map:
                text_extraction_service.apply_page_planilha_map(servicos_raw, page_planilha_map)

            # Extrair itens do texto
            text_items: List[Dict[str, Any]] = []
            section_items: List[Dict[str, Any]] = []
            if page_planilha_map:
                for page_num, page_text in page_segments:
                    planilha_id = page_planilha_map.get(page_num, 0)
                    if not planilha_id:
                        continue
                    page_text_items = text_extraction_service.extract_items_from_text_lines(
                        page_text
                    )
                    page_section_items = (
                        dp._extract_items_from_text_section(page_text)
                        if text_section_enabled else []
                    )
                    for item in page_text_items + page_section_items:
                        item["_page"] = page_num
                        item["_planilha_id"] = planilha_id
                    text_items.extend(page_text_items)
                    section_items.extend(page_section_items)
            else:
                text_items = text_extraction_service.extract_items_from_text_lines(texto)
                section_items = (
                    dp._extract_items_from_text_section(texto)
                    if text_section_enabled else []
                )

            # Combinar candidatos
            text_candidates = section_items + text_items

            # Aplicar descrições do texto
            if text_candidates:
                text_map = dp._build_text_item_map(text_candidates)
                dp._apply_text_descriptions(servicos_raw, text_map)

        # Atualizar debug info
        if isinstance(dados.get("_debug"), dict):
            dados["_debug"]["text_section"] = {
                "enabled": text_section_enabled,
                "reason": text_section_reason,
            }

        return servicos_raw


# Singleton (será configurado depois com document_processor)
atestado_processor = AtestadoProcessor()
