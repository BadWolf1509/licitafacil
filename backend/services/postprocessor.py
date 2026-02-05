"""
Pós-processamento de serviços extraídos de atestados.

Extraído de document_processor.py para manter cada módulo < 200 linhas.
Contém: normalização de campos, enriquecimento com dados de tabela,
filtros e deduplicação.
"""

from typing import Dict, Any

from .extraction import (
    normalize_unit,
    normalize_desc_for_match,
    description_similarity,
    parse_item_tuple,
    item_tuple_to_str,
    parse_quantity,
    filter_classification_paths,
    remove_duplicate_services,
    filter_summary_rows,
    UNIT_TOKENS,
    extract_item_code,
    split_item_description,
)
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
from config import AtestadoProcessingConfig as APC

from logging_config import get_logger
logger = get_logger('services.postprocessor')


def filter_items_without_code(servicos: list, min_items_with_code: int = APC.PP_MIN_ITEMS_WITH_CODE) -> list:
    """Remove itens sem código quando há itens suficientes com código."""
    if not servicos:
        return servicos

    com_codigo = [s for s in servicos if s.get("item")]
    sem_codigo = [s for s in servicos if not s.get("item")]

    if len(com_codigo) < min_items_with_code:
        return servicos

    if sem_codigo:
        logger.info(f"[FILTRO] Removendo {len(sem_codigo)} itens sem código de item (há {len(com_codigo)} itens com código)")
        for s in sem_codigo:
            desc = (s.get("descricao") or "")[:50]
            logger.info(f"[FILTRO] Removido item sem código: {desc}...")

    return com_codigo


def build_restart_prefix_maps(servicos: list) -> tuple[Dict[tuple, str], Dict[str, str]]:
    """Constrói mapas de prefixos de restart para itens renumerados."""
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


def should_replace_desc(current_desc: str, candidate_desc: str) -> bool:
    """Decide se uma descrição candidata deve substituir a atual."""
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
        return True
    if len(current) < 12:
        return True

    sim = description_similarity(current, candidate)
    if sim < APC.PP_DESC_REPLACE_SIMILARITY:
        if len(candidate) >= APC.PP_MIN_DESC_LEN_FOR_REPLACE:
            return True

    return False


def build_text_item_map(items: list) -> dict:
    """Constrói mapa de descrições extraídas por texto para enriquecimento."""
    text_map: Dict[tuple, str] = {}
    for item in items or []:
        key = helpers_item_key(item)
        if not key:
            continue
        desc = (item.get("descricao") or "").strip()
        if not desc or is_section_header_desc(desc) or is_narrative_desc(desc):
            continue
        if is_contaminated_desc(desc):
            continue
        existing = text_map.get(key)
        if not existing:
            text_map[key] = desc
    return text_map


def apply_text_descriptions(servicos: list, text_map: dict) -> int:
    """Aplica descrições do text_map nos serviços quando apropriado."""
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
        if should_replace_desc(servico.get("descricao"), candidate):
            servico["descricao"] = candidate
            servico["_desc_from_text"] = True
            updated += 1
    return updated


def _table_candidates_by_code(servicos_table: list) -> dict:
    """Indexa candidatos da tabela por código de item normalizado."""
    if not servicos_table:
        return {}
    unit_tokens = UNIT_TOKENS
    candidates: Dict[str, Any] = {}
    for servico in servicos_table:
        item = servico.get("item") or extract_item_code(servico.get("descricao") or "")
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


def attach_item_codes_from_table(servicos: list, servicos_table: list) -> list:
    """Enriquece serviços sem código com códigos de itens da tabela."""
    if not servicos or not servicos_table:
        return servicos
    table_candidates = _table_candidates_by_code(servicos_table)
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
                score += APC.PP_MATCH_SCORE_BOOST
            cand_qty = candidate.get("quantidade")
            if qty is not None and cand_qty is not None and isinstance(qty, (int, float)) and isinstance(cand_qty, (int, float)) and qty != 0 and cand_qty != 0:
                diff = abs(qty - cand_qty)
                denom = max(abs(qty), abs(cand_qty))
                if denom > 0 and (diff / denom) <= APC.PP_QTY_MATCH_TOLERANCE:
                    score += APC.PP_MATCH_SCORE_BOOST
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


def normalize_servicos_fields(servicos: list) -> None:
    """Normaliza campos de cada serviço (item, descricao, quantidade, unidade)."""
    for servico in servicos:
        desc = servico.get("descricao", "")
        existing_item = servico.get("item")
        item, clean_desc = split_item_description(desc)
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
        cleaned_desc = strip_trailing_unit_qty(desc, unit, qty)
        if cleaned_desc and cleaned_desc != desc:
            servico["descricao"] = cleaned_desc

        desc = servico.get("descricao") or ""
        cleaned_prefix = text_processor.strip_unit_qty_prefix(desc)
        if cleaned_prefix and cleaned_prefix != desc:
            servico["descricao"] = cleaned_prefix


def apply_servicos_filters(
    servicos: list,
    texto: str,
    servicos_table: list,
    strict_item_gate: bool,
    skip_no_code_dedupe: bool
) -> list:
    """Aplica filtros finais nos serviços."""
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
    servicos = filter_items_without_code(servicos)

    return servicos


def postprocess_servicos(
    servicos: list,
    use_ai: bool,
    table_used: bool,
    servicos_table: list,
    texto: str,
    strict_item_gate: bool = False,
    skip_no_code_dedupe: bool = False
) -> list:
    """
    Aplica pós-processamento completo nos serviços extraídos.

    Inclui: normalização, filtros, deduplicação, limpeza de códigos.
    """
    servicos = filter_summary_rows(servicos)
    servicos = text_processor.extract_hidden_items_from_servicos(servicos)

    if use_ai and not table_used:
        servicos = attach_item_codes_from_table(servicos, servicos_table)
        servicos = ServiceDeduplicator(servicos).prefer_items_with_code()

    normalize_servicos_fields(servicos)

    servicos = ServiceMerger(servicos).normalize_prefixes()
    servicos = ServiceDeduplicator(servicos).dedupe_by_restart_prefix()
    servicos = ServiceDeduplicator(servicos).dedupe_within_planilha()
    servicos = ServiceDeduplicator(servicos).cleanup_orphan_suffixes()

    servicos = apply_servicos_filters(
        servicos, texto, servicos_table, strict_item_gate, skip_no_code_dedupe
    )

    return servicos
