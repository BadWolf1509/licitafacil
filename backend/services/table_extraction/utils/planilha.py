"""
Utilitários para gerenciamento de planilhas.

Funções para detectar transições entre planilhas, gerenciar
prefixos de reinício (S1-, S2-), e assinaturas de tabela.
"""

import re
from typing import Any, Dict, List, Optional, Set, Tuple

from config import AtestadoProcessingConfig as APC
from config import TableExtractionConfig as TEC
from services.extraction import (
    item_tuple_to_str,
    normalize_description,
    normalize_header,
    parse_item_tuple,
)
from services.extraction.table_processor import guess_columns_by_header


def first_last_item_tuple(
    servicos: List[Dict[str, Any]]
) -> Tuple[Optional[tuple], Optional[tuple]]:
    """
    Retorna o primeiro e último item_tuple de uma lista de serviços.

    Args:
        servicos: Lista de serviços

    Returns:
        Tupla (primeiro, último) onde cada um é um item_tuple ou None
    """
    first = None
    last = None

    for servico in servicos or []:
        item_val = servico.get("item")
        item_tuple = parse_item_tuple(str(item_val)) if item_val else None
        if item_tuple:
            if first is None:
                first = item_tuple
            last = item_tuple

    return first, last


def _get_header_row(
    table: List[List[Any]],
    header_index: Optional[int]
) -> Optional[List[Any]]:
    """Retorna a linha de header da tabela."""
    if table is None:
        return None
    if isinstance(header_index, int) and 0 <= header_index < len(table):
        return table[header_index]
    for row in table:
        if row and any(str(cell or "").strip() for cell in row):
            return row
    return None


def _is_header_like(row: Optional[List[Any]]) -> bool:
    """Verifica se a linha parece ser um header de tabela."""
    if not row:
        return False
    header_map = guess_columns_by_header(row)
    match_count = sum(1 for v in header_map.values() if v is not None)
    return match_count >= TEC.HEADER_MIN_KEYWORD_MATCHES


def _extract_planilha_label(raw_header: str, header_like: bool) -> str:
    """Extrai label da planilha do header."""
    if not raw_header:
        return ""
    if header_like:
        return raw_header
    normalized = normalize_description(raw_header)
    if not normalized:
        return ""
    tokens = (
        "TIPO DE OBRA", "CONTRATO", "OBRA", "CNPJ",
        "GEOBRAS", "ORCAMENTO", "ORCAMENTO SINTETICO"
    )
    if any(token in normalized for token in tokens):
        return raw_header
    return ""


