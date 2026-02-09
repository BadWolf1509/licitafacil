"""
Parser de padrões de linhas de texto.

Contém a lógica para identificar e extrair itens de serviço
de diferentes padrões de formatação em linhas de texto.
"""

import re
from typing import Any, Dict, Optional

from services.extraction import (
    item_tuple_to_str,
    normalize_unit,
    parse_item_tuple,
    parse_quantity,
)


class TextLineParser:
    """
    Parser de padrões de linhas de texto.

    Detecta e extrai itens de serviço de diferentes formatos:
    - Código no início, unidade/quantidade no final
    - Código seguido imediatamente por unidade/quantidade
    - Código no meio da linha
    """

    def try_pattern_code_unit_end(
        self,
        line: str,
        prev_line: str,
        segment_index: int,
        last_tuple: Optional[tuple]
    ) -> Optional[Dict[str, Any]]:
        """
        Padrão 1: Linha começa com código, termina com unidade/quantidade.

        Exemplo: "9.11 DESCRICAO DO SERVICO UN 10,00"

        Args:
            line: Linha atual
            prev_line: Linha anterior
            segment_index: Índice do segmento atual
            last_tuple: Último item tuple processado

        Returns:
            Dict com item extraído ou None
        """
        match = re.match(r'^(\d+\.\d+(?:\.\d+){0,3})\s+(.+)$', line)
        if not match:
            return None

        item_raw = match.group(1)
        rest = match.group(2).strip()

        unit_match = re.search(
            r'\b([A-Za-z0-9\u00ba\u00b0/%\u00b2\u00b3\.]+)\s+([\d.,]+)\s*$',
            rest
        )
        if not unit_match:
            return None

        unit_raw = unit_match.group(1)
        qty_raw = unit_match.group(2)

        if parse_quantity(qty_raw) is None:
            return None

        item_tuple = parse_item_tuple(item_raw)
        if not item_tuple:
            return None

        unit_norm = normalize_unit(unit_raw)
        if not unit_norm:
            return None

        desc = rest[:unit_match.start()].strip()
        desc = self._merge_with_prev_line_if_needed(desc, prev_line)

        new_segment_index = segment_index
        if last_tuple and item_tuple < last_tuple:
            new_segment_index += 1

        prefix = f"S{new_segment_index}-" if new_segment_index > 1 else ""
        return {
            "item": {
                'item': f"{prefix}{item_tuple_to_str(item_tuple)}",
                'descricao': desc,
                'unidade': unit_norm,
                'quantidade': qty_raw,
                '_source': 'text_line'
            },
            "segment_index": new_segment_index,
            "last_tuple": item_tuple
        }

    def try_pattern_unit_first(
        self,
        line: str,
        prev_line: str,
        segment_index: int,
        last_tuple: Optional[tuple]
    ) -> Optional[Dict[str, Any]]:
        """
        Padrão 1b: Código seguido imediatamente por unidade e quantidade.

        Exemplo: "9.13 UN 5,00 FORNECIMENTO DE MATERIAL"

        Args:
            line: Linha atual
            prev_line: Linha anterior
            segment_index: Índice do segmento atual
            last_tuple: Último item tuple processado

        Returns:
            Dict com item extraído ou None
        """
        match = re.match(
            r'^(\d+\.\d+(?:\.\d+)?)\s+'
            r'(UN|M|M2|M3|KG|VB|CJ|L|T|HA|KM|MES|GB|PC|PT)\s+'
            r'([\d.,]+)\s+(.+)$',
            line,
            re.IGNORECASE
        )
        if not match:
            return None

        item_raw = match.group(1)
        unit_raw = match.group(2)
        qty_raw = match.group(3)
        desc = match.group(4).strip()

        item_tuple = parse_item_tuple(item_raw)
        if not item_tuple:
            return None

        qty = parse_quantity(qty_raw)
        if qty is None:
            return None

        unit_norm = normalize_unit(unit_raw)
        if not unit_norm:
            return None

        # Mesclar com linha anterior se for descrição válida
        if self._is_valid_prev_desc(prev_line):
            prev_clean = re.sub(r'\s*[,\-]\s*$', '', prev_line).strip()
            desc = f"{prev_clean} - {desc}"

        new_segment_index = segment_index
        if last_tuple and item_tuple < last_tuple:
            new_segment_index += 1

        prefix = f"S{new_segment_index}-" if new_segment_index > 1 else ""
        return {
            "item": {
                'item': f"{prefix}{item_tuple_to_str(item_tuple)}",
                'descricao': desc,
                'unidade': unit_norm,
                'quantidade': qty_raw,
                '_source': 'text_line_unit_first'
            },
            "segment_index": new_segment_index,
            "last_tuple": item_tuple
        }

    def extract_mid_pattern_item(
        self,
        line: str,
        segment_index: int,
        last_tuple: Optional[tuple]
    ) -> Optional[Dict[str, Any]]:
        """
        Extrai item quando código está no meio da linha.

        Exemplo: "DISJUNTOR BIPOLAR 9.11 UN 10,00"

        Args:
            line: Linha atual
            segment_index: Índice do segmento atual
            last_tuple: Último item tuple processado

        Returns:
            Dict com item extraído ou None
        """
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

    def extract_mid_pattern_unit_end(
        self,
        line: str,
        segment_index: int,
        last_tuple: Optional[tuple]
    ) -> Optional[Dict[str, Any]]:
        """
        Extrai item quando código está no meio e unidade no final.

        Exemplo: "DESCRICAO INICIAL 9.11 DESCRICAO FINAL UN 10,00"

        Args:
            line: Linha atual
            segment_index: Índice do segmento atual
            last_tuple: Último item tuple processado

        Returns:
            Dict com item extraído ou None
        """
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


# Instância singleton
text_line_parser = TextLineParser()
