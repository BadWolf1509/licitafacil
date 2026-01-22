"""
Serviço de Extração de Tabelas.

Responsável por:
- Extração de serviços de tabelas em PDFs
- Processamento com pdfplumber e Document AI
- Extração baseada em layout OCR
- Cascata de extração com thresholds de qualidade
"""

from typing import Dict, Any, List, Optional, Callable
from pathlib import Path
import re
import pdfplumber
import fitz
import numpy as np
import cv2

from .pdf_extractor import pdf_extractor
from .ocr_service import ocr_service
from .document_ai_service import document_ai_service
from .pdf_extraction_service import pdf_extraction_service
from .extraction import (
    normalize_description,
    normalize_unit,
    normalize_header,
    parse_item_tuple,
    item_tuple_to_str,
    parse_quantity,
    is_valid_item_context,
    score_item_column,
    detect_header_row,
    guess_columns_by_header,
    compute_column_stats,
    guess_columns_by_content,
    validate_column_mapping,
    build_description_from_cells,
    filter_servicos_by_item_prefix,
    filter_servicos_by_item_length,
    repair_missing_prefix,
    description_similarity,
    dominant_item_length,
    UNIT_TOKENS,
)
from .extraction.quality_assessor import compute_servicos_stats, compute_quality_score
from exceptions import PDFError, OCRError, AzureAPIError
from config import AtestadoProcessingConfig as APC, TableExtractionConfig as TEC

from logging_config import get_logger
logger = get_logger('services.table_extraction_service')


# Type aliases para callbacks
ProgressCallback = Optional[Callable[[int, int, str, str], None]]
CancelCheck = Optional[Callable[[], bool]]


