"""
Serviço de Análise de Documentos com IA.

Responsável por:
- Extração de dados usando Vision AI e OCR
- Seleção de fonte primária (vision vs ocr)
- Extração página por página com OpenAI
- Merge de resultados de múltiplas fontes
"""

from typing import Dict, Any, List, Optional, Callable

from .ai_provider import ai_provider
from .pdf_extraction_service import pdf_extraction_service
from .aditivo_processor import prefix_aditivo_items
from .extraction import (
    filter_summary_rows,
    compute_servicos_stats,
    compute_quality_score,
    merge_servicos_prefer_primary,
)
from exceptions import OpenAIError, GeminiError
from config import AtestadoProcessingConfig as APC

from logging_config import get_logger
logger = get_logger('services.document_analysis_service')


# Type aliases para callbacks
ProgressCallback = Optional[Callable[[int, int, str, str], None]]
CancelCheck = Optional[Callable[[], bool]]


class DocumentAnalysisService:
    """
    Serviço para análise de documentos usando IA.

    Fornece métodos para:
    - Extrair dados usando Vision AI e/ou análise de texto OCR
    - Selecionar fonte primária baseado em qualidade
    - Extrair serviços página por página
    - Combinar resultados de múltiplas fontes
    """

    def select_primary_source(
        self,
        vision_stats: dict,
        ocr_stats: dict,
        vision_score: float,
        ocr_score: float
    ) -> str:
        """
        Seleciona a fonte primária entre Vision e OCR.

        Args:
            vision_stats: Estatísticas dos serviços extraídos por Vision
            ocr_stats: Estatísticas dos serviços extraídos por OCR
            vision_score: Score de qualidade da extração Vision
            ocr_score: Score de qualidade da extração OCR

        Returns:
            "vision" ou "ocr" indicando a fonte primária
        """
        margin = APC.SCORE_MARGIN
        if vision_score >= ocr_score + margin:
            return "vision"
        if ocr_score >= vision_score + margin:
            return "ocr"

        def quality_tuple(stats: dict):
            total = max(1, stats.get("total", 0))
            return (
                stats.get("with_item", 0) / total,
                stats.get("with_qty", 0) / total,
                stats.get("with_unit", 0) / total,
                stats.get("total", 0)
            )

        vision_tuple = quality_tuple(vision_stats)
        ocr_tuple = quality_tuple(ocr_stats)
        if vision_tuple > ocr_tuple:
            return "vision"
        if ocr_tuple > vision_tuple:
            return "ocr"
        return "vision"

    def extract_servicos_pagewise(
        self,
        images: List[bytes],
        progress_callback: ProgressCallback = None,
        cancel_check: CancelCheck = None
    ) -> List[dict]:
        """
        Extrai serviços página por página usando Vision AI.

        Usa Gemini Vision (gratuito) como padrão, com fallback para OpenAI.
        Útil quando a extração completa falha ou para documentos com muitas páginas.

        Args:
            images: Lista de imagens de páginas em bytes
            progress_callback: Callback para progresso
            cancel_check: Função para verificar cancelamento

        Returns:
            Lista de serviços extraídos
        """
        servicos: List[Dict[str, Any]] = []
        total_pages = len(images)
        if total_pages == 0:
            return servicos

        table_pages = pdf_extraction_service.detect_table_pages(images)
        page_indexes = table_pages if table_pages else list(range(total_pages))
        total = len(page_indexes)

        logger.info(f"Pagewise: processando {total} paginas de {total_pages} - indices: {page_indexes}")

        for idx, page_index in enumerate(page_indexes):
            pdf_extraction_service._check_cancel(cancel_check)
            pdf_extraction_service._notify_progress(
                progress_callback, idx + 1, total, "ia",
                f"Analisando pagina {page_index + 1} de {total_pages} com IA"
            )
            image_bytes = images[page_index]
            cropped = pdf_extraction_service.crop_region(image_bytes, 0.05, 0.15, 0.95, 0.92)
            try:
                # Usa provider padrão (Gemini gratuito quando disponível, com fallback para OpenAI)
                result = ai_provider.extract_atestado_from_images([cropped])
                page_servicos = result.get("servicos", []) if isinstance(result, dict) else []
                logger.info(f"Pagewise: pagina {page_index + 1} extraiu {len(page_servicos)} servicos")
                for s in page_servicos:
                    logger.debug(f"  Item: {s.get('item', '?')}: {s.get('descricao', '')[:50]}")
                servicos.extend(page_servicos)
            except (OpenAIError, GeminiError, ValueError, KeyError) as exc:
                logger.warning(f"Erro na IA por pagina {page_index + 1}: {exc}")

        logger.info(f"Pagewise: total extraido = {len(servicos)} servicos")
        return servicos

    def extract_dados_with_ai(
        self,
        file_path: str,
        file_ext: str,
        texto: str,
        use_vision: bool,
        servicos_table: list,
        table_used: bool,
        progress_callback: ProgressCallback = None,
        cancel_check: CancelCheck = None,
        images: Optional[List[bytes]] = None
    ) -> tuple[dict, str, dict]:
        """
        Extrai dados do atestado usando IA (Vision e/ou OCR text).

        Args:
            file_path: Caminho para o arquivo
            file_ext: Extensão do arquivo
            texto: Texto extraído do documento
            use_vision: Se deve usar análise de imagem
            servicos_table: Serviços extraídos de tabelas
            table_used: Se tabela foi usada com alta confiança
            progress_callback: Callback para progresso
            cancel_check: Função para verificar cancelamento

        Returns:
            Tupla (dados, primary_source, debug_info)
        """
        images = list(images) if images else []
        vision_reprocessed = False
        vision_score = 0.0
        ocr_score = 0.0
        vision_stats = {"total": 0, "with_item": 0, "with_unit": 0, "with_qty": 0, "duplicate_ratio": 0.0}
        ocr_stats = {"total": 0, "with_item": 0, "with_unit": 0, "with_qty": 0, "duplicate_ratio": 0.0}
        dados_vision = None
        dados_ocr = None
        dados_meta = None
        primary_source = None

        llm_fallback_only = APC.LLM_FALLBACK_ONLY
        use_ai_for_services = not llm_fallback_only or not table_used

        # Método 1: OCR + análise de texto
        pdf_extraction_service._notify_progress(progress_callback, 0, 0, "ia", "Extraindo metadados com IA")
        pdf_extraction_service._check_cancel(cancel_check)
        dados_meta = ai_provider.extract_atestado_metadata(texto)

        if use_ai_for_services:
            pdf_extraction_service._notify_progress(progress_callback, 0, 0, "ia", "Analisando texto com IA")
            pdf_extraction_service._check_cancel(cancel_check)
            dados_ocr = ai_provider.extract_atestado_info(texto)

        # Método 2: Vision (GPT-4o ou Gemini)
        # OTIMIZAÇÃO: Só chamar Vision se precisamos da IA para serviços
        if use_vision and use_ai_for_services:
            try:
                vision_images = images
                if not vision_images:
                    if file_ext == ".pdf":
                        vision_images = pdf_extraction_service.pdf_to_images(
                            file_path,
                            dpi=300,
                            progress_callback=progress_callback,
                            cancel_check=cancel_check,
                            stage="vision"
                        )
                    else:
                        with open(file_path, "rb") as f:
                            pdf_extraction_service._check_cancel(cancel_check)
                            pdf_extraction_service._notify_progress(progress_callback, 1, 1, "vision", "Carregando imagem")
                            vision_images = [f.read()]

                if vision_images:
                    pdf_extraction_service._notify_progress(progress_callback, 0, 0, "ia", "Analisando imagens com IA")
                    pdf_extraction_service._check_cancel(cancel_check)
                    dados_vision = ai_provider.extract_atestado_from_images(vision_images)
                    images = vision_images
            except (OpenAIError, ValueError, KeyError) as e:
                logger.warning(f"Erro no Vision: {e}")
                dados_vision = None
        elif use_vision and not use_ai_for_services:
            logger.info("Vision pulado: tabela extraiu serviços com sucesso (economia de custo)")

        servicos_vision = filter_summary_rows(dados_vision.get("servicos", []) if dados_vision else [])
        servicos_ocr = filter_summary_rows(dados_ocr.get("servicos", []) if dados_ocr else [])
        vision_stats = compute_servicos_stats(servicos_vision)
        ocr_stats = compute_servicos_stats(servicos_ocr)
        vision_score = compute_quality_score(vision_stats)
        ocr_score = compute_quality_score(ocr_stats)

        # Fallback por página quando a qualidade estiver baixa
        # Usa Gemini (gratuito) ou OpenAI como fallback
        pagewise_enabled = APC.PAGEWISE_VISION_ENABLED
        has_vision_provider = bool(ai_provider.available_providers)
        logger.info(
            f"Pagewise check: enabled={pagewise_enabled}, use_vision={use_vision}, "
            f"images={len(images) if images else 0}, providers={ai_provider.available_providers}"
        )
        if pagewise_enabled and use_vision and images and has_vision_provider:
            quality_threshold = APC.VISION_QUALITY_THRESHOLD
            min_pages = APC.PAGEWISE_MIN_PAGES
            min_items = APC.PAGEWISE_MIN_ITEMS
            logger.info(
                f"Pagewise condition: vision_score={vision_score:.2f} < {quality_threshold} OR "
                f"(pages={len(images)} >= {min_pages} AND items={vision_stats.get('total', 0)} < {min_items})"
            )
            if vision_score < quality_threshold or (len(images) >= min_pages and vision_stats.get("total", 0) < min_items):
                page_servicos = self.extract_servicos_pagewise(images, progress_callback, cancel_check)
                if page_servicos:
                    if dados_vision is None:
                        meta = dados_meta or {}
                        def pick_meta(field: str) -> Any:
                            value = meta.get(field)
                            if value is None or value == "":
                                return dados_ocr.get(field) if dados_ocr else None
                            return value
                        dados_vision = {
                            "descricao_servico": pick_meta("descricao_servico"),
                            "contratante": pick_meta("contratante"),
                            "data_emissao": pick_meta("data_emissao"),
                            "quantidade": pick_meta("quantidade"),
                            "unidade": pick_meta("unidade"),
                        }
                    dados_vision["servicos"] = page_servicos
                    servicos_vision = filter_summary_rows(page_servicos)
                    vision_stats = compute_servicos_stats(servicos_vision)
                    vision_score = compute_quality_score(vision_stats)
                    vision_reprocessed = True
                    ocr_score = compute_quality_score(ocr_stats)

        # Combinar resultados
        pdf_extraction_service._notify_progress(progress_callback, 0, 0, "merge", "Consolidando dados extraidos")
        pdf_extraction_service._check_cancel(cancel_check)

        if dados_vision and dados_ocr:
            primary_source = self.select_primary_source(vision_stats, ocr_stats, vision_score, ocr_score)
            if primary_source == "vision":
                primary = dados_vision
                secondary = dados_ocr
                primary_servicos = servicos_vision
                secondary_servicos = servicos_ocr
            else:
                primary = dados_ocr
                secondary = dados_vision
                primary_servicos = servicos_ocr
                secondary_servicos = servicos_vision

            dados = {
                "descricao_servico": primary.get("descricao_servico") or secondary.get("descricao_servico"),
                "contratante": primary.get("contratante") or secondary.get("contratante"),
                "data_emissao": primary.get("data_emissao") or secondary.get("data_emissao"),
                "quantidade": primary.get("quantidade") or secondary.get("quantidade"),
                "unidade": primary.get("unidade") or secondary.get("unidade"),
            }

            # Prefixar itens do aditivo em cada fonte ANTES do merge
            primary_servicos = prefix_aditivo_items(primary_servicos, texto)
            secondary_servicos = prefix_aditivo_items(secondary_servicos, texto)
            dados["servicos"] = merge_servicos_prefer_primary(primary_servicos, secondary_servicos)

        else:
            if dados_vision:
                primary_source = "vision"
                dados = dados_vision
            elif dados_ocr:
                primary_source = "ocr"
                dados = dados_ocr
            else:
                primary_source = "none"
                dados = {
                    "descricao_servico": None,
                    "quantidade": None,
                    "unidade": None,
                    "contratante": None,
                    "data_emissao": None,
                    "servicos": []
                }
            servicos_list = dados.get("servicos")
            if servicos_list:
                dados["servicos"] = prefix_aditivo_items(servicos_list, texto)

        if isinstance(dados_meta, dict):
            for field in ("descricao_servico", "contratante", "data_emissao", "quantidade", "unidade"):
                value = dados_meta.get(field)
                if value is not None and value != "":
                    dados[field] = value

        # Se tabela foi usada com alta confiança e LLM é apenas fallback, usar tabela
        if table_used and not use_ai_for_services:
            servicos_table_filtered = prefix_aditivo_items(list(servicos_table), texto)

            # Sempre usar tabela quando LLM_FALLBACK_ONLY=True e tabela disponível
            dados["servicos"] = servicos_table_filtered
            primary_source = "table_services"

        debug_info = {
            "vision": {"count": len(servicos_vision), "score": vision_score, "reprocessed": vision_reprocessed},
            "ocr": {"count": len(servicos_ocr), "score": ocr_score},
            "vision_stats": vision_stats,
            "ocr_stats": ocr_stats,
            "page_count": len(images),
            "use_ai_for_services": use_ai_for_services,
        }

        return dados, primary_source, debug_info


# Instância singleton para uso global
document_analysis_service = DocumentAnalysisService()
