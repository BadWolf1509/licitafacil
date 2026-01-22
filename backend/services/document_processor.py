"""
Serviço integrado de processamento de documentos.
Combina extração de PDF, OCR e análise com IA.
Suporta GPT-4o Vision para análise direta de imagens.
Inclui processamento paralelo opcional para melhor performance.
"""

from typing import Dict, Any, List, Optional
from collections import Counter
from pathlib import Path
import re
import pdfplumber

from .pdf_extractor import pdf_extractor
from .ocr_service import ocr_service
from .ai_provider import ai_provider
from .matching_service import matching_service
from .document_ai_service import document_ai_service
from .pdf_extraction_service import pdf_extraction_service, ProcessingCancelled  # noqa: F401 (re-export)
from .table_extraction_service import table_extraction_service
from .document_analysis_service import document_analysis_service
# Módulos extraídos para migração gradual - noqa: F401
from .pdf_converter import pdf_converter  # noqa: F401
from .extraction import (  # noqa: F401
    # text_normalizer
    normalize_description,
    normalize_unit,
    normalize_header,
    normalize_desc_for_match,
    extract_keywords,
    description_similarity,
    UNIT_TOKENS,
    # table_processor
    parse_item_tuple,
    item_tuple_to_str,
    parse_quantity,
    score_item_column,
    detect_header_row,
    guess_columns_by_header,
    compute_column_stats,
    guess_columns_by_content,
    validate_column_mapping,
    build_description_from_cells,
    # service_filter
    filter_classification_paths,
    remove_duplicate_services,
    filter_servicos_by_item_length,
    filter_servicos_by_item_prefix,
    repair_missing_prefix,
    is_summary_row,
    filter_summary_rows,
    deduplicate_by_description,
    quantities_similar,
    descriptions_similar,
    items_similar,
    servico_key,
    merge_servicos_prefer_primary,
    dominant_item_length,
    # quality_assessor
    compute_servicos_stats,
    compute_description_quality,
    is_ocr_noisy,
    compute_quality_score,
)
from .aditivo_processor import prefix_aditivo_items
from exceptions import (
    PDFError,
    OCRError,
    UnsupportedFileError,
    TextExtractionError,
    AzureAPIError,
    OpenAIError,
)
from config import AtestadoProcessingConfig as APC

from logging_config import get_logger
logger = get_logger('services.document_processor')


