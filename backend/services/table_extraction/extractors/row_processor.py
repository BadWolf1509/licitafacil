"""
Processador de linhas de tabela.

Contém a lógica de processamento linha a linha para extração
de serviços de uma tabela normalizada.
"""

from typing import Any, Dict, List, Optional, Tuple

from services.extraction import (
    build_description_from_cells,
    item_tuple_to_str,
    normalize_description,
    normalize_unit,
    parse_item_tuple,
    parse_quantity,
)
from utils.text_utils import sanitize_description

from ..filters import (
    is_page_metadata,
    is_row_noise,
    is_section_header_row,
)
from ..parsers import find_unit_qty_pairs, parse_unit_qty_from_text
from .helpers import extract_hidden_item_from_text, extract_trailing_unit


class RowProcessor:
    """
    Processador de linhas de tabela.

    Processa cada linha da tabela e extrai serviços individuais,
    gerenciando estado de continuação entre linhas.
    """

    def process_rows(
        self,
        data_rows: List[List[Any]],
        item_col: Optional[int],
        desc_col: Optional[int],
        unit_col: Optional[int],
        qty_col: Optional[int],
        allow_itemless: bool,
        ignore_item_numbers: bool
    ) -> Tuple[List[Dict[str, Any]], List[tuple]]:
        """
        Processa as linhas da tabela e extrai serviços.

        Args:
            data_rows: Linhas de dados (sem header)
            item_col: Índice da coluna de item
            desc_col: Índice da coluna de descrição
            unit_col: Índice da coluna de unidade
            qty_col: Índice da coluna de quantidade
            allow_itemless: Permite itens sem código
            ignore_item_numbers: Ignora números de item

        Returns:
            Tupla (lista de serviços, lista de item_tuples)
        """
        servicos: List[Dict[str, Any]] = []
        last_item = None
        last_item_qty_present = False
        pending_desc = ""
        pending_unit = ""
        pending_qty = None
        pending_qty_present = False
        item_tuples: List[tuple] = []

        for row in data_rows:
            cells = [str(cell or "").strip() for cell in row]
            result = self._process_single_row(
                cells, item_col, desc_col, unit_col, qty_col,
                allow_itemless, ignore_item_numbers,
                last_item, last_item_qty_present,
                pending_desc, pending_unit, pending_qty, pending_qty_present,
                servicos, item_tuples
            )
            (
                last_item, last_item_qty_present,
                pending_desc, pending_unit, pending_qty, pending_qty_present
            ) = result

        # Processar pending restante
        if (pending_desc or pending_unit or pending_qty_present) and last_item:
            self._apply_pending_to_last(
                last_item, last_item_qty_present,
                pending_desc, pending_unit, pending_qty, pending_qty_present
            )

        return servicos, item_tuples

    def _process_single_row(
        self,
        cells: List[str],
        item_col: Optional[int],
        desc_col: Optional[int],
        unit_col: Optional[int],
        qty_col: Optional[int],
        allow_itemless: bool,
        ignore_item_numbers: bool,
        last_item: Optional[Dict],
        last_item_qty_present: bool,
        pending_desc: str,
        pending_unit: str,
        pending_qty: Optional[float],
        pending_qty_present: bool,
        servicos: List[Dict],
        item_tuples: List[tuple]
    ) -> Tuple[Optional[Dict], bool, str, str, Optional[float], bool]:
        """Processa uma única linha e retorna estado atualizado."""
        # Extrair valores das células
        item_val = cells[item_col] if item_col is not None and item_col < len(cells) else ""
        item_tuple = None
        item_col_effective = item_col

        if not ignore_item_numbers:
            item_tuple = parse_item_tuple(item_val)
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

        # Construir descrição de outras células se necessário
        exclude_cols = {c for c in (item_col_effective, unit_col, qty_col) if c is not None}
        if not desc_val or len(desc_val) < 6:
            desc_val = build_description_from_cells(cells, exclude_cols)

        row_text = " ".join(c for c in cells if c).strip()

        # Para modo itemless, extrair unit/qty do texto
        row_parsed_unit = None
        row_parsed_qty = None
        row_pairs = []
        if allow_itemless and row_text:
            parsed = parse_unit_qty_from_text(row_text)
            if parsed:
                row_parsed_unit, row_parsed_qty = parsed
            row_pairs = find_unit_qty_pairs(row_text)

        # Normalizar unidade
        if unit_val:
            unit_val = normalize_unit(unit_val)

        desc_val = str(desc_val or "").strip()
        unit_val = str(unit_val or "").strip()
        qty_parsed = parse_quantity(qty_val)

        if allow_itemless and (not unit_val or qty_parsed is None):
            if row_parsed_unit and row_parsed_qty is not None:
                unit_val = unit_val or row_parsed_unit
                qty_parsed = qty_parsed if qty_parsed is not None else row_parsed_qty

        qty_present = qty_parsed is not None

        # Verificar ruído
        row_is_noise = allow_itemless and row_text and is_row_noise(row_text)
        if allow_itemless and row_text and not row_is_noise:
            normalized_row = normalize_description(row_text)
            if "SERVICOS" in normalized_row and len(normalized_row) <= 40:
                row_is_noise = True

        if row_is_noise and not item_tuple and not unit_val and not qty_present and not row_pairs:
            if pending_desc and is_row_noise(pending_desc):
                return last_item, last_item_qty_present, "", "", None, False
            return last_item, last_item_qty_present, pending_desc, pending_unit, pending_qty, pending_qty_present

        # Processar linha sem item (modo itemless)
        if not item_tuple and allow_itemless:
            result = self._process_itemless_row(
                desc_val, unit_val, qty_parsed, qty_present,
                row_text, row_pairs, row_parsed_unit, row_parsed_qty,
                pending_desc, pending_unit, pending_qty, pending_qty_present,
                last_item, last_item_qty_present, servicos
            )
            if result is not None:
                return result

        # Processar linha com item
        if item_tuple:
            return self._process_item_row(
                item_tuple, item_val, desc_val, unit_val, qty_parsed, qty_present,
                pending_desc, pending_unit, pending_qty, pending_qty_present,
                servicos, item_tuples
            )

        # Linha sem item em modo normal
        return self._process_continuation_row(
            item_val, desc_val, unit_val, qty_parsed, qty_present,
            allow_itemless, last_item, last_item_qty_present,
            pending_desc, pending_unit, pending_qty, pending_qty_present,
            servicos, item_tuples
        )

    def _process_itemless_row(
        self,
        desc_val: str,
        unit_val: str,
        qty_parsed: Optional[float],
        qty_present: bool,
        row_text: str,
        row_pairs: List,
        row_parsed_unit: Optional[str],
        row_parsed_qty: Optional[float],
        pending_desc: str,
        pending_unit: str,
        pending_qty: Optional[float],
        pending_qty_present: bool,
        last_item: Optional[Dict],
        last_item_qty_present: bool,
        servicos: List[Dict]
    ) -> Optional[Tuple]:
        """Processa linha em modo itemless."""
        merged_desc = desc_val
        if not merged_desc and pending_desc:
            merged_desc = pending_desc
        elif pending_desc:
            merged_desc = (pending_desc + " " + merged_desc).strip()

        if pending_unit and not unit_val:
            unit_val = pending_unit
        if pending_qty_present and not qty_present:
            qty_parsed = pending_qty
            qty_present = True

        # Processar múltiplos pares unit/qty
        if row_pairs:
            for idx, (unit_pair, qty_pair, start, end) in enumerate(row_pairs):
                next_start = row_pairs[idx + 1][2] if idx + 1 < len(row_pairs) else len(row_text)
                desc_candidate = row_text[end:next_start].strip()
                if not desc_candidate:
                    desc_candidate = row_text[:start].strip()
                if not desc_candidate or is_row_noise(desc_candidate):
                    continue
                if qty_pair > 1_000_000:
                    continue
                servico = {
                    "item": None,
                    "descricao": sanitize_description(desc_candidate),
                    "unidade": unit_pair,
                    "quantidade": qty_pair
                }
                servicos.append(servico)
                last_item = servico
                last_item_qty_present = True
            return last_item, last_item_qty_present, "", "", None, False

        # Processar linha com unit/qty do texto
        if row_text and row_parsed_unit and row_parsed_qty is not None:
            merged_desc = row_text
            qty_parsed = row_parsed_qty
            unit_val = row_parsed_unit

        if merged_desc and unit_val and qty_present:
            if is_row_noise(merged_desc) or (qty_parsed and qty_parsed > 1_000_000):
                return last_item, last_item_qty_present, "", "", None, False
            servico = {
                "item": None,
                "descricao": sanitize_description(merged_desc),
                "unidade": unit_val,
                "quantidade": qty_parsed
            }
            servicos.append(servico)
            return servico, qty_present, "", "", None, False

        return None

    def _process_item_row(
        self,
        item_tuple: tuple,
        item_val: str,
        desc_val: str,
        unit_val: str,
        qty_parsed: Optional[float],
        qty_present: bool,
        pending_desc: str,
        pending_unit: str,
        pending_qty: Optional[float],
        pending_qty_present: bool,
        servicos: List[Dict],
        item_tuples: List[tuple]
    ) -> Tuple[Dict, bool, str, str, Optional[float], bool]:
        """Processa linha com código de item."""
        # Aplicar pending ao item atual
        if pending_desc:
            desc_val = (pending_desc + " " + desc_val).strip() if desc_val else pending_desc
        if pending_unit and not unit_val:
            unit_val = pending_unit
        if pending_qty_present and qty_parsed is None:
            qty_parsed = pending_qty
            qty_present = True

        item_tuples.append(item_tuple)
        item_str = item_tuple_to_str(item_tuple)

        # Extrair unidade do final da descrição
        if not unit_val and desc_val:
            desc_val, trailing_unit = extract_trailing_unit(desc_val, qty_parsed)
            if trailing_unit:
                unit_val = trailing_unit

        servico = {
            "item": item_str,
            "descricao": sanitize_description(desc_val),
            "unidade": unit_val,
            "quantidade": qty_parsed
        }
        servicos.append(servico)

        return servico, qty_present, "", "", None, False

    def _process_continuation_row(
        self,
        item_val: str,
        desc_val: str,
        unit_val: str,
        qty_parsed: Optional[float],
        qty_present: bool,
        allow_itemless: bool,
        last_item: Optional[Dict],
        last_item_qty_present: bool,
        pending_desc: str,
        pending_unit: str,
        pending_qty: Optional[float],
        pending_qty_present: bool,
        servicos: List[Dict],
        item_tuples: List[tuple]
    ) -> Tuple[Optional[Dict], bool, str, str, Optional[float], bool]:
        """Processa linha de continuação (sem código de item)."""
        row_is_section_header = is_section_header_row(item_val, desc_val, unit_val, qty_present)

        if pending_desc or pending_unit or pending_qty_present:
            if desc_val and not row_is_section_header and not is_page_metadata(desc_val):
                if not (allow_itemless and is_row_noise(desc_val)):
                    if pending_desc and len(pending_desc) < 150:
                        pending_desc = (pending_desc + " " + desc_val).strip()
                    elif not pending_desc:
                        pending_desc = desc_val
            if unit_val and not pending_unit:
                pending_unit = unit_val
            if qty_present and not pending_qty_present:
                pending_qty = qty_parsed
                pending_qty_present = True
            return last_item, last_item_qty_present, pending_desc, pending_unit, pending_qty, pending_qty_present

        if not last_item:
            if desc_val and not row_is_section_header and not is_page_metadata(desc_val):
                if not (allow_itemless and is_row_noise(desc_val)):
                    pending_desc = desc_val
            if unit_val:
                pending_unit = unit_val
            if qty_present:
                pending_qty = qty_parsed
                pending_qty_present = True
            return None, False, pending_desc, pending_unit, pending_qty, pending_qty_present

        # Atualizar último item
        last_desc = str(last_item.get("descricao") or "").strip()
        last_desc_missing = not last_desc or len(last_desc) < 6
        last_unit_missing = not last_item.get("unidade")
        last_qty_missing = not last_item_qty_present
        row_desc_present = bool(desc_val)
        row_has_unit_or_qty = bool(unit_val) or qty_present

        # Verificar item oculto
        if row_desc_present and len(desc_val) > 20:
            hidden = extract_hidden_item_from_text(desc_val)
            if hidden:
                if hidden.get("prefix_for_last"):
                    last_item["descricao"] = (last_desc + " " + hidden["prefix_for_last"]).strip()
                hidden_tuple = parse_item_tuple(hidden["item"])
                if hidden_tuple:
                    item_tuples.append(hidden_tuple)
                    servico = {
                        "item": hidden["item"],
                        "descricao": hidden["descricao"],
                        "unidade": unit_val,
                        "quantidade": qty_parsed
                    }
                    servicos.append(servico)
                    return servico, qty_present, "", "", None, False

        # Continuação de descrição
        if row_desc_present and not row_has_unit_or_qty and not row_is_section_header:
            if not is_page_metadata(desc_val):
                desc_starts_uppercase = desc_val and desc_val[0].isupper()
                last_desc_significant = len(last_desc) >= 20
                if desc_starts_uppercase and last_desc_significant:
                    return last_item, last_item_qty_present, desc_val, "", None, False
                last_item["descricao"] = (last_desc + " " + desc_val).strip()
                return last_item, last_item_qty_present, "", "", None, False

        # Preencher dados faltantes
        if (not row_desc_present) and row_has_unit_or_qty and (last_unit_missing or last_qty_missing):
            if last_unit_missing and unit_val:
                last_item["unidade"] = unit_val
            if last_qty_missing and qty_present:
                last_item["quantidade"] = qty_parsed
                last_item_qty_present = True
            return last_item, last_item_qty_present, "", "", None, False

        if row_desc_present and row_has_unit_or_qty and last_desc_missing:
            last_item["descricao"] = (last_desc + " " + desc_val).strip() if last_desc else desc_val
            if last_unit_missing and unit_val:
                last_item["unidade"] = unit_val
            if last_qty_missing and qty_present:
                last_item["quantidade"] = qty_parsed
                last_item_qty_present = True
            return last_item, last_item_qty_present, "", "", None, False

        # Armazenar em pending
        if desc_val and not row_is_section_header and not is_page_metadata(desc_val):
            if not (allow_itemless and is_row_noise(desc_val)):
                pending_desc = desc_val
        if unit_val:
            pending_unit = unit_val
        if qty_present:
            pending_qty = qty_parsed
            pending_qty_present = True

        return last_item, last_item_qty_present, pending_desc, pending_unit, pending_qty, pending_qty_present

    def _apply_pending_to_last(
        self,
        last_item: Dict,
        last_item_qty_present: bool,
        pending_desc: str,
        pending_unit: str,
        pending_qty: Optional[float],
        pending_qty_present: bool
    ) -> None:
        """Aplica dados pending ao último item."""
        last_desc = str(last_item.get("descricao") or "").strip()
        last_desc_missing = not last_desc or len(last_desc) < 6
        last_unit_missing = not last_item.get("unidade")
        last_qty_missing = not last_item_qty_present

        if pending_desc and last_desc_missing:
            last_item["descricao"] = (last_desc + " " + pending_desc).strip() if last_desc else pending_desc
        if pending_unit and last_unit_missing:
            last_item["unidade"] = pending_unit
        if pending_qty_present and last_qty_missing:
            last_item["quantidade"] = pending_qty


# Instância singleton
row_processor = RowProcessor()
