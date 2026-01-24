"""
Extrator principal de serviços de tabelas.

Contém a lógica central para extrair serviços de uma tabela normalizada,
identificando colunas, processando linhas e gerando serviços.
"""

from typing import Any, Dict, List, Optional, Tuple

from services.extraction import (
    normalize_description,
    normalize_unit,
    parse_item_tuple,
    item_tuple_to_str,
    parse_quantity,
    detect_header_row,
    guess_columns_by_header,
    compute_column_stats,
    guess_columns_by_content,
    validate_column_mapping,
    build_description_from_cells,
    filter_servicos_by_item_prefix,
    filter_servicos_by_item_length,
    repair_missing_prefix,
    score_item_column,
    dominant_item_length,
)
from services.extraction.quality_assessor import compute_servicos_stats
from config import AtestadoProcessingConfig as APC
from utils.text_utils import sanitize_description

from ..parsers import parse_unit_qty_from_text, find_unit_qty_pairs
from ..filters import (
    is_row_noise,
    is_section_header_row,
    is_page_metadata,
    strip_section_header_prefix,
)
from .helpers import extract_hidden_item_from_text, extract_trailing_unit


class TableExtractor:
    """
    Extrator de serviços de uma tabela.

    Processa uma tabela (lista de linhas) e extrai serviços
    com item, descrição, unidade e quantidade.
    """

    def extract(
        self,
        table: List[List[Any]],
        preferred_item_col: Optional[int] = None,
        allow_itemless: bool = False,
        ignore_item_numbers: bool = False
    ) -> Tuple[List[Dict[str, Any]], float, Dict[str, Any]]:
        """
        Extrai serviços de uma única tabela.

        Args:
            table: Lista de linhas da tabela (cada linha é lista de células)
            preferred_item_col: Índice preferido para coluna de item
            allow_itemless: Permite extrair itens sem código
            ignore_item_numbers: Ignora números de item

        Returns:
            Tupla (servicos, confidence, debug)
        """
        if not table:
            return [], 0.0, {}

        # Normalizar linhas
        rows = [
            row for row in table
            if row and any(str(cell or "").strip() for cell in row)
        ]
        if not rows:
            return [], 0.0, {}

        max_cols = max(len(row) for row in rows)
        normalized_rows = []
        for row in rows:
            padded = list(row) + [""] * (max_cols - len(row))
            normalized_rows.append(padded)

        # Detectar header e mapear colunas
        header_index = detect_header_row(normalized_rows)
        header_map: Dict[str, Optional[int]] = {
            "item": None,
            "descricao": None,
            "unidade": None,
            "quantidade": None,
            "valor": None
        }
        data_rows = normalized_rows

        if header_index is not None:
            header_map = guess_columns_by_header(normalized_rows[header_index])
            data_rows = normalized_rows[header_index + 1:]

        # Detectar coluna de item
        item_col, item_score_data, preferred_used = self._detect_item_column(
            data_rows, max_cols, header_map,
            preferred_item_col, ignore_item_numbers
        )

        if not ignore_item_numbers and header_map.get("item") is None and item_col is not None:
            header_map["item"] = item_col

        if ignore_item_numbers:
            item_col = None
            header_map["item"] = None

        # Mapear outras colunas por conteúdo
        col_stats = compute_column_stats(data_rows, max_cols)
        header_map = guess_columns_by_content(data_rows, max_cols, header_map, col_stats)
        header_map = validate_column_mapping(header_map, col_stats)
        header_map = guess_columns_by_content(data_rows, max_cols, header_map, col_stats)

        desc_col = header_map.get("descricao")
        unit_col = header_map.get("unidade")
        qty_col = header_map.get("quantidade")

        # Processar linhas
        servicos, item_tuples = self._process_rows(
            data_rows, item_col, desc_col, unit_col, qty_col,
            allow_itemless, ignore_item_numbers
        )

        # Pós-processamento
        servicos = [s for s in servicos if s.get("descricao")]
        servicos, prefix_info = filter_servicos_by_item_prefix(servicos)
        dominant_len, dominant_len_ratio = dominant_item_length(servicos)

        repair_info = {"applied": False, "repaired": 0}
        if dominant_len == 3 and prefix_info.get("dominant_prefix") is not None:
            servicos, repair_info = repair_missing_prefix(
                servicos, prefix_info.get("dominant_prefix")
            )

        servicos, dominant_info = filter_servicos_by_item_length(servicos)

        # Calcular confiança
        stats = compute_servicos_stats(servicos)
        confidence = self._calculate_confidence(
            servicos, item_tuples, item_score_data,
            stats, prefix_info, dominant_info
        )

        # Limpar prefixos de header das descrições
        for servico in servicos:
            desc = servico.get("descricao")
            if desc:
                cleaned = strip_section_header_prefix(desc)
                if cleaned != desc:
                    servico["descricao"] = cleaned

        debug = {
            "header_index": header_index,
            "columns": header_map,
            "item_col_score": item_score_data,
            "preferred_item_col": preferred_item_col,
            "preferred_item_used": preferred_used,
            "prefix_item": prefix_info,
            "dominant_item": dominant_info,
            "prefix_repair": repair_info,
            "stats": stats,
            "confidence": confidence
        }

        return servicos, confidence, debug

    def _detect_item_column(
        self,
        data_rows: List[List[Any]],
        max_cols: int,
        header_map: Dict[str, Any],
        preferred_item_col: Optional[int],
        ignore_item_numbers: bool
    ) -> Tuple[Optional[int], Dict[str, Any], bool]:
        """Detecta a coluna de item."""
        item_col = header_map.get("item")
        item_score_data = {"score": 0.0}
        preferred_used = False

        if ignore_item_numbers:
            return None, item_score_data, False

        if item_col is None and preferred_item_col is not None and preferred_item_col < max_cols:
            col_cells = [
                row[preferred_item_col]
                for row in data_rows
                if preferred_item_col < len(row)
            ]
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

        return item_col, item_score_data, preferred_used

    def _process_rows(
        self,
        data_rows: List[List[Any]],
        item_col: Optional[int],
        desc_col: Optional[int],
        unit_col: Optional[int],
        qty_col: Optional[int],
        allow_itemless: bool,
        ignore_item_numbers: bool
    ) -> Tuple[List[Dict[str, Any]], List[tuple]]:
        """Processa as linhas da tabela e extrai serviços."""
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

    def _calculate_confidence(
        self,
        servicos: List[Dict],
        item_tuples: List[tuple],
        item_score_data: Dict,
        stats: Dict,
        prefix_info: Dict,
        dominant_info: Dict
    ) -> float:
        """Calcula a confiança da extração."""
        # Calcular sequência ordenada
        seq_ratio = 0.0
        filtered_tuples = []
        for servico in servicos:
            item_value = servico.get("item")
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

        return max(0.0, min(1.0, round(confidence, 3)))
