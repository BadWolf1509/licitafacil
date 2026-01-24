"""
Servico de extracao de texto de documentos.
Extrai itens, quantidades e descricoes de texto bruto.
"""
from typing import Dict, Any, List, Optional, Set
import re

from .extraction import (
    normalize_description,
    normalize_unit,
    parse_item_tuple,
    item_tuple_to_str,
    parse_quantity,
    UNIT_TOKENS,
    normalize_item_code as _normalize_item_code,
    item_code_in_text as _item_code_in_text,
)
from logging_config import get_logger

logger = get_logger('services.text_extraction')


class TextExtractionService:
    """Servico de extracao de itens de texto."""

    def normalize_item_code(self, item: Any) -> Optional[str]:
        """Normaliza codigo de item removendo espacos e prefixos."""
        return _normalize_item_code(item)

    def item_code_in_text(self, item_code: str, texto: str) -> bool:
        """Verifica se codigo de item aparece no texto."""
        return _item_code_in_text(item_code, texto)

    def count_item_codes_in_text(self, texto: str) -> int:
        """Conta quantos codigos de item aparecem no texto."""
        if not texto:
            return 0
        pattern = re.compile(r'\b\d{1,3}(?:\s*\.\s*\d{1,3}){1,4}\b')
        matches = pattern.findall(texto)
        unique = set()
        for m in matches:
            code = re.sub(r'\s+', '', m)
            if re.match(r'^\d+(\.\d+)+$', code):
                unique.add(code)
        return len(unique)

    def extract_item_codes_from_text_lines(self, texto: str) -> list:
        """Extrai codigos de item do texto linha a linha."""
        if not texto:
            return []
        codes = []
        pattern = re.compile(r'\b(\d{1,3}(?:\s*\.\s*\d{1,3}){1,4})\b')
        for line in texto.splitlines():
            matches = pattern.findall(line)
            for m in matches:
                code = re.sub(r'\s+', '', m)
                if re.match(r'^\d+(\.\d+)+$', code):
                    codes.append(code)
        return codes

    def split_text_by_pages(self, texto: str) -> list:
        """Divide texto em segmentos por pagina."""
        if not texto:
            return []
        matches = list(re.finditer(r'P[aá]gina\s+(\d+)\s*/\s*(\d+)', texto, re.IGNORECASE))
        if not matches:
            return []
        segments = []
        for idx, match in enumerate(matches):
            start = match.start()
            end = matches[idx + 1].start() if idx + 1 < len(matches) else len(texto)
            try:
                page_num = int(match.group(1))
            except (TypeError, ValueError):
                continue
            segments.append((page_num, texto[start:end]))
        merged: Dict[int, str] = {}
        for page_num, content in segments:
            if page_num in merged:
                merged[page_num] += "\n" + content
            else:
                merged[page_num] = content
        return [(p, c) for p, c in sorted(merged.items())]

    def find_servicos_anchor_line(self, lines: list) -> Optional[int]:
        """Encontra linha ancora 'SERVICOS EXECUTADOS'."""
        if not lines:
            return None
        anchors = ("SERVICOS EXECUTADOS", "SERVICOS EXECUTADO")
        for idx, line in enumerate(lines):
            normalized = normalize_description(line)
            if not normalized:
                continue
            for anchor in anchors:
                if anchor in normalized:
                    return idx
        return None

    def find_unit_qty_in_line(self, line: str) -> Optional[tuple]:
        """Encontra unidade e quantidade em uma linha."""
        if not line:
            return None
        stop_units = {"N", "A", "NO", "AO", "NA", "EM", "DE", "DO", "DA", "ITEM", "LINHA", "01", "02", "03"}
        allowed_units = UNIT_TOKENS
        pattern = re.compile(
            r'(?<![A-Za-z0-9])'
            r'([A-Za-z][A-Za-z0-9\u00ba\u00b0/%\u00b2\u00b3\.]*)'
            r'\s+'
            r'([\d.,]+)'
            r'(?:\s|$)',
            re.IGNORECASE
        )
        last_valid = None
        for match in pattern.finditer(line):
            unit_raw = match.group(1)
            qty_raw = match.group(2)
            qty = parse_quantity(qty_raw)
            if qty is None or qty == 0:
                continue
            unit_norm = normalize_unit(unit_raw)
            if not unit_norm:
                continue
            if unit_norm in stop_units:
                continue
            if unit_norm not in allowed_units:
                continue
            last_valid = (unit_norm, qty, match.start(), match.end())
        return last_valid

    def parse_unit_qty_from_line(self, line: str) -> Optional[tuple]:
        """Extrai unidade e quantidade de uma linha."""
        if not line:
            return None
        # Padrao: UNIDADE QTY no final
        match = re.search(
            r'\b([A-Za-z][A-Za-z0-9\u00ba\u00b0/%\u00b2\u00b3\.]*)\s+([\d.,]+)\s*$',
            line
        )
        if match:
            unit_raw = match.group(1)
            qty_raw = match.group(2)
            qty = parse_quantity(qty_raw)
            if qty is not None and qty > 0:
                unit_norm = normalize_unit(unit_raw)
                if unit_norm and unit_norm in UNIT_TOKENS:
                    return (unit_norm, qty)
        return None

    def strip_trailing_unit_qty(
        self,
        desc: str,
        unit: str,
        qty: float,
        max_tries: int = 3
    ) -> str:
        """Remove unidade/quantidade do final da descricao."""
        if not desc:
            return desc
        for _ in range(max_tries):
            match = re.search(
                r'\s+([A-Za-z][A-Za-z0-9\u00ba\u00b0/%\u00b2\u00b3\.]*)\s+([\d.,]+)\s*$',
                desc
            )
            if not match:
                break
            trail_unit = normalize_unit(match.group(1))
            trail_qty = parse_quantity(match.group(2))
            if trail_unit and trail_qty is not None:
                desc = desc[:match.start()].strip()
            else:
                break
        return desc

    def strip_unit_qty_prefix(self, desc: str) -> str:
        """Remove unidade/quantidade do inicio da descricao."""
        if not desc:
            return desc
        match = re.match(
            r'^([A-Za-z][A-Za-z0-9\u00ba\u00b0/%\u00b2\u00b3\.]*)\s+([\d.,]+)\s+(.+)$',
            desc
        )
        if match:
            unit_norm = normalize_unit(match.group(1))
            qty = parse_quantity(match.group(2))
            if unit_norm and qty is not None:
                return match.group(3).strip()
        return desc

    def strip_footer_prefix_from_desc(self, desc: str) -> str:
        """Remove prefixos de rodape da descricao."""
        if not desc:
            return desc
        anchors = [
            "FORNECIMENTO", "EXECUCAO", "LOCACAO", "ESCAVACAO",
            "REATERRO", "LASTRO", "FUNDACAO", "CONCRETO",
            "ADMINISTRACAO", "MOBILIZACAO", "PLACA", "PERFURACAO"
        ]
        normalized = normalize_description(desc)
        if not normalized:
            return desc
        anchor_pos = None
        for anchor in anchors:
            pos = normalized.find(anchor)
            if pos != -1:
                if anchor_pos is None or pos < anchor_pos:
                    anchor_pos = pos
        if anchor_pos is None or anchor_pos == 0:
            return desc
        prefix_norm = normalized[:anchor_pos].strip()
        footer_tokens = (
            "CNPJ", "CPF", "PREFEITURA", "CONSELHO REGIONAL", "CREA",
            "DOCUSIGN", "CEP", "RUA", "EMAIL", "TEL", "IMPRESSO"
        )
        for token in footer_tokens:
            if re.search(rf'\b{re.escape(token)}\b', prefix_norm):
                return desc[anchor_pos:].strip()
        return desc

    def extract_items_from_text_lines(self, texto: str) -> list:
        """
        Extrai itens de servico do texto linha a linha.
        Reconhece varios padroes de formatacao.
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

            # Padrao 1: Linha comeca com codigo do item
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
                                # Verificar se descricao parece truncada
                                desc_looks_truncated = (
                                    desc and (
                                        desc[0].islower() or
                                        desc[0].isdigit() or
                                        len(desc) < 30
                                    )
                                )
                                prev_ends_continuation = (
                                    prev_line and
                                    re.search(r'[,\-]\s*$', prev_line)
                                )
                                prev_is_valid_desc = (
                                    prev_line and
                                    not re.match(r'^\d+\.\d+', prev_line) and
                                    len(prev_line) > 10 and
                                    any(c.isalpha() for c in prev_line)
                                )
                                should_merge = prev_is_valid_desc and (
                                    desc_looks_truncated or prev_ends_continuation
                                )
                                if should_merge:
                                    prev_clean = re.sub(r'\s*[,\-]\s*$', '', prev_line).strip()
                                    desc = f"{prev_clean} {desc}"

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

            # Padrao 2: Codigo no meio da linha
            mid_pattern = re.search(
                r'(.{10,}?)\s+(\d{1,2}\.\d{1,2}(?:\.\d{1,2})?)\s+'
                r'(UN|M|M2|M3|KG|VB|CJ|L|T|HA|KM|MES|GB|PC|PT)\s+'
                r'([\d.,]+)\s*(.*)$',
                line,
                re.IGNORECASE
            )
            if mid_pattern:
                desc_start = mid_pattern.group(1).strip()
                item_raw = mid_pattern.group(2)
                unit_raw = mid_pattern.group(3)
                qty_raw = mid_pattern.group(4)
                desc_end = mid_pattern.group(5).strip()

                if re.search(r'\blinha\s*$', desc_start, re.IGNORECASE):
                    prev_line = line
                    continue

                item_tuple = parse_item_tuple(item_raw)
                if not item_tuple:
                    prev_line = line
                    continue

                qty = parse_quantity(qty_raw)
                if qty is None:
                    prev_line = line
                    continue

                unit_norm = normalize_unit(unit_raw)
                if not unit_norm:
                    prev_line = line
                    continue

                desc_start_clean = re.sub(r'\s*-\s*$', '', desc_start).strip()
                if desc_end:
                    full_desc = f"{desc_start_clean} - {desc_end}"
                else:
                    full_desc = desc_start_clean

                if last_tuple and item_tuple < last_tuple:
                    segment_index += 1
                last_tuple = item_tuple

                prefix = f"S{segment_index}-" if segment_index > 1 else ""
                items.append({
                    'item': f"{prefix}{item_tuple_to_str(item_tuple)}",
                    'descricao': full_desc,
                    'unidade': unit_norm,
                    'quantidade': qty_raw,
                    '_source': 'text_line_mid'
                })
                prev_line = line
                continue

            prev_line = line

        return items

    def extract_items_without_codes_from_text(self, texto: str) -> list:
        """Extrai itens sem codigo do texto."""
        if not texto:
            return []
        lines = [line.strip() for line in texto.splitlines()]
        anchor_idx = self.find_servicos_anchor_line(lines)
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
            if "DESCRICAO" in normalized and "QUANT" in normalized and "UND" in normalized:
                pending_desc = ""
                continue

            unit_match = self.find_unit_qty_in_line(line)
            if unit_match:
                unit, qty, start, end = unit_match
                before = line[:start].strip()
                after = line[end:].strip()
                anchors = [
                    "FORNEC", "LOCAÇÃO", "LOCACAO", "EXECUÇÃO", "EXECUCAO",
                    "ESCAVAÇÃO", "ESCAVACAO", "REATERRO", "LASTRO",
                    "FUNDAÇÃO", "FUNDACAO", "CONCRETO", "ADMINISTRAÇÃO",
                    "ADMINISTRACAO", "MOBILIZAÇÃO", "MOBILIZACAO",
                    "PLACA", "PERFURAÇÃO", "PERFURACAO"
                ]
                if before:
                    upper_before = before.upper()
                    anchor_pos = None
                    for anchor in anchors:
                        pos = upper_before.find(anchor)
                        if pos == -1:
                            continue
                        if anchor_pos is None or pos < anchor_pos:
                            anchor_pos = pos
                    if anchor_pos is not None and anchor_pos > 0:
                        before = before[anchor_pos:].strip()
                        pending_desc = ""
                parts = []
                if pending_desc:
                    parts.append(pending_desc)
                    pending_desc = ""
                if before:
                    parts.append(before)
                if after:
                    parts.append(after)
                desc = " ".join(parts).strip()
                desc = self.strip_footer_prefix_from_desc(desc)
                desc = self.strip_trailing_unit_qty(desc, unit, qty)
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
                last_item["descricao"] = (last_desc + " " + line).strip() if last_desc else line
                continue

            if not re.search(r'\d', line):
                if len(normalized) <= 40 and line == line.upper():
                    pending_desc = ""
                    continue
            pending_desc = (pending_desc + " " + line).strip() if pending_desc else line

        return items

    def extract_quantities_from_text(self, texto: str, item_codes: Set[str]) -> Dict[str, list]:
        """Extrai quantidades do texto para codigos de item especificos."""
        if not texto or not item_codes:
            return {}
        pattern = re.compile(r'(\d{1,3}(?:\s*\.\s*\d{1,3}){1,4})(?!\s*/\s*\d)')
        qty_map: Dict[str, list] = {}
        current_code = None
        pending_unit = None

        def add_qty(code: str, unit_qty: tuple) -> None:
            qty_map.setdefault(code, []).append(unit_qty)

        def find_unit_in_text(segment: str) -> Optional[str]:
            for token in reversed(re.findall(r'[\w\u00ba\u00b0/%\u00b2\u00b3\.]+', segment)):
                unit_norm = normalize_unit(token)
                if unit_norm and unit_norm in UNIT_TOKENS:
                    return unit_norm
            return None

        def find_last_qty(line: str) -> Optional[float]:
            for token in reversed(re.findall(r'[\d.,]+', line)):
                qty = parse_quantity(token)
                if qty not in (None, 0):
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
                code = self.normalize_item_code(raw_code)
                if code and code in item_codes:
                    matches.append((match.start(), match.end(), code))
            if matches:
                if current_code:
                    prefix = line[:matches[0][0]].strip()
                    if prefix:
                        parsed = self.parse_unit_qty_from_line(prefix)
                        if parsed:
                            add_qty(current_code, parsed)
                            current_code = None
                            pending_unit = None
                        elif pending_unit:
                            qty = find_last_qty(prefix)
                            if qty is not None:
                                add_qty(current_code, (pending_unit, qty))
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
                    parsed = self.parse_unit_qty_from_line(segment)
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

                parsed = self.parse_unit_qty_from_line(line)
                if parsed:
                    add_qty(current_code, parsed)
                    current_code = None
                    pending_unit = None
                    continue

                if pending_unit:
                    qty = find_last_qty(line)
                    if qty is not None:
                        add_qty(current_code, (pending_unit, qty))
                        current_code = None
                        pending_unit = None
                        continue

                if not re.search(r'\d', line):
                    unit_norm = normalize_unit(line)
                    if unit_norm and unit_norm in UNIT_TOKENS:
                        pending_unit = unit_norm
                        continue

        return qty_map

    def detect_planilha_signature(self, texto: str) -> Optional[str]:
        """Detecta assinatura de planilha no texto (ORCAMENTO, FISICO, etc)."""
        normalized = normalize_description(texto or "")
        if not normalized:
            return None
        has_orcamento = "ORCAMENTO" in normalized
        has_fisico = "FISICO" in normalized
        has_geobras = "GEOBRAS" in normalized
        has_contrato = "CONTRATO" in normalized
        if has_fisico:
            if has_geobras or has_contrato:
                return "FISICO_CONTRATO"
            return "FISICO"
        if has_orcamento:
            return "ORCAMENTO"
        return None

    def build_page_planilha_map(self, page_segments: list) -> tuple:
        """Constroi mapeamento de pagina para planilha baseado em assinaturas."""
        if not page_segments:
            return {}, []
        page_map: Dict[int, int] = {}
        audit: list = []
        current_sig = None
        planilha_id = 0
        found_signature = False
        for page_num, page_text in page_segments:
            sig = self.detect_planilha_signature(page_text)
            if sig:
                found_signature = True
                if sig != current_sig:
                    planilha_id += 1
                    current_sig = sig
            page_map[page_num] = planilha_id if planilha_id else 0
            audit.append({
                "page": page_num,
                "planilha_id": page_map[page_num],
                "signature": sig or current_sig
            })
        if not found_signature:
            return {}, []
        return page_map, audit

    def apply_page_planilha_map(self, servicos: list, page_map: Dict[int, int]) -> int:
        """Aplica mapeamento de pagina para planilha nos servicos."""
        if not servicos or not page_map:
            return 0
        remapped = 0
        for servico in servicos:
            page = servico.get("_page")
            if page is None:
                continue
            try:
                page_num = int(page)
            except (TypeError, ValueError):
                continue
            target_id = page_map.get(page_num)
            if not target_id:
                continue
            current_id = int(servico.get("_planilha_id") or 0)
            if current_id != target_id:
                servico["_planilha_id"] = target_id
                servico.pop("_planilha_label", None)
                remapped += 1
        return remapped


# Singleton
text_extraction_service = TextExtractionService()
