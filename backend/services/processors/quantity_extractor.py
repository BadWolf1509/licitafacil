"""
Extrator de quantidades de texto.

Extrai quantidades e unidades de texto associadas a códigos de item.
"""

import re
from typing import Any, Dict, List, Optional, Set

from logging_config import get_logger
from services.extraction import (
    UNIT_TOKENS,
    normalize_unit,
    parse_quantity,
)
from services.processing_helpers import normalize_item_code

logger = get_logger("services.processors.quantity_extractor")

# Padrão para código de item com espaços opcionais
PATTERN_ITEM_CODE_SPACED = re.compile(r'(\d{1,3}(?:\s*\.\s*\d{1,3}){1,4})(?!\s*/\s*\d)')

# Padrão para unidade e quantidade
PATTERN_UNIT_QTY = re.compile(r'([\w\u00ba\u00b0/%\u00b2\u00b3\.]+)\s+([\d.,]+)')


class QuantityExtractor:
    """
    Extrai quantidades e unidades de texto para códigos de item.

    Analisa o texto procurando padrões de código + unidade + quantidade
    e constrói um mapa de código -> [(unidade, quantidade), ...].
    """

    def extract_quantities(
        self,
        texto: str,
        item_codes: Set[str]
    ) -> Dict[str, List]:
        """
        Extrai quantidades e unidades do texto para códigos conhecidos.

        Args:
            texto: Texto do documento
            item_codes: Conjunto de códigos de item a procurar

        Returns:
            Mapa de código -> lista de (unidade, quantidade)
        """
        if not texto or not item_codes:
            return {}

        qty_map: Dict[str, List] = {}
        current_code = None
        pending_unit = None
        next_line_qty_hits = 0

        for raw_line in texto.splitlines():
            line = raw_line.strip()
            if not line:
                continue

            any_code_match = bool(PATTERN_ITEM_CODE_SPACED.search(line))
            raw_matches = list(PATTERN_ITEM_CODE_SPACED.finditer(line))
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
                            self._add_qty_to_map(qty_map, current_code, parsed)
                            current_code = None
                            pending_unit = None
                        elif pending_unit:
                            qty = self._extract_last_quantity(prefix)
                            if qty is not None:
                                self._add_qty_to_map(qty_map, current_code, (pending_unit, qty))
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
                    if parsed and code:
                        self._add_qty_to_map(qty_map, code, parsed)
                        continue

                    unit_norm = self._extract_unit_from_segment(segment)
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
                    self._add_qty_to_map(qty_map, current_code, parsed)
                    current_code = None
                    pending_unit = None
                    continue

                if pending_unit:
                    qty = self._extract_last_quantity(line)
                    if qty is not None:
                        self._add_qty_to_map(qty_map, current_code, (pending_unit, qty))
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

    def backfill_quantities(
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

        qty_map = self.extract_quantities(texto, item_codes)
        if not qty_map:
            return 0

        normalized_map: Dict[str, List] = {}
        for code, entries in qty_map.items():
            if isinstance(entries, list):
                normalized_map[code] = list(entries)
            else:
                normalized_map[code] = [entries]

        # Remover quantidades já presentes
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

    def _add_qty_to_map(
        self,
        qty_map: Dict[str, List],
        code: str,
        unit_qty: tuple
    ) -> None:
        """Adiciona quantidade ao mapa."""
        qty_map.setdefault(code, []).append(unit_qty)

    def _extract_unit_from_segment(self, segment: str) -> Optional[str]:
        """Extrai unidade do segmento de texto."""
        tokens = segment.split()
        for token in tokens:
            norm = normalize_unit(token)
            if norm and norm in UNIT_TOKENS:
                return norm
        return None

    def _extract_last_quantity(self, line: str) -> Optional[float]:
        """Extrai última quantidade da linha."""
        tokens = line.split()
        for token in reversed(tokens):
            qty = parse_quantity(token)
            if qty is not None and qty > 0:
                return qty
        return None

    def _parse_unit_qty_from_line(self, line: str) -> Optional[tuple]:
        """Extrai par (unidade, quantidade) da linha."""
        tokens = line.split()
        if len(tokens) < 2:
            return None

        for i in range(len(tokens) - 1):
            unit_norm = normalize_unit(tokens[i])
            if unit_norm and unit_norm in UNIT_TOKENS:
                qty = parse_quantity(tokens[i + 1])
                if qty is not None and qty > 0:
                    return (unit_norm, qty)

        # Tentar padrão regex
        match = PATTERN_UNIT_QTY.search(line)
        if match:
            unit_norm = normalize_unit(match.group(1))
            qty = parse_quantity(match.group(2))
            if unit_norm and unit_norm in UNIT_TOKENS and qty is not None and qty > 0:
                return (unit_norm, qty)

        return None


# Instância singleton
quantity_extractor = QuantityExtractor()
