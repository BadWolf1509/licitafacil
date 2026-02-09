"""
Processador de extração de itens a partir de texto.

Contém métodos extraídos do DocumentProcessor para extração
de itens de serviço a partir de texto OCR ou extraído de PDFs.
"""

import re
from collections import Counter
from typing import Any, Dict, List, Optional, Set

from config import AtestadoProcessingConfig as APC
from logging_config import get_logger
from services.extraction import (
    is_corrupted_text,
    is_valid_item_context,
    item_tuple_to_str,
    normalize_description,
    parse_item_tuple,
)
from services.processing_helpers import (
    is_section_header_desc,
    normalize_item_code,
)
from services.text_extraction_service import text_extraction_service

from .quantity_extractor import quantity_extractor
from .text_cleanup import (
    find_unit_qty_in_line,
    strip_footer_prefix_from_desc,
    strip_trailing_unit_qty,
)
from .text_cleanup import (
    strip_unit_qty_prefix as _strip_unit_qty_prefix,
)
from .text_line_parser import text_line_parser
from .text_section_builder import build_items_from_code_lines

logger = get_logger("services.processors.text_processor")


class TextProcessor:
    """
    Processador especializado para extração de itens de texto.

    Extrai códigos de item, descrições, unidades e quantidades
    de texto livre ou semi-estruturado.
    """

    # ==================== Métodos Públicos ====================

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
        - "9.11 DESCRICAO UN 10,00" (código início, unidade fim)
        - "9.13 UN 5,00 FORNECIMENTO..." (unidade logo após código)
        - "DISJUNTOR... 9.11 UN 10,00 FORNECIMENTO..." (código no meio)

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

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Rejeitar linhas com texto corrompido (OCR com caracteres intercalados)
            if is_corrupted_text(line):
                continue

            # Tentar cada padrão em ordem de prioridade
            result = (
                text_line_parser.try_pattern_code_unit_end(line, prev_line, segment_index, last_tuple) or
                text_line_parser.try_pattern_unit_first(line, prev_line, segment_index, last_tuple) or
                text_line_parser.extract_mid_pattern_item(line, segment_index, last_tuple) or
                text_line_parser.extract_mid_pattern_unit_end(line, segment_index, last_tuple)
            )

            if result:
                items.append(result["item"])
                segment_index = result["segment_index"]
                last_tuple = result["last_tuple"]

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

        return build_items_from_code_lines(
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

            unit_match = find_unit_qty_in_line(line)
            if unit_match:
                unit, qty, start, end = unit_match
                before = line[:start].strip()
                after = line[end:].strip()

                if before:
                    before = strip_footer_prefix_from_desc(before)

                parts = []
                if pending_desc:
                    parts.append(pending_desc)
                    pending_desc = ""
                if before:
                    parts.append(before)
                if after:
                    parts.append(after)

                desc = " ".join(parts).strip()
                desc = strip_footer_prefix_from_desc(desc)
                desc = strip_trailing_unit_qty(desc, unit, qty)

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

        Delega para QuantityExtractor.

        Args:
            texto: Texto do documento
            item_codes: Conjunto de códigos de item a procurar

        Returns:
            Mapa de código -> lista de (unidade, quantidade)
        """
        return quantity_extractor.extract_quantities(texto, item_codes)

    def backfill_quantities_from_text(
        self,
        servicos: List[Dict[str, Any]],
        texto: str
    ) -> int:
        """
        Preenche quantidades faltantes usando o texto.

        Delega para QuantityExtractor.

        Args:
            servicos: Lista de serviços (modificada in-place)
            texto: Texto do documento

        Returns:
            Número de quantidades preenchidas
        """
        return quantity_extractor.backfill_quantities(servicos, texto)

    def strip_unit_qty_prefix(self, desc: str) -> str:
        """Remove prefixo de unidade/quantidade da descrição."""
        return _strip_unit_qty_prefix(desc)

    def recover_descriptions_from_text(
        self,
        servicos: list,
        texto: str
    ) -> list:
        """
        Recupera descrições ausentes do texto OCR para itens com descrição curta.

        Alguns PDFs têm formato onde a descrição aparece na linha anterior
        ao código do item. Este método tenta recuperar essas descrições.

        Args:
            servicos: Lista de serviços
            texto: Texto OCR extraído

        Returns:
            Lista de serviços com descrições recuperadas
        """
        if not servicos or not texto:
            return servicos

        lines = texto.split('\n')
        line_map = {}

        # Criar mapa de linhas que começam com código de item
        for i, line in enumerate(lines):
            match = re.match(r'^(\d+\.\d+(?:\.\d+)?)\s+', line.strip())
            if match:
                item_code = match.group(1)
                line_map[item_code] = i

        # Para cada serviço com descrição curta, tentar recuperar
        for servico in servicos:
            desc = (servico.get("descricao") or "").strip()
            item_code = servico.get("item")

            # Só processar se descrição curta ou claramente um cabeçalho
            if not item_code:
                continue
            if len(desc) >= 10 and not is_section_header_desc(desc):
                continue

            line_idx = line_map.get(str(item_code))
            if line_idx is None or line_idx == 0:
                continue

            # Verificar linha anterior
            prev_line = lines[line_idx - 1].strip()

            # A linha anterior deve ser texto (não um código de item)
            if re.match(r'^(S\d+-)?\d+\.\d+', prev_line):
                continue

            # Ignorar linhas muito curtas ou que são apenas números
            if len(prev_line) < 15:
                continue
            if re.match(r'^[\d\s,\.]+$', prev_line):
                continue
            if is_section_header_desc(prev_line):
                continue

            # Ignorar linhas de cabeçalho/rodapé comuns
            skip_patterns = [
                r'^p[áa]gina\s+\d',
                r'^\d+/\d+$',
                r'^af_\d+/\d+$',
            ]
            should_skip = False
            for pattern in skip_patterns:
                if re.match(pattern, prev_line, re.I):
                    should_skip = True
                    break
            if should_skip:
                continue

            # Recuperar descrição da linha anterior
            servico["descricao"] = prev_line
            servico["_desc_recovered"] = True
            logger.debug(f"Recuperada descrição para {item_code}: {prev_line[:50]}...")

        return servicos

    def extract_hidden_items_from_servicos(self, servicos: list) -> list:
        """
        Extrai itens ocultos de descrições.

        Escaneia todas as descrições procurando códigos de item embutidos
        (ex: "TE, PVC... JUNTA 6.14 ELÁSTICA...") e extrai como serviços separados.

        Args:
            servicos: Lista de serviços

        Returns:
            Lista atualizada com itens ocultos extraídos
        """
        # Padrão para detectar item oculto no meio do texto
        hidden_pattern = re.compile(
            r'(.{5,}?)\s+(\d{1,2}\.\d{1,2}(?:\.\d{1,2})?)\s+([A-ZÀ-ÚÇ].{10,})',
            re.IGNORECASE
        )

        new_servicos = []
        for servico in servicos:
            desc = servico.get("descricao") or ""
            if len(desc) < 25:
                new_servicos.append(servico)
                continue

            match = hidden_pattern.search(desc)
            if not match:
                new_servicos.append(servico)
                continue

            prefix = match.group(1).strip()
            hidden_code = match.group(2)
            suffix = match.group(3).strip()

            # Verificar contexto
            if not is_valid_item_context(desc, match.start(2)):
                new_servicos.append(servico)
                continue

            # Verificar se o código é válido
            hidden_tuple = parse_item_tuple(hidden_code)
            if not hidden_tuple:
                new_servicos.append(servico)
                continue

            # Atualizar descrição do serviço original com o prefix
            servico["descricao"] = prefix

            # Criar novo serviço para o item oculto
            hidden_servico = {
                "item": hidden_code,
                "descricao": suffix,
                "unidade": None,
                "quantidade": None,
                "_planilha_id": servico.get("_planilha_id"),
                "_page": servico.get("_page"),
                "_hidden_from": servico.get("item"),
            }

            new_servicos.append(servico)
            new_servicos.append(hidden_servico)
            logger.info(f"[HIDDEN-ITEM] Extraído item oculto {hidden_code} de {servico.get('item')}")

        return new_servicos


# Instância singleton para uso conveniente
text_processor = TextProcessor()
