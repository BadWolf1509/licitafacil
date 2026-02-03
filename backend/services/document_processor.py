"""
Serviço integrado de processamento de documentos.
Combina extração de PDF, OCR e análise com IA.
Suporta GPT-4o Vision para análise direta de imagens.
Inclui processamento paralelo opcional para melhor performance.
"""

from typing import Dict, Any, List, Optional, Set
import re

from .pdf_extractor import pdf_extractor  # noqa: F401
from .ocr_service import ocr_service  # noqa: F401
from .ai_provider import ai_provider  # noqa: F401
from .document_ai_service import document_ai_service  # noqa: F401
from .pdf_extraction_service import pdf_extraction_service, ProcessingCancelled  # noqa: F401 (re-export)
from .table_extraction_service import table_extraction_service  # noqa: F401
from .document_analysis_service import document_analysis_service  # noqa: F401
# Módulos extraídos para migração gradual
from .pdf_converter import pdf_converter  # noqa: F401
from .extraction import (
    # text_normalizer
    normalize_unit,
    normalize_desc_for_match,
    extract_keywords,
    description_similarity,
    # table_processor
    parse_item_tuple,
    item_tuple_to_str,
    parse_quantity,
    # item_filters
    filter_classification_paths,
    remove_duplicate_services,
    filter_summary_rows,
    # quality_assessor
    UNIT_TOKENS,
)
from .edital_processor import edital_processor
from .processing_helpers import (
    normalize_item_code as helpers_normalize_item_code,
    is_section_header_desc,
    is_narrative_desc,
    is_contaminated_desc,
    split_restart_prefix,
    item_key as helpers_item_key,
)
from .processors.text_processor import text_processor
from .processors.text_cleanup import strip_trailing_unit_qty
from .processors.deduplication import ServiceDeduplicator
from .processors.service_merger import ServiceMerger
from .processors.validation_filter import ServiceFilter
from config import AtestadoProcessingConfig as APC, PAID_SERVICES_ENABLED

from logging_config import get_logger
logger = get_logger('services.document_processor')


