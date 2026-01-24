"""
Processador de extração de itens a partir de texto.

Contém métodos extraídos do DocumentProcessor para extração
de itens de serviço a partir de texto OCR ou extraído de PDFs.
"""

import re
from collections import Counter
from typing import Any, Dict, List, Optional, Set

from config import AtestadoProcessingConfig as APC
from services.extraction import (
    normalize_description,
    normalize_unit,
    parse_item_tuple,
    item_tuple_to_str,
    parse_quantity,
    UNIT_TOKENS,
)
from services.processing_helpers import (
    normalize_item_code,
    is_section_header_desc,
    is_narrative_desc,
)
from services.text_extraction_service import text_extraction_service

from logging_config import get_logger

logger = get_logger("services.processors.text_processor")


class TextProcessor:
    """
    Processador especializado para extração de itens de texto.

    Extrai códigos de item, descrições, unidades e quantidades
    de texto livre ou semi-estruturado.
    """

    def extract_item_codes_from_text_lines(self, texto: str) -> List[str]:
        """
        Extrai códigos de item únicos das linhas de texto.

        Args:
            texto: Texto para análise

        Returns:
            Lista de códigos de item encontrados (ex: ["1.2", "1.3"])
        """
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

    def extract_items_from_text_lines(self, texto: str) -> List[Dict[str, Any]]:
        """
        Extrai itens completos de linhas de texto.

        Detecta padrões como:
        - "9.11 DESCRICAO UN 10,00"
        - "9.13 UN 5,00 FORNECIMENTO..."
        - "DISJUNTOR... 9.11 UN 10,00 FORNECIMENTO..."

        Args:
            texto: Texto para análise

        Returns:
            Lista de dicionários com item, descricao, unidade, quantidade
        """
        if not texto:
            return []

        items = []
        lines = texto.split('\n')
        segment_index = 1
        last_tuple = None
        prev_line = ""

        for idx, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue

            # Padrão 1: Linha começa com código do item (ex: "9.11 DESCRICAO UN 10,00")
            match = re.match(r'^(\d+\.\d+(?:\.\d+){0,3})\s+(.+)$', line)
            if match:
                item_raw = match.group(1)
                rest = match.group(2).strip()
                unit_match = re.search(
                    r'\b([A-Za-z0-9\u00ba\u00b0/%\u00b2\u00b3\.]+)\s+([\d.,]+)\s*$',
                    rest
                )
                if unit_match:
                    unit_raw = unit_match.group(1)
                    qty_raw = unit_match.group(2)
                    if parse_quantity(qty_raw) is not None:
                        item_tuple = parse_item_tuple(item_raw)
                        if item_tuple:
                            if last_tuple and item_tuple < last_tuple:
                                segment_index += 1
                            last_tuple = item_tuple
                            desc = rest[:unit_match.start()].strip()
                            unit_norm = normalize_unit(unit_raw)
                            if unit_norm:
                                desc = self._merge_with_prev_line_if_needed(
                                    desc, prev_line
                                )
                                prefix = f"S{segment_index}-" if segment_index > 1 else ""
                                items.append({
                                    'item': f"{prefix}{item_tuple_to_str(item_tuple)}",
                                    'descricao': desc,
                                    'unidade': unit_norm,
                                    'quantidade': qty_raw,
                                    '_source': 'text_line'
                                })
                                prev_line = line
                                continue

                # Padrão 1b: "ITEM UN QTY DESC" (ex: "9.13 UN 5,00 FORNECIMENTO...")
                unit_first_match = re.match(
                    r'^(\d+\.\d+(?:\.\d+)?)\s+'
                    r'(UN|M|M2|M3|KG|VB|CJ|L|T|HA|KM|MES|GB|PC|PT)\s+'
                    r'([\d.,]+)\s+(.+)$',
                    line,
                    re.IGNORECASE
                )
                if unit_first_match:
                    item_raw = unit_first_match.group(1)
                    unit_raw = unit_first_match.group(2)
                    qty_raw = unit_first_match.group(3)
                    desc = unit_first_match.group(4).strip()

                    item_tuple = parse_item_tuple(item_raw)
                    if item_tuple:
                        qty = parse_quantity(qty_raw)
                        if qty is not None:
                            unit_norm = normalize_unit(unit_raw)
                            if unit_norm:
                                if last_tuple and item_tuple < last_tuple:
                                    segment_index += 1
                                last_tuple = item_tuple

                                prev_is_valid_desc = self._is_valid_prev_desc(prev_line)
                                if prev_is_valid_desc:
                                    prev_clean = re.sub(
                                        r'\s*[,\-]\s*$', '', prev_line
                                    ).strip()
                                    desc = f"{prev_clean} - {desc}"

                                prefix = f"S{segment_index}-" if segment_index > 1 else ""
                                items.append({
                                    'item': f"{prefix}{item_tuple_to_str(item_tuple)}",
                                    'descricao': desc,
                                    'unidade': unit_norm,
                                    'quantidade': qty_raw,
                                    '_source': 'text_line_unit_first'
                                })
                                prev_line = line
                                continue

            # Padrão 2: Código do item no MEIO da linha
            mid_item = self._extract_mid_pattern_item(
                line, segment_index, last_tuple
            )
            if mid_item:
                items.append(mid_item["item"])
                segment_index = mid_item["segment_index"]
                last_tuple = mid_item["last_tuple"]
                prev_line = line
                continue

            # Padrão 3: Código no meio, unidade no final
            mid_unit_end_item = self._extract_mid_pattern_unit_end(
                line, segment_index, last_tuple
            )
            if mid_unit_end_item:
                items.append(mid_unit_end_item["item"])
                segment_index = mid_unit_end_item["segment_index"]
                last_tuple = mid_unit_end_item["last_tuple"]
                prev_line = line
                continue

            # Atualizar prev_line para próxima iteração
            prev_line = line

        return items

    def extract_items_from_text_section(
        self,
        texto: str,
        existing_keys: Optional[Set] = None
    ) -> List[Dict[str, Any]]:
        """
        Extrai itens da seção "SERVICOS EXECUTADOS" do texto.

        Args:
            texto: Texto completo do documento
            existing_keys: Chaves de itens já existentes para evitar duplicatas

        Returns:
            Lista de itens extraídos
        """
        if not texto:
            return []

        lines = [line.strip() for line in texto.splitlines()]
        anchor_idx = text_extraction_service.find_servicos_anchor_line(lines)
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
            code = normalize_item_code(raw_code)
            if not code:
                continue
            code_lines.append((idx, code, match.end(), line))

        if not code_lines:
            return []

        # Detectar restart de numeração
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
                f"codes={len(code_counts)}, dup_codes={len(dup_codes)}, "
                f"dup_ratio={dup_ratio:.2f}"
            )

        item_codes = {code for _, code, _, _ in code_lines}
        qty_map = self.extract_quantities_from_text(texto, item_codes)
        if not qty_map:
            return []

        return self._build_items_from_code_lines(
            lines, code_lines, qty_map, dup_codes,
            allow_restart, existing_keys
        )

    def extract_items_without_codes_from_text(
        self,
        texto: str
    ) -> List[Dict[str, Any]]:
        """
        Extrai itens que não possuem código de item.

        Útil para documentos onde os itens são listados apenas
        com descrição, unidade e quantidade.

        Args:
            texto: Texto do documento

        Returns:
            Lista de itens sem código (item=None)
        """
        if not texto:
            return []

        lines = [line.strip() for line in texto.splitlines()]
        anchor_idx = text_extraction_service.find_servicos_anchor_line(lines)
        if anchor_idx is None:
            return []

        items = []
        pending_desc = ""
        last_item = None
        stop_prefixes = (
            "CNPJ", "CPF CNPJ", "PREFEITURA", "CONSELHO REGIONAL",
            "CREA", "CEP", "E MAIL", "EMAIL", "TEL", "TELEFONE",
            "IMPRESSO", "DOCUSIGN",
        )
        footer_tokens = (
            "CNPJ", "CPF", "PREFEITURA", "CONSELHO REGIONAL", "CREA",
            "DOCUSIGN", "CEP", "JOAO PESSOA", "ARARUNA", "RUA",
            "EMAIL", "TEL", "IMPRESSO", "AGRONOMIA",
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
            if (
                "DESCRICAO" in normalized
                and "QUANT" in normalized
                and "UND" in normalized
            ):
                pending_desc = ""
                continue

            unit_match = self._find_unit_qty_in_line(line)
            if unit_match:
                unit, qty, start, end = unit_match
                before = line[:start].strip()
                after = line[end:].strip()

                if before:
                    before = self._strip_footer_prefix_from_desc(before)

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
                if re.search(rf'\b{re.escape(token)}\b', normalized):
                    has_footer = True
                    break
            if has_footer:
                pending_desc = ""
                continue

            cont_prefixes = (
                "A ", "DE ", "DO ", "DA ", "DOS ", "DAS ", "COM ", "SEM ",
                "INCLUINDO", "INCLUSIVE", "BORRACHA", "AF_"
            )
            if last_item and line.upper().startswith(cont_prefixes):
                last_desc = (last_item.get("descricao") or "").strip()
                last_item["descricao"] = (
                    (last_desc + " " + line).strip() if last_desc else line
                )
                continue

            if not re.search(r'\d', line):
                if len(normalized) <= 40 and line == line.upper():
                    pending_desc = ""
                    continue

            pending_desc = (
                (pending_desc + " " + line).strip() if pending_desc else line
            )

        return items

    def extract_quantities_from_text(
        self,
        texto: str,
        item_codes: Set[str]
    ) -> Dict[str, List]:
        """
        Extrai quantidades e unidades do texto para códigos de item conhecidos.

        Args:
            texto: Texto do documento
            item_codes: Conjunto de códigos de item a procurar

        Returns:
            Mapa de código -> lista de (unidade, quantidade)
        """
        if not texto or not item_codes:
            return {}

        pattern = re.compile(r'(\d{1,3}(?:\s*\.\s*\d{1,3}){1,4})(?!\s*/\s*\d)')
        qty_map: Dict[str, List] = {}
        current_code = None
        pending_unit = None
        next_line_qty_hits = 0

        def add_qty(code: str, unit_qty: tuple) -> None:
            qty_map.setdefault(code, []).append(unit_qty)

        def find_unit_in_text(segment: str) -> Optional[str]:
            for token in reversed(
                re.findall(r'[\w\u00ba\u00b0/%\u00b2\u00b3\.]+', segment)
            ):
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
            matches: List[tuple] = []

            for match in raw_matches:
                raw_code = re.sub(r'\s+', '', match.group(1))
                code = normalize_item_code(raw_code)
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
            logger.info(
                f"[QTY] Quantidades detectadas em linha seguinte: {next_line_qty_hits}"
            )

        return qty_map

    def backfill_quantities_from_text(
        self,
        servicos: List[Dict[str, Any]],
        texto: str
    ) -> int:
        """
        Preenche quantidades faltantes usando o texto.

        Args:
            servicos: Lista de serviços (modificada in-place)
            texto: Texto do documento

        Returns:
            Número de quantidades preenchidas
        """
        if not servicos or not texto:
            return 0

        item_codes: Set[str] = set()
        for s in servicos:
            code = normalize_item_code(s.get("item"))
            if code:
                item_codes.add(code)
        if not item_codes:
            return 0

        qty_map = self.extract_quantities_from_text(texto, item_codes)
        if not qty_map:
            return 0

        normalized_map: Dict[str, List] = {}
        for code, entries in qty_map.items():
            if isinstance(entries, list):
                normalized_map[code] = list(entries)
            else:
                normalized_map[code] = [entries]

        # Remover quantidades já presentes para evitar reuse em códigos duplicados
        for s in servicos:
            code = normalize_item_code(s.get("item"))
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
            if idx is not None:
                entries.pop(idx)

        filled = 0
        for s in servicos:
            code = normalize_item_code(s.get("item"))
            if not code or code not in normalized_map:
                continue
            qty = parse_quantity(s.get("quantidade"))
            if qty not in (None, 0):
                continue
            entries = normalized_map.get(code) or []
            if not entries:
                continue
            unit_qty = entries.pop(0)
            if isinstance(unit_qty, (tuple, list)) and len(unit_qty) >= 2:
                s["unidade"] = unit_qty[0]
                s["quantidade"] = unit_qty[1]
                filled += 1

        if filled:
            logger.info(f"[QTY] Quantidades preenchidas via texto: {filled}")

        return filled

    # =========================================================================
    # Métodos auxiliares privados
    # =========================================================================

    def _merge_with_prev_line_if_needed(
        self,
        desc: str,
        prev_line: str
    ) -> str:
        """Mescla descrição com linha anterior se parecer truncada."""
        if not desc or not prev_line:
            return desc

        desc_looks_truncated = (
            desc[0].islower() or
            desc[0].isdigit() or
            len(desc) < 30
        )
        prev_ends_continuation = re.search(r'[,\-]\s*$', prev_line)
        prev_is_valid_desc = self._is_valid_prev_desc(prev_line)

        should_merge = prev_is_valid_desc and (
            desc_looks_truncated or prev_ends_continuation
        )

        if should_merge:
            prev_clean = re.sub(r'\s*[,\-]\s*$', '', prev_line).strip()
            return f"{prev_clean} {desc}"

        return desc

    def _is_valid_prev_desc(self, prev_line: str) -> bool:
        """Verifica se linha anterior pode ser início de descrição."""
        return (
            bool(prev_line)
            and not re.match(r'^\d+\.\d+', prev_line)
            and len(prev_line) > 10
            and any(c.isalpha() for c in prev_line)
        )

    def _extract_mid_pattern_item(
        self,
        line: str,
        segment_index: int,
        last_tuple: Optional[tuple]
    ) -> Optional[Dict[str, Any]]:
        """Extrai item quando código está no meio da linha."""
        mid_pattern = re.search(
            r'(.{10,}?)\s+(\d{1,2}\.\d{1,2}(?:\.\d{1,2})?)\s+'
            r'(UN|M|M2|M3|KG|VB|CJ|L|T|HA|KM|MES|GB|PC|PT)\s+'
            r'([\d.,]+)\s*(.*)$',
            line,
            re.IGNORECASE
        )
        if not mid_pattern:
            return None

        desc_start = mid_pattern.group(1).strip()
        item_raw = mid_pattern.group(2)
        unit_raw = mid_pattern.group(3)
        qty_raw = mid_pattern.group(4)
        desc_end = mid_pattern.group(5).strip()

        if re.search(r'\blinha\s*$', desc_start, re.IGNORECASE):
            return None

        item_tuple = parse_item_tuple(item_raw)
        if not item_tuple:
            return None

        qty = parse_quantity(qty_raw)
        if qty is None:
            return None

        unit_norm = normalize_unit(unit_raw)
        if not unit_norm:
            return None

        desc_start_clean = re.sub(r'\s*-\s*$', '', desc_start).strip()
        full_desc = (
            f"{desc_start_clean} - {desc_end}" if desc_end else desc_start_clean
        )

        new_segment_index = segment_index
        if last_tuple and item_tuple < last_tuple:
            new_segment_index += 1

        prefix = f"S{new_segment_index}-" if new_segment_index > 1 else ""
        return {
            "item": {
                'item': f"{prefix}{item_tuple_to_str(item_tuple)}",
                'descricao': full_desc,
                'unidade': unit_norm,
                'quantidade': qty_raw,
                '_source': 'text_line_mid'
            },
            "segment_index": new_segment_index,
            "last_tuple": item_tuple
        }

    def _extract_mid_pattern_unit_end(
        self,
        line: str,
        segment_index: int,
        last_tuple: Optional[tuple]
    ) -> Optional[Dict[str, Any]]:
        """Extrai item quando código está no meio e unidade no final."""
        mid_pattern = re.search(
            r'(.{10,}?)\s+(\d{1,2}\.\d{1,2}(?:\.\d{1,2})?)\s+'
            r'(.+?)\s+'
            r'(UN|M|M2|M3|KG|VB|CJ|L|T|HA|KM|MES|GB|PC|PT)\s+'
            r'([\d.,]+)\s*$',
            line,
            re.IGNORECASE
        )
        if not mid_pattern:
            return None

        desc_start = mid_pattern.group(1).strip()
        item_raw = mid_pattern.group(2)
        desc_end = mid_pattern.group(3).strip()
        unit_raw = mid_pattern.group(4)
        qty_raw = mid_pattern.group(5)

        if re.search(r'\blinha\s*$', desc_start, re.IGNORECASE):
            return None

        item_tuple = parse_item_tuple(item_raw)
        if not item_tuple:
            return None

        qty = parse_quantity(qty_raw)
        if qty is None:
            return None

        unit_norm = normalize_unit(unit_raw)
        if not unit_norm:
            return None

        desc_start_clean = re.sub(r'\s*[,\-]\s*$', '', desc_start).strip()
        full_desc = (
            f"{desc_start_clean} - {desc_end}" if desc_end else desc_start_clean
        )

        new_segment_index = segment_index
        if last_tuple and item_tuple < last_tuple:
            new_segment_index += 1

        prefix = f"S{new_segment_index}-" if new_segment_index > 1 else ""
        return {
            "item": {
                'item': f"{prefix}{item_tuple_to_str(item_tuple)}",
                'descricao': full_desc,
                'unidade': unit_norm,
                'quantidade': qty_raw,
                '_source': 'text_line_mid'
            },
            "segment_index": new_segment_index,
            "last_tuple": item_tuple
        }

    def _build_items_from_code_lines(
        self,
        lines: List[str],
        code_lines: List[tuple],
        qty_map: Dict[str, List],
        dup_codes: set,
        allow_restart: bool,
        existing_keys: Optional[Set]
    ) -> List[Dict[str, Any]]:
        """Constrói lista de itens a partir de linhas com código."""
        added = []
        qty_remaining = {code: list(entries) for code, entries in qty_map.items()}
        stop_prefixes = (
            "CNPJ", "CPF CNPJ", "PREFEITURA", "CONSELHO REGIONAL",
            "CREA", "CEP", "E MAIL", "EMAIL", "TEL", "TELEFONE", "IMPRESSO",
        )
        segment_index = 1
        max_tuple = None

        for pos, (line_idx, code, code_end, line) in enumerate(code_lines):
            code_tuple = parse_item_tuple(code)
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

            if (
                not unit_qty
                or not isinstance(unit_qty, (tuple, list))
                or len(unit_qty) < 2
            ):
                continue

            unit, qty = unit_qty[0], unit_qty[1]
            if qty in (None, 0) or not unit:
                continue

            if existing_keys:
                key = (item_code, unit, qty)
                if key in existing_keys:
                    continue

            # Construir descrição
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

            # Coletar continuação nas linhas seguintes
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

    def _parse_unit_qty_from_line(self, line: str) -> Optional[tuple]:
        """Extrai par (unidade, quantidade) de uma linha."""
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

    def _find_unit_qty_in_line(self, line: str) -> Optional[tuple]:
        """Encontra unidade e quantidade em qualquer posição da linha."""
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

    def _strip_trailing_unit_qty(
        self,
        text: str,
        unit: Optional[str] = None,
        qty: Optional[float] = None
    ) -> str:
        """Remove unidade/quantidade do final do texto."""
        if not text:
            return text

        match = re.search(
            r'\b([\w\u00ba\u00b0/%\u00b2\u00b3\.]+)\s+([\d.,]+)\s*$',
            text
        )
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

    def _strip_footer_prefix_from_desc(self, desc: str) -> str:
        """Remove prefixo de rodapé que vazou para a descrição."""
        if not desc:
            return desc

        upper = desc.upper()
        anchors = [
            "FORNEC", "LOCAÇÃO", "LOCACAO", "EXECUÇÃO", "EXECUCAO",
            "ESCAVAÇÃO", "ESCAVACAO", "REATERRO", "LASTRO",
            "FUNDAÇÃO", "FUNDACAO", "CONCRETO", "ADMINISTRAÇÃO",
            "ADMINISTRACAO", "MOBILIZAÇÃO", "MOBILIZACAO",
            "PLACA", "PERFURAÇÃO", "PERFURACAO"
        ]

        anchor_pos = None
        for anchor in anchors:
            pos = upper.find(anchor)
            if pos == -1:
                continue
            if anchor_pos is None or pos < anchor_pos:
                anchor_pos = pos

        if anchor_pos is not None and anchor_pos > 0:
            return desc[anchor_pos:].strip()

        return desc

    def strip_unit_qty_prefix(self, desc: str) -> str:
        """
        Remove prefixo de unidade/quantidade da descrição.

        Exemplo: "UN 1,00 FORNECIMENTO..." -> "FORNECIMENTO..."
        """
        if not desc:
            return desc

        pattern = r'^(UN|M|M2|M3|M²|M³|KG|L|CJ|VB|PC|PÇ|JG|CONJ)\s+[\d.,]+\s+'
        match = re.match(pattern, desc, re.IGNORECASE)
        if match:
            cleaned = desc[match.end():].strip()
            if len(cleaned) >= 5:
                return cleaned

        return desc


# Instância singleton para uso conveniente
text_processor = TextProcessor()