class TableExtractionService:
    """
    Serviço para extração de serviços de tabelas em documentos.

    Implementa um fluxo em cascata:
    1. pdfplumber (gratuito) - se qty_ratio >= 70%: SUCESSO
    2. Document AI (~R$0.008/pág) - se qty_ratio >= 60%: SUCESSO
    3. Fallback para melhor resultado disponível
    """

    def _parse_unit_qty_from_text(self, text: str) -> Optional[tuple]:
        if not text:
            return None
        tokens = re.findall(r'[\w\u00ba\u00b0/%\u00b2\u00b3\.]+', text)
        if len(tokens) < 2:
            return None
        stop_units = {"DE", "DA", "DO", "EM", "COM", "PARA", "POR", "QUE"}
        allowed_units = set(UNIT_TOKENS) | {"MES"}
        for idx in range(len(tokens) - 2, -1, -1):
            unit_raw = tokens[idx]
            qty_raw = tokens[idx + 1]
            if not re.fullmatch(r'[\d.,]+', qty_raw):
                continue
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
            return unit_norm, qty
        return None

    def _find_unit_qty_pairs(self, text: str) -> list:
        if not text:
            return []
        pattern = re.compile(r'([\w\u00ba\u00b0/%\u00b2\u00b3\.]+)\s+([\d.,]+)')
        stop_units = {"DE", "DA", "DO", "EM", "COM", "PARA", "POR", "QUE"}
        allowed_units = set(UNIT_TOKENS) | {"MES"}
        pairs = []
        for match in pattern.finditer(text):
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
            pairs.append((unit_norm, qty, match.start(), match.end()))
        return pairs

    def _is_row_noise(self, text: str) -> bool:
        if not text:
            return True
        normalized = normalize_description(text)
        if not normalized:
            return True
        noise_tokens = (
            "RUA PROJETADA",
            "SERVICOS PRELIMINARES",
            "SERVICOS COMPLEMENTARES",
            "SERVICOS EXECUTADOS",
            "PAGINA",
            "CNPJ",
            "CPF",
            "CREA",
            "CONSELHO REGIONAL",
            "PREFEITURA",
            "MUNICIPIO",
            "ESTADO",
            "ART",
        )
        normalized_compact = normalized.replace(" ", "")
        for token in noise_tokens:
            if token in normalized:
                return True
            if token.replace(" ", "") in normalized_compact:
                return True
        return False

    def _extract_hidden_item_from_text(self, text: str) -> Optional[dict]:
        """
        Fix A3: Extrai item oculto de texto concatenado.

        Detecta se o texto contém um código de item no meio (ex: "JUNTA 6.14 ELÁSTICA...")
        e extrai esse item como um serviço separado.

        Args:
            text: Texto a verificar

        Returns:
            Dict com item/descricao se encontrou item oculto, None caso contrário
        """
        if not text or len(text) < 10:
            return None

        # Padrão: código de item (X.Y ou X.Y.Z) no meio do texto
        # Deve ter pelo menos 5 caracteres antes e depois
        pattern = re.compile(r'(.{5,}?)\s+(\d{1,2}\.\d{1,2}(?:\.\d{1,2})?)\s+([A-ZÀ-ÚÇ].{10,})', re.IGNORECASE)
        match = pattern.search(text)

        if not match:
            return None

        prefix = match.group(1).strip()
        item_code = match.group(2)
        suffix = match.group(3).strip()

        # Verificar contexto - não extrair se precedido por palavra de contexto
        if not is_valid_item_context(text, match.start(2)):
            return None

        # Verificar se o código é válido
        item_tuple = parse_item_tuple(item_code)
        if not item_tuple:
            return None

        # A descrição do item oculto é o suffix
        return {
            "item": item_code,
            "descricao": suffix,
            "prefix_for_last": prefix  # Texto que deve ir para o item anterior
        }

    def _extract_trailing_unit(self, desc: str) -> tuple:
        """
        Fix B3: Extrai unidade do final da descrição se presente.

        Args:
            desc: Descrição a verificar

        Returns:
            Tupla (desc_limpa, unidade) ou (desc, None)
        """
        if not desc:
            return desc, None
        # Padrão: unidade no final, após espaço
        pattern = r'\s+(UN|M|M2|M3|M²|M³|KG|L|CJ|VB|PC|PÇ|JG|CONJ)\s*$'
        match = re.search(pattern, desc, re.IGNORECASE)
        if match:
            return desc[:match.start()].strip(), match.group(1).upper()
        return desc, None

    def extract_servicos_from_table(
        self,
        table: list,
        preferred_item_col: Optional[int] = None,
        allow_itemless: bool = False,
        ignore_item_numbers: bool = False
    ) -> tuple[list, float, dict]:
        """
        Extrai serviços de uma única tabela.

        Args:
            table: Lista de linhas da tabela (cada linha é lista de células)
            preferred_item_col: Índice preferido para coluna de item

        Returns:
            Tupla (servicos, confidence, debug)
        """
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
        if not ignore_item_numbers:
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
        else:
            item_col = None
            header_map["item"] = None

        col_stats = compute_column_stats(data_rows, max_cols)
        header_map = guess_columns_by_content(data_rows, max_cols, header_map, col_stats)
        header_map = validate_column_mapping(header_map, col_stats)
        header_map = guess_columns_by_content(data_rows, max_cols, header_map, col_stats)
        desc_col = header_map.get("descricao")
        unit_col = header_map.get("unidade")
        qty_col = header_map.get("quantidade")

        servicos = []
        last_item = None
        last_item_qty_present = False
        pending_desc = ""
        pending_unit = ""
        pending_qty = None
        pending_qty_present = False
        item_tuples = []
        for row in data_rows:
            cells = [str(cell or "").strip() for cell in row]
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

            # Detectar se a linha é um cabeçalho de seção (número simples como "2", "3")
            # Isso evita concatenar "2 QUADRA SITIO..." ao item anterior
            is_section_header = bool(
                item_tuple is None and
                item_val and
                re.match(r'^\d{1,2}$', item_val.strip())
            )

            exclude_cols = {c for c in (item_col_effective, unit_col, qty_col) if c is not None}
            if not desc_val or len(desc_val) < 6:
                desc_val = build_description_from_cells(cells, exclude_cols)

            row_text = " ".join(c for c in cells if c).strip()
            row_parsed_unit = None
            row_parsed_qty = None
            row_pairs = []
            if allow_itemless and row_text:
                parsed = self._parse_unit_qty_from_text(row_text)
                if parsed:
                    row_parsed_unit, row_parsed_qty = parsed
                row_pairs = self._find_unit_qty_pairs(row_text)

            # Normalizar unidade (corrige artefatos de OCR como M23... M2)
            if unit_val:
                unit_val = normalize_unit(unit_val)

            desc_val = str(desc_val or "").strip()
            unit_val = str(unit_val or "").strip()
            qty_parsed = parse_quantity(qty_val)
            if allow_itemless and (not unit_val or qty_parsed is None) and row_parsed_unit and row_parsed_qty is not None:
                unit_val = unit_val or row_parsed_unit
                qty_parsed = qty_parsed if qty_parsed is not None else row_parsed_qty
            qty_present = qty_parsed is not None
            row_is_noise = allow_itemless and row_text and self._is_row_noise(row_text)
            if allow_itemless and row_text and not row_is_noise:
                normalized_row = normalize_description(row_text)
                if "SERVICOS" in normalized_row and len(normalized_row) <= 40:
                    row_is_noise = True
            if row_is_noise and not item_tuple and not unit_val and not qty_present and not row_pairs:
                if pending_desc and self._is_row_noise(pending_desc):
                    pending_desc = ""
                    pending_unit = ""
                    pending_qty = None
                    pending_qty_present = False
                continue

            if not item_tuple and allow_itemless:
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
                if row_pairs:
                    for idx, (unit_pair, qty_pair, start, end) in enumerate(row_pairs):
                        next_start = row_pairs[idx + 1][2] if idx + 1 < len(row_pairs) else len(row_text)
                        desc_candidate = row_text[end:next_start].strip()
                        if not desc_candidate:
                            desc_candidate = row_text[:start].strip()
                        if not desc_candidate or self._is_row_noise(desc_candidate):
                            continue
                        if qty_pair > 1_000_000:
                            continue
                        servico = {
                            "item": None,
                            "descricao": desc_candidate,
                            "unidade": unit_pair,
                            "quantidade": qty_pair
                        }
                        servicos.append(servico)
                        last_item = servico
                        last_item_qty_present = True
                    pending_desc = ""
                    pending_unit = ""
                    pending_qty = None
                    pending_qty_present = False
                    continue
                if row_text and row_parsed_unit and row_parsed_qty is not None:
                    merged_desc = row_text
                    qty_parsed = row_parsed_qty
                    unit_val = row_parsed_unit
                if merged_desc and unit_val and qty_present:
                    if self._is_row_noise(merged_desc) or (qty_parsed and qty_parsed > 1_000_000):
                        pending_desc = ""
                        pending_unit = ""
                        pending_qty = None
                        pending_qty_present = False
                        continue
                    servico = {
                        "item": None,
                        "descricao": merged_desc,
                        "unidade": unit_val,
                        "quantidade": qty_parsed
                    }
                    servicos.append(servico)
                    last_item = servico
                    last_item_qty_present = qty_present
                    pending_desc = ""
                    pending_unit = ""
                    pending_qty = None
                    pending_qty_present = False
                    continue

            if item_tuple:
                if pending_desc or pending_unit or pending_qty_present:
                    current_unit_missing = not unit_val
                    current_qty_missing = qty_parsed is None

                    # Fix B1: SEMPRE prepend pending_desc ao item atual (multi-line PDF layout)
                    # A linha anterior sem código é o início da descrição do item atual
                    if pending_desc:
                        desc_val = (pending_desc + " " + desc_val).strip() if desc_val else pending_desc

                    # Preencher unit/qty faltantes
                    if pending_unit and current_unit_missing:
                        unit_val = pending_unit
                    if pending_qty_present and current_qty_missing:
                        qty_parsed = pending_qty
                        qty_present = True

                    pending_desc = ""
                    pending_unit = ""
                    pending_qty = None
                    pending_qty_present = False

                item_tuples.append(item_tuple)
                item_str = item_tuple_to_str(item_tuple)
                # Fix B3: Extrair unidade do final da descrição se não tiver unidade
                if not unit_val and desc_val:
                    desc_val, trailing_unit = self._extract_trailing_unit(desc_val)
                    if trailing_unit:
                        unit_val = trailing_unit
                servico = {
                    "item": item_str,
                    "descricao": desc_val,
                    "unidade": unit_val,
                    "quantidade": qty_parsed
                }
                servicos.append(servico)
                last_item = servico
                last_item_qty_present = qty_present
            else:
                if pending_desc or pending_unit or pending_qty_present:
                    if desc_val and not (allow_itemless and self._is_row_noise(desc_val)):
                        pending_desc = (pending_desc + " " + desc_val).strip() if pending_desc else desc_val
                    if unit_val and not pending_unit:
                        pending_unit = unit_val
                    if qty_present and not pending_qty_present:
                        pending_qty = qty_parsed
                        pending_qty_present = True
                    continue
                if not last_item:
                    if desc_val and not (allow_itemless and self._is_row_noise(desc_val)):
                        pending_desc = desc_val
                    if unit_val:
                        pending_unit = unit_val
                    if qty_present:
                        pending_qty = qty_parsed
                        pending_qty_present = True
                    continue

                last_desc = str(last_item.get("descricao") or "").strip()
                last_desc_missing = not last_desc or len(last_desc) < 6
                last_unit_missing = not last_item.get("unidade")
                last_qty_missing = not last_item_qty_present
                row_desc_present = bool(desc_val)
                row_desc_short = (not row_desc_present) or len(desc_val) < 6
                row_has_unit_or_qty = bool(unit_val) or qty_present

                # Fix A3 (ampliado): Verificar se há item oculto no texto ANTES de processar
                # Isso captura casos como "JUNTA 6.14 ELÁSTICA... UN 2,00" onde o item está no meio
                if row_desc_present and len(desc_val) > 20:
                    hidden = self._extract_hidden_item_from_text(desc_val)
                    if hidden:
                        # Adicionar prefix ao item anterior
                        if hidden.get("prefix_for_last"):
                            last_item["descricao"] = (last_desc + " " + hidden["prefix_for_last"]).strip()
                        # Criar novo serviço para o item oculto (com unit/qty da linha se presente)
                        hidden_item_tuple = parse_item_tuple(hidden["item"])
                        if hidden_item_tuple:
                            item_tuples.append(hidden_item_tuple)
                            servico = {
                                "item": hidden["item"],
                                "descricao": hidden["descricao"],
                                "unidade": unit_val,  # Usar unit/qty da linha
                                "quantidade": qty_parsed
                            }
                            servicos.append(servico)
                            last_item = servico
                            last_item_qty_present = qty_present
                        continue

                if row_desc_present and not row_has_unit_or_qty and not is_section_header:
                    # Concatenar descrição ao último item (hidden item já foi verificado acima)
                    # Não concatenar se a linha parece ser um cabeçalho de seção (ex: "2 QUADRA...")
                    last_item["descricao"] = (last_desc + " " + desc_val).strip()
                    continue

                if (not row_desc_present) and row_has_unit_or_qty and (last_unit_missing or last_qty_missing):
                    if last_unit_missing and unit_val:
                        last_item["unidade"] = unit_val
                    if last_qty_missing and qty_present:
                        last_item["quantidade"] = qty_parsed
                        last_item_qty_present = True
                    continue

                if row_desc_present and row_has_unit_or_qty and last_desc_missing:
                    last_item["descricao"] = (last_desc + " " + desc_val).strip() if last_desc else desc_val
                    if last_unit_missing and unit_val:
                        last_item["unidade"] = unit_val
                    if last_qty_missing and qty_present:
                        last_item["quantidade"] = qty_parsed
                        last_item_qty_present = True
                    continue

                if row_desc_short and row_has_unit_or_qty and (last_unit_missing or last_qty_missing):
                    if last_unit_missing and unit_val:
                        last_item["unidade"] = unit_val
                    if last_qty_missing and qty_present:
                        last_item["quantidade"] = qty_parsed
                        last_item_qty_present = True
                    if row_desc_present:
                        last_item["descricao"] = (last_desc + " " + desc_val).strip()
                    continue

                if desc_val and not (allow_itemless and self._is_row_noise(desc_val)):
                    pending_desc = desc_val
                if unit_val:
                    pending_unit = unit_val
                if qty_present:
                    pending_qty = qty_parsed
                    pending_qty_present = True

        if (pending_desc or pending_unit or pending_qty_present) and last_item:
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
                last_item_qty_present = True
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

    def _first_last_item_tuple(self, servicos: list) -> tuple[Optional[tuple], Optional[tuple]]:
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

    def _get_header_row(self, table: list, header_index: Optional[int]) -> Optional[list]:
        if table is None:
            return None
        if isinstance(header_index, int) and 0 <= header_index < len(table):
            return table[header_index]
        for row in table:
            if row and any(str(cell or "").strip() for cell in row):
                return row
        return None

    def _is_header_like(self, row: Optional[list]) -> bool:
        if not row:
            return False
        header_map = guess_columns_by_header(row)
        match_count = sum(1 for v in header_map.values() if v is not None)
        return match_count >= TEC.HEADER_MIN_KEYWORD_MATCHES

    def _extract_planilha_label(self, raw_header: str, header_like: bool) -> str:
        if not raw_header:
            return ""
        if header_like:
            return raw_header
        normalized = normalize_description(raw_header)
        if not normalized:
            return ""
        tokens = ("TIPO DE OBRA", "CONTRATO", "OBRA", "CNPJ", "GEOBRAS", "ORCAMENTO", "ORCAMENTO SINTETICO")
        if any(token in normalized for token in tokens):
            return raw_header
        return ""

    def _build_table_signature(self, table: list, debug: dict) -> dict:
        header_index = debug.get("header_index") if isinstance(debug, dict) else None
        header_row = self._get_header_row(table, header_index)
        header_like = self._is_header_like(header_row)
        header_cells = []
        raw_header = ""
        if header_row:
            raw_header = " | ".join(str(cell or "").strip() for cell in header_row if str(cell or "").strip())
            if header_like:
                for cell in header_row:
                    normalized = normalize_header(str(cell or ""))
                    if normalized:
                        header_cells.append(normalized)
        header_text = " | ".join(header_cells) if header_cells else ""
        columns = (debug.get("columns") or {}) if isinstance(debug, dict) else {}
        col_sig = ",".join(f"{key}:{value}" for key, value in columns.items() if value is not None)
        if header_text:
            signature = f"h:{header_text}|c:{col_sig}"
        elif col_sig:
            signature = f"c:{col_sig}"
        else:
            signature = "c:none"
        label = self._extract_planilha_label(raw_header, header_like)
        return {
            "signature": signature,
            "label": label,
            "header_like": header_like,
            "raw_header": raw_header
        }

    def _should_start_new_planilha(
        self,
        current_planilha: Optional[dict],
        sig_info: dict,
        first_tuple: Optional[tuple]
    ) -> tuple[bool, str]:
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

    def _collect_item_codes(self, servicos: list) -> set:
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

    def _should_restart_prefix(
        self,
        first_tuple: Optional[tuple],
        max_tuple: Optional[tuple],
        table_codes: set,
        seen_codes: set
    ) -> tuple[bool, dict]:
        """
        Determina se deve adicionar prefixo de reinício (S1-, S2-, etc).

        Critério:
        - Primeira planilha NUNCA recebe prefixo (seen_codes vazio)
        - Planilhas subsequentes recebem prefixo SE houver overlap de códigos
          (mesmo número de item já foi usado anteriormente)
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

    def _apply_restart_prefix(self, servicos: list, prefix: str) -> None:
        if not servicos or not prefix:
            return
        for servico in servicos:
            item = str(servico.get("item") or "").strip()
            if not item:
                continue
            if re.match(r'^(AD|[A-Z]{1,3}\d+)-', item, re.IGNORECASE):
                continue
            servico["item"] = f"{prefix}-{item}"
            servico["_item_prefix"] = prefix

    def extract_servicos_from_tables(self, file_path: str) -> tuple[list, float, dict]:
        """
        Extrai serviços de todas as tabelas em um PDF usando pdfplumber.

        Args:
            file_path: Caminho para o arquivo PDF

        Returns:
            Tupla (servicos, confidence, debug)
        """
        try:
            tables = pdf_extractor.extract_tables(file_path, include_page=True)
        except (PDFError, IOError, ValueError) as exc:
            logger.warning(f"Erro ao extrair tabelas: {exc}")
            return [], 0.0, {"error": str(exc)}
        if not tables:
            return [], 0.0, {"tables": 0}

        all_servicos: list = []
        all_confidences: list = []
        best_debug: dict = {}
        seen_keys: set = set()
        global_seen_codes: set = set()
        restart_audit: list = []
        planilha_audit: list = []
        segment_index = 1
        global_max_tuple = None
        planilha_id = 0
        current_planilha: Optional[dict] = None

        for table_index, table in enumerate(tables):
            page_number = None
            rows = table
            if isinstance(table, dict):
                rows = table.get("rows") or []
                page_number = table.get("page")
            servicos, confidence, debug = self.extract_servicos_from_table(rows)
            debug["page"] = page_number
            if servicos:
                first_tuple, table_last_tuple = self._first_last_item_tuple(servicos)
                sig_info = self._build_table_signature(rows, debug)
                start_new, planilha_reason = self._should_start_new_planilha(
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
                    if page_number is not None:
                        s["_page"] = page_number

                table_codes = self._collect_item_codes(servicos)
                if start_new:
                    scope = "global"
                    scope_max = global_max_tuple
                    scope_seen = global_seen_codes
                else:
                    scope = "planilha"
                    scope_max = current_planilha.get("max_tuple")
                    scope_seen = current_planilha.get("seen_codes", set())
                apply_prefix, audit = self._should_restart_prefix(
                    first_tuple, scope_max, table_codes, scope_seen
                )
                audit["scope"] = scope
                audit["planilha_id"] = current_planilha["id"]
                audit["table_index"] = table_index
                audit["segment_index_before"] = segment_index
                if apply_prefix:
                    segment_index += 1
                    self._apply_restart_prefix(servicos, f"S{segment_index}")
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

    def extract_servicos_from_document_ai(
        self,
        file_path: str,
        use_native_pdf_parsing: bool = False,
        allow_itemless: bool = False,
        ignore_item_numbers: bool = False
    ) -> tuple[list, float, dict]:
        """
        Extrai serviços usando Google Document AI.

        Combina serviços de TODAS as tabelas detectadas (não apenas a melhor).

        Args:
            file_path: Caminho para o arquivo

        Returns:
            Tupla (servicos, confidence, debug)
        """
        if not document_ai_service.is_configured:
            return [], 0.0, {"enabled": False, "error": "not_configured", "imageless": use_native_pdf_parsing}
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

        # Combinar serviços de TODAS as tabelas (similar ao pdfplumber)
        all_servicos: list = []
        all_confidences: list = []
        best_debug: dict = {}
        seen_keys: set = set()
        global_seen_codes: set = set()
        restart_audit: list = []
        planilha_audit: list = []
        segment_index = 1
        global_max_tuple = None
        planilha_id = 0
        current_planilha: Optional[dict] = None

        for table_index, table in enumerate(tables):
            rows = table.get("rows") or []
            servicos, confidence, debug = self.extract_servicos_from_table(
                rows,
                allow_itemless=allow_itemless,
                ignore_item_numbers=ignore_item_numbers
            )
            debug["page"] = table.get("page")
            debug["imageless"] = use_native_pdf_parsing
            debug["allow_itemless"] = allow_itemless
            debug["ignore_item_numbers"] = ignore_item_numbers

            if servicos:
                first_tuple, table_last_tuple = self._first_last_item_tuple(servicos)
                sig_info = self._build_table_signature(rows, debug)
                start_new, planilha_reason = self._should_start_new_planilha(
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
                    # Atribuir página ao serviço para mapeamento correto
                    if page_number is not None:
                        s["_page"] = page_number

                table_codes = self._collect_item_codes(servicos)
                if start_new:
                    scope = "global"
                    scope_max = global_max_tuple
                    scope_seen = global_seen_codes
                else:
                    scope = "planilha"
                    scope_max = current_planilha.get("max_tuple")
                    scope_seen = current_planilha.get("seen_codes", set())
                apply_prefix, audit = self._should_restart_prefix(
                    first_tuple, scope_max, table_codes, scope_seen
                )
                audit["scope"] = scope
                audit["planilha_id"] = current_planilha["id"]
                audit["table_index"] = table_index
                audit["page"] = page_number
                audit["segment_index_before"] = segment_index
                if apply_prefix:
                    segment_index += 1
                    self._apply_restart_prefix(servicos, f"S{segment_index}")
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

        return all_servicos, avg_confidence, best_debug

    def calc_qty_ratio(self, servicos: list) -> float:
        """Calcula a proporção de serviços com quantidade válida."""
        if not servicos:
            return 0.0
        qty_count = sum(1 for s in servicos if parse_quantity(s.get("quantidade")) not in (None, 0))
        return qty_count / len(servicos)

    def calc_complete_ratio(self, servicos: list) -> float:
        """
        Calcula a proporção de serviços completos.

        Um serviço é considerado completo se possui:
        - item (código do item)
        - descricao (com mais de 5 caracteres)
        - unidade
        - quantidade (valor válido)

        Returns:
            Proporção de serviços completos (0.0 a 1.0)
        """
        if not servicos:
            return 0.0

        complete_count = sum(
            1 for s in servicos
            if (
                s.get("item") and
                s.get("descricao") and len(str(s.get("descricao", ""))) > 5 and
                s.get("unidade") and
                parse_quantity(s.get("quantidade")) not in (None, 0)
            )
        )
        return complete_count / len(servicos)

    def calc_quality_metrics(self, servicos: list) -> dict:
        """
        Calcula métricas de qualidade dos serviços extraídos.

        Returns:
            Dict com métricas: total, qty_ratio, complete_ratio, item_ratio, unit_ratio
        """
        if not servicos:
            return {
                "total": 0,
                "qty_ratio": 0.0,
                "complete_ratio": 0.0,
                "item_ratio": 0.0,
                "unit_ratio": 0.0
            }

        total = len(servicos)
        with_item = sum(1 for s in servicos if s.get("item"))
        with_qty = sum(1 for s in servicos if parse_quantity(s.get("quantidade")) not in (None, 0))
        with_unit = sum(1 for s in servicos if s.get("unidade"))
        complete = sum(
            1 for s in servicos
            if (
                s.get("item") and
                s.get("descricao") and len(str(s.get("descricao", ""))) > 5 and
                s.get("unidade") and
                parse_quantity(s.get("quantidade")) not in (None, 0)
            )
        )

        return {
            "total": total,
            "qty_ratio": with_qty / total,
            "complete_ratio": complete / total,
            "item_ratio": with_item / total,
            "unit_ratio": with_unit / total
        }

    def _normalize_desc_key(self, desc: str) -> str:
        if not desc:
            return ""
        return normalize_description(desc)[:80]

    def _merge_table_sources(self, primary: list, secondary: list) -> tuple[list, dict]:
        """
        Merge table items, preferring primary but filling missing data from secondary.
        """
        if not secondary:
            return primary, {"merged": False, "reason": "no_secondary", "primary_count": len(primary)}
        if not primary:
            return secondary, {"merged": False, "reason": "no_primary", "secondary_count": len(secondary)}

        result = []
        by_item: dict[str, list] = {}
        by_item_desc: dict[tuple[str, str], dict] = {}
        by_item_desc_keys: dict[str, set] = {}
        by_desc: set[str] = set()

        def add_servico(servico: dict) -> None:
            result.append(servico)
            item = servico.get("item")
            if item:
                item_key = str(item)
                by_item.setdefault(item_key, []).append(servico)
                desc_key = self._normalize_desc_key(servico.get("descricao") or "")
                if desc_key:
                    by_item_desc[(item_key, desc_key)] = servico
                    by_item_desc_keys.setdefault(item_key, set()).add(desc_key)
            else:
                key = self._normalize_desc_key(servico.get("descricao") or "")
                if key:
                    by_desc.add(key)

        for servico in primary:
            add_servico(servico)

        added = 0
        qty_filled = 0
        unit_filled = 0
        desc_updated = 0

        def find_similar_candidate(item_key: str, desc: str, threshold: float = 0.6) -> Optional[dict]:
            if not desc or item_key not in by_item:
                return None
            best = None
            best_score = 0.0
            for candidate in by_item[item_key]:
                cand_desc = candidate.get("descricao") or ""
                score = description_similarity(desc, cand_desc)
                if score > best_score:
                    best_score = score
                    best = candidate
            if best_score >= threshold:
                return best
            return None

        for servico in secondary:
            item = servico.get("item")
            item = str(item) if item else ""
            if item:
                desc_key = self._normalize_desc_key(servico.get("descricao"))
                target = None
                if desc_key:
                    target = by_item_desc.get((item, desc_key))
                    if target is None and item in by_item_desc_keys:
                        for existing_key in by_item_desc_keys[item]:
                            if desc_key in existing_key or existing_key in desc_key:
                                target = by_item_desc.get((item, existing_key))
                                break
                if target is None:
                    target = find_similar_candidate(item, servico.get("descricao") or "")
                if target is None and not desc_key and item in by_item:
                    target = by_item[item][0]

                if target is not None:
                    primary_qty = parse_quantity(target.get("quantidade"))
                    secondary_qty = parse_quantity(servico.get("quantidade"))
                    if (primary_qty in (None, 0)) and (secondary_qty not in (None, 0)):
                        target["quantidade"] = secondary_qty
                        qty_filled += 1

                    if not (target.get("unidade") or "").strip() and (servico.get("unidade") or "").strip():
                        target["unidade"] = servico.get("unidade")
                        unit_filled += 1

                    primary_desc = str(target.get("descricao") or "").strip()
                    secondary_desc = str(servico.get("descricao") or "").strip()
                    if secondary_desc and (not primary_desc or len(secondary_desc) > len(primary_desc) + 5):
                        target["descricao"] = secondary_desc
                        desc_updated += 1
                        updated_key = self._normalize_desc_key(secondary_desc)
                        if updated_key:
                            by_item_desc[(item, updated_key)] = target
                            by_item_desc_keys.setdefault(item, set()).add(updated_key)
                    continue

                if desc_key and item in by_item_desc_keys and desc_key in by_item_desc_keys[item]:
                    continue

                add_servico(servico)
                added += 1
                continue

            key = self._normalize_desc_key(servico.get("descricao"))
            if key and key in by_desc:
                continue
            add_servico(servico)
            added += 1

        debug = {
            "merged": True,
            "primary_count": len(primary),
            "secondary_count": len(secondary),
            "added": added,
            "qty_filled": qty_filled,
            "unit_filled": unit_filled,
            "desc_updated": desc_updated,
        }
        return result, debug

    def analyze_document_type(self, file_path: str) -> dict:
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

                    large_images = sum(
                        1 for img in page.images
                        if img.get("width", 0) > 400 and img.get("height", 0) > 400
                    )
                    total_large_images += large_images

                    if chars < APC.SCANNED_MIN_CHARS_PER_PAGE and large_images > 0:
                        pages_with_tables_in_images += 1

                avg_chars = total_chars / total_pages if total_pages > 0 else 0
                image_ratio = total_large_images / total_pages if total_pages > 0 else 0

                result["total_pages"] = total_pages
                result["avg_chars_per_page"] = avg_chars
                result["large_images_count"] = total_large_images

                result["is_scanned"] = (
                    avg_chars < APC.SCANNED_MIN_CHARS_PER_PAGE
                    or (avg_chars < 500 and image_ratio >= APC.SCANNED_IMAGE_PAGE_RATIO)
                )

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
        """Calcula a mediana de uma lista de valores."""
        if not values:
            return 0.0
        sorted_vals = sorted(values)
        mid = len(sorted_vals) // 2
        if len(sorted_vals) % 2 == 1:
            return float(sorted_vals[mid])
        return float(sorted_vals[mid - 1] + sorted_vals[mid]) / 2

    def _render_pdf_page(self, file_path: str, page_index: int, dpi: int) -> Optional[bytes]:
        """Renderiza uma pagina do PDF como imagem PNG."""
        try:
            doc = fitz.open(file_path)
            page = doc[page_index]
            zoom = dpi / 72
            matrix = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=matrix)
            img_bytes = pix.tobytes("png")
            doc.close()
            return img_bytes
        except Exception as exc:
            logger.debug(f"OCR layout: erro ao renderizar pagina {page_index + 1}: {exc}")
            return None

    def _crop_page_image(
        self,
        file_path: str,
        file_ext: str,
        page_index: int,
        image_bytes: bytes
    ) -> bytes:
        """Recorta a area mais provavel da tabela para OCR."""
        cropped = None
        if file_ext == ".pdf":
            try:
                with pdfplumber.open(file_path) as pdf:
                    page = pdf.pages[page_index]
                    large_images = [
                        img for img in (page.images or [])
                        if img.get("width", 0) > 400 and img.get("height", 0) > 400
                    ]
                    if large_images:
                        biggest = max(large_images, key=lambda img: img.get("width", 0) * img.get("height", 0))
                        page_width = page.width or 1
                        page_height = page.height or 1
                        left = biggest["x0"] / page_width
                        right = biggest["x1"] / page_width
                        top = biggest["top"] / page_height
                        bottom = biggest["bottom"] / page_height
                        cropped = pdf_extraction_service.crop_region(image_bytes, left, top, right, bottom)
            except Exception as exc:
                logger.debug(f"OCR layout: erro ao localizar imagem grande na pagina {page_index + 1}: {exc}")
        if cropped is None:
            cropped = pdf_extraction_service.crop_region(image_bytes, 0.05, 0.15, 0.95, 0.92)
        return cropped

    def _build_table_from_ocr_words(
        self,
        words: list,
        row_tol_factor: float = 0.6,
        col_tol_factor: float = 0.7,
        min_row_tol: float = 6.0,
        min_col_tol: float = 18.0
    ) -> tuple[list, list]:
        """Constrói tabela a partir de palavras OCR baseado em layout."""
        if not words:
            return [], []
        heights = [w["height"] for w in words if w.get("height")]
        widths = [w["width"] for w in words if w.get("width")]
        median_height = self._median(heights) or 12.0
        median_width = self._median(widths) or 40.0
        row_tol = max(min_row_tol, median_height * row_tol_factor)
        col_tol = max(min_col_tol, median_width * col_tol_factor)

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
        """Infere a coluna de item a partir das palavras OCR."""
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

    def _extract_from_ocr_words(
        self,
        words: list,
        row_tol_factor: float = 0.6,
        col_tol_factor: float = 0.7,
        enable_refine: bool = True
    ) -> tuple[list, float, dict, dict]:
        table_rows, col_centers = self._build_table_from_ocr_words(
            words,
            row_tol_factor=row_tol_factor,
            col_tol_factor=col_tol_factor
        )
        preferred_item_col, item_col_debug = self._infer_item_column_from_words(words, col_centers)
        servicos, confidence, debug = self.extract_servicos_from_table(
            table_rows,
            preferred_item_col=preferred_item_col
        )
        servicos_itemless, conf_itemless, debug_itemless = self.extract_servicos_from_table(
            table_rows,
            preferred_item_col=None,
            allow_itemless=True,
            ignore_item_numbers=True
        )
        item_suspicious, item_suspicious_info = self._item_sequence_suspicious(servicos)
        if servicos_itemless:
            qty_ratio_itemless = self.calc_qty_ratio(servicos_itemless)
            qty_ratio_regular = self.calc_qty_ratio(servicos)
            prefer_itemless = (
                len(servicos_itemless) >= len(servicos) + 3
                and qty_ratio_itemless >= max(0.6, qty_ratio_regular)
            )
            if qty_ratio_itemless >= max(0.9, qty_ratio_regular + 0.4):
                prefer_itemless = True
            if item_suspicious:
                servicos = servicos_itemless
                confidence = conf_itemless
                debug = debug_itemless
                debug["itemless_forced"] = True
            elif prefer_itemless:
                servicos = servicos_itemless
                confidence = conf_itemless
                debug = debug_itemless
                debug["itemless_mode"] = True
        debug["item_suspicious"] = item_suspicious_info
        stats = debug.get("stats") or {}
        dominant = debug.get("dominant_item") or {}
        total_page_items = stats.get("total", 0)
        item_ratio = stats.get("with_item", 0) / max(1, total_page_items)
        unit_ratio = stats.get("with_unit", 0) / max(1, total_page_items)
        dominant_len = dominant.get("dominant_len", 0) or 0
        qty_ratio = self.calc_qty_ratio(servicos)
        metrics = {
            "row_count": len(table_rows),
            "word_count": len(words),
            "item_col": item_col_debug,
            "total_page_items": total_page_items,
            "item_ratio": item_ratio,
            "unit_ratio": unit_ratio,
            "dominant_len": dominant_len,
            "qty_ratio": qty_ratio
        }
        if enable_refine and row_tol_factor >= 0.6:
            refine_min_words = max(40, int(APC.OCR_LAYOUT_RETRY_MIN_WORDS * 0.6))
            needs_refine = (
                metrics.get("total_page_items", 0) < APC.OCR_LAYOUT_RETRY_MIN_ITEMS
                and metrics.get("word_count", 0) >= refine_min_words
            )
            if needs_refine:
                refined_servicos, refined_conf, refined_debug, refined_metrics = self._extract_from_ocr_words(
                    words,
                    row_tol_factor=0.45,
                    col_tol_factor=col_tol_factor,
                    enable_refine=False
                )
                refine_info = {
                    "attempted": True,
                    "used": False,
                    "base": {
                        "items": len(servicos),
                        "row_count": metrics.get("row_count", 0),
                        "qty_ratio": round(metrics.get("qty_ratio", 0.0), 3)
                    },
                    "refined": {
                        "items": len(refined_servicos),
                        "row_count": refined_metrics.get("row_count", 0),
                        "qty_ratio": round(refined_metrics.get("qty_ratio", 0.0), 3)
                    }
                }
                use_refine = False
                if refined_servicos:
                    if len(refined_servicos) >= len(servicos) + 2:
                        use_refine = True
                    elif refined_metrics.get("qty_ratio", 0.0) >= metrics.get("qty_ratio", 0.0) + 0.1:
                        use_refine = True
                    elif (
                        len(refined_servicos) > len(servicos)
                        and refined_metrics.get("unit_ratio", 0.0) >= metrics.get("unit_ratio", 0.0)
                    ):
                        use_refine = True
                if use_refine:
                    refine_info["used"] = True
                    refined_debug["row_refine"] = refine_info
                    return refined_servicos, refined_conf, refined_debug, refined_metrics
                debug["row_refine"] = refine_info
        return servicos, confidence, debug, metrics

    def _item_sequence_suspicious(self, servicos: list) -> tuple[bool, dict]:
        items = [str(s.get("item")).strip() for s in servicos if s.get("item")]
        count = len(items)
        if count < 4:
            return False, {"count": count, "large_segment_ratio": 0.0, "duplicate_ratio": 0.0}

        tuples = [parse_item_tuple(item) for item in items]
        large_segment = 0
        for item_tuple in tuples:
            if not item_tuple:
                continue
            if any(seg >= 100 for seg in item_tuple):
                large_segment += 1

        unique_ratio = len(set(items)) / max(1, count)
        duplicate_ratio = 1 - unique_ratio
        large_segment_ratio = large_segment / max(1, count)

        suspicious = large_segment_ratio >= 0.3 or duplicate_ratio >= 0.25
        info = {
            "count": count,
            "large_segment_ratio": round(large_segment_ratio, 3),
            "duplicate_ratio": round(duplicate_ratio, 3),
            "large_segment_count": large_segment
        }
        return suspicious, info

    def _assign_itemless_items(self, servicos: list, page_number: int) -> None:
        prefix = f"S{page_number}-"
        seq = 1
        for servico in servicos:
            if servico.get("item"):
                continue
            servico["item"] = f"{prefix}{seq}"
            seq += 1

    def _detect_grid_rows(self, image_bytes: bytes) -> tuple[list, dict]:
        if not image_bytes:
            return [], {"error": "empty_image"}
        img_array = np.frombuffer(image_bytes, np.uint8)
        gray = cv2.imdecode(img_array, cv2.IMREAD_GRAYSCALE)
        if gray is None:
            return [], {"error": "decode_failed"}
        height, width = gray.shape[:2]
        blur = cv2.GaussianBlur(gray, (3, 3), 0)
        _, bw = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

        def detect_rows_by_projection() -> tuple[list, dict]:
            row_sum = (bw > 0).sum(axis=1)
            threshold = max(10, int(width * 0.02))
            segments = []
            in_row = False
            start = 0
            for idx, value in enumerate(row_sum):
                if value >= threshold and not in_row:
                    start = idx
                    in_row = True
                elif value < threshold and in_row:
                    end = idx - 1
                    segments.append((start, end))
                    in_row = False
            if in_row:
                segments.append((start, height - 1))

            if not segments:
                return [], {"segments": 0, "threshold": threshold}

            heights = [end - start + 1 for start, end in segments]
            median_height = self._median(heights) or max(12, int(height * 0.015))
            merge_gap = max(4, int(median_height * 0.6))
            merged: List[List[int]] = []
            for start, end in segments:
                if not merged:
                    merged.append([start, end])
                    continue
                if start - merged[-1][1] <= merge_gap:
                    merged[-1][1] = end
                else:
                    merged.append([start, end])
            rows = []
            min_row_height = max(12, int(height * 0.015))
            for start, end in merged:
                if end - start + 1 < min_row_height:
                    continue
                top = max(0, start - 1)
                bottom = min(height - 1, end + 1)
                rows.append((top, bottom))
            debug = {
                "segments": len(segments),
                "rows_detected": len(rows),
                "threshold": threshold,
                "merge_gap": merge_gap,
                "method": "projection"
            }
            return rows, debug

        def extract_rows(min_width_ratio: float, max_height_ratio: float) -> tuple[list, dict]:
            horizontal_kernel = cv2.getStructuringElement(
                cv2.MORPH_RECT,
                (max(10, int(width * 0.03)), 1)
            )
            horizontal = cv2.erode(bw, horizontal_kernel, iterations=1)
            horizontal = cv2.dilate(horizontal, horizontal_kernel, iterations=1)
            contours, _ = cv2.findContours(horizontal, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            lines_y = []
            min_width = int(width * min_width_ratio)
            max_height = max(6, int(height * max_height_ratio))
            for cnt in contours:
                x, y, w, h = cv2.boundingRect(cnt)
                if w < min_width or h > max_height:
                    continue
                lines_y.append(y)
                lines_y.append(y + h)
            lines_y = sorted(lines_y)
            merged: List[int] = []
            for y in lines_y:
                if not merged or y - merged[-1] > 4:
                    merged.append(y)
            rows = []
            min_row_height = max(12, int(height * 0.015))
            for idx in range(len(merged) - 1):
                top = merged[idx] + 1
                bottom = merged[idx + 1] - 1
                if bottom - top < min_row_height:
                    continue
                rows.append((top, bottom))
            return rows, {
                "lines_detected": len(merged),
                "rows_detected": len(rows),
                "width": width,
                "height": height
            }

        rows, debug = extract_rows(0.6, 0.03)
        if len(rows) < 8:
            fallback_rows, fallback_debug = extract_rows(0.4, 0.05)
            if len(fallback_rows) > len(rows):
                fallback_debug["fallback"] = True
                rows, debug = fallback_rows, fallback_debug

        if len(rows) < 8:
            proj_rows, proj_debug = detect_rows_by_projection()
            if len(proj_rows) > len(rows):
                proj_debug["fallback"] = True
                return proj_rows, proj_debug
        return rows, debug

    def _is_header_row(self, text: str) -> bool:
        if not text:
            return False
        normalized = normalize_description(text)
        if not normalized:
            return False
        header_tokens = ("ITEM", "DESCRICAO", "UND", "UNID", "QUANT")
        hits = sum(1 for token in header_tokens if token in normalized)
        return hits >= 2

    def _parse_row_text_to_servicos(self, row_text: str) -> list:
        if not row_text:
            return []
        if self._is_row_noise(row_text) or self._is_header_row(row_text):
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

        row_pairs = self._find_unit_qty_pairs(base_text)
        servicos = []
        if row_pairs:
            prev_end = 0
            for idx, (unit_pair, qty_pair, start, end) in enumerate(row_pairs):
                desc_candidate = base_text[prev_end:start].strip()
                if not desc_candidate:
                    desc_candidate = base_text[:start].strip()
                prev_end = end
                if not desc_candidate or self._is_row_noise(desc_candidate):
                    continue
                servicos.append({
                    "item": item_val if idx == 0 else None,
                    "descricao": desc_candidate,
                    "unidade": unit_pair,
                    "quantidade": qty_pair
                })
            if servicos:
                return servicos

        parsed = self._parse_unit_qty_from_text(base_text)
        if not parsed:
            return []
        unit_val, qty_val = parsed
        desc = re.sub(
            rf'\\b{re.escape(unit_val)}\\b\\s*[\d.,]+\\s*$',
            '',
            base_text,
            flags=re.IGNORECASE
        ).strip()
        if not desc or self._is_row_noise(desc):
            return []
        servicos.append({
            "item": item_val,
            "descricao": desc,
            "unidade": unit_val,
            "quantidade": qty_val
        })
        return servicos

    def extract_servicos_from_grid_ocr(
        self,
        file_path: str,
        progress_callback: ProgressCallback = None,
        cancel_check: CancelCheck = None
    ) -> tuple[list, float, dict]:
        min_conf = APC.OCR_LAYOUT_CONFIDENCE
        dpi = APC.OCR_LAYOUT_DPI

        images = []
        file_ext = Path(file_path).suffix.lower()
        if file_ext == ".pdf":
            images = pdf_extraction_service.pdf_to_images(
                file_path,
                dpi=dpi,
                progress_callback=progress_callback,
                cancel_check=cancel_check,
                stage="ocr_grid"
            )
        else:
            with open(file_path, "rb") as f:
                images = [f.read()]

        if not images:
            return [], 0.0, {"pages": 0}

        all_servicos = []
        page_debug = []

        for page_index, image_bytes in enumerate(images):
            pdf_extraction_service._check_cancel(cancel_check)
            cropped = self._crop_page_image(file_path, file_ext, page_index, image_bytes)
            row_boxes, row_debug = self._detect_grid_rows(cropped)
            if not row_boxes:
                page_debug.append({
                    "page": page_index + 1,
                    "rows": 0,
                    "grid": row_debug,
                    "reason": "no_rows"
                })
                continue
            try:
                words = ocr_service.extract_words_from_bytes(cropped, min_confidence=min_conf)
            except OCRError as exc:
                page_debug.append({
                    "page": page_index + 1,
                    "rows": len(row_boxes),
                    "grid": row_debug,
                    "error": str(exc)
                })
                continue

            row_count = 0
            for top, bottom in row_boxes:
                row_words = [
                    w for w in words
                    if w.get("y_center") is not None
                    and top <= w["y_center"] <= bottom
                ]
                if not row_words:
                    continue
                row_words_sorted = sorted(row_words, key=lambda w: w.get("x_center", 0))
                row_text = " ".join(w.get("text", "") for w in row_words_sorted).strip()
                if not row_text:
                    continue
                row_servicos = self._parse_row_text_to_servicos(row_text)
                if row_servicos:
                    row_count += 1
                    all_servicos.extend(row_servicos)

            page_debug.append({
                "page": page_index + 1,
                "rows": row_count,
                "grid": row_debug,
                "word_count": len(words)
            })

        stats = compute_servicos_stats(all_servicos)
        confidence = compute_quality_score(stats)
        confidence = max(0.0, min(1.0, round(confidence, 3)))
        debug = {
            "pages": len(images),
            "page_debug": page_debug,
            "stats": stats,
            "confidence": confidence
        }
        return all_servicos, confidence, debug

    def extract_servicos_from_ocr_layout(
        self,
        file_path: str,
        progress_callback: ProgressCallback = None,
        cancel_check: CancelCheck = None
    ) -> tuple[list, float, dict]:
        """
        Extrai serviços usando OCR com análise de layout.

        Args:
            file_path: Caminho para o arquivo
            progress_callback: Callback para progresso
            cancel_check: Função para verificar cancelamento

        Returns:
            Tupla (servicos, confidence, debug)
        """
        min_conf = APC.OCR_LAYOUT_CONFIDENCE
        dpi = APC.OCR_LAYOUT_DPI
        page_min_items = APC.OCR_LAYOUT_PAGE_MIN_ITEMS
        retry_dpi = APC.OCR_LAYOUT_RETRY_DPI
        retry_dpi_hard = APC.OCR_LAYOUT_RETRY_DPI_HARD
        retry_conf = APC.OCR_LAYOUT_RETRY_CONFIDENCE
        retry_min_words = APC.OCR_LAYOUT_RETRY_MIN_WORDS
        retry_min_items = APC.OCR_LAYOUT_RETRY_MIN_ITEMS
        retry_min_qty_ratio = APC.OCR_LAYOUT_RETRY_MIN_QTY_RATIO

        images = []
        file_ext = Path(file_path).suffix.lower()
        if file_ext == ".pdf":
            images = pdf_extraction_service.pdf_to_images(
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

        table_pages = pdf_extraction_service.detect_table_pages(images)
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
            pdf_extraction_service._check_cancel(cancel_check)
            image_bytes = images[page_index]
            cropped = self._crop_page_image(file_path, file_ext, page_index, image_bytes)
            try:
                words = ocr_service.extract_words_from_bytes(cropped, min_confidence=min_conf)
            except OCRError as exc:
                logger.debug(f"Erro OCR na pagina {page_index + 1}: {exc}")
                page_debug.append({"page": page_index + 1, "error": str(exc)})
                continue

            servicos, confidence, debug, metrics = self._extract_from_ocr_words(words)
            base_metrics = metrics
            retry_info = {
                "attempted": False,
                "used": False,
                "base": {
                    "word_count": base_metrics.get("word_count", 0),
                    "items": len(servicos),
                    "qty_ratio": round(base_metrics.get("qty_ratio", 0.0), 3)
                }
            }
            should_retry = (
                base_metrics.get("word_count", 0) < retry_min_words
                or base_metrics.get("total_page_items", 0) < retry_min_items
                or base_metrics.get("qty_ratio", 0.0) < retry_min_qty_ratio
            )
            if should_retry:
                retry_info["attempted"] = True
                retry_image_bytes = image_bytes
                rendered_dpi = dpi
                if file_ext == ".pdf" and retry_dpi > dpi:
                    rerendered = self._render_pdf_page(file_path, page_index, retry_dpi)
                    if rerendered:
                        retry_image_bytes = rerendered
                        rendered_dpi = retry_dpi
                retry_cropped = self._crop_page_image(file_path, file_ext, page_index, retry_image_bytes)
                try:
                    words_retry = ocr_service.extract_words_from_bytes(
                        retry_cropped,
                        min_confidence=retry_conf,
                        use_binarization=True
                    )
                    servicos_retry, conf_retry, debug_retry, metrics_retry = self._extract_from_ocr_words(words_retry)
                    retry_info["retry"] = {
                        "rendered_dpi": rendered_dpi,
                        "min_confidence": retry_conf,
                        "word_count": metrics_retry.get("word_count", 0),
                        "items": len(servicos_retry),
                        "qty_ratio": round(metrics_retry.get("qty_ratio", 0.0), 3)
                    }
                    use_retry = False
                    if servicos_retry:
                        if not servicos:
                            use_retry = True
                        elif len(servicos_retry) >= len(servicos) + 2:
                            use_retry = True
                        elif metrics_retry.get("qty_ratio", 0.0) >= base_metrics.get("qty_ratio", 0.0) + 0.1:
                            use_retry = True
                        elif (
                            len(servicos_retry) > len(servicos)
                            and metrics_retry.get("unit_ratio", 0.0) >= base_metrics.get("unit_ratio", 0.0)
                        ):
                            use_retry = True
                    if use_retry:
                        servicos = servicos_retry
                        confidence = conf_retry
                        debug = debug_retry
                        metrics = metrics_retry
                        retry_info["used"] = True
                except OCRError as exc:
                    retry_info["error"] = str(exc)

                needs_hard_retry = (
                    retry_dpi_hard
                    and retry_dpi_hard > retry_dpi
                    and (metrics.get("word_count", 0) < retry_min_words
                         or metrics.get("total_page_items", 0) < retry_min_items
                         or metrics.get("qty_ratio", 0.0) < retry_min_qty_ratio)
                )
                if needs_hard_retry:
                    retry_info["hard_attempted"] = True
                    hard_image_bytes = image_bytes
                    hard_rendered_dpi = dpi
                    if file_ext == ".pdf" and retry_dpi_hard > dpi:
                        rerendered = self._render_pdf_page(file_path, page_index, retry_dpi_hard)
                        if rerendered:
                            hard_image_bytes = rerendered
                            hard_rendered_dpi = retry_dpi_hard
                    hard_cropped = self._crop_page_image(file_path, file_ext, page_index, hard_image_bytes)
                    try:
                        words_hard = ocr_service.extract_words_from_bytes(
                            hard_cropped,
                            min_confidence=retry_conf,
                            use_binarization=True
                        )
                        servicos_hard, conf_hard, debug_hard, metrics_hard = self._extract_from_ocr_words(words_hard)
                        retry_info["hard"] = {
                            "rendered_dpi": hard_rendered_dpi,
                            "min_confidence": retry_conf,
                            "word_count": metrics_hard.get("word_count", 0),
                            "items": len(servicos_hard),
                            "qty_ratio": round(metrics_hard.get("qty_ratio", 0.0), 3)
                        }
                        use_hard = False
                        if servicos_hard:
                            if not servicos:
                                use_hard = True
                            elif len(servicos_hard) >= len(servicos) + 2:
                                use_hard = True
                            elif metrics_hard.get("qty_ratio", 0.0) >= metrics.get("qty_ratio", 0.0) + 0.1:
                                use_hard = True
                            elif (
                                len(servicos_hard) > len(servicos)
                                and metrics_hard.get("unit_ratio", 0.0) >= metrics.get("unit_ratio", 0.0)
                            ):
                                use_hard = True
                        if use_hard:
                            servicos = servicos_hard
                            confidence = conf_hard
                            debug = debug_hard
                            metrics = metrics_hard
                            retry_info["used"] = True
                            retry_info["hard_used"] = True
                    except OCRError as exc:
                        retry_info["hard_error"] = str(exc)

            total_page_items = metrics.get("total_page_items", 0)
            item_ratio = metrics.get("item_ratio", 0.0)
            unit_ratio = metrics.get("unit_ratio", 0.0)
            dominant_len = metrics.get("dominant_len", 0) or 0
            qty_ratio = metrics.get("qty_ratio", 0.0)

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
            itemless_accept = (
                (debug.get("itemless_mode") or debug.get("itemless_forced"))
                and total_page_items >= APC.OCR_PAGE_MIN_ITEMS
                and unit_ratio >= APC.OCR_PAGE_FALLBACK_UNIT_RATIO
                and qty_ratio >= APC.OCR_PAGE_FALLBACK_UNIT_RATIO
            )
            page_accept = primary_accept or fallback_accept or itemless_accept
            if page_accept and servicos and (debug.get("itemless_mode") or debug.get("itemless_forced")):
                self._assign_itemless_items(servicos, page_index + 1)
                debug["itemless_assigned"] = True
            debug.update({
                "page": page_index + 1,
                "row_count": metrics.get("row_count", 0),
                "word_count": metrics.get("word_count", 0),
                "item_col": metrics.get("item_col", {}),
                "page_accept": page_accept,
                "qty_ratio": round(qty_ratio, 3),
                "ocr_retry": retry_info
            })
            page_debug.append(debug)
            processed_pages.append(page_index)
            if not page_accept:
                continue

            if servicos:
                # Atribuir página a cada serviço (1-indexed)
                page_num = page_index + 1
                for s in servicos:
                    s["_page"] = page_num
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

    def _summarize_table_debug(self, debug: dict) -> dict:
        """Resume informações de debug da tabela."""
        if not isinstance(debug, dict):
            return {}
        summary = {}
        for key in ("source", "tables", "pages", "pages_used", "error", "imageless"):
            if key in debug:
                summary[key] = debug.get(key)
        if "ocr_noise" in debug:
            summary["ocr_noise"] = debug.get("ocr_noise")
        return summary

    def extract_cascade(
        self,
        file_path: str,
        file_ext: str,
        progress_callback: ProgressCallback = None,
        cancel_check: CancelCheck = None,
        doc_analysis: Optional[dict] = None
    ) -> tuple[list, float, dict, dict]:
        """
        Extrai serviços de tabelas usando fluxo em cascata otimizado.

        Fluxo:
        1. pdfplumber (gratuito) - se qty_ratio >= 70%: SUCESSO
        2. Document AI (~R$0.008/pág) - se qty_ratio >= 60%: SUCESSO
        3. Fallback para melhor resultado disponível

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

        stage1_threshold = APC.STAGE1_QTY_THRESHOLD
        stage2_threshold = APC.STAGE2_QTY_THRESHOLD
        min_items_for_confidence = APC.MIN_ITEMS_FOR_CONFIDENCE

        document_ai_enabled = APC.DOCUMENT_AI_ENABLED
        document_ai_ready = document_ai_enabled and document_ai_service.is_configured
        document_ai_fallback_only = APC.DOCUMENT_AI_FALLBACK_ONLY

        if file_ext == ".pdf":
            if doc_analysis is None:
                doc_analysis = self.analyze_document_type(file_path)
            table_debug["doc_analysis"] = doc_analysis
            is_scanned = bool(doc_analysis.get("is_scanned")) if isinstance(doc_analysis, dict) else False
            has_image_tables = bool(doc_analysis.get("has_image_tables")) if isinstance(doc_analysis, dict) else False
            text_useful = (not is_scanned) and (not has_image_tables)
            large_images = int(doc_analysis.get("large_images_count") or 0) if isinstance(doc_analysis, dict) else 0
            allow_itemless_doc = bool(is_scanned or has_image_tables)

            # ETAPA 1: pdfplumber
            pdf_servicos: list = []
            pdf_conf = 0.0
            pdf_debug: dict = {}
            pdf_qty_ratio = 0.0
            pdf_complete_ratio = 0.0
            doc_servicos: list = []
            doc_conf = 0.0
            doc_debug: dict = {}
            doc_qty_ratio = 0.0
            doc_complete_ratio = 0.0

            if is_scanned:
                logger.info("Cascata: pulando pdfplumber (documento escaneado)")
                table_attempts["pdfplumber"] = {"skipped": True, "reason": "scanned"}
            else:
                logger.info("Cascata Etapa 1: Tentando pdfplumber...")
                pdf_servicos, pdf_conf, pdf_debug = self.extract_servicos_from_tables(file_path)
                pdf_debug["source"] = "pdfplumber"
                pdf_qty_ratio = self.calc_qty_ratio(pdf_servicos)
                pdf_complete_ratio = self.calc_complete_ratio(pdf_servicos)
                table_attempts["pdfplumber"] = {
                    "count": len(pdf_servicos),
                    "confidence": pdf_conf,
                    "qty_ratio": pdf_qty_ratio,
                    "complete_ratio": pdf_complete_ratio,
                    "debug": self._summarize_table_debug(pdf_debug)
                }

            # Sucesso se qty_ratio >= threshold E complete_ratio > 0 (tem serviços completos)
            if pdf_servicos and pdf_qty_ratio >= stage1_threshold and pdf_complete_ratio > 0:
                logger.info(
                    f"Cascata: pdfplumber SUCESSO - {len(pdf_servicos)} serviços, "
                    f"qty_ratio={pdf_qty_ratio:.0%}, complete_ratio={pdf_complete_ratio:.0%}"
                )
                servicos_table = pdf_servicos
                table_confidence = pdf_conf
                table_debug = pdf_debug
                table_debug["cascade_stage"] = 1
                table_debug["cascade_reason"] = "pdfplumber_success"
                return servicos_table, table_confidence, table_debug, table_attempts

            logger.info(
                f"Cascata: pdfplumber insuficiente - {len(pdf_servicos)} serviços, "
                f"qty_ratio={pdf_qty_ratio:.0%}, complete_ratio={pdf_complete_ratio:.0%}"
            )

            # ETAPA 2: Document AI
            if document_ai_ready and not document_ai_fallback_only:
                logger.info("Cascata Etapa 2: Tentando Document AI...")
                try:
                    doc_servicos, doc_conf, doc_debug = self.extract_servicos_from_document_ai(
                        file_path,
                        allow_itemless=allow_itemless_doc
                    )
                    doc_debug["source"] = "document_ai"
                    if (
                        doc_debug.get("error")
                        and "PAGE_LIMIT_EXCEEDED" in str(doc_debug.get("error"))
                        and not text_useful
                    ):
                        logger.info("Cascata: Document AI page limit, tentando imageless...")
                        doc_servicos, doc_conf, doc_debug = self.extract_servicos_from_document_ai(
                            file_path,
                            use_native_pdf_parsing=True,
                            allow_itemless=allow_itemless_doc
                        )
                        doc_debug["source"] = "document_ai"
                        doc_debug["retry_reason"] = "page_limit_exceeded"

                    if doc_servicos and pdf_servicos:
                        doc_servicos, merge_debug = self._merge_table_sources(doc_servicos, pdf_servicos)
                        doc_debug["merge"] = merge_debug
                    doc_qty_ratio = self.calc_qty_ratio(doc_servicos)
                    doc_complete_ratio = self.calc_complete_ratio(doc_servicos)
                    table_attempts["document_ai"] = {
                        "count": len(doc_servicos),
                        "confidence": doc_conf,
                        "qty_ratio": doc_qty_ratio,
                        "complete_ratio": doc_complete_ratio,
                        "debug": self._summarize_table_debug(doc_debug)
                    }

                    if doc_servicos and doc_qty_ratio >= stage2_threshold:
                        logger.info(
                            f"Cascata: Document AI SUCESSO - {len(doc_servicos)} serviços, "
                            f"qty_ratio={doc_qty_ratio:.0%}, complete_ratio={doc_complete_ratio:.0%}"
                        )
                        servicos_table = doc_servicos
                        table_confidence = doc_conf
                        table_debug = doc_debug
                        table_debug["cascade_stage"] = 2
                        table_debug["cascade_reason"] = "document_ai_success"
                        return servicos_table, table_confidence, table_debug, table_attempts

                    logger.info(
                        f"Cascata: Document AI insuficiente - {len(doc_servicos)} serviços, "
                        f"qty_ratio={doc_qty_ratio:.0%}, complete_ratio={doc_complete_ratio:.0%}"
                    )

                    # Usar Document AI se tiver melhor qualidade (qty_ratio ou complete_ratio)
                    if doc_qty_ratio > pdf_qty_ratio or doc_complete_ratio > pdf_complete_ratio:
                        servicos_table = doc_servicos
                        table_confidence = doc_conf
                        table_debug = doc_debug
                        table_debug["cascade_stage"] = 2
                        table_debug["cascade_reason"] = "document_ai_better"

                except Exception as e:
                    logger.warning(f"Cascata: Document AI falhou - {e}")
                    table_attempts["document_ai"] = {"error": str(e)}
            elif document_ai_ready and document_ai_fallback_only:
                logger.info("Cascata: Document AI aguardando fallback pós-OCR")
                table_attempts["document_ai"] = {"skipped": True, "reason": "fallback_only"}
            else:
                logger.info("Cascata: Document AI não disponível")

            # ETAPA 2.5: OCR layout (fallback para tabelas em imagem sem numeração)
            ocr_servicos: list = []
            ocr_conf = 0.0
            ocr_debug: dict = {}
            ocr_qty_ratio = 0.0
            ocr_complete_ratio = 0.0
            should_try_ocr = (
                large_images > 0
                and not pdf_servicos
                and (not doc_servicos or doc_qty_ratio < stage2_threshold)
            )
            if should_try_ocr:
                logger.info("Cascata Etapa 2.5: Tentando OCR layout (tabela em imagem)...")
                try:
                    ocr_servicos, ocr_conf, ocr_debug = self.extract_servicos_from_ocr_layout(
                        file_path,
                        progress_callback=progress_callback,
                        cancel_check=cancel_check
                    )
                    ocr_debug["source"] = "ocr_layout"
                    ocr_qty_ratio = self.calc_qty_ratio(ocr_servicos)
                    ocr_complete_ratio = self.calc_complete_ratio(ocr_servicos)
                    table_attempts["ocr_layout"] = {
                        "count": len(ocr_servicos),
                        "confidence": ocr_conf,
                        "qty_ratio": ocr_qty_ratio,
                        "complete_ratio": ocr_complete_ratio,
                        "debug": self._summarize_table_debug(ocr_debug)
                    }
                    if (
                        ocr_servicos
                        and (ocr_qty_ratio > doc_qty_ratio or ocr_complete_ratio > doc_complete_ratio)
                    ):
                        servicos_table = ocr_servicos
                        table_confidence = ocr_conf
                        table_debug = ocr_debug
                        table_debug["cascade_stage"] = 3
                        table_debug["cascade_reason"] = "ocr_layout_better"
                except Exception as exc:
                    logger.warning(f"Cascata: OCR layout falhou - {exc}")
                    table_attempts["ocr_layout"] = {"error": str(exc)}

            best_ocr_servicos = ocr_servicos
            best_ocr_conf = ocr_conf
            best_ocr_debug = ocr_debug
            best_ocr_qty_ratio = ocr_qty_ratio
            best_ocr_complete_ratio = ocr_complete_ratio
            best_ocr_label = "ocr_layout"

            # ETAPA 2.6: Grid OCR (OpenCV) para tabelas em imagem
            grid_servicos: list = []
            grid_conf = 0.0
            grid_debug: dict = {}
            grid_qty_ratio = 0.0
            grid_complete_ratio = 0.0
            best_ocr_count = len(best_ocr_servicos) if best_ocr_servicos else 0
            should_try_grid = (
                large_images > 0
                and best_ocr_count < min_items_for_confidence
            )
            if should_try_grid:
                logger.info("Cascata Etapa 2.6: Tentando Grid OCR (OpenCV)...")
                try:
                    grid_servicos, grid_conf, grid_debug = self.extract_servicos_from_grid_ocr(
                        file_path,
                        progress_callback=progress_callback,
                        cancel_check=cancel_check
                    )
                    grid_debug["source"] = "grid_ocr"
                    grid_qty_ratio = self.calc_qty_ratio(grid_servicos)
                    grid_complete_ratio = self.calc_complete_ratio(grid_servicos)
                    table_attempts["grid_ocr"] = {
                        "count": len(grid_servicos),
                        "confidence": grid_conf,
                        "qty_ratio": grid_qty_ratio,
                        "complete_ratio": grid_complete_ratio,
                        "debug": self._summarize_table_debug(grid_debug)
                    }
                    if grid_servicos and (
                        grid_qty_ratio > best_ocr_qty_ratio
                        or grid_complete_ratio > best_ocr_complete_ratio
                        or len(grid_servicos) >= len(best_ocr_servicos) + 2
                    ):
                        best_ocr_servicos = grid_servicos
                        best_ocr_conf = grid_conf
                        best_ocr_debug = grid_debug
                        best_ocr_qty_ratio = grid_qty_ratio
                        best_ocr_complete_ratio = grid_complete_ratio
                        best_ocr_label = "grid_ocr"
                except Exception as exc:
                    logger.warning(f"Cascata: Grid OCR falhou - {exc}")
                    table_attempts["grid_ocr"] = {"error": str(exc)}

            # Usar o melhor OCR se superar Document AI
            if (
                best_ocr_servicos
                and (best_ocr_qty_ratio > doc_qty_ratio or best_ocr_complete_ratio > doc_complete_ratio)
            ):
                servicos_table = best_ocr_servicos
                table_confidence = best_ocr_conf
                table_debug = best_ocr_debug
                table_debug["cascade_stage"] = 3
                table_debug["cascade_reason"] = f"{best_ocr_label}_better"

            # ETAPA 2.7: Document AI fallback (após OCR, apenas se necessário)
            if document_ai_ready and document_ai_fallback_only:
                ocr_count = len(best_ocr_servicos) if best_ocr_servicos else 0
                grid_count = len(grid_servicos) if grid_servicos else 0
                current_count = len(servicos_table) if servicos_table else 0
                fallback_count = grid_count if should_try_grid else ocr_count
                _raw_stats = grid_debug.get("stats") if isinstance(grid_debug, dict) else None
                grid_stats: Dict[str, Any] = _raw_stats if isinstance(_raw_stats, dict) else {}
                grid_dup_ratio = float(grid_stats.get("duplicate_ratio") or 0.0)
                grid_has_items = int(grid_stats.get("with_item") or 0) > 0
                grid_low_quality = bool(grid_servicos) and (not grid_has_items) and grid_dup_ratio >= 0.25
                if (fallback_count < min_items_for_confidence and current_count < min_items_for_confidence) or grid_low_quality:
                    if grid_low_quality:
                        logger.info("Cascata Etapa 2.7: Grid OCR com baixa qualidade, tentando Document AI...")
                    else:
                        logger.info("Cascata Etapa 2.7: Tentando Document AI como fallback...")
                    try:
                        doc_servicos, doc_conf, doc_debug = self.extract_servicos_from_document_ai(
                            file_path,
                            allow_itemless=allow_itemless_doc
                        )
                        doc_debug["source"] = "document_ai"
                        doc_debug["fallback_only"] = True
                        if grid_low_quality:
                            doc_debug["fallback_reason"] = "grid_ocr_low_quality"
                        if (
                            doc_debug.get("error")
                            and "PAGE_LIMIT_EXCEEDED" in str(doc_debug.get("error"))
                            and not text_useful
                        ):
                            logger.info("Cascata: Document AI page limit, tentando imageless...")
                            doc_servicos, doc_conf, doc_debug = self.extract_servicos_from_document_ai(
                                file_path,
                                use_native_pdf_parsing=True,
                                allow_itemless=allow_itemless_doc
                            )
                            doc_debug["source"] = "document_ai"
                            doc_debug["retry_reason"] = "page_limit_exceeded"

                        if doc_servicos and pdf_servicos:
                            doc_servicos, merge_debug = self._merge_table_sources(doc_servicos, pdf_servicos)
                            doc_debug["merge"] = merge_debug
                        doc_qty_ratio = self.calc_qty_ratio(doc_servicos)
                        doc_complete_ratio = self.calc_complete_ratio(doc_servicos)
                        table_attempts["document_ai"] = {
                            "count": len(doc_servicos),
                            "confidence": doc_conf,
                            "qty_ratio": doc_qty_ratio,
                            "complete_ratio": doc_complete_ratio,
                            "debug": self._summarize_table_debug(doc_debug)
                        }

                        if doc_servicos and doc_qty_ratio >= stage2_threshold:
                            servicos_table = doc_servicos
                            table_confidence = doc_conf
                            table_debug = doc_debug
                            table_debug["cascade_stage"] = 2
                            table_debug["cascade_reason"] = "document_ai_fallback"
                        elif doc_servicos and (
                            doc_qty_ratio > best_ocr_qty_ratio or doc_complete_ratio > best_ocr_complete_ratio
                        ):
                            servicos_table = doc_servicos
                            table_confidence = doc_conf
                            table_debug = doc_debug
                            table_debug["cascade_stage"] = 2
                            table_debug["cascade_reason"] = "document_ai_fallback_better"
                    except Exception as e:
                        logger.warning(f"Cascata: Document AI fallback falhou - {e}")
                        table_attempts["document_ai"] = {"error": str(e)}

            # FALLBACK
            if not servicos_table and pdf_servicos:
                servicos_table = pdf_servicos
                table_confidence = pdf_conf
                table_debug = pdf_debug
                table_debug["cascade_stage"] = 1
                table_debug["cascade_reason"] = "pdfplumber_fallback"
                logger.info(f"Cascata: Usando pdfplumber como fallback ({len(pdf_servicos)} serviços)")

        elif file_ext in [".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif"]:
            logger.info("Imagem detectada: Usando Document AI diretamente")

            if document_ai_ready:
                try:
                    doc_servicos, doc_conf, doc_debug = self.extract_servicos_from_document_ai(
                        file_path,
                        allow_itemless=True
                    )
                    doc_debug["source"] = "document_ai"
                    doc_qty_ratio = self.calc_qty_ratio(doc_servicos)
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

        table_debug["cascade_summary"] = {
            "final_source": table_debug.get("source", "none"),
            "final_stage": table_debug.get("cascade_stage", 0),
            "attempts": list(table_attempts.keys())
        }

        return servicos_table, table_confidence, table_debug, table_attempts


# Instância singleton para uso global
table_extraction_service = TableExtractionService()
