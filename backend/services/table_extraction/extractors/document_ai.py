"""
Extrator de servicos usando Google Document AI.

Extrai servicos de tabelas em documentos usando o servico Document AI.
"""

from typing import Any, Dict, List, Optional, Tuple

from services.extraction import normalize_description, normalize_unit, parse_quantity
from exceptions import AzureAPIError
from logging_config import get_logger

logger = get_logger('services.table_extraction.extractors.document_ai')


def extract_servicos_from_document_ai(
    service: Any,
    file_path: str,
    use_native_pdf_parsing: bool = False,
    allow_itemless: bool = False,
    ignore_item_numbers: bool = False
) -> Tuple[List[Dict], float, Dict]:
    """
    Extrai servicos usando Google Document AI.

    Combina servicos de TODAS as tabelas detectadas (nao apenas a melhor).

    Args:
        service: Instancia do TableExtractionService para delegar operacoes
        file_path: Caminho para o arquivo
        use_native_pdf_parsing: Usar parsing nativo de PDF (sem OCR)
        allow_itemless: Permitir itens sem codigo
        ignore_item_numbers: Ignorar numeros de item

    Returns:
        Tupla (servicos, confidence, debug)
    """
    # Importar aqui para evitar import circular
    from services.document_ai_service import document_ai_service

    if not document_ai_service.is_configured:
        return [], 0.0, {
            "enabled": False,
            "error": "not_configured",
            "imageless": use_native_pdf_parsing
        }

    try:
        result = document_ai_service.extract_tables(
            file_path,
            use_native_pdf_parsing=use_native_pdf_parsing
        )
    except (AzureAPIError, IOError, ValueError) as exc:
        logger.warning(f"Erro no Document AI: {exc}")
        return [], 0.0, {"error": str(exc), "imageless": use_native_pdf_parsing}
    except Exception as exc:
        logger.warning(f"Erro no Document AI: {exc}")
        return [], 0.0, {"error": str(exc), "imageless": use_native_pdf_parsing}

    tables = result.get("tables") or []
    if not tables:
        return [], 0.0, {
            "tables": 0,
            "pages": result.get("pages", 0),
            "imageless": use_native_pdf_parsing
        }

    # Combinar servicos de TODAS as tabelas (similar ao pdfplumber)
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
        rows = table.get("rows") or []
        servicos, confidence, debug = service.extract_servicos_from_table(
            rows,
            allow_itemless=allow_itemless,
            ignore_item_numbers=ignore_item_numbers
        )
        debug["page"] = table.get("page")
        debug["imageless"] = use_native_pdf_parsing
        debug["allow_itemless"] = allow_itemless
        debug["ignore_item_numbers"] = ignore_item_numbers

        if servicos:
            first_tuple, table_last_tuple = service._first_last_item_tuple(servicos)
            sig_info = service._build_table_signature(rows, debug)
            start_new, planilha_reason = service._should_start_new_planilha(
                current_planilha, sig_info, first_tuple
            )
            page_number = table.get("page")

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
            audit["page"] = page_number
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
    best_debug["tables_with_data"] = len([c for c in all_confidences if c > 0])
    best_debug["pages"] = result.get("pages", 0)
    best_debug["imageless"] = use_native_pdf_parsing
    best_debug["restart_prefixes"] = restart_audit
    best_debug["planilhas"] = planilha_audit

    # Inferir unidades faltantes de itens similares
    inferred = service._infer_missing_units(all_servicos)
    if inferred > 0:
        best_debug["units_inferred"] = inferred

    return all_servicos, avg_confidence, best_debug
