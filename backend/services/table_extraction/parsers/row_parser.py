"""
Parser para linhas de texto de tabela.

Funcoes para extrair servicos de texto de linhas de tabela.
"""

import re
from typing import Any, Dict, List

from utils.text_utils import sanitize_description
from ..filters import is_row_noise, is_header_row
from .text_parser import parse_unit_qty_from_text, find_unit_qty_pairs


def parse_row_text_to_servicos(row_text: str) -> List[Dict[str, Any]]:
    """
    Extrai servicos de uma linha de texto.

    Processa texto de uma linha de tabela e extrai servicos com
    item, descricao, unidade e quantidade.

    Args:
        row_text: Texto da linha

    Returns:
        Lista de servicos extraidos
    """
    if not row_text:
        return []
    if is_row_noise(row_text) or is_header_row(row_text):
        return []

    item_val = None
    item_match = re.match(r'^(S\d+-)?\d{1,3}(?:\.\d{1,3}){1,4}', row_text)
    if item_match:
        item_val = item_match.group(0).strip()
        base_text = row_text[item_match.end():].strip()
    else:
        base_text = row_text

    if not base_text:
        return []

    row_pairs = find_unit_qty_pairs(base_text)
    servicos = []
    if row_pairs:
        prev_end = 0
        for idx, (unit_pair, qty_pair, start, end) in enumerate(row_pairs):
            desc_candidate = base_text[prev_end:start].strip()
            if not desc_candidate:
                desc_candidate = base_text[:start].strip()
            prev_end = end
            if not desc_candidate or is_row_noise(desc_candidate):
                continue
            servicos.append({
                "item": item_val if idx == 0 else None,
                "descricao": sanitize_description(desc_candidate),
                "unidade": unit_pair,
                "quantidade": qty_pair
            })
        if servicos:
            return servicos

    parsed = parse_unit_qty_from_text(base_text)
    if not parsed:
        return []
    unit_val, qty_val = parsed
    desc = re.sub(
        rf'\\b{re.escape(unit_val)}\\b\\s*[\d.,]+\\s*$',
        '',
        base_text,
        flags=re.IGNORECASE
    ).strip()
    if not desc or is_row_noise(desc):
        return []
    servicos.append({
        "item": item_val,
        "descricao": sanitize_description(desc),
        "unidade": unit_val,
        "quantidade": qty_val
    })
    return servicos