class DocumentProcessor:
    """Processador integrado de documentos."""

    def _filter_items_without_code(self, servicos: list, min_items_with_code: int = 5) -> list:
        """
        Remove itens sem código de item quando há itens suficientes com código.

        Itens sem código (item=None) geralmente são descrições gerais do documento
        (ex: "Execução de obra de SISTEMAS DE ILUMINAÇÃO") que foram erroneamente
        extraídos como serviços pela IA.

        Só remove itens sem código quando há pelo menos `min_items_with_code` itens
        com código, para não afetar documentos simples sem numeração.

        Args:
            servicos: Lista de serviços
            min_items_with_code: Mínimo de itens com código para ativar o filtro

        Returns:
            Lista filtrada de serviços
        """
        if not servicos:
            return servicos

        # Contar itens com e sem código
        com_codigo = [s for s in servicos if s.get("item")]
        sem_codigo = [s for s in servicos if not s.get("item")]

        # Se há poucos itens com código, manter todos (documento pode não ter numeração)
        if len(com_codigo) < min_items_with_code:
            return servicos

        # Se há itens suficientes com código, remover os sem código
        if sem_codigo:
            logger.info(f"[FILTRO] Removendo {len(sem_codigo)} itens sem código de item (há {len(com_codigo)} itens com código)")
            for s in sem_codigo:
                desc = (s.get("descricao") or "")[:50]
                logger.info(f"[FILTRO] Removido item sem código: {desc}...")

        return com_codigo

    def _build_restart_prefix_maps(self, servicos: list) -> tuple[Dict[tuple, str], Dict[str, str]]:
        prefix_map: Dict[tuple, str] = {}
        prefixes_by_code: Dict[str, set] = {}
        codes_without_prefix: set = set()
        for servico in servicos or []:
            if servico.get("_section") == "AD":
                continue
            prefix, core = split_restart_prefix(servico.get("item"))
            code = helpers_normalize_item_code(core)
            if not code:
                continue
            if not prefix:
                codes_without_prefix.add(code)
                continue
            unit = normalize_unit(servico.get("unidade") or "")
            qty = parse_quantity(servico.get("quantidade"))
            prefix_map[(code, unit, qty)] = prefix
            prefixes_by_code.setdefault(code, set()).add(prefix)
        unique_prefix_by_code = {
            code: next(iter(prefixes))
            for code, prefixes in prefixes_by_code.items()
            if len(prefixes) == 1 and code not in codes_without_prefix
        }
        return prefix_map, unique_prefix_by_code

    def _should_replace_desc(self, current_desc: str, candidate_desc: str) -> bool:
        if not candidate_desc:
            return False
        if is_section_header_desc(candidate_desc):
            return False
        if is_contaminated_desc(candidate_desc):
            return False
        current = (current_desc or "").strip()
        candidate = candidate_desc.strip()
        if not current:
            return True
        if is_section_header_desc(current):
            return True
        if is_contaminated_desc(current):
            # Substituir descrição contaminada apenas se candidato não estiver contaminado
            return True
        if len(current) < 12:
            return True

        sim = description_similarity(current, candidate)

        # Descrições muito diferentes (sim < 0.3)
        if sim < 0.3:
            # Aceitar descrições mais curtas se forem específicas (>= 20 chars)
            # e não forem contaminadas
            if len(candidate) >= 20:
                return True

        # REMOVIDO: Lógica "longer wins" que causava substituição incorreta
        # As descrições serão corrigidas pelo description_fixer.py

        return False

    def _build_text_item_map(self, items: list) -> dict:
        text_map: Dict[tuple, str] = {}
        for item in items or []:
            key = helpers_item_key(item)
            if not key:
                continue
            desc = (item.get("descricao") or "").strip()
            # Filtrar descrições inválidas, narrativas ou contaminadas
            if not desc or is_section_header_desc(desc) or is_narrative_desc(desc):
                continue
            if is_contaminated_desc(desc):
                continue
            existing = text_map.get(key)
            # Manter primeira ocorrência, não a mais longa (evita spillover)
            if not existing:
                text_map[key] = desc
        return text_map

    def _apply_text_descriptions(self, servicos: list, text_map: dict) -> int:
        if not servicos or not text_map:
            return 0
        updated = 0
        for servico in servicos:
            key = helpers_item_key(servico)
            if not key:
                continue
            candidate = text_map.get(key)
            if not candidate:
                continue
            if is_narrative_desc(candidate):
                continue
            if self._should_replace_desc(servico.get("descricao"), candidate):
                servico["descricao"] = candidate
                servico["_desc_from_text"] = True
                updated += 1
        return updated

    def _backfill_quantities_from_text(self, servicos: list, texto: str) -> int:
        """Preenche quantidades faltantes via texto extraído."""
        return text_processor.backfill_quantities_from_text(servicos, texto)

    def _extract_items_from_text_section(
        self,
        texto: str,
        existing_keys: Optional[Set] = None
    ) -> list:
        """Extrai itens da seção de serviços via text_section."""
        return text_processor.extract_items_from_text_section(texto, existing_keys)

    def _item_qty_matches_code(self, item_code: str, qty: float) -> bool:
        if not item_code or qty is None:
            return False
        digits = re.sub(r'\D', '', item_code)
        if not digits:
            return False
        try:
            return float(digits) == float(qty)
        except (TypeError, ValueError):
            return False

    def _clear_item_code_quantities(self, servicos: list, min_ratio: float = 0.7, min_samples: int = 10) -> int:
        if not servicos:
            return 0
        total = 0
        matches = 0
        for s in servicos:
            item_code = helpers_normalize_item_code(s.get("item"))
            qty = parse_quantity(s.get("quantidade"))
            if not item_code or qty is None:
                continue
            total += 1
            if self._item_qty_matches_code(item_code, qty):
                matches += 1
        ratio = (matches / total) if total else 0.0
        if total < min_samples or ratio < min_ratio:
            return 0

        cleared = 0
        for s in servicos:
            item_code = helpers_normalize_item_code(s.get("item"))
            qty = parse_quantity(s.get("quantidade"))
            if item_code and qty is not None and self._item_qty_matches_code(item_code, qty):
                s["quantidade"] = None
                cleared += 1
        if cleared:
            logger.info(f"[QTY] Quantidades removidas por vazamento de coluna: {cleared} (ratio={ratio:.0%})")
        return cleared

    def _summarize_table_debug(self, debug: dict) -> dict:
        if not isinstance(debug, dict):
            return {}
        summary = {}
        for key in ("source", "tables", "pages", "pages_used", "error"):
            if key in debug:
                summary[key] = debug.get(key)
        if "ocr_noise" in debug:
            summary["ocr_noise"] = debug.get("ocr_noise")
        return summary

    def _calc_qty_ratio(self, servicos: list) -> float:
        """Calcula a proporção de serviços com quantidade válida."""
        if not servicos:
            return 0.0
        qty_count = sum(1 for s in servicos if parse_quantity(s.get("quantidade")) not in (None, 0))
        return qty_count / len(servicos)

    def _extract_item_code(self, desc: str) -> str:
        """
        Extrai código do item da descrição (ex: "001.03.01" de "001.03.01 MOBILIZAÇÃO").
        Também reconhece formatos com prefixo AD- (legacy) e reinícios Sx-.
        """
        if not desc:
            return ""

        text = desc.strip()

        # Primeiro, tentar extrair formato com prefixo Sx- (ex: S2-1.1)
        restart_match = re.match(r'^(S\d+-\d{1,3}(?:\.\d{1,3})+(?:-[A-Z])?)\b', text, re.IGNORECASE)
        if restart_match:
            return restart_match.group(1).upper()

        # Tentar extrair formato com prefixo AD- (legacy: AD-1.1, AD-1.1-A)
        ad_match = re.match(r'^(AD-\d{1,3}(?:\.\d{1,3})+(?:-[A-Z])?)\b', text, re.IGNORECASE)
        if ad_match:
            return ad_match.group(1).upper()

        # Formato numérico padrão (ex: 1.1, 10.4, 10.4-A)
        match = re.match(r'^(\d{1,3}(?:\s*\.\s*\d{1,3}){1,4}(?:-[A-Z])?)\b', text)
        if not match:
            match = re.match(r'^(\d{1,3}(?:\s+\d{1,2}){1,3})\b', text)

        if match:
            code = re.sub(r'[\s]+', '.', match.group(1))
            code = re.sub(r'\.{2,}', '.', code).strip('.')
            return code
        return ""

    def _split_item_description(self, desc: str) -> tuple[str, str]:
        """
        Separa o codigo do item da descricao, se presente.
        """
        if not desc:
            return "", ""

        code = self._extract_item_code(desc)
        if not code:
            return "", desc.strip()

        cleaned = re.sub(
            r"^(S\d+-)?(\d{1,3}(?:\s*\.\s*\d{1,3}){1,4}|\d{1,3}(?:\s+\d{1,2}){1,3})\s*[-.]?\s*",
            "",
            desc
        ).strip()
        return code, cleaned or desc.strip()

    def _servico_match_key(self, servico: dict) -> str:
        desc = normalize_desc_for_match(servico.get("descricao") or "")
        unit = normalize_unit(servico.get("unidade") or "")
        if not desc:
            return ""
        return f"{desc}|||{unit}"

    def _servico_desc_key(self, servico: dict) -> str:
        return normalize_desc_for_match(servico.get("descricao") or "")

    def _table_candidates_by_code(self, servicos_table: list) -> dict:
        if not servicos_table:
            return {}
        unit_tokens = UNIT_TOKENS
        candidates: Dict[str, Any] = {}
        for servico in servicos_table:
            item = servico.get("item") or self._extract_item_code(servico.get("descricao") or "")
            if not item:
                continue
            item_tuple = parse_item_tuple(item)
            if not item_tuple:
                continue
            desc = (servico.get("descricao") or "").strip()
            if len(desc) < 8:
                continue
            qty = parse_quantity(servico.get("quantidade"))
            if qty is None:
                continue
            unit = normalize_unit(servico.get("unidade") or "")
            if unit and unit not in unit_tokens:
                unit = ""
            normalized_item = item_tuple_to_str(item_tuple)
            candidate = {
                "item": normalized_item,
                "descricao": desc,
                "quantidade": qty,
                "unidade": unit
            }
            existing = candidates.get(normalized_item)
            if not existing or len(desc) > len(existing.get("descricao") or ""):
                candidates[normalized_item] = candidate
        return candidates

    def _attach_item_codes_from_table(self, servicos: list, servicos_table: list) -> list:
        if not servicos or not servicos_table:
            return servicos
        table_candidates = self._table_candidates_by_code(servicos_table)
        if not table_candidates:
            return servicos

        match_threshold = APC.CODE_MATCH_THRESHOLD

        used_codes = {s.get("item") for s in servicos if s.get("item")}
        used_codes.discard(None)
        for servico in servicos:
            if servico.get("item"):
                continue
            desc = servico.get("descricao") or ""
            unit = normalize_unit(servico.get("unidade") or "")
            qty = parse_quantity(servico.get("quantidade"))
            best_code = None
            best_score = 0.0
            best_candidate = None
            for code, candidate in table_candidates.items():
                if code in used_codes:
                    continue
                score = description_similarity(desc, candidate["descricao"])
                if score < match_threshold:
                    continue
                if unit and candidate["unidade"] and unit == candidate["unidade"]:
                    score += 0.1
                cand_qty = candidate.get("quantidade")
                if qty is not None and cand_qty is not None and isinstance(qty, (int, float)) and isinstance(cand_qty, (int, float)) and qty != 0 and cand_qty != 0:
                    diff = abs(qty - cand_qty)
                    denom = max(abs(qty), abs(cand_qty))
                    if denom > 0 and (diff / denom) <= 0.05:
                        score += 0.1
                if score > best_score:
                    best_score = score
                    best_code = code
                    best_candidate = candidate
            if best_code:
                servico["item"] = best_code
                used_codes.add(best_code)
                if best_candidate and not servico.get("unidade") and best_candidate.get("unidade"):
                    servico["unidade"] = best_candidate["unidade"]
                if best_candidate and parse_quantity(servico.get("quantidade")) in (None, 0) and best_candidate.get("quantidade") is not None:
                    servico["quantidade"] = best_candidate["quantidade"]

        return servicos

    def _is_short_description(self, desc: str) -> bool:
        desc = (desc or '').strip()
        if not desc:
            return True
        if len(desc) < 35:
            return True
        if len(desc.split()) < 4:
            return True
        return False

    def _postprocess_servicos(
        self,
        servicos: list,
        use_ai: bool,
        table_used: bool,
        servicos_table: list,
        texto: str,
        strict_item_gate: bool = False,
        skip_no_code_dedupe: bool = False
    ) -> list:
        """
        Aplica pós-processamento nos serviços extraídos.

        Inclui: normalização, filtros, deduplicação, limpeza de códigos.

        Args:
            servicos: Lista de serviços brutos
            use_ai: Se IA foi usada
            table_used: Se tabela foi usada com alta confiança
            servicos_table: Serviços da tabela (para enriquecimento)
            texto: Texto extraido do documento
            strict_item_gate: Se True, remove itens nao encontrados no texto/tabela
            skip_no_code_dedupe: Se True, evita dedupe agressiva para documentos sem itens numerados

        Returns:
            Lista de serviços processados
        """
        # Etapa 1: Preparação inicial
        servicos = filter_summary_rows(servicos)
        servicos = text_processor.extract_hidden_items_from_servicos(servicos)

        # Etapa 2: Enriquecer com dados da tabela se IA foi usada
        if use_ai and not table_used:
            servicos = self._attach_item_codes_from_table(servicos, servicos_table)
            servicos = ServiceDeduplicator(servicos).prefer_items_with_code()

        # Etapa 3: Normalizar campos de cada serviço
        self._normalize_servicos_fields(servicos)

        # Etapa 4: Tratar prefixos de restart e duplicatas (usando classes extraídas)
        servicos = ServiceMerger(servicos).normalize_prefixes()
        servicos = ServiceDeduplicator(servicos).dedupe_by_restart_prefix()
        servicos = ServiceDeduplicator(servicos).dedupe_within_planilha()
        servicos = ServiceDeduplicator(servicos).cleanup_orphan_suffixes()

        # Etapa 5: Aplicar filtros finais
        servicos = self._apply_servicos_filters(
            servicos, texto, servicos_table, strict_item_gate, skip_no_code_dedupe
        )

        return servicos

    def _normalize_servicos_fields(self, servicos: list) -> None:
        """Normaliza campos de cada serviço (item, descricao, quantidade, unidade)."""
        for servico in servicos:
            # Normalizar item e descrição
            desc = servico.get("descricao", "")
            existing_item = servico.get("item")
            item, clean_desc = self._split_item_description(desc)
            if not item and existing_item:
                item = existing_item
            if item:
                servico["item"] = item
                if clean_desc:
                    servico["descricao"] = clean_desc
            else:
                servico["item"] = None

            # Normalizar quantidade
            qty = parse_quantity(servico.get("quantidade"))
            if qty is not None:
                servico["quantidade"] = qty

            # Normalizar unidade
            unit = servico.get("unidade")
            if isinstance(unit, str):
                unit = unit.strip()
                if unit:
                    unit = normalize_unit(unit)
                servico["unidade"] = unit

            # Limpar trailing unit/qty da descrição
            desc = servico.get("descricao") or ""
            cleaned_desc = strip_trailing_unit_qty(desc, unit, qty)
            if cleaned_desc and cleaned_desc != desc:
                servico["descricao"] = cleaned_desc

            # Fix B2: Remover prefixo UN/QTD da descrição
            desc = servico.get("descricao") or ""
            cleaned_prefix = text_processor.strip_unit_qty_prefix(desc)
            if cleaned_prefix and cleaned_prefix != desc:
                servico["descricao"] = cleaned_prefix

    def _apply_servicos_filters(
        self,
        servicos: list,
        texto: str,
        servicos_table: list,
        strict_item_gate: bool,
        skip_no_code_dedupe: bool
    ) -> list:
        """Aplica filtros finais nos serviços."""
        # Usar classes extraídas para filtros e deduplicação
        if strict_item_gate:
            servicos = ServiceFilter(servicos, texto, servicos_table).filter_not_in_sources()

        servicos = filter_classification_paths(servicos)

        if skip_no_code_dedupe:
            com_item = [s for s in servicos if s.get("item")]
            sem_item = [s for s in servicos if not s.get("item")]
            sem_item = ServiceDeduplicator(sem_item).dedupe_by_desc_unit()
            servicos = com_item + sem_item
        else:
            servicos = remove_duplicate_services(servicos)

        servicos = ServiceDeduplicator(servicos).remove_duplicate_pairs()
        servicos = ServiceFilter(servicos).filter_headers()
        servicos = ServiceFilter(servicos).filter_no_quantity()
        servicos = self._filter_items_without_code(servicos)

        return servicos

    def _find_better_description(self, item: dict, candidates: list) -> str:
        target_desc = (item.get('descricao') or '').strip()
        target_unit = normalize_unit(item.get('unidade') or '')
        try:
            target_qty = float(item.get('quantidade') or 0)
        except (TypeError, ValueError):
            target_qty = 0
        target_kw = extract_keywords(target_desc)

        best_desc = None
        best_len = len(target_desc)

        for cand in candidates:
            cand_desc = (cand.get('descricao') or '').strip()
            if not cand_desc or len(cand_desc) <= best_len:
                continue
            cand_unit = normalize_unit(cand.get('unidade') or '')
            if target_unit and cand_unit and cand_unit != target_unit:
                continue
            try:
                cand_qty = float(cand.get('quantidade') or 0)
            except (TypeError, ValueError):
                cand_qty = 0
            if target_qty and cand_qty and abs(target_qty - cand_qty) > 0.01:
                continue
            cand_kw = extract_keywords(cand_desc)
            if target_kw and cand_kw and len(target_kw & cand_kw) == 0:
                if not cand_desc.upper().startswith(target_desc.upper()):
                    continue
            best_desc = cand_desc
            best_len = len(cand_desc)

        return best_desc or ''

    def process_atestado(
        self,
        file_path: str,
        use_vision: bool = True,
        progress_callback=None,
        cancel_check=None
    ) -> Dict[str, Any]:
        """
        Processa um atestado de capacidade técnica usando abordagem híbrida.

        Combina GPT-4o Vision (para precisão) com OCR+texto (para completude).

        Args:
            file_path: Caminho para o arquivo (PDF ou imagem)
            use_vision: Se True, usa abordagem híbrida Vision+OCR; se False, apenas OCR+texto

        Returns:
            Dicionário com dados extraídos do atestado
        """
        from .atestado.pipeline import AtestadoPipeline
        return AtestadoPipeline(self, file_path, use_vision, progress_callback, cancel_check).run()

    def process_edital(self, file_path: str, progress_callback=None, cancel_check=None) -> Dict[str, Any]:
        """
        Processa uma pagina de edital com quantitativos minimos.
        Delega ao EditalProcessor.

        Args:
            file_path: Caminho para o arquivo PDF
            progress_callback: Callback para progresso
            cancel_check: Funcao para verificar cancelamento

        Returns:
            Dicionario com exigencias extraidas
        """
        return edital_processor.process(file_path, progress_callback, cancel_check)

    def analyze_qualification(
        self,
        exigencias: List[Dict[str, Any]],
        atestados: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Analisa a qualificacao tecnica comparando exigencias e atestados.
        Delega ao EditalProcessor.

        Args:
            exigencias: Lista de exigencias do edital
            atestados: Lista de atestados do usuario

        Returns:
            Resultado da analise com status de atendimento
        """
        return edital_processor.analyze_qualification(exigencias, atestados)

    def get_status(self) -> Dict[str, Any]:
        """
        Retorna o status dos serviços de processamento.

        Returns:
            Dicionário com status de cada serviço
        """
        provider_status = ai_provider.get_status()
        return {
            "pdf_extractor": True,
            "ocr_service": True,
            "ai_provider": provider_status,
            "document_ai": {
                "available": document_ai_service.is_available,
                "configured": document_ai_service.is_configured,
                "enabled": APC.DOCUMENT_AI_ENABLED,
                "paid_services_enabled": PAID_SERVICES_ENABLED
            },
            "is_configured": ai_provider.is_configured,
            "mensagem": (
                "Serviços pagos desativados (PAID_SERVICES_ENABLED=false)."
                if not PAID_SERVICES_ENABLED
                else (
                    f"IA configurada ({', '.join(ai_provider.available_providers)})"
                    if ai_provider.is_configured
                    else "Configure OPENAI_API_KEY ou GOOGLE_API_KEY para análise inteligente"
                )
            )
        }


# Instancia singleton para uso global
document_processor = DocumentProcessor()

# Configurar AtestadoProcessor com referencia ao DocumentProcessor
# Importação tardia necessária para evitar dependência circular
from .atestado_processor import atestado_processor  # noqa: E402
atestado_processor.set_document_processor(document_processor)
