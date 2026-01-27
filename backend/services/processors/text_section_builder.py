"""
Construtor de itens a partir de seções de texto.

Extrai itens de serviço de linhas de texto que contêm códigos de item,
construindo descrições a partir de linhas consecutivas.
"""

import re
from typing import Any, Dict, List, Optional, Set

from config import AtestadoProcessingConfig as APC
from services.extraction import (
    normalize_description,
    normalize_unit,
    parse_item_tuple,
    parse_quantity,
    is_corrupted_text,
)
from services.processing_helpers import (
    is_section_header_desc,
    is_narrative_desc,
)

from .text_cleanup import (
    parse_unit_qty_from_line,
    strip_trailing_unit_qty,
)


# Prefixos que indicam rodapé/cabeçalho (não descrição)
STOP_PREFIXES = (
    "CNPJ", "CPF CNPJ", "PREFEITURA", "CONSELHO REGIONAL",
    "CREA", "CEP", "E MAIL", "EMAIL", "TEL", "TELEFONE", "IMPRESSO",
)


def build_items_from_code_lines(
    lines: List[str],
    code_lines: List[tuple],
    qty_map: Dict[str, List],
    dup_codes: set,
    allow_restart: bool,
    existing_keys: Optional[Set]
) -> List[Dict[str, Any]]:
    """
    Constrói lista de itens a partir de linhas com código.

    Args:
        lines: Todas as linhas do texto
        code_lines: Lista de (line_idx, code, code_end, line) para linhas com código
        qty_map: Mapa de código -> lista de (unidade, quantidade)
        dup_codes: Códigos duplicados (para detecção de restart)
        allow_restart: Se permite restart de numeração
        existing_keys: Chaves já existentes para evitar duplicatas

    Returns:
        Lista de dicionários de itens extraídos
    """
    added = []
    qty_remaining = {code: list(entries) for code, entries in qty_map.items()}
    segment_index = 1
    max_tuple = None

    for pos, (line_idx, code, code_end, line) in enumerate(code_lines):
        # Rejeitar linhas com texto corrompido (OCR com caracteres intercalados)
        if is_corrupted_text(line):
            continue

        code_tuple = parse_item_tuple(code)

        # Detectar restart de numeração
        if (
            allow_restart
            and code_tuple
            and max_tuple
            and code_tuple < max_tuple
            and code in dup_codes
        ):
            segment_index += 1

        if code_tuple and (max_tuple is None or code_tuple > max_tuple):
            max_tuple = code_tuple

        item_code = f"S{segment_index}-{code}" if segment_index > 1 else code

        # Obter unidade/quantidade
        unit_qty = _get_unit_qty_for_code(line, code, qty_remaining)
        if not unit_qty:
            continue

        unit, qty = unit_qty[0], unit_qty[1]
        if qty in (None, 0) or not unit:
            continue

        # Verificar duplicata
        if existing_keys:
            key = (item_code, unit, qty)
            if key in existing_keys:
                continue

        # Construir descrição
        desc = _build_description(
            lines, code_lines, pos, line_idx, code_end, line, unit, qty
        )

        added.append({
            "item": item_code,
            "descricao": desc,
            "unidade": unit,
            "quantidade": qty,
            "_source": "text_section"
        })

    return added


def _get_unit_qty_for_code(
    line: str,
    code: str,
    qty_remaining: Dict[str, List]
) -> Optional[tuple]:
    """Obtém unidade/quantidade para um código de item."""
    unit_qty = None

    # Primeiro tentar extrair da própria linha
    line_unit_qty = parse_unit_qty_from_line(line)
    if line_unit_qty:
        unit_qty = line_unit_qty
        # Remover do mapa se encontrar correspondência
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

    # Se não encontrou na linha, usar do mapa
    if not unit_qty:
        candidates = qty_remaining.get(code) or []
        if candidates:
            unit_qty = candidates.pop(0)

    # Validar resultado
    if (
        not unit_qty
        or not isinstance(unit_qty, (tuple, list))
        or len(unit_qty) < 2
    ):
        return None

    return unit_qty


def _build_description(
    lines: List[str],
    code_lines: List[tuple],
    pos: int,
    line_idx: int,
    code_end: int,
    line: str,
    unit: str,
    qty: float
) -> str:
    """Constrói a descrição coletando linhas consecutivas."""
    desc_parts = []

    # Processar resto da linha após o código
    rest = line[code_end:].strip()
    if rest.startswith("-"):
        rest = rest[1:].strip()

    if rest:
        tokens = rest.split()
        # Remover unidade/quantidade do início se já conhecidos
        if len(tokens) >= 2:
            lead_unit = normalize_unit(tokens[0])
            lead_qty = parse_quantity(tokens[1])
            if lead_unit == unit and lead_qty == qty:
                rest = " ".join(tokens[2:]).strip()

        rest = strip_trailing_unit_qty(rest, unit, qty)
        if rest:
            desc_parts.append(rest)

    # Coletar linhas de continuação
    next_idx = (
        code_lines[pos + 1][0] if pos + 1 < len(code_lines) else len(lines)
    )

    for j in range(line_idx + 1, next_idx):
        cont = lines[j].strip()
        if not cont:
            continue

        normalized = normalize_description(cont)
        if not normalized:
            continue

        # Ignorar linhas de rodapé/cabeçalho
        if normalized.startswith("PAGINA") or normalized.startswith("DOCUSIGN"):
            continue
        if "SERVICOS EXECUTADOS" in normalized:
            continue
        if is_section_header_desc(cont):
            break
        if is_narrative_desc(cont):
            break
        if re.match(r'^\d+\s*/\s*\d+$', cont):
            continue
        if normalized.startswith(STOP_PREFIXES):
            break

        # Linha com código AF
        if re.search(r'\bAF_\d+/\d+\b', cont, re.I):
            cleaned = strip_trailing_unit_qty(cont, unit, qty)
            if cleaned:
                desc_parts.append(cleaned)
            break

        # Linha com unidade/quantidade indica fim da descrição
        if parse_unit_qty_from_line(cont):
            cleaned = strip_trailing_unit_qty(cont, unit, qty)
            if cleaned and cleaned != cont:
                desc_parts.append(cleaned)
            break

        desc_parts.append(cont)

        # Limite de tamanho
        if sum(len(part) for part in desc_parts) >= APC.TEXT_SECTION_MAX_DESC_LEN:
            break

    return " ".join(desc_parts).strip()