class DocumentProcessor:
    """Processador integrado de documentos."""

    # ==================== Delegação ao PDFExtractionService ====================

    def _pdf_to_images(
        self,
        file_path: str,
        dpi: int = 300,
        progress_callback=None,
        cancel_check=None,
        stage: str = "vision"
    ) -> List[bytes]:
        """Delega conversão de PDF para imagens ao PDFExtractionService."""
        return pdf_extraction_service.pdf_to_images(
            file_path, dpi, progress_callback, cancel_check, stage
        )

    def _extract_pdf_with_ocr_fallback(
        self,
        file_path: str,
        progress_callback=None,
        cancel_check=None
    ) -> str:
        """Delega extração de texto com OCR ao PDFExtractionService."""
        return pdf_extraction_service.extract_text_with_ocr_fallback(
            file_path, progress_callback, cancel_check
        )

    def _notify_progress(self, progress_callback, current: int, total: int, stage: str, message: str):
        """Delega notificação de progresso ao PDFExtractionService."""
        pdf_extraction_service._notify_progress(progress_callback, current, total, stage, message)

    def _check_cancel(self, cancel_check):
        """Delega verificação de cancelamento ao PDFExtractionService."""
        pdf_extraction_service._check_cancel(cancel_check)

    def _ocr_image_list(self, image_list, progress_callback=None, cancel_check=None) -> str:
        """Delega OCR de lista de imagens ao PDFExtractionService."""
        return pdf_extraction_service.ocr_image_list(image_list, progress_callback, cancel_check)

    def _remove_duplicate_pairs(self, servicos: list) -> list:
        """
        Remove duplicatas entre pares X.Y e X.Y.1 que representam o mesmo serviço.

        Quando ambos existem com quantidade igual e descrições similares:
        - Calcula similaridade baseada em keywords em comum
        - Se similaridade >= 50%, são considerados duplicados
        - Mantém apenas o item com código mais curto (X.Y) pois geralmente é o original
        - Exceto quando o pai é um header curto (< 20 chars), aí mantém o filho (X.Y.1)
        """
        if not servicos:
            return servicos

        # Indexar serviços por código de item
        by_item_code = {}
        for s in servicos:
            item = s.get("item")
            if item:
                planilha_id = s.get("_planilha_id") or 0
                by_item_code[(planilha_id, str(item))] = s

        # Identificar itens a remover
        items_to_remove = set()

        for item_key, servico in by_item_code.items():
            planilha_id, item_code = item_key
            # Verificar se existe item pai (X.Y para X.Y.1)
            parts = item_code.split(".")
            if len(parts) >= 2:
                parent_code = ".".join(parts[:-1])
                parent_key = (planilha_id, parent_code)
                if parent_key in by_item_code:
                    parent = by_item_code[parent_key]

                    # Comparar quantidade
                    qty_filho = parse_quantity(servico.get("quantidade"))
                    qty_pai = parse_quantity(parent.get("quantidade"))

                    if not (qty_filho is not None and qty_pai is not None):
                        continue

                    # Verificar se quantidades são iguais ou similares
                    if not quantities_similar(qty_filho, qty_pai):
                        continue

                    # Calcular similaridade de descrições via keywords
                    desc_filho = servico.get("descricao") or ""
                    desc_pai = parent.get("descricao") or ""
                    kw_filho = extract_keywords(desc_filho)
                    kw_pai = extract_keywords(desc_pai)

                    if not kw_filho or not kw_pai:
                        continue

                    # Calcular Jaccard similarity
                    intersection = len(kw_filho & kw_pai)
                    union = len(kw_filho | kw_pai)
                    similarity = intersection / union if union > 0 else 0

                    # Se similaridade >= 50%, são duplicados
                    if similarity >= 0.5:
                        # Decidir qual remover baseado no contexto
                        desc_pai_norm = normalize_description(desc_pai)

                        # Caso 1: Pai é header curto - remover pai, manter filho
                        if len(desc_pai_norm) < 20:
                            items_to_remove.add(parent_key)
                        # Caso 2: Itens do aditivo (11.x) - manter filho (são os serviços reais)
                        elif parent_code.startswith("11"):
                            items_to_remove.add(parent_key)
                        # Caso 3: Itens do contrato - remover filho (provavelmente fantasma do OCR)
                        else:
                            items_to_remove.add(item_key)

        # Filtrar serviços removendo os duplicados
        return [
            s for s in servicos
            if (s.get("_planilha_id") or 0, s.get("item")) not in items_to_remove
        ]

    def _filter_section_headers(self, servicos: list) -> list:
        """
        Remove cabeçalhos de seção que não são itens reais.

        Cabeçalhos de seção são itens como "1.4.10 COBERTURA" que servem apenas
        para agrupar sub-itens (1.4.10.1, 1.4.10.2, etc.) e não devem ser
        contabilizados como serviços.

        Critérios para identificar cabeçalhos:
        1. Descrição muito curta (menos de 25 caracteres)
        2. Tem pelo menos um item filho (código que começa com o código do pai + ".")

        Args:
            servicos: Lista de serviços

        Returns:
            Lista filtrada sem cabeçalhos de seção
        """
        if not servicos:
            return servicos

        # Construir set de códigos para busca rápida
        all_codes = set()
        for s in servicos:
            code = s.get("item")
            if code:
                # Remover prefixo S1-, S2-, etc.
                clean_code = re.sub(r'^S\d+-', '', str(code))
                all_codes.add(clean_code)

        filtered = []
        removed = 0
        for s in servicos:
            code = s.get("item")
            desc = s.get("descricao") or ""

            # Só verificar itens com código e descrição curta
            if code and len(desc.strip()) < 25:
                clean_code = re.sub(r'^S\d+-', '', str(code))
                # Verificar se tem filhos (códigos que começam com este + ".")
                has_children = any(
                    c.startswith(clean_code + ".") for c in all_codes if c != clean_code
                )
                if has_children:
                    removed += 1
                    logger.info(f"[FILTRO] Removido cabeçalho de seção: {code} ({desc[:30]})")
                    continue

            filtered.append(s)

        if removed > 0:
            logger.info(f"[FILTRO] {removed} cabeçalhos de seção removidos")

        return filtered

    def _filter_items_without_quantity(self, servicos: list) -> list:
        """
        Remove itens que nao tem quantidade definida.

        Filtro estrito: remove itens com quantidade nula ou zero.
        """
        if not servicos:
            return servicos

        return [
            s for s in servicos
            if parse_quantity(s.get("quantidade")) not in (None, 0)
        ]

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

    def _normalize_item_code(self, item: Any) -> Optional[str]:
        if item is None:
            return None
        item_str = str(item).strip()
        if not item_str:
            return None
        if item_str.upper().startswith("AD-"):
            item_str = item_str[3:].strip()
        item_tuple = parse_item_tuple(item_str)
        if not item_tuple:
            return None
        return item_tuple_to_str(item_tuple)

    def _item_code_in_text(self, item_code: str, texto: str) -> bool:
        if not item_code or not texto:
            return False
        escaped = re.escape(item_code)
        escaped = escaped.replace(r"\.", r"\s*\.\s*")
        pattern = rf"(?<!\d){escaped}(?!\d)"
        return re.search(pattern, texto) is not None

    def _count_item_codes_in_text(self, texto: str) -> int:
        if not texto:
            return 0
        codes = set()
        pattern = re.compile(r'(?<!\d)(\d{1,3}\s*\.\s*\d{1,3}(?:\s*\.\s*\d{1,3}){0,3})(?!\d)')
        for match in pattern.finditer(texto):
            raw = match.group(1)
            raw = re.sub(r'\s+', '', raw)
            item_tuple = parse_item_tuple(raw)
            if item_tuple:
                codes.add(item_tuple_to_str(item_tuple))
        return len(codes)

    def _extract_item_codes_from_text_lines(self, texto: str) -> list:
        if not texto:
            return []
        codes = []
        lines = texto.split('\n')
        for line in lines:
            line = line.strip()
            if not line:
                continue
            match = re.match(r'^(\d+\.\d+(?:\.\d+){0,3})\b', line)
            item_raw = None
            if match:
                item_raw = match.group(1)
            else:
                matches = re.findall(r'(?<!\d)(\d+\.\d+(?:\.\d+){0,3})(?!\d)', line)
                if matches:
                    item_raw = matches[0]
            if not item_raw:
                continue
            item_tuple = parse_item_tuple(item_raw)
            if not item_tuple:
                continue
            codes.append(item_tuple_to_str(item_tuple))
        return codes

    def _extract_items_from_text_lines(self, texto: str) -> list:
        if not texto:
            return []
        items = []
        lines = texto.split('\n')
        segment_index = 1
        last_tuple = None
        for line in lines:
            line = line.strip()
            if not line:
                continue
            match = re.match(r'^(\d+\.\d+(?:\.\d+){0,3})\s+(.+)$', line)
            if not match:
                continue
            item_raw = match.group(1)
            rest = match.group(2).strip()
            unit_match = re.search(r'\b([A-Za-z0-9\u00ba\u00b0/%\u00b2\u00b3\.]+)\s+([\d.,]+)\s*$', rest)
            if not unit_match:
                continue
            unit_raw = unit_match.group(1)
            qty_raw = unit_match.group(2)
            if parse_quantity(qty_raw) is None:
                continue
            item_tuple = parse_item_tuple(item_raw)
            if not item_tuple:
                continue
            if last_tuple and item_tuple < last_tuple:
                segment_index += 1
            last_tuple = item_tuple
            desc = rest[:unit_match.start()].strip()
            unit_norm = normalize_unit(unit_raw)
            if not unit_norm:
                continue
            prefix = f"S{segment_index}-" if segment_index > 1 else ""
            items.append({
                'item': f"{prefix}{item_tuple_to_str(item_tuple)}",
                'descricao': desc,
                'unidade': unit_norm,
                'quantidade': qty_raw,
                '_source': 'text_line'
            })
        return items

    def _split_text_by_pages(self, texto: str) -> list:
        if not texto:
            return []
        matches = list(re.finditer(r'P[aá]gina\s+(\d+)\s*/\s*(\d+)', texto, re.IGNORECASE))
        if not matches:
            return []
        segments = []
        for idx, match in enumerate(matches):
            start = match.start()
            end = matches[idx + 1].start() if idx + 1 < len(matches) else len(texto)
            try:
                page_num = int(match.group(1))
            except (TypeError, ValueError):
                continue
            segments.append((page_num, texto[start:end]))
        merged = {}
        order = []
        for page_num, segment in segments:
            if page_num not in merged:
                order.append(page_num)
                merged[page_num] = segment
            else:
                merged[page_num] += "\n" + segment
        return [(page_num, merged[page_num]) for page_num in order]

    def _detect_planilha_signature(self, texto: str) -> Optional[str]:
        normalized = normalize_description(texto or "")
        if not normalized:
            return None
        has_orcamento = "ORCAMENTO" in normalized
        has_fisico = "FISICO" in normalized
        has_geobras = "GEOBRAS" in normalized
        has_contrato = "CONTRATO" in normalized
        if has_fisico:
            if has_geobras or has_contrato:
                return "FISICO_CONTRATO"
            return "FISICO"
        if has_orcamento:
            return "ORCAMENTO"
        return None

    def _build_page_planilha_map(self, page_segments: list) -> tuple[Dict[int, int], list]:
        if not page_segments:
            return {}, []
        page_map: Dict[int, int] = {}
        audit: list = []
        current_sig = None
        planilha_id = 0
        found_signature = False
        for page_num, page_text in page_segments:
            sig = self._detect_planilha_signature(page_text)
            if sig:
                found_signature = True
                if sig != current_sig:
                    planilha_id += 1
                    current_sig = sig
            page_map[page_num] = planilha_id if planilha_id else 0
            audit.append({
                "page": page_num,
                "planilha_id": page_map[page_num],
                "signature": sig or current_sig
            })
        if not found_signature:
            return {}, []
        return page_map, audit

    def _apply_page_planilha_map(self, servicos: list, page_map: Dict[int, int]) -> int:
        if not servicos or not page_map:
            return 0
        remapped = 0
        for servico in servicos:
            page = servico.get("_page")
            if page is None:
                continue
            try:
                page_num = int(page)
            except (TypeError, ValueError):
                continue
            target_id = page_map.get(page_num)
            if not target_id:
                continue
            current_id = int(servico.get("_planilha_id") or 0)
            if current_id != target_id:
                servico["_planilha_id"] = target_id
                servico.pop("_planilha_label", None)
                remapped += 1
        return remapped

    def _split_restart_prefix(self, item: Any) -> tuple[Optional[str], str]:
        item_str = str(item or "").strip()
        if not item_str:
            return None, ""
        match = re.match(r'^(S\d+)-(.+)$', item_str, re.IGNORECASE)
        if match:
            return match.group(1).upper(), match.group(2).strip()
        return None, item_str

    def _build_restart_prefix_maps(self, servicos: list) -> tuple[Dict[tuple, str], Dict[str, str]]:
        prefix_map: Dict[tuple, str] = {}
        prefixes_by_code: Dict[str, set] = {}
        codes_without_prefix: set = set()
        for servico in servicos or []:
            if servico.get("_section") == "AD":
                continue
            prefix, core = self._split_restart_prefix(servico.get("item"))
            code = self._normalize_item_code(core)
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

    def _merge_fragmented_planilhas(self, servicos: list) -> list:
        """
        Mescla planilhas fragmentadas que deveriam ser uma só.

        Critério de mesclagem:
        - Planilhas com baixo overlap (< MIN_OVERLAP) são candidatas a mesclagem
        - Planilhas sem _page são mescladas com a planilha principal (maior)
        - Resultado: planilhas corretamente agrupadas
        """
        if not servicos:
            return servicos

        # Agrupa serviços por planilha
        servicos_by_planilha: dict = {}
        codes_by_planilha: dict = {}
        pages_by_planilha: dict = {}

        for servico in servicos:
            planilha_id = int(servico.get("_planilha_id") or 0)
            servicos_by_planilha.setdefault(planilha_id, []).append(servico)

            # Coleta códigos de item
            item_val = servico.get("item")
            if item_val:
                prefix, core = self._split_restart_prefix(item_val)
                code = self._normalize_item_code(core or item_val)
                if code:
                    codes_by_planilha.setdefault(planilha_id, set()).add(code)

            # Coleta páginas
            page = servico.get("_page")
            if page:
                pages_by_planilha.setdefault(planilha_id, set()).add(page)

        planilha_ids = sorted(servicos_by_planilha.keys())
        if len(planilha_ids) <= 1:
            return servicos

        # Identifica planilha principal (maior quantidade de itens)
        main_planilha = max(planilha_ids, key=lambda pid: len(servicos_by_planilha.get(pid, [])))
        main_codes = codes_by_planilha.get(main_planilha, set())
        main_pages = pages_by_planilha.get(main_planilha, set())

        # Identifica planilhas a mesclar com a principal
        # Critérios: sem páginas OU baixo overlap com principal
        planilhas_to_merge = []
        for pid in planilha_ids:
            if pid == main_planilha:
                continue

            pid_pages = pages_by_planilha.get(pid, set())
            pid_codes = codes_by_planilha.get(pid, set())

            # Calcula overlap com a principal
            overlap = pid_codes & main_codes
            overlap_count = len(overlap)

            # Regra fundamental: NUNCA mesclar planilhas com alto overlap
            # Alto overlap significa que são planilhas DIFERENTES com itens repetidos
            # Só mesclar se overlap < MIN_OVERLAP (indica continuação, não nova planilha)
            if overlap_count >= APC.RESTART_MIN_OVERLAP:
                # Alto overlap - são planilhas diferentes, não mesclar
                continue

            # Mesclar apenas se overlap é baixo E uma das condições:
            # 1. Ambas sem páginas
            # 2. Uma tem páginas e são adjacentes/contidas no range da principal
            should_merge = False

            if not pid_pages and not main_pages:
                # Ambas sem página e baixo overlap - mesclar
                should_merge = True
            elif not pid_pages or not main_pages:
                # Uma sem página e baixo overlap - provavelmente fragmentada
                should_merge = True
            else:
                # Ambas têm páginas - verificar se são consecutivas ou sobrepostas
                min_main = min(main_pages)
                max_main = max(main_pages)
                min_pid = min(pid_pages)
                max_pid = max(pid_pages)

                # Páginas dentro ou adjacentes ao range da principal
                pages_adjacent = (min_pid >= min_main - 1 and max_pid <= max_main + 1)
                if pages_adjacent:
                    should_merge = True

            if should_merge:
                planilhas_to_merge.append(pid)

        # Mescla planilhas
        if planilhas_to_merge:
            for servico in servicos:
                pid = int(servico.get("_planilha_id") or 0)
                if pid in planilhas_to_merge:
                    servico["_planilha_id"] = main_planilha
                    servico["_merged_from"] = pid

        return servicos

    def _normalize_restart_prefixes_by_planilha(self, servicos: list) -> list:
        """
        Normaliza prefixos de reinício baseado em overlap de códigos entre planilhas.

        Critério:
        - Primeira planilha (a com mais itens) NUNCA recebe prefixo
        - Planilhas subsequentes recebem prefixo APENAS se houver overlap
          (mesmo código de item já existe em planilha anterior)
        """
        if not servicos:
            return servicos

        # Passo 1: Mesclar planilhas fragmentadas antes de processar
        servicos = self._merge_fragmented_planilhas(servicos)

        # Agrupa serviços por planilha e coleta códigos
        servicos_by_planilha: dict = {}
        codes_by_planilha: dict = {}
        for servico in servicos:
            planilha_id = int(servico.get("_planilha_id") or 0)
            servicos_by_planilha.setdefault(planilha_id, []).append(servico)
            item_val = servico.get("item")
            if item_val:
                prefix, core = self._split_restart_prefix(item_val)
                code = self._normalize_item_code(core or item_val)
                if code:
                    codes_by_planilha.setdefault(planilha_id, set()).add(code)

        planilha_ids = sorted(servicos_by_planilha.keys())
        if len(planilha_ids) <= 1:
            # Só uma planilha, remove todos os prefixos
            for servico in servicos:
                item_val = servico.get("item")
                if not item_val:
                    continue
                prefix, core = self._split_restart_prefix(item_val)
                if prefix:
                    servico["item"] = core
                    servico.pop("_item_prefix", None)
            return servicos

        # Ordena planilhas por quantidade de itens (maior primeiro = planilha principal)
        # A planilha com mais itens é considerada a principal e não recebe prefixo
        planilha_order = sorted(
            planilha_ids,
            key=lambda pid: len(servicos_by_planilha.get(pid, [])),
            reverse=True
        )
        main_planilha = planilha_order[0]  # Planilha com mais itens

        # Determina quais planilhas precisam de prefixo (têm overlap com a principal)
        main_codes = codes_by_planilha.get(main_planilha, set())
        planilhas_with_prefix: dict = {}  # planilha_id -> prefix_idx
        prefix_counter = 0

        # Processa planilhas secundárias em ordem de ID
        secondary_planilhas = [pid for pid in sorted(planilha_ids) if pid != main_planilha]
        for planilha_id in secondary_planilhas:
            planilha_codes = codes_by_planilha.get(planilha_id, set())
            overlap = planilha_codes & main_codes
            if overlap and len(overlap) >= APC.RESTART_MIN_OVERLAP:
                prefix_counter += 1
                planilhas_with_prefix[planilha_id] = prefix_counter

        # Aplica prefixos apenas onde necessário
        for servico in servicos:
            item_val = servico.get("item")
            if not item_val:
                continue
            prefix, core = self._split_restart_prefix(item_val)
            item_str = str(core or item_val).strip()
            if item_str.upper().startswith("AD-"):
                item_str = item_str[3:].strip()
            if not item_str:
                continue
            planilha_id = int(servico.get("_planilha_id") or 0)
            prefix_idx = planilhas_with_prefix.get(planilha_id)
            if prefix_idx:
                servico["item"] = f"S{prefix_idx}-{item_str}"
                servico["_item_prefix"] = f"S{prefix_idx}"
            else:
                servico["item"] = item_str
                if "_item_prefix" in servico:
                    servico.pop("_item_prefix", None)
        return servicos

    def _item_key(self, item: dict) -> Optional[tuple]:
        prefix, core = self._split_restart_prefix(item.get("item"))
        code = self._normalize_item_code(core)
        if not code:
            return None
        code_key = f"{prefix}-{code}" if prefix else code
        unit = normalize_unit(item.get("unidade") or "")
        qty = parse_quantity(item.get("quantidade"))
        return (code_key, unit, qty)

    def _is_section_header_desc(self, desc: str) -> bool:
        normalized = normalize_description(desc or "")
        if not normalized:
            return False
        headers = {
            "SERVICOS PRELIMINARES",
            "DEMOLICOES",
            "PAVIMENTACAO",
            "URBANIZACAO",
            "INSTALACOES",
            "REVESTIMENTOS",
            "SERVICOS EXECUTADOS",
            "SERVICOS",
            "PRACA",
        }
        if normalized in headers:
            return True
        for token in headers:
            if normalized.startswith(token) and len(normalized) <= len(token) + 6:
                return True
        return False

    def _is_narrative_desc(self, desc: str) -> bool:
        normalized = normalize_description(desc or "")
        if not normalized:
            return False
        tokens = (
            "ATESTAMOS",
            "CERTIFICAMOS",
            "DECLARAMOS",
            "RESPONSAVEL TECNICO",
            "CAPACIDADE TECNICA",
            "CONSELHO REGIONAL",
            "ENGENHEIRO",
            "CREA",
            "CNPJ",
            "CPF",
            "PREFEITURA",
            "DATA",
        )
        return any(token in normalized for token in tokens)

    def _should_replace_desc(self, current_desc: str, candidate_desc: str) -> bool:
        if not candidate_desc:
            return False
        if self._is_section_header_desc(candidate_desc):
            return False
        current = (current_desc or "").strip()
        candidate = candidate_desc.strip()
        if not current:
            return True
        if self._is_section_header_desc(current):
            return True
        if len(current) < 12:
            return True
        sim = description_similarity(current, candidate)
        if sim < 0.3 and len(candidate) >= len(current) + 8:
            return True
        return False

    def _build_text_item_map(self, items: list) -> dict:
        text_map: Dict[tuple, str] = {}
        for item in items or []:
            key = self._item_key(item)
            if not key:
                continue
            desc = (item.get("descricao") or "").strip()
            if not desc or self._is_section_header_desc(desc) or self._is_narrative_desc(desc):
                continue
            existing = text_map.get(key)
            if not existing or len(desc) > len(existing):
                text_map[key] = desc
        return text_map

    def _apply_text_descriptions(self, servicos: list, text_map: dict) -> int:
        if not servicos or not text_map:
            return 0
        updated = 0
        for servico in servicos:
            key = self._item_key(servico)
            if not key:
                continue
            candidate = text_map.get(key)
            if not candidate:
                continue
            if self._is_narrative_desc(candidate):
                continue
            if self._should_replace_desc(servico.get("descricao"), candidate):
                servico["descricao"] = candidate
                servico["_desc_from_text"] = True
                updated += 1
        return updated

    def _dedupe_restart_prefix_duplicates(self, servicos: list) -> list:
        if not servicos:
            return servicos
        groups: Dict[tuple, list] = {}
        for idx, servico in enumerate(servicos):
            item_val = servico.get("item")
            if not item_val:
                continue
            item_str = str(item_val).strip()
            if not item_str:
                continue
            if item_str.upper().startswith("AD-"):
                continue
            prefix, core = self._split_restart_prefix(item_str)
            code = self._normalize_item_code(core)
            if not code:
                continue
            planilha_id = servico.get("_planilha_id") or 0
            section = servico.get("_section") or ""
            unit = normalize_unit(servico.get("unidade") or "")
            qty = parse_quantity(servico.get("quantidade"))
            if not unit or qty in (None, 0):
                continue
            key = (section, planilha_id, code, unit, qty)
            groups.setdefault(key, []).append((idx, servico, prefix))

        to_drop = set()
        for key, entries in groups.items():
            if len(entries) < 2:
                continue
            prefixes = {entry[2] for entry in entries}
            if len(prefixes) < 2:
                continue

            def score(entry: tuple) -> float:
                _, servico, prefix = entry
                desc = (servico.get("descricao") or "").strip()
                score_val = 0.0
                if desc:
                    score_val += min(len(desc), 120)
                    if not self._is_section_header_desc(desc):
                        score_val += 10
                if servico.get("_desc_from_text"):
                    score_val += 6
                if servico.get("_source") in ("text_section", "text_line"):
                    score_val += 4
                if servico.get("_desc_recovered"):
                    score_val -= 8
                segment_num = 1
                if prefix:
                    try:
                        segment_num = int(prefix[1:])
                    except ValueError:
                        segment_num = 1
                score_val -= segment_num * 0.01
                return score_val

            best = max(entries, key=score)
            for entry in entries:
                if entry is best:
                    continue
                to_drop.add(entry[0])

        if not to_drop:
            return servicos
        return [s for idx, s in enumerate(servicos) if idx not in to_drop]

    def _dedupe_same_code_within_planilha(self, servicos: list) -> list:
        """
        Remove duplicatas de itens com mesmo código dentro da mesma planilha.

        Mantém o item com melhor descrição e dados mais completos.
        """
        if not servicos:
            return servicos

        # Agrupa por (planilha_id, código normalizado)
        groups: Dict[tuple, list] = {}
        for idx, servico in enumerate(servicos):
            item_val = servico.get("item")
            if not item_val:
                continue
            item_str = str(item_val).strip()
            if not item_str:
                continue
            # Extrair código sem prefixo
            prefix, core = self._split_restart_prefix(item_str)
            code = self._normalize_item_code(core)
            if not code:
                continue
            planilha_id = servico.get("_planilha_id") or 0
            key = (planilha_id, code)
            groups.setdefault(key, []).append((idx, servico))

        to_drop = set()
        for key, entries in groups.items():
            if len(entries) < 2:
                continue

            # Função de score para escolher o melhor item
            def score(entry: tuple) -> float:
                _, servico = entry
                score_val = 0.0
                # Preferir descrição mais longa e completa
                desc = (servico.get("descricao") or "").strip()
                if desc:
                    score_val += min(len(desc), 150)
                    if not self._is_section_header_desc(desc):
                        score_val += 20
                # Preferir itens com unidade e quantidade
                if servico.get("unidade"):
                    score_val += 10
                if servico.get("quantidade"):
                    score_val += 10
                # Preferir itens do Document AI / tabela
                source = servico.get("_source", "")
                if source in ("document_ai", "table", "pdfplumber"):
                    score_val += 15
                elif source in ("text_section", "text_line"):
                    score_val += 5
                # Preferir itens com página definida
                if servico.get("_page"):
                    score_val += 5
                return score_val

            # Manter o melhor, remover os outros
            best = max(entries, key=score)
            for entry in entries:
                if entry is best:
                    continue
                to_drop.add(entry[0])

        if not to_drop:
            return servicos

        logger.info(f"[DEDUP-CODIGO] {len(to_drop)} itens duplicados removidos por código")
        return [s for idx, s in enumerate(servicos) if idx not in to_drop]

    def _find_unit_qty_in_line(self, line: str) -> Optional[tuple]:
        if not line:
            return None
        pattern = re.compile(r'([\w\u00ba\u00b0/%\u00b2\u00b3\.]+)\s+([\d.,]+)')
        matches = list(pattern.finditer(line))
        if not matches:
            return None
        stop_units = {"DE", "DA", "DO", "EM", "COM", "PARA", "POR", "QUE"}
        allowed_units = set(UNIT_TOKENS) | {"MES"}
        last_valid = None
        for match in matches:
            unit_raw = match.group(1)
            qty_raw = match.group(2)
            qty = parse_quantity(qty_raw)
            if qty in (None, 0):
                continue
            unit_norm = normalize_unit(unit_raw)
            if not unit_norm or unit_norm in ("MM", "CM"):
                continue
            if unit_norm in stop_units:
                continue
            if unit_norm not in allowed_units:
                continue
            last_valid = (unit_norm, qty, match.start(), match.end())
        return last_valid

    def _extract_items_without_codes_from_text(self, texto: str) -> list:
        if not texto:
            return []
        lines = [line.strip() for line in texto.splitlines()]
        anchor_idx = self._find_servicos_anchor_line(lines)
        if anchor_idx is None:
            return []

        items = []
        pending_desc = ""
        last_item = None
        stop_prefixes = (
            "CNPJ",
            "CPF CNPJ",
            "PREFEITURA",
            "CONSELHO REGIONAL",
            "CREA",
            "CEP",
            "E MAIL",
            "EMAIL",
            "TEL",
            "TELEFONE",
            "IMPRESSO",
            "DOCUSIGN",
        )
        footer_tokens = (
            "CNPJ",
            "CPF",
            "PREFEITURA",
            "CONSELHO REGIONAL",
            "CREA",
            "DOCUSIGN",
            "CEP",
            "JOAO PESSOA",
            "ARARUNA",
            "RUA",
            "EMAIL",
            "TEL",
            "IMPRESSO",
            "AGRONOMIA",
        )

        for idx in range(anchor_idx + 1, len(lines)):
            line = lines[idx]
            if not line:
                continue
            normalized = normalize_description(line)
            if not normalized:
                continue
            if normalized.startswith("PAGINA"):
                continue
            if normalized.startswith(stop_prefixes):
                continue
            if "SERVICOS EXECUTADOS" in normalized:
                continue
            if "DESCRICAO" in normalized and "QUANT" in normalized and "UND" in normalized:
                pending_desc = ""
                continue

            unit_match = self._find_unit_qty_in_line(line)
            if unit_match:
                unit, qty, start, end = unit_match
                before = line[:start].strip()
                after = line[end:].strip()
                anchors = [
                    "FORNEC", "LOCAÇÃO", "LOCACAO", "EXECUÇÃO", "EXECUCAO", "ESCAVAÇÃO",
                    "ESCAVACAO", "REATERRO", "LASTRO", "FUNDAÇÃO", "FUNDACAO", "CONCRETO",
                    "ADMINISTRAÇÃO", "ADMINISTRACAO", "MOBILIZAÇÃO", "MOBILIZACAO",
                    "PLACA", "PERFURAÇÃO", "PERFURACAO"
                ]
                if before:
                    upper_before = before.upper()
                    anchor_pos = None
                    for anchor in anchors:
                        pos = upper_before.find(anchor)
                        if pos == -1:
                            continue
                        if anchor_pos is None or pos < anchor_pos:
                            anchor_pos = pos
                    if anchor_pos is not None and anchor_pos > 0:
                        before = before[anchor_pos:].strip()
                        pending_desc = ""
                parts = []
                if pending_desc:
                    parts.append(pending_desc)
                    pending_desc = ""
                if before:
                    parts.append(before)
                if after:
                    parts.append(after)
                desc = " ".join(parts).strip()
                desc = self._strip_footer_prefix_from_desc(desc)
                desc = self._strip_trailing_unit_qty(desc, unit, qty)
                if desc:
                    item = {
                        "item": None,
                        "descricao": desc,
                        "unidade": unit,
                        "quantidade": qty,
                        "_source": "text_no_code"
                    }
                    items.append(item)
                    last_item = item
                continue

            has_footer = False
            for token in footer_tokens:
                if re.search(rf'\\b{re.escape(token)}\\b', normalized):
                    has_footer = True
                    break
            if has_footer:
                pending_desc = ""
                continue

            cont_prefixes = (
                "A ", "DE ", "DO ", "DA ", "DOS ", "DAS ", "COM ", "SEM ", "INCLUINDO",
                "INCLUSIVE", "BORRACHA", "AF_"
            )
            if last_item and line.upper().startswith(cont_prefixes):
                last_desc = (last_item.get("descricao") or "").strip()
                last_item["descricao"] = (last_desc + " " + line).strip() if last_desc else line
                continue

            if not re.search(r'\d', line):
                if len(normalized) <= 40 and line == line.upper():
                    pending_desc = ""
                    continue
            pending_desc = (pending_desc + " " + line).strip() if pending_desc else line

        return items

    def _find_servicos_anchor_line(self, lines: list) -> Optional[int]:
        if not lines:
            return None
        anchors = ("SERVICOS EXECUTADOS", "SERVICOS EXECUTADO")
        for idx, line in enumerate(lines):
            normalized = normalize_description(line)
            if not normalized:
                continue
            for anchor in anchors:
                if anchor in normalized:
                    return idx
        return None

    def _extract_items_from_text_section(self, texto: str, existing_keys: Optional[set] = None) -> list:
        if not texto:
            return []
        lines = [line.strip() for line in texto.splitlines()]
        anchor_idx = self._find_servicos_anchor_line(lines)
        if anchor_idx is None:
            return []

        pattern = re.compile(r'^\s*(\d{1,3}(?:\s*\.\s*\d{1,3}){1,4})\b')
        code_lines = []
        for idx in range(anchor_idx + 1, len(lines)):
            line = lines[idx]
            if not line:
                continue
            match = pattern.match(line)
            if not match:
                continue
            raw_code = match.group(1)
            code = self._normalize_item_code(raw_code)
            if not code:
                continue
            code_lines.append((idx, code, match.end(), line))

        if not code_lines:
            return []

        code_counts = Counter(code for _, code, _, _ in code_lines)
        dup_codes = {code for code, count in code_counts.items() if count > 1}
        dup_ratio = (len(dup_codes) / len(code_counts)) if code_counts else 0.0
        allow_restart = (
            len(code_counts) >= APC.RESTART_MIN_CODES
            and len(dup_codes) >= APC.RESTART_MIN_OVERLAP
            and dup_ratio >= APC.RESTART_MIN_OVERLAP_RATIO
        )
        if not allow_restart:
            logger.info(
                "[TEXTO] restart_prefix desativado no text_section: "
                f"codes={len(code_counts)}, dup_codes={len(dup_codes)}, dup_ratio={dup_ratio:.2f}"
            )

        item_codes = {code for _, code, _, _ in code_lines}
        qty_map = self._extract_quantities_from_text(texto, item_codes)
        if not qty_map:
            return []

        added = []
        qty_remaining = {code: list(entries) for code, entries in qty_map.items()}
        stop_prefixes = (
            "CNPJ",
            "CPF CNPJ",
            "PREFEITURA",
            "CONSELHO REGIONAL",
            "CREA",
            "CEP",
            "E MAIL",
            "EMAIL",
            "TEL",
            "TELEFONE",
            "IMPRESSO",
        )
        segment_index = 1
        max_tuple = None
        for pos, (line_idx, code, code_end, line) in enumerate(code_lines):
            code_tuple = parse_item_tuple(code)
            if allow_restart and code_tuple and max_tuple and code_tuple < max_tuple and code in dup_codes:
                segment_index += 1
            if code_tuple and (max_tuple is None or code_tuple > max_tuple):
                max_tuple = code_tuple
            item_code = f"S{segment_index}-{code}" if segment_index > 1 else code
            unit_qty = None
            line_unit_qty = self._parse_unit_qty_from_line(line)
            if line_unit_qty:
                unit_qty = line_unit_qty
                candidates = qty_remaining.get(code) or []
                for idx, entry in enumerate(candidates):
                    if (
                        isinstance(entry, (tuple, list))
                        and len(entry) >= 2
                        and entry[0] == unit_qty[0]
                        and abs(entry[1] - unit_qty[1]) <= 0.01
                    ):
                        candidates.pop(idx)
                        break
            if not unit_qty:
                candidates = qty_remaining.get(code) or []
                if candidates:
                    unit_qty = candidates.pop(0)
            if not unit_qty or not isinstance(unit_qty, (tuple, list)) or len(unit_qty) < 2:
                continue
            unit, qty = unit_qty[0], unit_qty[1]
            if qty in (None, 0) or not unit:
                continue
            if existing_keys:
                key = (item_code, unit, qty)
                if key in existing_keys:
                    continue

            desc_parts = []
            rest = line[code_end:].strip()
            if rest.startswith("-"):
                rest = rest[1:].strip()
            if rest:
                tokens = rest.split()
                if len(tokens) >= 2:
                    lead_unit = normalize_unit(tokens[0])
                    lead_qty = parse_quantity(tokens[1])
                    if lead_unit == unit and lead_qty == qty:
                        rest = " ".join(tokens[2:]).strip()
                rest = self._strip_trailing_unit_qty(rest, unit, qty)
                if rest:
                    desc_parts.append(rest)

            next_idx = code_lines[pos + 1][0] if pos + 1 < len(code_lines) else len(lines)
            for j in range(line_idx + 1, next_idx):
                cont = lines[j].strip()
                if not cont:
                    continue
                normalized = normalize_description(cont)
                if not normalized:
                    continue
                if normalized.startswith("PAGINA") or normalized.startswith("DOCUSIGN"):
                    continue
                if "SERVICOS EXECUTADOS" in normalized:
                    continue
                if self._is_section_header_desc(cont):
                    break
                if self._is_narrative_desc(cont):
                    break
                if re.match(r'^\d+\s*/\s*\d+$', cont):
                    continue
                if normalized.startswith(stop_prefixes):
                    break
                if re.search(r'\bAF_\d+/\d+\b', cont, re.I):
                    cleaned = self._strip_trailing_unit_qty(cont, unit, qty)
                    if cleaned:
                        desc_parts.append(cleaned)
                    break
                if self._parse_unit_qty_from_line(cont):
                    cleaned = self._strip_trailing_unit_qty(cont, unit, qty)
                    if cleaned and cleaned != cont:
                        desc_parts.append(cleaned)
                    break
                desc_parts.append(cont)
                if sum(len(part) for part in desc_parts) >= APC.TEXT_SECTION_MAX_DESC_LEN:
                    break

            desc = " ".join(desc_parts).strip()
            added.append({
                "item": item_code,
                "descricao": desc,
                "unidade": unit,
                "quantidade": qty,
                "_source": "text_section"
            })

        return added

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
            item_code = self._normalize_item_code(s.get("item"))
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
            item_code = self._normalize_item_code(s.get("item"))
            qty = parse_quantity(s.get("quantidade"))
            if item_code and qty is not None and self._item_qty_matches_code(item_code, qty):
                s["quantidade"] = None
                cleared += 1
        if cleared:
            logger.info(f"[QTY] Quantidades removidas por vazamento de coluna: {cleared} (ratio={ratio:.0%})")
        return cleared

    def _parse_unit_qty_from_line(self, line: str) -> Optional[tuple]:
        tokens = line.split()
        if len(tokens) < 2:
            return None
        last_match = None
        for idx in range(len(tokens) - 1):
            unit_token = tokens[idx]
            raw_unit = re.sub(r'[^A-Za-z0-9]', '', unit_token).upper()
            if raw_unit in ("MM", "CM"):
                continue
            qty_token = tokens[idx + 1]
            if not re.fullmatch(r'[\d.,]+', qty_token):
                continue
            qty = parse_quantity(qty_token)
            if qty in (None, 0):
                continue
            unit_norm = normalize_unit(unit_token)
            if not unit_norm or unit_norm not in UNIT_TOKENS:
                continue
            last_match = (unit_norm, qty)
        return last_match

    def _strip_trailing_unit_qty(
        self,
        text: str,
        unit: Optional[str] = None,
        qty: Optional[float] = None
    ) -> str:
        if not text:
            return text
        match = re.search(r'\b([\w\u00ba\u00b0/%\u00b2\u00b3\.]+)\s+([\d.,]+)\s*$', text)
        if not match:
            return text
        unit_raw = match.group(1)
        qty_raw = match.group(2)
        parsed_qty = parse_quantity(qty_raw)
        if parsed_qty is None:
            return text
        unit_norm = normalize_unit(unit_raw)
        if not unit_norm or unit_norm not in UNIT_TOKENS:
            return text
        if unit:
            unit_expected = normalize_unit(unit)
            if unit_expected and unit_norm != unit_expected:
                return text
        if qty is not None and abs(parsed_qty - qty) > 0.01:
            return text
        return text[:match.start()].strip()

    def _strip_unit_qty_prefix(self, desc: str) -> str:
        """
        Fix B2: Remove prefixo de unidade/quantidade da descrição.

        Exemplo: "UN 1,00 FORNECIMENTO..." -> "FORNECIMENTO..."
        Exemplo: "M 2,05 inclusive roldanas" -> "inclusive roldanas"
        """
        if not desc:
            return desc
        # Padrão: unidade + quantidade no início
        pattern = r'^(UN|M|M2|M3|M²|M³|KG|L|CJ|VB|PC|PÇ|JG|CONJ)\s+[\d.,]+\s+'
        match = re.match(pattern, desc, re.IGNORECASE)
        if match:
            cleaned = desc[match.end():].strip()
            # Garantir que sobrou descrição significativa
            if len(cleaned) >= 5:
                return cleaned
        return desc

    def _extract_hidden_items_from_servicos(self, servicos: list) -> list:
        """
        Fix A3 (pós-processamento): Extrai itens ocultos de descrições.

        Escaneia todas as descrições procurando códigos de item embutidos
        (ex: "TE, PVC... JUNTA 6.14 ELÁSTICA...") e extrai como serviços separados.

        Args:
            servicos: Lista de serviços

        Returns:
            Lista atualizada com itens ocultos extraídos
        """
        from services.extraction import parse_item_tuple, is_valid_item_context

        # Padrão para detectar item oculto no meio do texto
        hidden_pattern = re.compile(
            r'(.{5,}?)\s+(\d{1,2}\.\d{1,2}(?:\.\d{1,2})?)\s+([A-ZÀ-ÚÇ].{10,})',
            re.IGNORECASE
        )

        new_servicos = []
        for servico in servicos:
            desc = servico.get("descricao") or ""
            if len(desc) < 25:
                new_servicos.append(servico)
                continue

            match = hidden_pattern.search(desc)
            if not match:
                new_servicos.append(servico)
                continue

            prefix = match.group(1).strip()
            hidden_code = match.group(2)
            suffix = match.group(3).strip()

            # Verificar contexto
            if not is_valid_item_context(desc, match.start(2)):
                new_servicos.append(servico)
                continue

            # Verificar se o código é válido
            hidden_tuple = parse_item_tuple(hidden_code)
            if not hidden_tuple:
                new_servicos.append(servico)
                continue

            # Atualizar descrição do serviço original com o prefix
            servico["descricao"] = prefix

            # Criar novo serviço para o item oculto
            hidden_servico = {
                "item": hidden_code,
                "descricao": suffix,
                "unidade": None,
                "quantidade": None,
                "_planilha_id": servico.get("_planilha_id"),
                "_page": servico.get("_page"),
                "_hidden_from": servico.get("item"),
            }

            new_servicos.append(servico)
            new_servicos.append(hidden_servico)
            logger.info(f"[HIDDEN-ITEM] Extraído item oculto {hidden_code} de {servico.get('item')}")

        return new_servicos

    def _strip_footer_prefix_from_desc(self, desc: str) -> str:
        if not desc:
            return desc
        upper = desc.upper()
        anchors = [
            "FORNEC", "LOCAÇÃO", "LOCACAO", "EXECUÇÃO", "EXECUCAO", "ESCAVAÇÃO",
            "ESCAVACAO", "REATERRO", "LASTRO", "FUNDAÇÃO", "FUNDACAO", "CONCRETO",
            "ADMINISTRAÇÃO", "ADMINISTRACAO", "MOBILIZAÇÃO", "MOBILIZACAO",
            "PLACA", "PERFURAÇÃO", "PERFURACAO"
        ]
        anchor_pos = None
        for anchor in anchors:
            pos = upper.find(anchor)
            if pos == -1:
                continue
            if anchor_pos is None or pos < anchor_pos:
                anchor_pos = pos
        if anchor_pos is None or anchor_pos == 0:
            return desc

        prefix = upper[:anchor_pos]
        prefix_norm = normalize_description(prefix)
        if re.search(r'\b\d{2,4}/\d{2}/\d{2}\b', prefix_norm):
            return desc[anchor_pos:].strip()
        footer_tokens = (
            "AV", "RUA", "CEP", "CREA", "CONSELHO", "PREFEITURA", "JOAO PESSOA",
            "ARARUNA", "CNPJ", "DOCUSIGN", "EMAIL", "TEL", "IMPRESSO", "AGRONOMIA"
        )
        for token in footer_tokens:
            if re.search(rf'\b{re.escape(token)}\b', prefix_norm):
                return desc[anchor_pos:].strip()
        return desc

    def _extract_quantities_from_text(self, texto: str, item_codes: set) -> dict:
        if not texto or not item_codes:
            return {}
        pattern = re.compile(r'(\d{1,3}(?:\s*\.\s*\d{1,3}){1,4})(?!\s*/\s*\d)')
        qty_map: Dict[str, list] = {}
        current_code = None
        pending_unit = None
        next_line_qty_hits = 0

        def add_qty(code: str, unit_qty: tuple) -> None:
            qty_map.setdefault(code, []).append(unit_qty)

        def find_unit_in_text(segment: str) -> Optional[str]:
            for token in reversed(re.findall(r'[\w\u00ba\u00b0/%\u00b2\u00b3\.]+', segment)):
                unit_norm = normalize_unit(token)
                if unit_norm and unit_norm in UNIT_TOKENS:
                    return unit_norm
            return None

        def find_last_qty(line: str) -> Optional[float]:
            for token in reversed(re.findall(r'[\d.,]+', line)):
                qty = parse_quantity(token)
                if qty in (None, 0):
                    continue
                return qty
            return None

        for raw_line in texto.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            any_code_match = bool(pattern.search(line))
            raw_matches = list(pattern.finditer(line))
            matches: List[tuple[int, int, str]] = []
            for match in raw_matches:
                raw_code = re.sub(r'\s+', '', match.group(1))
                code = self._normalize_item_code(raw_code)
                if code and code in item_codes:
                    matches.append((match.start(), match.end(), code))
            if matches:
                if current_code:
                    prefix = line[:matches[0][0]].strip()
                    if prefix:
                        parsed = self._parse_unit_qty_from_line(prefix)
                        if parsed:
                            add_qty(current_code, parsed)
                            current_code = None
                            pending_unit = None
                        elif pending_unit:
                            qty = find_last_qty(prefix)
                            if qty is not None:
                                add_qty(current_code, (pending_unit, qty))
                                next_line_qty_hits += 1
                                current_code = None
                                pending_unit = None

                current_code = None
                pending_unit = None
                last_unfilled = None
                for idx, item_match in enumerate(matches):
                    start = item_match[0]
                    end = matches[idx + 1][0] if idx + 1 < len(matches) else len(line)
                    segment = line[start:end].strip()
                    code = item_match[2]
                    parsed = self._parse_unit_qty_from_line(segment)
                    if parsed:
                        add_qty(code, parsed)
                        continue
                    unit_norm = find_unit_in_text(segment)
                    if unit_norm:
                        pending_unit = unit_norm
                    last_unfilled = code
                if last_unfilled:
                    current_code = last_unfilled
                continue

            if current_code:
                if any_code_match:
                    current_code = None
                    pending_unit = None
                    continue

                parsed = self._parse_unit_qty_from_line(line)
                if parsed:
                    add_qty(current_code, parsed)
                    current_code = None
                    pending_unit = None
                    continue

                if pending_unit:
                    qty = find_last_qty(line)
                    if qty is not None:
                        add_qty(current_code, (pending_unit, qty))
                        next_line_qty_hits += 1
                        current_code = None
                        pending_unit = None
                        continue

                if not re.search(r'\d', line):
                    unit_norm = normalize_unit(line)
                    if unit_norm and unit_norm in UNIT_TOKENS:
                        pending_unit = unit_norm
                        continue

        if next_line_qty_hits:
            logger.info(f"[QTY] Quantidades detectadas em linha seguinte: {next_line_qty_hits}")
        return qty_map

    def _backfill_quantities_from_text(self, servicos: list, texto: str) -> int:
        if not servicos or not texto:
            return 0
        item_codes = {
            self._normalize_item_code(s.get("item"))
            for s in servicos
            if self._normalize_item_code(s.get("item"))
        }
        if not item_codes:
            return 0

        qty_map = self._extract_quantities_from_text(texto, item_codes)
        if not qty_map:
            return 0
        normalized_map: Dict[str, list] = {}
        for code, entries in qty_map.items():
            if isinstance(entries, list):
                normalized_map[code] = list(entries)
            else:
                normalized_map[code] = [entries]

        # Remover quantidades já presentes para evitar reuse em códigos duplicados
        for s in servicos:
            code = self._normalize_item_code(s.get("item"))
            if not code or code not in normalized_map:
                continue
            qty = parse_quantity(s.get("quantidade"))
            if qty in (None, 0):
                continue
            unit = normalize_unit(s.get("unidade") or "")
            entries = normalized_map.get(code) or []
            idx = None
            if unit:
                for i, (u, q) in enumerate(entries):
                    if u == unit and abs(q - qty) <= 0.01:
                        idx = i
                        break
            if idx is None:
                for i, (u, q) in enumerate(entries):
                    if abs(q - qty) <= 0.01:
                        idx = i
                        break
            if idx is not None:
                entries.pop(idx)

        updated = 0
        for s in servicos:
            code = self._normalize_item_code(s.get("item"))
            if not code or code not in normalized_map:
                continue
            if parse_quantity(s.get("quantidade")) not in (None, 0):
                continue
            entries = normalized_map.get(code) or []
            if not entries:
                continue
            unit_expected = normalize_unit(s.get("unidade") or "")
            idx = None
            if unit_expected:
                for i, (u, q) in enumerate(entries):
                    if u == unit_expected:
                        idx = i
                        break
            if idx is None:
                idx = 0
            unit, qty = entries.pop(idx)
            s["quantidade"] = qty
            if not s.get("unidade") and unit:
                s["unidade"] = unit
            updated += 1

        if updated:
            logger.info(f"[QTY] Quantidades preenchidas do texto: {updated}")
        return updated

    def _refine_item_codes_from_text(
        self,
        servicos: list,
        text_items: list,
        text_codes: Optional[list] = None
    ) -> int:
        if not servicos or (not text_items and not text_codes):
            return 0

        candidates_by_prefix: Dict[str, list] = {}
        for item in text_items or []:
            code = self._normalize_item_code(item.get("item"))
            if not code:
                continue
            parts = code.split(".")
            if len(parts) < 3:
                continue
            prefix = ".".join(parts[:-1])
            desc = (item.get("descricao") or "").strip()
            unit = normalize_unit(item.get("unidade") or "")
            qty = parse_quantity(item.get("quantidade"))
            candidates_by_prefix.setdefault(prefix, []).append({
                "code": code,
                "desc": desc,
                "unit": unit,
                "qty": qty,
            })

        updated = 0
        used_codes = {
            self._normalize_item_code(s.get("item"))
            for s in servicos
            if self._normalize_item_code(s.get("item"))
        }
        score_threshold = 0.55
        sim_floor = 0.2

        processed_prefixes = set()
        if text_codes:
            ordered_by_prefix: Dict[str, list] = {}
            for code in text_codes:
                normalized = self._normalize_item_code(code)
                if not normalized:
                    continue
                parts = normalized.split(".")
                if len(parts) < 3:
                    continue
                prefix = ".".join(parts[:-1])
                ordered_by_prefix.setdefault(prefix, []).append(normalized)

            for prefix, codes in ordered_by_prefix.items():
                prefix_indices = [
                    idx for idx, s in enumerate(servicos)
                    if self._normalize_item_code(s.get("item")) == prefix
                ]
                if not prefix_indices or len(codes) < 2:
                    continue
                if len(codes) != len(prefix_indices):
                    continue
                if any(code in used_codes for code in codes):
                    continue
                for idx, code in zip(prefix_indices, codes):
                    servicos[idx]["item"] = code
                    used_codes.add(code)
                    updated += 1
                processed_prefixes.add(prefix)

        for prefix, candidates in candidates_by_prefix.items():
            if prefix in processed_prefixes:
                continue
            prefix_indices = [
                idx for idx, s in enumerate(servicos)
                if self._normalize_item_code(s.get("item")) == prefix
            ]
            if not prefix_indices:
                continue

            pairs = []
            for idx in prefix_indices:
                servico = servicos[idx]
                serv_desc = (servico.get("descricao") or "").strip()
                serv_unit = normalize_unit(servico.get("unidade") or "")
                serv_qty = parse_quantity(servico.get("quantidade"))
                for cand in candidates:
                    if cand["code"] in used_codes:
                        continue
                    sim = description_similarity(serv_desc, cand["desc"])
                    unit_match = bool(serv_unit and cand["unit"] and serv_unit == cand["unit"])
                    qty_match = False
                    if serv_qty is not None and cand["qty"] is not None:
                        if serv_qty != 0 and cand["qty"] != 0:
                            diff = abs(serv_qty - cand["qty"])
                            denom = max(abs(serv_qty), abs(cand["qty"]))
                            if denom > 0:
                                qty_match = (diff / denom) <= 0.02 or diff <= 0.01
                    score = sim
                    if unit_match:
                        score += 0.2
                    if qty_match:
                        score += 0.2
                    if serv_desc and cand["desc"]:
                        serv_upper = serv_desc.upper()
                        cand_upper = cand["desc"].upper()
                        if cand_upper in serv_upper or serv_upper in cand_upper:
                            score += 0.1
                    if score < score_threshold:
                        if sim < sim_floor and not (unit_match and qty_match):
                            continue
                    pairs.append((score, sim, idx, cand["code"]))

            if not pairs:
                continue
            pairs.sort(key=lambda x: (-x[0], -x[1]))

            used_indices = set()
            for score, sim, idx, code in pairs:
                if idx in used_indices or code in used_codes:
                    continue
                servicos[idx]["item"] = code
                used_indices.add(idx)
                used_codes.add(code)
                updated += 1

        return updated

    def _filter_items_not_in_text_or_table(
        self,
        servicos: list,
        texto: str,
        servicos_table: list
    ) -> list:
        if not servicos or not texto:
            return servicos

        table_items = set()
        for s in servicos_table or []:
            code = self._normalize_item_code(s.get("item"))
            if code:
                table_items.add(code)

        filtered = []
        removed = []
        for s in servicos:
            item = s.get("item")
            code = self._normalize_item_code(item)
            if not code:
                filtered.append(s)
                continue
            if self._item_code_in_text(code, texto):
                filtered.append(s)
                continue
            removed.append((item, s.get("descricao"), code in table_items))

        if removed:
            logger.info(
                f"[FILTRO] Removendo {len(removed)} itens sem codigo no texto"
            )
            for item, desc, in_table in removed:
                desc_preview = (desc or "")[:60]
                origem = "tabela" if in_table else "ia"
                logger.info(f"[FILTRO] Removido item {item} (origem={origem}): {desc_preview}...")

        return filtered
    def _extract_servicos_from_table(self, table: list, preferred_item_col: Optional[int] = None) -> tuple[list, float, dict]:
        if not table:
            return [], 0.0, {}
        rows = [row for row in table if row and any(str(cell or "").strip() for cell in row)]
        if not rows:
            return [], 0.0, {}
        max_cols = max(len(row) for row in rows)
        normalized_rows = []
        for row in rows:
            padded = list(row) + [""] * (max_cols - len(row))
            normalized_rows.append(padded)

        header_index = detect_header_row(normalized_rows)
        header_map = {"item": None, "descricao": None, "unidade": None, "quantidade": None, "valor": None}
        data_rows = normalized_rows
        if header_index is not None:
            header_map = guess_columns_by_header(normalized_rows[header_index])
            data_rows = normalized_rows[header_index + 1:]

        item_col: Optional[int] = header_map.get("item")
        item_score_data = {"score": 0.0}
        preferred_score_data = None
        preferred_used = False
        if item_col is None and preferred_item_col is not None and preferred_item_col < max_cols:
            col_cells = [row[preferred_item_col] for row in data_rows if preferred_item_col < len(row)]
            preferred_score_data = score_item_column(col_cells, preferred_item_col, max_cols)
            if preferred_score_data["score"] >= APC.ITEM_COL_MIN_SCORE:
                item_col = preferred_item_col
                item_score_data = preferred_score_data
                preferred_used = True

        if item_col is None:
            best_score = 0.0
            best_col = None
            for col in range(max_cols):
                col_cells = [row[col] for row in data_rows if col < len(row)]
                score_data = score_item_column(col_cells, col, max_cols)
                if score_data["score"] > best_score:
                    best_score = score_data["score"]
                    best_col = col
                    item_score_data = score_data
            item_col = best_col
        else:
            col_cells = [row[item_col] for row in data_rows if item_col < len(row)]
            item_score_data = score_item_column(col_cells, item_col, max_cols)

        if header_map.get("item") is None and item_col is not None:
            header_map["item"] = item_col  # type: ignore[assignment]

        col_stats = compute_column_stats(data_rows, max_cols)
        header_map = guess_columns_by_content(data_rows, max_cols, header_map, col_stats)
        header_map = validate_column_mapping(header_map, col_stats)
        header_map = guess_columns_by_content(data_rows, max_cols, header_map, col_stats)
        desc_col = header_map.get("descricao")
        unit_col = header_map.get("unidade")
        qty_col = header_map.get("quantidade")

        servicos = []
        last_item = None
        item_tuples = []
        for row in data_rows:
            cells = [str(cell or "").strip() for cell in row]
            item_val = cells[item_col] if item_col is not None and item_col < len(cells) else ""
            item_tuple = parse_item_tuple(item_val)
            item_col_effective = item_col
            if item_tuple is None:
                for idx, cell in enumerate(cells):
                    if idx == desc_col:
                        continue
                    candidate = parse_item_tuple(cell)
                    if candidate:
                        item_tuple = candidate
                        item_col_effective = idx
                        item_val = cell
                        break
            desc_val = cells[desc_col] if desc_col is not None and desc_col < len(cells) else ""
            unit_val = cells[unit_col] if unit_col is not None and unit_col < len(cells) else ""
            qty_val = cells[qty_col] if qty_col is not None and qty_col < len(cells) else ""

            exclude_cols = {c for c in (item_col_effective, unit_col, qty_col) if c is not None}
            if not desc_val or len(desc_val) < 6:
                desc_val = build_description_from_cells(cells, exclude_cols)

            if unit_val:
                unit_val = normalize_unit(unit_val).strip()

            if item_tuple:
                item_tuples.append(item_tuple)
                item_str = item_tuple_to_str(item_tuple)
                servico = {
                    "item": item_str,
                    "descricao": desc_val.strip(),
                    "unidade": unit_val.strip(),
                    "quantidade": parse_quantity(qty_val)
                }
                servicos.append(servico)
                last_item = servico
            else:
                if last_item:
                    if desc_val:
                        last_item["descricao"] = (str(last_item.get("descricao") or "") + " " + str(desc_val)).strip()
                    if not last_item.get("unidade") and unit_val:
                        last_item["unidade"] = unit_val.strip()
                    if (last_item.get("quantidade") in (None, 0)) and parse_quantity(qty_val) not in (None, 0):
                        last_item["quantidade"] = parse_quantity(qty_val)

        servicos = [s for s in servicos if s.get("descricao")]
        servicos, prefix_info = filter_servicos_by_item_prefix(servicos)
        dominant_len, dominant_len_ratio = dominant_item_length(servicos)
        repair_info = {"applied": False, "repaired": 0}
        if dominant_len == 3 and prefix_info.get("dominant_prefix") is not None:
            servicos, repair_info = repair_missing_prefix(servicos, prefix_info.get("dominant_prefix"))
        servicos, dominant_info = filter_servicos_by_item_length(servicos)
        stats = compute_servicos_stats(servicos)
        seq_ratio = 0.0
        filtered_tuples = []
        for servico in servicos:
            item_value: Any = servico.get("item")
            item_tuple = parse_item_tuple(str(item_value)) if item_value else None
            if item_tuple:
                filtered_tuples.append(item_tuple)
        if len(filtered_tuples) > 1:
            ordered = 0
            total_pairs = 0
            prev = None
            for item_tuple in filtered_tuples:
                if prev is not None:
                    total_pairs += 1
                    if item_tuple >= prev:
                        ordered += 1
                prev = item_tuple
            seq_ratio = ordered / total_pairs if total_pairs else 0.0
        total = max(1, stats.get("total", 0))
        with_qty_ratio = stats.get("with_qty", 0) / total
        with_unit_ratio = stats.get("with_unit", 0) / total
        dominant_ratio = dominant_info.get("ratio", 0.0)
        prefix_ratio = prefix_info.get("ratio", 0.0)
        confidence = (
            0.4 * item_score_data.get("score", 0.0) +
            0.2 * seq_ratio +
            0.2 * with_qty_ratio +
            0.1 * with_unit_ratio +
            0.05 * dominant_ratio +
            0.05 * prefix_ratio
        )
        confidence = max(0.0, min(1.0, round(confidence, 3)))
        debug = {
            "header_index": header_index,
            "columns": header_map,
            "item_col_score": item_score_data,
            "preferred_item_col": preferred_item_col,
            "preferred_item_score": preferred_score_data,
            "preferred_item_used": preferred_used,
            "seq_ratio": round(seq_ratio, 3),
            "prefix_item": prefix_info,
            "dominant_item": dominant_info,
            "prefix_repair": repair_info,
            "stats": stats,
            "confidence": confidence
        }
        return servicos, confidence, debug

    def _extract_servicos_from_tables(self, file_path: str) -> tuple[list, float, dict]:
        try:
            tables = pdf_extractor.extract_tables(file_path)
        except (PDFError, IOError, ValueError) as exc:
            logger.warning(f"Erro ao extrair tabelas: {exc}")
            return [], 0.0, {"error": str(exc)}
        if not tables:
            return [], 0.0, {"tables": 0}

        # Combinar servicos de TODAS as tabelas (não apenas a melhor)
        all_servicos: list = []
        all_confidences: list = []
        best_debug: dict = {}
        item_counts: dict[str, int] = {}  # Contador de ocorrências de cada item

        for table in tables:
            servicos, confidence, debug = self._extract_servicos_from_table(table)
            if servicos:
                all_confidences.append(confidence)
                if not best_debug or confidence > best_debug.get("confidence", 0):
                    best_debug = debug

                # Adicionar serviços - NÃO prefixar aqui; o prefixo de reinício
                # é aplicado posteriormente no processamento de aditivo/segmentos.
                for s in servicos:
                    item = s.get("item", "")
                    if item:
                        count = item_counts.get(item, 0)
                        if count == 0:
                            # Primeira ocorrência - manter item original
                            item_counts[item] = 1
                            all_servicos.append(s)
                        else:
                            # Item duplicado - manter sem prefixo aqui
                            # O prefixo de reinício será aplicado por _prefix_aditivo_items
                            item_counts[item] = count + 1
                            all_servicos.append(s)
                    else:
                        # Item sem número - adicionar diretamente
                        all_servicos.append(s)

        # Calcular confidence média
        avg_confidence = sum(all_confidences) / len(all_confidences) if all_confidences else 0.0
        best_debug["tables"] = len(tables)
        best_debug["combined_tables"] = len([c for c in all_confidences if c > 0])

        return all_servicos, avg_confidence, best_debug

    def _extract_servicos_from_document_ai(self, file_path: str) -> tuple[list, float, dict]:
        if not document_ai_service.is_configured:
            return [], 0.0, {"enabled": False, "error": "not_configured"}
        try:
            result = document_ai_service.extract_tables(file_path)
        except (AzureAPIError, IOError, ValueError) as exc:
            logger.warning(f"Erro no Document AI: {exc}")
            return [], 0.0, {"error": str(exc)}

        tables = result.get("tables") or []
        if not tables:
            return [], 0.0, {"tables": 0, "pages": result.get("pages", 0)}

        best: Dict[str, Any] = {"servicos": [], "confidence": 0.0, "debug": {}}
        for table in tables:
            rows = table.get("rows") or []
            servicos, confidence, debug = self._extract_servicos_from_table(rows)
            debug["page"] = table.get("page")
            if confidence > best["confidence"] or (
                confidence == best["confidence"] and len(servicos) > len(best["servicos"])
            ):
                best = {"servicos": servicos, "confidence": confidence, "debug": debug}

        best["debug"]["tables"] = len(tables)
        best["debug"]["pages"] = result.get("pages", 0)
        return best["servicos"], best["confidence"], best["debug"]

    def _choose_best_table(
        self,
        current_servicos: list,
        current_confidence: float,
        current_debug: dict,
        candidate_servicos: list,
        candidate_confidence: float,
        candidate_debug: dict
    ) -> tuple[list, float, dict]:
        if candidate_confidence > current_confidence:
            return candidate_servicos, candidate_confidence, candidate_debug
        if candidate_confidence == current_confidence and len(candidate_servicos) > len(current_servicos):
            return candidate_servicos, candidate_confidence, candidate_debug
        return current_servicos, current_confidence, current_debug

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

    def _analyze_document_type(self, file_path: str) -> dict:
        """
        Analisa o tipo de documento para otimizar o fluxo de extração.

        Returns:
            dict com:
                - is_scanned: bool - documento é escaneado
                - has_image_tables: bool - tem tabelas dentro de imagens
                - total_pages: int
                - avg_chars_per_page: float
                - large_images_count: int
        """
        result = {
            "is_scanned": False,
            "has_image_tables": False,
            "total_pages": 0,
            "avg_chars_per_page": 0.0,
            "large_images_count": 0
        }

        try:
            with pdfplumber.open(file_path) as pdf:
                total_pages = len(pdf.pages)
                total_chars = 0
                total_large_images = 0
                pages_with_tables_in_images = 0

                for page in pdf.pages:
                    text = page.extract_text() or ""
                    chars = len(text.strip())
                    total_chars += chars

                    # Contar imagens grandes (potenciais tabelas escaneadas)
                    large_images = sum(
                        1 for img in page.images
                        if img.get("width", 0) > 400 and img.get("height", 0) > 400
                    )
                    total_large_images += large_images

                    # Página com pouco texto mas com imagem grande = tabela em imagem
                    if chars < APC.SCANNED_MIN_CHARS_PER_PAGE and large_images > 0:
                        pages_with_tables_in_images += 1

                avg_chars = total_chars / total_pages if total_pages > 0 else 0
                image_ratio = total_large_images / total_pages if total_pages > 0 else 0

                result["total_pages"] = total_pages
                result["avg_chars_per_page"] = avg_chars
                result["large_images_count"] = total_large_images

                # Documento escaneado: pouco texto OU muitas imagens grandes
                result["is_scanned"] = (
                    avg_chars < APC.SCANNED_MIN_CHARS_PER_PAGE
                    or (avg_chars < 500 and image_ratio >= APC.SCANNED_IMAGE_PAGE_RATIO)
                )

                # Tem tabelas em imagens: páginas específicas com pouco texto + imagem
                result["has_image_tables"] = pages_with_tables_in_images > 0

                logger.info(
                    f"Análise do documento: {total_pages} páginas, "
                    f"média {avg_chars:.0f} chars/página, "
                    f"{total_large_images} imagens grandes, "
                    f"escaneado={result['is_scanned']}, "
                    f"tabelas_em_imagens={result['has_image_tables']}"
                )

        except Exception as e:
            logger.warning(f"Erro ao analisar documento: {e}")

        return result

    def _median(self, values: list) -> float:
        if not values:
            return 0.0
        sorted_vals = sorted(values)
        mid = len(sorted_vals) // 2
        if len(sorted_vals) % 2 == 1:
            return float(sorted_vals[mid])
        return float(sorted_vals[mid - 1] + sorted_vals[mid]) / 2

    def _build_table_from_ocr_words(self, words: list) -> tuple[list, list]:
        if not words:
            return [], []
        heights = [w["height"] for w in words if w.get("height")]
        widths = [w["width"] for w in words if w.get("width")]
        median_height = self._median(heights) or 12.0
        median_width = self._median(widths) or 40.0
        row_tol = max(6.0, median_height * 0.6)
        col_tol = max(18.0, median_width * 0.7)

        words_sorted = sorted(words, key=lambda w: (w["y_center"], w["x_center"]))
        rows = []
        current = []
        current_y = None
        for word in words_sorted:
            if current_y is None:
                current_y = word["y_center"]
                current = [word]
                continue
            if abs(word["y_center"] - current_y) > row_tol:
                rows.append(current)
                current = [word]
                current_y = word["y_center"]
            else:
                current.append(word)
                current_y = (current_y + word["y_center"]) / 2
        if current:
            rows.append(current)

        centers = sorted(w["x_center"] for w in words)
        clusters: List[Dict[str, Any]] = []
        for center in centers:
            if not clusters:
                clusters.append({"center": center, "values": [center]})
                continue
            if abs(center - clusters[-1]["center"]) > col_tol:
                clusters.append({"center": center, "values": [center]})
            else:
                clusters[-1]["values"].append(center)
                clusters[-1]["center"] = sum(clusters[-1]["values"]) / len(clusters[-1]["values"])

        col_centers = [c["center"] for c in clusters]
        col_centers.sort()

        table_rows = []
        for row in rows:
            cells = [""] * len(col_centers)
            for word in sorted(row, key=lambda w: w["x_center"]):
                distances = [abs(word["x_center"] - c) for c in col_centers]
                if not distances:
                    continue
                col_idx = distances.index(min(distances))
                if cells[col_idx]:
                    cells[col_idx] = f"{cells[col_idx]} {word['text']}".strip()
                else:
                    cells[col_idx] = word["text"]
            if any(cells):
                table_rows.append(cells)
        return table_rows, col_centers

    def _infer_item_column_from_words(self, words: list, col_centers: list) -> tuple[Optional[int], dict]:
        if not words or not col_centers:
            return None, {}

        min_ratio = APC.ITEM_COL_RATIO
        max_x_ratio = APC.ITEM_COL_MAX_X_RATIO
        max_index = APC.ITEM_COL_MAX_INDEX
        min_count = APC.ITEM_COL_MIN_COUNT

        min_x = min(w["x0"] for w in words)
        max_x = max(w["x1"] for w in words)
        span = max(1.0, max_x - min_x)

        counts = [0] * len(col_centers)
        total_candidates = 0
        for word in words:
            item_tuple = parse_item_tuple(word.get("text"))
            if not item_tuple:
                continue
            total_candidates += 1
            distances = [abs(word["x_center"] - c) for c in col_centers]
            if not distances:
                continue
            col_idx = distances.index(min(distances))
            counts[col_idx] += 1

        if total_candidates == 0:
            return None, {"item_col_counts": counts}

        best_idx = counts.index(max(counts))
        ratio = counts[best_idx] / max(1, total_candidates)
        x_ratio = (col_centers[best_idx] - min_x) / span
        debug = {
            "item_col_counts": counts,
            "item_col_ratio": round(ratio, 3),
            "item_col_x_ratio": round(x_ratio, 3),
            "item_col_best": best_idx
        }
        if best_idx > max_index or x_ratio > max_x_ratio:
            return None, debug
        if ratio < min_ratio and counts[best_idx] < min_count:
            return None, debug
        return best_idx, debug

    def _extract_servicos_from_ocr_layout(
        self,
        file_path: str,
        progress_callback=None,
        cancel_check=None
    ) -> tuple[list, float, dict]:
        min_conf = APC.OCR_LAYOUT_CONFIDENCE
        dpi = APC.OCR_LAYOUT_DPI
        page_min_items = APC.OCR_LAYOUT_PAGE_MIN_ITEMS

        images = []
        file_ext = Path(file_path).suffix.lower()
        if file_ext == ".pdf":
            images = self._pdf_to_images(
                file_path,
                dpi=dpi,
                progress_callback=progress_callback,
                cancel_check=cancel_check,
                stage="ocr"
            )
        else:
            with open(file_path, "rb") as f:
                images = [f.read()]

        if not images:
            return [], 0.0, {"pages": 0}

        table_pages = self._detect_table_pages(images)
        if table_pages:
            page_queue = list(dict.fromkeys(table_pages))
            page_seen = set(page_queue)
        else:
            page_queue = list(range(len(images)))
            page_seen = set(page_queue)
        processed_pages = []

        total_items = 0
        weighted_conf = 0.0
        all_servicos = []
        page_debug = []

        while page_queue:
            page_index = page_queue.pop(0)
            self._check_cancel(cancel_check)
            image_bytes = images[page_index]
            cropped = self._crop_region(image_bytes, 0.05, 0.15, 0.95, 0.92)
            try:
                words = ocr_service.extract_words_from_bytes(cropped, min_confidence=min_conf)
            except OCRError as exc:
                logger.debug(f"Erro OCR na pagina {page_index + 1}: {exc}")
                page_debug.append({"page": page_index + 1, "error": str(exc)})
                continue

            table_rows, col_centers = self._build_table_from_ocr_words(words)
            preferred_item_col, item_col_debug = self._infer_item_column_from_words(words, col_centers)
            servicos, confidence, debug = self._extract_servicos_from_table(
                table_rows,
                preferred_item_col=preferred_item_col
            )
            stats = debug.get("stats") or {}
            dominant = debug.get("dominant_item") or {}
            total_page_items = stats.get("total", 0)
            item_ratio = stats.get("with_item", 0) / max(1, total_page_items)
            unit_ratio = stats.get("with_unit", 0) / max(1, total_page_items)
            dominant_len = dominant.get("dominant_len", 0) or 0

            primary_accept = (
                total_page_items > 0
                and dominant_len >= APC.OCR_PAGE_MIN_DOMINANT_LEN
                and item_ratio >= APC.OCR_PAGE_MIN_ITEM_RATIO
                and unit_ratio >= APC.OCR_PAGE_MIN_UNIT_RATIO
            )
            fallback_accept = (
                total_page_items >= APC.OCR_PAGE_MIN_ITEMS
                and dominant_len == 1
                and item_ratio >= APC.OCR_PAGE_FALLBACK_ITEM_RATIO
                and unit_ratio >= APC.OCR_PAGE_FALLBACK_UNIT_RATIO
            )
            page_accept = primary_accept or fallback_accept
            debug.update({
                "page": page_index + 1,
                "row_count": len(table_rows),
                "word_count": len(words),
                "item_col": item_col_debug,
                "page_accept": page_accept
            })
            page_debug.append(debug)
            processed_pages.append(page_index)
            if not page_accept:
                continue

            if servicos:
                all_servicos.extend(servicos)
                total_items += len(servicos)
                weighted_conf += confidence * len(servicos)
                if table_pages and len(servicos) >= page_min_items:
                    for neighbor in (page_index - 1, page_index + 1):
                        if 0 <= neighbor < len(images) and neighbor not in page_seen:
                            page_seen.add(neighbor)
                            page_queue.append(neighbor)

        overall_conf = (weighted_conf / total_items) if total_items else 0.0
        return all_servicos, round(overall_conf, 3), {
            "pages": len(processed_pages),
            "pages_used": sorted(set(processed_pages)),
            "page_debug": page_debug
        }

    def _select_primary_source(self, vision_stats: dict, ocr_stats: dict, vision_score: float, ocr_score: float) -> str:
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

    def _crop_region(self, image_bytes: bytes, left: float, top: float, right: float, bottom: float) -> bytes:
        """Delega recorte de imagem ao PDFExtractionService."""
        return pdf_extraction_service.crop_region(image_bytes, left, top, right, bottom)

    def _resize_image_bytes(self, image_bytes: bytes, scale: float = 0.5) -> bytes:
        """Delega redimensionamento de imagem ao PDFExtractionService."""
        return pdf_extraction_service.resize_image(image_bytes, scale)

    def _detect_table_pages(self, images: List[bytes]) -> List[int]:
        """Delega detecção de páginas com tabelas ao PDFExtractionService."""
        return pdf_extraction_service.detect_table_pages(images)

    def _extract_servicos_pagewise(self, images: List[bytes], progress_callback=None, cancel_check=None) -> List[dict]:
        servicos: List[Dict[str, Any]] = []
        total_pages = len(images)
        if total_pages == 0:
            return servicos
        table_pages = self._detect_table_pages(images)
        page_indexes = table_pages if table_pages else list(range(total_pages))
        total = len(page_indexes)
        logger.info(f"Pagewise: processando {total} paginas de {total_pages} - indices: {page_indexes}")
        for idx, page_index in enumerate(page_indexes):
            self._check_cancel(cancel_check)
            self._notify_progress(progress_callback, idx + 1, total, "ia", f"Analisando pagina {page_index + 1} de {total_pages} com IA")
            image_bytes = images[page_index]
            cropped = self._crop_region(image_bytes, 0.05, 0.15, 0.95, 0.92)
            try:
                result = ai_provider.extract_atestado_from_images([cropped], provider="openai")
                page_servicos = result.get("servicos", []) if isinstance(result, dict) else []
                logger.info(f"Pagewise: pagina {page_index + 1} extraiu {len(page_servicos)} servicos")
                for s in page_servicos:
                    logger.debug(f"  Item: {s.get('item', '?')}: {s.get('descricao', '')[:50]}")
                servicos.extend(page_servicos)
            except (OpenAIError, ValueError, KeyError) as exc:
                logger.warning(f"Erro na IA por pagina {page_index + 1}: {exc}")
        logger.info(f"Pagewise: total extraido = {len(servicos)} servicos")
        return servicos

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

    def _dedupe_no_code_by_desc_unit(self, servicos: list) -> list:
        if not servicos:
            return servicos

        deduped: Dict[str, Any] = {}
        extras = []

        def score(item: dict) -> int:
            score_val = len((item.get("descricao") or "").strip())
            if parse_quantity(item.get("quantidade")) not in (None, 0):
                score_val += 50
            if item.get("unidade"):
                score_val += 10
            return score_val

        for servico in servicos:
            key = self._servico_match_key(servico)
            if not key:
                extras.append(servico)
                continue
            existing = deduped.get(key)
            if not existing or score(servico) > score(existing):
                deduped[key] = servico

        return list(deduped.values()) + extras

    def _prefer_items_with_code(self, servicos: list) -> list:
        if not servicos:
            return servicos if isinstance(servicos, list) else []

        if isinstance(servicos, dict):
            nested = servicos.get("servicos")
            if isinstance(nested, list):
                servicos = nested
            else:
                servicos = [servicos]

        if not isinstance(servicos, list):
            return []

        servicos = [servico for servico in servicos if isinstance(servico, dict)]
        if not servicos:
            return []

        coded = []
        no_code = []
        for servico in servicos:
            item = servico.get("item") or self._extract_item_code(servico.get("descricao") or "")
            if item:
                servico["item"] = item
                coded.append(servico)
            else:
                no_code.append(servico)

        if not coded:
            return self._dedupe_no_code_by_desc_unit(no_code)

        coded_keys = {self._servico_match_key(servico) for servico in coded}
        coded_desc_keys = {self._servico_desc_key(servico) for servico in coded if self._servico_desc_key(servico)}
        coded_entries = [
            {
                "descricao": servico.get("descricao") or "",
                "unidade": normalize_unit(servico.get("unidade") or ""),
                "quantidade": parse_quantity(servico.get("quantidade"))
            }
            for servico in coded
        ]
        similarity_threshold = APC.DESC_SIM_THRESHOLD

        filtered_no_code = [
            servico for servico in no_code
            if self._servico_match_key(servico) not in coded_keys
            and self._servico_desc_key(servico) not in coded_desc_keys
        ]
        refined_no_code = []
        for servico in filtered_no_code:
            desc = servico.get("descricao") or ""
            unit = normalize_unit(servico.get("unidade") or "")
            qty = parse_quantity(servico.get("quantidade"))
            drop = False
            for coded_entry in coded_entries:
                coded_desc = str(coded_entry.get("descricao") or "")
                if description_similarity(desc, coded_desc) < similarity_threshold:
                    continue
                unit_match = bool(unit and coded_entry["unidade"] and unit == coded_entry["unidade"])
                qty_match = False
                coded_qty = coded_entry.get("quantidade")
                if qty is not None and coded_qty is not None and isinstance(qty, (int, float)) and isinstance(coded_qty, (int, float)) and qty != 0 and coded_qty != 0:
                    diff = abs(qty - coded_qty)
                    denom = max(abs(qty), abs(coded_qty))
                    if denom > 0:
                        qty_match = (diff / denom) <= 0.02 or diff <= 0.01
                if unit_match or qty_match:
                    drop = True
                    break
            if not drop:
                refined_no_code.append(servico)

        refined_no_code = self._dedupe_no_code_by_desc_unit(refined_no_code)
        return coded + refined_no_code

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

    # ========================================================================
    # Métodos auxiliares para process_atestado (divididos para legibilidade)
    # ========================================================================

    def _extract_texto_from_file(
        self,
        file_path: str,
        file_ext: str,
        progress_callback=None,
        cancel_check=None
    ) -> str:
        """
        Extrai texto do arquivo (PDF ou imagem) usando OCR quando necessário.

        Args:
            file_path: Caminho para o arquivo
            file_ext: Extensão do arquivo (ex: ".pdf", ".png")
            progress_callback: Callback para progresso
            cancel_check: Função para verificar cancelamento

        Returns:
            Texto extraído do documento

        Raises:
            PDFError, OCRError, UnsupportedFileError, TextExtractionError
        """
        texto = ""

        if file_ext == ".pdf":
            try:
                texto = self._extract_pdf_with_ocr_fallback(
                    file_path,
                    progress_callback=progress_callback,
                    cancel_check=cancel_check
                )
            except (PDFError, TextExtractionError) as e:
                logger.warning(f"Fallback para OCR apos erro: {e}")
                try:
                    images = pdf_extractor.pdf_to_images(file_path)
                    texto = self._ocr_image_list(
                        images,
                        progress_callback=progress_callback,
                        cancel_check=cancel_check
                    )
                except (PDFError, OCRError) as e2:
                    raise PDFError("processar", f"{e} / OCR: {e2}")
        elif file_ext in [".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif"]:
            try:
                self._check_cancel(cancel_check)
                self._notify_progress(progress_callback, 1, 1, "ocr", "OCR da imagem")
                texto = ocr_service.extract_text_from_image(file_path)
            except (OCRError, IOError) as e:
                raise OCRError(str(e))
        else:
            raise UnsupportedFileError(file_ext)

        if not texto.strip():
            raise TextExtractionError("documento")

        return texto

    def _extract_servicos_from_all_tables(
        self,
        file_path: str,
        file_ext: str,
        progress_callback=None,
        cancel_check=None
    ) -> tuple[list, float, dict, dict]:
        """
        Extrai serviços de tabelas usando fluxo em cascata otimizado.

        Fluxo:
        1. pdfplumber (gratuito) - se qty_ratio >= 70%: SUCESSO
        2. Document AI (~R$0.008/pág) - se qty_ratio >= 60%: SUCESSO
        3. OCR Layout removido do fluxo principal (muito lento, baixa qualidade)

        Args:
            file_path: Caminho para o arquivo
            file_ext: Extensão do arquivo
            progress_callback: Callback para progresso
            cancel_check: Função para verificar cancelamento

        Returns:
            Tupla (servicos, confidence, debug, attempts)
        """
        servicos_table: list = []
        table_confidence = 0.0
        table_debug: dict = {}
        table_attempts: dict = {}

        # Thresholds de qualidade por etapa (baseado apenas em qty_ratio)
        # Nota: não usamos TABLE_MIN_ITEMS pois atestados podem ter apenas 1 item
        stage1_threshold = APC.STAGE1_QTY_THRESHOLD  # 70% para pdfplumber
        stage2_threshold = APC.STAGE2_QTY_THRESHOLD  # 60% para Document AI

        document_ai_enabled = APC.DOCUMENT_AI_ENABLED
        document_ai_ready = document_ai_enabled and document_ai_service.is_configured

        if file_ext == ".pdf":
            # Analisar tipo de documento
            doc_analysis = self._analyze_document_type(file_path)
            table_debug["doc_analysis"] = doc_analysis

            # ============================================================
            # ETAPA 1: pdfplumber (GRATUITO)
            # ============================================================
            logger.info("Cascata Etapa 1: Tentando pdfplumber...")
            pdf_servicos, pdf_conf, pdf_debug = self._extract_servicos_from_tables(file_path)
            pdf_debug["source"] = "pdfplumber"
            pdf_qty_ratio = self._calc_qty_ratio(pdf_servicos)
            table_attempts["pdfplumber"] = {
                "count": len(pdf_servicos),
                "confidence": pdf_conf,
                "qty_ratio": pdf_qty_ratio,
                "debug": self._summarize_table_debug(pdf_debug)
            }

            # Verificar se pdfplumber atende o threshold (apenas qty_ratio)
            if pdf_servicos and pdf_qty_ratio >= stage1_threshold:
                logger.info(
                    f"Cascata: pdfplumber SUCESSO - {len(pdf_servicos)} serviços, "
                    f"qty_ratio={pdf_qty_ratio:.0%} >= {stage1_threshold:.0%}"
                )
                servicos_table = pdf_servicos
                table_confidence = pdf_conf
                table_debug = pdf_debug
                table_debug["cascade_stage"] = 1
                table_debug["cascade_reason"] = "pdfplumber_success"
                return servicos_table, table_confidence, table_debug, table_attempts

            logger.info(
                f"Cascata: pdfplumber insuficiente - {len(pdf_servicos)} serviços, "
                f"qty_ratio={pdf_qty_ratio:.0%} < {stage1_threshold:.0%}"
            )

            # ============================================================
            # ETAPA 2: Document AI (BAIXO CUSTO ~R$0.008/página)
            # ============================================================
            if document_ai_ready:
                logger.info("Cascata Etapa 2: Tentando Document AI...")
                try:
                    doc_servicos, doc_conf, doc_debug = self._extract_servicos_from_document_ai(file_path)
                    doc_debug["source"] = "document_ai"
                    doc_qty_ratio = self._calc_qty_ratio(doc_servicos)
                    table_attempts["document_ai"] = {
                        "count": len(doc_servicos),
                        "confidence": doc_conf,
                        "qty_ratio": doc_qty_ratio,
                        "debug": self._summarize_table_debug(doc_debug)
                    }

                    # Verificar se Document AI atende o threshold (apenas qty_ratio)
                    if doc_servicos and doc_qty_ratio >= stage2_threshold:
                        logger.info(
                            f"Cascata: Document AI SUCESSO - {len(doc_servicos)} serviços, "
                            f"qty_ratio={doc_qty_ratio:.0%} >= {stage2_threshold:.0%}"
                        )
                        servicos_table = doc_servicos
                        table_confidence = doc_conf
                        table_debug = doc_debug
                        table_debug["cascade_stage"] = 2
                        table_debug["cascade_reason"] = "document_ai_success"
                        return servicos_table, table_confidence, table_debug, table_attempts

                    logger.info(
                        f"Cascata: Document AI insuficiente - {len(doc_servicos)} serviços, "
                        f"qty_ratio={doc_qty_ratio:.0%} < {stage2_threshold:.0%}"
                    )

                    # Se Document AI tem melhor qualidade que pdfplumber, usar ele
                    if doc_qty_ratio > pdf_qty_ratio:
                        servicos_table = doc_servicos
                        table_confidence = doc_conf
                        table_debug = doc_debug
                        table_debug["cascade_stage"] = 2
                        table_debug["cascade_reason"] = "document_ai_better"

                except Exception as e:
                    logger.warning(f"Cascata: Document AI falhou - {e}")
                    table_attempts["document_ai"] = {"error": str(e)}
            else:
                logger.info("Cascata: Document AI não disponível")

            # ============================================================
            # FALLBACK: Usar melhor resultado disponível
            # ============================================================
            if not servicos_table and pdf_servicos:
                servicos_table = pdf_servicos
                table_confidence = pdf_conf
                table_debug = pdf_debug
                table_debug["cascade_stage"] = 1
                table_debug["cascade_reason"] = "pdfplumber_fallback"
                logger.info(f"Cascata: Usando pdfplumber como fallback ({len(pdf_servicos)} serviços)")

        elif file_ext in [".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif"]:
            # ============================================================
            # IMAGEM: Ir direto para Document AI
            # ============================================================
            logger.info("Imagem detectada: Usando Document AI diretamente")

            if document_ai_ready:
                try:
                    doc_servicos, doc_conf, doc_debug = self._extract_servicos_from_document_ai(file_path)
                    doc_debug["source"] = "document_ai"
                    doc_qty_ratio = self._calc_qty_ratio(doc_servicos)
                    table_attempts["document_ai"] = {
                        "count": len(doc_servicos),
                        "confidence": doc_conf,
                        "qty_ratio": doc_qty_ratio,
                        "debug": self._summarize_table_debug(doc_debug)
                    }

                    if doc_servicos and doc_qty_ratio >= stage2_threshold:
                        servicos_table = doc_servicos
                        table_confidence = doc_conf
                        table_debug = doc_debug
                        table_debug["cascade_stage"] = 2
                        table_debug["cascade_reason"] = "document_ai_image"
                        logger.info(
                            f"Imagem: Document AI SUCESSO - {len(doc_servicos)} serviços, "
                            f"qty_ratio={doc_qty_ratio:.0%}"
                        )

                except Exception as e:
                    logger.warning(f"Imagem: Document AI falhou - {e}")
                    table_attempts["document_ai"] = {"error": str(e)}
            else:
                logger.warning("Imagem: Document AI não disponível")

        # Adicionar resumo do fluxo
        table_debug["cascade_summary"] = {
            "final_source": table_debug.get("source", "none"),
            "final_stage": table_debug.get("cascade_stage", 0),
            "attempts": list(table_attempts.keys())
        }

        return servicos_table, table_confidence, table_debug, table_attempts

    def _extract_dados_with_ai(
        self,
        file_path: str,
        file_ext: str,
        texto: str,
        use_vision: bool,
        servicos_table: list,
        table_used: bool,
        progress_callback=None,
        cancel_check=None
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
        images: list = []
        vision_reprocessed = False
        vision_score = 0.0
        ocr_score = 0.0
        vision_stats = {"total": 0, "with_item": 0, "with_unit": 0, "with_qty": 0, "duplicate_ratio": 0.0}
        ocr_stats = {"total": 0, "with_item": 0, "with_unit": 0, "with_qty": 0, "duplicate_ratio": 0.0}
        dados_vision = None
        dados_ocr = None
        primary_source = None

        llm_fallback_only = APC.LLM_FALLBACK_ONLY
        use_ai_for_services = not llm_fallback_only or not table_used

        # Método 1: OCR + análise de texto
        pdf_extraction_service._notify_progress(progress_callback, 0, 0, "ia", "Analisando texto com IA")
        pdf_extraction_service._check_cancel(cancel_check)
        dados_ocr = ai_provider.extract_atestado_info(texto)

        # Método 2: Vision (GPT-4o ou Gemini)
        # OTIMIZAÇÃO: Só chamar Vision se precisamos da IA para serviços
        # Quando tabela funciona (use_ai_for_services=False), pular Vision para economizar
        if use_vision and use_ai_for_services:
            try:
                if file_ext == ".pdf":
                    images = self._pdf_to_images(
                        file_path,
                        dpi=300,
                        progress_callback=progress_callback,
                        cancel_check=cancel_check,
                        stage="vision"
                    )
                else:
                    with open(file_path, "rb") as f:
                        self._check_cancel(cancel_check)
                        self._notify_progress(progress_callback, 1, 1, "vision", "Carregando imagem")
                        images = [f.read()]

                self._notify_progress(progress_callback, 0, 0, "ia", "Analisando imagens com IA")
                self._check_cancel(cancel_check)
                dados_vision = ai_provider.extract_atestado_from_images(images)
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

        # Fallback por página com OpenAI quando a qualidade estiver baixa
        pagewise_enabled = APC.PAGEWISE_VISION_ENABLED
        logger.info(f"Pagewise check: enabled={pagewise_enabled}, use_vision={use_vision}, images={len(images) if images else 0}, openai_available={'openai' in ai_provider.available_providers}")
        if pagewise_enabled and use_vision and images and "openai" in ai_provider.available_providers:
            quality_threshold = APC.VISION_QUALITY_THRESHOLD
            min_pages = APC.PAGEWISE_MIN_PAGES
            min_items = APC.PAGEWISE_MIN_ITEMS
            logger.info(f"Pagewise condition: vision_score={vision_score:.2f} < {quality_threshold} OR (pages={len(images)} >= {min_pages} AND items={vision_stats.get('total', 0)} < {min_items})")
            if vision_score < quality_threshold or (len(images) >= min_pages and vision_stats.get("total", 0) < min_items):
                page_servicos = self._extract_servicos_pagewise(images, progress_callback, cancel_check)
                if page_servicos:
                    if dados_vision is None:
                        dados_vision = {
                            "descricao_servico": dados_ocr.get("descricao_servico") if dados_ocr else None,
                            "contratante": dados_ocr.get("contratante") if dados_ocr else None,
                            "data_emissao": dados_ocr.get("data_emissao") if dados_ocr else None,
                            "quantidade": dados_ocr.get("quantidade") if dados_ocr else None,
                            "unidade": dados_ocr.get("unidade") if dados_ocr else None,
                        }
                    dados_vision["servicos"] = page_servicos
                    servicos_vision = filter_summary_rows(page_servicos)
                    vision_stats = compute_servicos_stats(servicos_vision)
                    vision_score = compute_quality_score(vision_stats)
                    vision_reprocessed = True
                    ocr_score = compute_quality_score(ocr_stats)

        # Combinar resultados
        self._notify_progress(progress_callback, 0, 0, "merge", "Consolidando dados extraidos")
        self._check_cancel(cancel_check)

        if dados_vision and dados_ocr:
            primary_source = self._select_primary_source(vision_stats, ocr_stats, vision_score, ocr_score)
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

        # Se tabela foi usada com alta confiança e LLM é apenas fallback, usar tabela
        if table_used and not use_ai_for_services:
            servicos_table_filtered = prefix_aditivo_items(list(servicos_table), texto)

            # Sempre usar tabela quando LLM_FALLBACK_ONLY=True e tabela disponível
            # A tabela estruturada é mais confiável que a IA para extração de itens
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
        servicos = filter_summary_rows(servicos)

        # Fix A3: Extrair itens ocultos de descrições (antes de normalização)
        servicos = self._extract_hidden_items_from_servicos(servicos)

        # Enriquecer com dados da tabela se IA foi usada
        if use_ai and not table_used:
            servicos = self._attach_item_codes_from_table(servicos, servicos_table)
            servicos = self._prefer_items_with_code(servicos)

        # Normalizar cada serviço
        for servico in servicos:
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
            qty = parse_quantity(servico.get("quantidade"))
            if qty is not None:
                servico["quantidade"] = qty
            unit = servico.get("unidade")
            if isinstance(unit, str):
                unit = unit.strip()
                if unit:
                    unit = normalize_unit(unit)
                servico["unidade"] = unit
            desc = servico.get("descricao") or ""
            cleaned_desc = self._strip_trailing_unit_qty(desc, unit, qty)
            if cleaned_desc and cleaned_desc != desc:
                servico["descricao"] = cleaned_desc
            # Fix B2: Remover prefixo UN/QTD da descrição
            desc = servico.get("descricao") or ""
            cleaned_prefix = self._strip_unit_qty_prefix(desc)
            if cleaned_prefix and cleaned_prefix != desc:
                servico["descricao"] = cleaned_prefix

        servicos = self._normalize_restart_prefixes_by_planilha(servicos)
        servicos = self._dedupe_restart_prefix_duplicates(servicos)
        servicos = self._dedupe_same_code_within_planilha(servicos)

        if strict_item_gate:
            servicos = self._filter_items_not_in_text_or_table(servicos, texto, servicos_table)

        # Aplicar filtros
        servicos = filter_classification_paths(servicos)
        if skip_no_code_dedupe:
            com_item = [s for s in servicos if s.get("item")]
            sem_item = [s for s in servicos if not s.get("item")]
            sem_item = self._dedupe_no_code_by_desc_unit(sem_item)
            servicos = com_item + sem_item
        else:
            servicos = remove_duplicate_services(servicos)
        servicos = self._remove_duplicate_pairs(servicos)
        servicos = self._filter_section_headers(servicos)
        servicos = self._filter_items_without_quantity(servicos)
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

    def _improve_short_descriptions(self, items: list, candidates: list) -> list:
        if not items or not candidates:
            return items
        for item in items:
            desc = item.get('descricao', '')
            if not self._is_short_description(desc):
                continue
            better = self._find_better_description(item, candidates)
            if better:
                item['descricao'] = better
        return items

    def _recover_descriptions_from_text(
        self,
        servicos: list,
        texto: str
    ) -> list:
        """
        Recupera descrições ausentes do texto OCR para itens com descrição curta.

        Alguns PDFs têm formato onde a descrição aparece na linha anterior
        ao código do item. Este método tenta recuperar essas descrições.

        Args:
            servicos: Lista de serviços
            texto: Texto OCR extraído

        Returns:
            Lista de serviços com descrições recuperadas
        """

        if not servicos or not texto:
            return servicos

        lines = texto.split('\n')
        line_map = {}

        # Criar mapa de linhas que começam com código de item
        for i, line in enumerate(lines):
            match = re.match(r'^(\d+\.\d+(?:\.\d+)?)\s+', line.strip())
            if match:
                item_code = match.group(1)
                line_map[item_code] = i

        # Para cada serviço com descrição curta, tentar recuperar
        for servico in servicos:
            desc = (servico.get("descricao") or "").strip()
            item_code = servico.get("item")

            # Só processar se descrição curta ou claramente um cabeçalho
            if not item_code:
                continue
            if len(desc) >= 10 and not self._is_section_header_desc(desc):
                continue

            line_idx = line_map.get(str(item_code))
            if line_idx is None or line_idx == 0:
                continue

            # Verificar linha anterior
            prev_line = lines[line_idx - 1].strip()

            # A linha anterior deve ser texto (não um código de item)
            if re.match(r'^(S\d+-)?\d+\.\d+', prev_line):
                continue

            # Ignorar linhas muito curtas ou que são apenas números
            if len(prev_line) < 15:
                continue
            if re.match(r'^[\d\s,\.]+$', prev_line):
                continue
            if self._is_section_header_desc(prev_line):
                continue

            # Ignorar linhas de cabeçalho/rodapé comuns
            skip_patterns = [
                r'^p[áa]gina\s+\d',
                r'^\d+/\d+$',
                r'^af_\d+/\d+$',
            ]
            should_skip = False
            for pattern in skip_patterns:
                if re.match(pattern, prev_line, re.I):
                    should_skip = True
                    break
            if should_skip:
                continue

            # Recuperar descrição da linha anterior
            servico["descricao"] = prev_line
            servico["_desc_recovered"] = True
            logger.debug(f"Recuperada descrição para {item_code}: {prev_line[:50]}...")

        return servicos

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
        self._check_cancel(cancel_check)
        file_ext = Path(file_path).suffix.lower()

        # 1. Extrair texto do documento
        doc_analysis = None
        images = None
        if file_ext == ".pdf":
            doc_analysis = table_extraction_service.analyze_document_type(file_path)
            if isinstance(doc_analysis, dict) and doc_analysis.get("is_scanned"):
                images = self._pdf_to_images(
                    file_path,
                    dpi=300,
                    progress_callback=progress_callback,
                    cancel_check=cancel_check,
                    stage="ocr"
                )
                texto = self._ocr_image_list(images, progress_callback, cancel_check)
            else:
                texto = self._extract_texto_from_file(
                    file_path, file_ext, progress_callback, cancel_check
                )
        else:
            texto = self._extract_texto_from_file(
                file_path, file_ext, progress_callback, cancel_check
            )

        # 2. Extrair serviços de tabelas (múltiplos métodos)
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

        # Determinar se tabela será usada (validação final)
        # Usar threshold mais permissivo na validação final (Stage 3)
        # Nota: não usamos TABLE_MIN_ITEMS pois atestados podem ter apenas 1 item
        min_qty_ratio = APC.STAGE3_QTY_THRESHOLD

        # Calcular qty_ratio
        qty_ratio = table_extraction_service.calc_qty_ratio(servicos_table)

        # Tabela é usada se passou pela cascata com qualidade aceitável
        cascade_stage = table_debug.get("cascade_stage", 0) if isinstance(table_debug, dict) else 0

        # Critério simplificado: apenas qty_ratio
        table_used = bool(servicos_table and qty_ratio >= min_qty_ratio)

        if servicos_table and not table_used:
            logger.info(
                f"Tabela descartada na validação final: {len(servicos_table)} itens, "
                f"qty_ratio={qty_ratio:.2%} < {min_qty_ratio:.0%}, cascade_stage={cascade_stage}"
            )

        if isinstance(table_debug, dict):
            table_debug.setdefault("attempts", table_attempts)

        # 3. Extrair dados com IA (se configurada)
        use_ai = ai_provider.is_configured

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
                images=images
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
        else:
            # IA não configurada - usar apenas tabela
            servicos_table_filtered = prefix_aditivo_items(list(servicos_table), texto) if table_used else []

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

        # 4. Pós-processamento dos serviços
        self._notify_progress(progress_callback, 0, 0, "final", "Finalizando processamento")
        self._check_cancel(cancel_check)

        # Recuperar descrições ausentes do texto OCR
        servicos_raw = dados.get("servicos") or []
        text_items: List[Dict[str, Any]] = []
        itemless_mode = False
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
                text_section_reason = (
                    "strong_table "
                    f"source={source} qty_ratio={qty_ratio:.2f} "
                    f"confidence={table_confidence:.2f} duplicate_ratio={duplicate_ratio:.2f}"
                )
                logger.info(f"[TEXTO] text_section desativado: {text_section_reason}")
        if texto and isinstance(doc_analysis, dict) and not doc_analysis.get("is_scanned") and table_used:
            page_segments = self._split_text_by_pages(texto)
            page_planilha_map, page_planilha_audit = self._build_page_planilha_map(page_segments)
            if page_planilha_map:
                remapped = self._apply_page_planilha_map(servicos_raw, page_planilha_map)
                if remapped:
                    logger.info(f"[TEXTO] Planilha reatribuida por pagina: {remapped} itens")
                if isinstance(dados.get("_debug"), dict):
                    dados["_debug"]["page_planilha"] = {
                        "map": page_planilha_map,
                        "audit": page_planilha_audit
                    }
            text_items = []
            section_items = []
            if page_planilha_map:
                for page_num, page_text in page_segments:
                    planilha_id = page_planilha_map.get(page_num, 0)
                    if not planilha_id:
                        continue
                    page_text_items = self._extract_items_from_text_lines(page_text)
                    page_section_items = (
                        self._extract_items_from_text_section(page_text) if text_section_enabled else []
                    )
                    for item in page_text_items + page_section_items:
                        prefix, core = self._split_restart_prefix(item.get("item"))
                        if prefix:
                            item["item"] = core
                            item.pop("_item_prefix", None)
                        item["_page"] = page_num
                        item["_planilha_id"] = planilha_id
                    text_items.extend(page_text_items)
                    section_items.extend(page_section_items)
            else:
                text_items = self._extract_items_from_text_lines(texto)
                section_items = self._extract_items_from_text_section(texto) if text_section_enabled else []
            text_codes = self._extract_item_codes_from_text_lines(texto)
            updated = self._refine_item_codes_from_text(servicos_raw, text_items, text_codes)
            if updated:
                logger.info(f"[TEXTO] Codigos refinados do texto: {updated}")
            text_candidates = []
            if section_items:
                text_candidates.extend(section_items)
            if text_items:
                text_candidates.extend(text_items)
            prefix_map, unique_prefix_by_code = self._build_restart_prefix_maps(servicos_raw)
            if text_candidates and (prefix_map or unique_prefix_by_code):
                for item in text_candidates:
                    prefix, core = self._split_restart_prefix(item.get("item"))
                    if prefix:
                        continue
                    code = self._normalize_item_code(core)
                    if not code:
                        continue
                    unit = normalize_unit(item.get("unidade") or "")
                    qty = parse_quantity(item.get("quantidade"))
                    mapped = prefix_map.get((code, unit, qty)) or unique_prefix_by_code.get(code)
                    if mapped:
                        item["item"] = f"{mapped}-{code}"
            text_map = self._build_text_item_map(text_candidates)
            enriched = self._apply_text_descriptions(servicos_raw, text_map)
            if enriched:
                logger.info(f"[TEXTO] Descricoes enriquecidas pelo texto: {enriched}")
            existing_index: Dict[tuple, dict] = {}
            existing_keys = set()
            for servico in servicos_raw:
                key = self._item_key(servico)
                if key:
                    existing_keys.add(key)
                    existing_index[key] = servico
            if text_candidates:
                added = 0
                replaced = 0
                for item in text_candidates:
                    key = self._item_key(item)
                    if not key:
                        continue
                    existing = existing_index.get(key)
                    if existing:
                        if self._should_replace_desc(existing.get("descricao") or "", item.get("descricao") or ""):
                            existing["descricao"] = (item.get("descricao") or "").strip()
                            existing["_desc_from_text"] = True
                            replaced += 1
                        continue
                    servicos_raw.append(item)
                    existing_keys.add(key)
                    existing_index[key] = item
                    added += 1
                if added:
                    logger.info(f"[TEXTO] Itens adicionados do texto: {added}")
                if replaced:
                    logger.info(f"[TEXTO] Itens atualizados pelo texto: {replaced}")
            structured_ratio = None
            with_code = [s for s in servicos_raw if s.get("item")]
            if with_code:
                structured = [
                    parse_item_tuple(str(s.get("item")))
                    for s in with_code
                ]
                structured = [t for t in structured if t and len(t) >= 2]
                structured_ratio = len(structured) / len(with_code)
            if structured_ratio is not None and structured_ratio < 0.4:
                itemless_mode = True
                no_code_items = self._extract_items_without_codes_from_text(texto)
                if no_code_items:
                    if len(no_code_items) >= len(servicos_raw):
                        servicos_raw = list(no_code_items)
                        logger.info(f"[TEXTO] Itens sem codigo substituindo tabela: {len(servicos_raw)}")
                    else:
                        existing_keys = set()
                        for existing in servicos_raw:
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
                                servicos_raw.append(item)
                                added_no_code += 1
                        if added_no_code:
                            logger.info(f"[TEXTO] Itens sem codigo adicionados do texto: {added_no_code}")
        if isinstance(dados.get("_debug"), dict):
            dados["_debug"]["text_section"] = {
                "enabled": text_section_enabled,
                "reason": text_section_reason,
                "max_desc_len": APC.TEXT_SECTION_MAX_DESC_LEN,
                "table_confidence_min": APC.TEXT_SECTION_TABLE_CONFIDENCE_MIN,
                "qty_ratio_min": APC.TEXT_SECTION_QTY_RATIO_MIN,
                "dup_ratio_max": APC.TEXT_SECTION_DUP_RATIO_MAX
            }

        cleared = self._clear_item_code_quantities(servicos_raw)
        if texto:
            needs_qty = any(parse_quantity(s.get("quantidade")) in (None, 0) for s in servicos_raw)
            if cleared or needs_qty:
                self._backfill_quantities_from_text(servicos_raw, texto)
        servicos_raw = self._recover_descriptions_from_text(servicos_raw, texto)
        text_item_count = self._count_item_codes_in_text(texto)
        strict_item_gate = bool(texto) and isinstance(doc_analysis, dict) and not doc_analysis.get("is_scanned") and text_item_count >= 5
        if strict_item_gate and table_used and servicos_raw:
            with_code = [s for s in servicos_raw if s.get("item")]
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
                    strict_item_gate = False
        if strict_item_gate and isinstance(table_debug, dict):
            table_source = (table_debug.get("source") or "").lower()
            if table_source and table_source != "pdfplumber":
                logger.info(
                    f"[FILTRO] strict_item_gate desativado: tabela veio de {table_source}"
                )
                strict_item_gate = False

        servicos = self._postprocess_servicos(
            servicos_raw,
            use_ai,
            table_used,
            servicos_table,
            texto,
            strict_item_gate,
            skip_no_code_dedupe=itemless_mode
        )

        dados["servicos"] = servicos
        dados["texto_extraido"] = texto
        return dados

    def process_edital(self, file_path: str, progress_callback=None, cancel_check=None) -> Dict[str, Any]:
        """
        Processa uma página de edital com quantitativos mínimos.

        Args:
            file_path: Caminho para o arquivo PDF

        Returns:
            Dicionário com exigências extraídas
        """
        self._check_cancel(cancel_check)
        self._notify_progress(progress_callback, 0, 0, "texto", "Extraindo texto do edital")
        file_ext = Path(file_path).suffix.lower()
        texto = ""
        tabelas = []

        if file_ext != ".pdf":
            raise UnsupportedFileError("não-PDF", ["PDF"])

        # Extrair conteúdo do PDF
        resultado = pdf_extractor.extract_all(file_path)

        if resultado["tem_texto"]:
            texto = resultado["texto"]
            tabelas = resultado["tabelas"]
        else:
            # PDF escaneado - usar OCR
            try:
                images = pdf_extractor.pdf_to_images(file_path)
                texto = self._ocr_image_list(
                images,
                progress_callback=progress_callback,
                cancel_check=cancel_check
            )
            except (PDFError, OCRError, IOError) as e:
                raise OCRError(str(e))

        if not texto.strip():
            raise TextExtractionError("edital")

        # Combinar texto e tabelas para análise
        texto_completo = texto
        if tabelas:
            texto_completo += "\n\nTABELAS ENCONTRADAS:\n"
            for i, tabela in enumerate(tabelas):
                texto_completo += f"\nTabela {i + 1}:\n"
                for linha in tabela:
                    texto_completo += " | ".join(linha) + "\n"

        # Extrair exigencias com IA
        if ai_provider.is_configured:
            self._notify_progress(progress_callback, 0, 0, "ia", "Analisando exigencias")
            self._check_cancel(cancel_check)
            # Usar OpenAI diretamente para exigências (mais maduro)
            from .ai_analyzer import ai_analyzer
            if ai_analyzer.is_configured:
                exigencias = ai_analyzer.extract_edital_requirements(texto_completo)
            else:
                # Tentar com Gemini
                from .gemini_analyzer import gemini_analyzer
                exigencias = gemini_analyzer.extract_edital_requirements(texto_completo) if gemini_analyzer.is_configured else []
        else:
            exigencias = []

        self._notify_progress(progress_callback, 0, 0, "final", "Finalizando processamento")
        return {
            "texto_extraido": texto,
            "tabelas": tabelas,
            "exigencias": exigencias,
            "paginas": resultado.get("paginas", 1)
        }

    def analyze_qualification(
        self,
        exigencias: List[Dict[str, Any]],
        atestados: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Analisa a qualificação técnica comparando exigências e atestados.

        Args:
            exigencias: Lista de exigências do edital
            atestados: Lista de atestados do usuário

        Returns:
            Resultado da análise com status de atendimento
        """
        return matching_service.match_exigencias(exigencias, atestados)

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
                "enabled": APC.DOCUMENT_AI_ENABLED
            },
            "is_configured": ai_provider.is_configured,
            "mensagem": f"IA configurada ({', '.join(ai_provider.available_providers)})" if ai_provider.is_configured else "Configure OPENAI_API_KEY ou GOOGLE_API_KEY para análise inteligente"
        }


# Instância singleton para uso global
document_processor = DocumentProcessor()
