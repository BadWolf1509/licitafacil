"""
Extrator de servicos usando pdfplumber.

Extrai servicos de tabelas em PDFs usando a biblioteca pdfplumber.
"""

from typing import Any, Dict, List, Optional, Tuple

from exceptions import PDFError
from logging_config import get_logger
from services.extraction import normalize_description, normalize_unit, parse_quantity

logger = get_logger('services.table_extraction.extractors.pdfplumber')


def extract_servicos_from_tables(
    service: Any,
    file_path: str
) -> Tuple[List[Dict], float, Dict]:
    """
    Extrai servicos de todas as tabelas em um PDF usando pdfplumber.

    Args:
        service: Instancia do TableExtractionService para delegar operacoes
        file_path: Caminho para o arquivo PDF

    Returns:
        Tupla (servicos, confidence, debug)
    """
    # Importar aqui para evitar import circular
    from services.pdf_extractor import pdf_extractor

    try:
        tables = pdf_extractor.extract_tables(file_path, include_page=True)
    except (PDFError, IOError, ValueError) as exc:
        logger.warning(f"Erro ao extrair tabelas: {exc}")
        return [], 0.0, {"error": str(exc)}

    if not tables:
        return [], 0.0, {"tables": 0}

    all_servicos: List[Dict] = []
    all_confidences: List[float] = []
    best_debug: Dict[str, Any] = {}
    seen_keys: set = set()
    global_seen_codes: set = set()
    restart_audit: List[Dict] = []
    planilha_audit: List[Dict] = []
    segment_index = 1
    global_max_tuple: Optional[Tuple] = None
    planilha_id = 0
    current_planilha: Optional[Dict] = None

    for table_index, table in enumerate(tables):
        page_number = None
        rows = table
        if isinstance(table, dict):
            rows = table.get("rows") or []
            page_number = table.get("page")

        servicos, confidence, debug = service.extract_servicos_from_table(rows)
        debug["page"] = page_number

        if servicos:
            first_tuple, table_last_tuple = service._first_last_item_tuple(servicos)
            sig_info = service._build_table_signature(rows, debug)
            start_new, planilha_reason = service._should_start_new_planilha(
                current_planilha, sig_info, first_tuple
            )

            if start_new:
                planilha_id += 1
                current_planilha = {
                    "id": planilha_id,
                    "signature": sig_info.get("signature"),
                    "label": sig_info.get("label") or "",
                    "header_like": bool(sig_info.get("header_like")),
                    "tables": [table_index],
                    "pages": [page_number] if page_number is not None else [],
                    "start_reason": planilha_reason,
                    "max_tuple": None,
                    "seen_codes": set(),
                }
                planilha_audit.append({
                    "id": planilha_id,
                    "signature": current_planilha["signature"],
                    "label": current_planilha["label"],
                    "header_like": current_planilha["header_like"],
                    "start_table": table_index,
                    "start_page": page_number,
                    "start_reason": planilha_reason,
                    "tables": [table_index],
                    "pages": [page_number] if page_number is not None else [],
                })
            else:
                if current_planilha:
                    current_planilha["tables"].append(table_index)
                    planilha_audit[-1]["tables"].append(table_index)
                    if page_number is not None:
                        current_planilha["pages"].append(page_number)
                        planilha_audit[-1]["pages"].append(page_number)

            if not current_planilha:
                continue

            debug["planilha"] = {
                "id": current_planilha["id"],
                "signature": sig_info.get("signature"),
                "label": current_planilha["label"],
                "header_like": bool(sig_info.get("header_like")),
                "decision": "new" if start_new else "continue",
                "reason": planilha_reason
            }

            for s in servicos:
                s["_planilha_id"] = current_planilha["id"]
                if current_planilha["label"]:
                    s["_planilha_label"] = current_planilha["label"]
                if page_number is not None:
                    s["_page"] = page_number

            table_codes = service._collect_item_codes(servicos)
            if start_new:
                scope = "global"
                scope_max = global_max_tuple
                scope_seen = global_seen_codes
            else:
                scope = "planilha"
                scope_max = current_planilha.get("max_tuple")
                scope_seen = current_planilha.get("seen_codes", set())

            apply_prefix, audit = service._should_restart_prefix(
                first_tuple, scope_max, table_codes, scope_seen
            )
            audit["scope"] = scope
            audit["planilha_id"] = current_planilha["id"]
            audit["table_index"] = table_index
            audit["segment_index_before"] = segment_index

            if apply_prefix:
                segment_index += 1
                service._apply_restart_prefix(servicos, f"S{segment_index}")
            audit["segment_index_after"] = segment_index
            restart_audit.append(audit)

            if table_last_tuple and (global_max_tuple is None or table_last_tuple > global_max_tuple):
                global_max_tuple = table_last_tuple
            planilha_max = current_planilha.get("max_tuple")
            if table_last_tuple and (planilha_max is None or table_last_tuple > planilha_max):
                current_planilha["max_tuple"] = table_last_tuple
            global_seen_codes.update(table_codes)
            current_planilha["seen_codes"].update(table_codes)
            all_confidences.append(confidence)

            if not best_debug or confidence > best_debug.get("confidence", 0):
                best_debug = debug

            for s in servicos:
                item = str(s.get("item") or "").strip()
                unit = normalize_unit(s.get("unidade") or "")
                qty = parse_quantity(s.get("quantidade"))
                desc_key = normalize_description(s.get("descricao") or "")[:80]
                key = (current_planilha["id"], item, unit, qty, desc_key)
                if key in seen_keys:
                    continue
                seen_keys.add(key)
                all_servicos.append(s)

    avg_confidence = sum(all_confidences) / len(all_confidences) if all_confidences else 0.0
    best_debug["tables"] = len(tables)
    best_debug["combined_tables"] = len([c for c in all_confidences if c > 0])
    best_debug["restart_prefixes"] = restart_audit
    best_debug["planilhas"] = planilha_audit

    return all_servicos, avg_confidence, best_debug