def build_table_signature(
    table: List[List[Any]],
    debug: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Constrói assinatura de uma tabela para identificação.

    Args:
        table: Linhas da tabela
        debug: Informações de debug da extração

    Returns:
        Dict com signature, label, header_like, raw_header
    """
    header_index = debug.get("header_index") if isinstance(debug, dict) else None
    header_row = _get_header_row(table, header_index)
    header_like = _is_header_like(header_row)

    header_cells = []
    raw_header = ""

    if header_row:
        raw_header = " | ".join(
            str(cell or "").strip()
            for cell in header_row
            if str(cell or "").strip()
        )
        if header_like:
            for cell in header_row:
                normalized = normalize_header(str(cell or ""))
                if normalized:
                    header_cells.append(normalized)

    header_text = " | ".join(header_cells) if header_cells else ""
    columns = (debug.get("columns") or {}) if isinstance(debug, dict) else {}
    col_sig = ",".join(
        f"{key}:{value}"
        for key, value in columns.items()
        if value is not None
    )

    if header_text:
        signature = f"h:{header_text}|c:{col_sig}"
    elif col_sig:
        signature = f"c:{col_sig}"
    else:
        signature = "c:none"

    label = _extract_planilha_label(raw_header, header_like)

    return {
        "signature": signature,
        "label": label,
        "header_like": header_like,
        "raw_header": raw_header
    }


def should_start_new_planilha(
    current_planilha: Optional[Dict[str, Any]],
    sig_info: Dict[str, Any],
    first_tuple: Optional[tuple]
) -> Tuple[bool, str]:
    """
    Determina se deve iniciar uma nova planilha.

    Args:
        current_planilha: Planilha atual (ou None se primeira)
        sig_info: Informações de assinatura da nova tabela
        first_tuple: Primeiro item_tuple da nova tabela

    Returns:
        Tupla (start_new, reason)
    """
    if current_planilha is None:
        return True, "initial"

    signature = sig_info.get("signature")
    header_like = bool(sig_info.get("header_like"))
    label = sig_info.get("label") or ""

    if label and label != current_planilha.get("label"):
        return True, "label_change"

    if signature and (header_like or label):
        if signature != current_planilha.get("signature"):
            return True, "signature_change"
        return False, "signature_match"

    max_tuple = current_planilha.get("max_tuple")
    if first_tuple and max_tuple and first_tuple >= max_tuple:
        return False, "continuity"

    return False, "no_header_default"


def collect_item_codes(servicos: List[Dict[str, Any]]) -> Set[str]:
    """
    Coleta todos os códigos de item normalizados de uma lista de serviços.

    Args:
        servicos: Lista de serviços

    Returns:
        Set de códigos de item normalizados
    """
    codes = set()
    for servico in servicos or []:
        item_val = servico.get("item")
        if not item_val:
            continue
        item_tuple = parse_item_tuple(str(item_val))
        if not item_tuple:
            continue
        codes.add(item_tuple_to_str(item_tuple))
    return codes


def should_restart_prefix(
    first_tuple: Optional[tuple],
    max_tuple: Optional[tuple],
    table_codes: Set[str],
    seen_codes: Set[str]
) -> Tuple[bool, Dict[str, Any]]:
    """
    Determina se deve adicionar prefixo de reinício (S1-, S2-, etc).

    Critério:
    - Primeira planilha NUNCA recebe prefixo (seen_codes vazio)
    - Planilhas subsequentes recebem prefixo SE houver overlap de códigos

    Args:
        first_tuple: Primeiro item_tuple da tabela
        max_tuple: Máximo item_tuple visto até agora
        table_codes: Códigos de item da tabela atual
        seen_codes: Códigos já vistos anteriormente

    Returns:
        Tupla (apply_prefix, audit_info)
    """
    overlap_codes = table_codes & seen_codes
    overlap_count = len(overlap_codes)
    overlap_ratio = overlap_count / len(table_codes) if table_codes else 0.0

    audit = {
        "first_item": item_tuple_to_str(first_tuple) if first_tuple else None,
        "max_item": item_tuple_to_str(max_tuple) if max_tuple else None,
        "code_count": len(table_codes),
        "seen_count": len(seen_codes),
        "overlap_count": overlap_count,
        "overlap_ratio": round(overlap_ratio, 4),
        "overlap_codes": sorted(list(overlap_codes))[:10] if overlap_codes else [],
        "min_overlap": APC.RESTART_MIN_OVERLAP,
        "decision": "skip_no_anchor",
    }

    # Primeira planilha nunca recebe prefixo
    if not seen_codes:
        audit["decision"] = "skip_first_planilha"
        return False, audit

    # Sem códigos de item para comparar
    if not table_codes:
        audit["decision"] = "skip_no_table_codes"
        return False, audit

    # Aplica prefixo se houver overlap suficiente
    if overlap_count >= APC.RESTART_MIN_OVERLAP:
        audit["decision"] = "apply_overlap"
        return True, audit

    audit["decision"] = "skip_low_overlap"
    return False, audit


def apply_restart_prefix(servicos: List[Dict[str, Any]], prefix: str) -> None:
    """
    Aplica prefixo de reinício aos itens dos serviços.

    Modifica os serviços in-place.

    Args:
        servicos: Lista de serviços
        prefix: Prefixo a aplicar (ex: "S2")
    """
    if not servicos or not prefix:
        return

    for servico in servicos:
        item = str(servico.get("item") or "").strip()
        if not item:
            continue
        # Não aplicar se já tem prefixo
        if re.match(r'^(AD|[A-Z]{1,3}\d+)-', item, re.IGNORECASE):
            continue
        servico["item"] = f"{prefix}-{item}"
        servico["_item_prefix"] = prefix
