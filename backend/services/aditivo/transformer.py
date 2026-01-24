"""
Transformador de itens de aditivo.

Responsável por prefixar e processar itens de aditivo contratual.
"""

import re
from typing import List, Dict, Any, Set, Tuple, Optional

from logging_config import get_logger
from ..extraction import parse_item_tuple
from ..extraction.item_utils import strip_restart_prefix, max_restart_prefix_index
from utils.text_utils import sanitize_description

from .detector import detect_aditivo_sections, get_aditivo_start_line
from .validators import is_contaminated_line, is_good_description
from .extractors import AditivoItemExtractor

logger = get_logger('services.aditivo.transformer')


class AditivoTransformer:
    """
    Transforma itens de serviço com prefixos de aditivo.

    Processa itens de aditivo em 5 fases:
    - FASE 1: Prefixação de itens do aditivo
    - FASE 1.5: Detecção de itens faltantes do contrato
    - FASE 2: Detecção de itens faltantes do aditivo
    - FASE 2.5: Remoção de duplicatas exatas
    - FASE 3: Validação e filtragem
    """

    def __init__(self, servicos: List[Dict[str, Any]], texto: str):
        """
        Inicializa o transformador.

        Args:
            servicos: Lista de serviços extraídos
            texto: Texto extraído do documento
        """
        self.servicos = servicos
        self.texto = texto
        self.lines = texto.split("\n") if texto else []
        self.sections = detect_aditivo_sections(texto)
        self.aditivo_start_line = get_aditivo_start_line(self.sections)

        # Mapeamento de prefixos
        self.aditivo_prefixes: Dict[int, int] = {}
        self._build_prefix_mapping()

        # Índice de itens
        self.item_set: Set[str] = set()
        self.planilha_by_code: Dict[str, int] = {}
        self._build_item_index()

        # Extrator
        self.extractor = AditivoItemExtractor(self.lines, self.aditivo_start_line)

    def transform(self) -> List[Dict[str, Any]]:
        """
        Executa a transformação completa.

        Returns:
            Lista de serviços com itens do aditivo prefixados
        """
        if not self.servicos or not self.texto:
            return self.servicos

        if not self.sections:
            return self.servicos

        # FASE 1: Prefixação de itens
        result = self._fase1_prefix_items()

        # FASE 1.5: Detectar itens faltantes do contrato
        result = self._fase1_5_detect_contract_items(result)

        # FASE 2: Detectar itens faltantes do aditivo
        result = self._fase2_detect_aditivo_items(result)

        # FASE 2.5: Remover duplicatas exatas
        result = self._fase2_5_remove_exact_duplicates(result)

        # FASE 3: Validação e filtragem
        result = self._fase3_validate_and_filter(result)

        # Log resumo
        aditivo_count = sum(1 for r in result if r.get("_section") == "AD")
        contrato_count = len(result) - aditivo_count
        auto_detected = sum(1 for r in result if r.get("_auto_detected"))
        logger.info(
            f"[ADITIVO] Resultado: {len(result)} itens total "
            f"({contrato_count} contrato, {aditivo_count} aditivo, {auto_detected} auto-detectados)"
        )

        return result

    def _build_prefix_mapping(self) -> None:
        """Constrói mapeamento de seção para prefixo de restart."""
        next_segment = max_restart_prefix_index(self.servicos) + 1
        for section in sorted(self.sections, key=lambda s: s.get("start_line", 0)):
            section_num = section["section_num"]
            if section_num not in self.aditivo_prefixes:
                self.aditivo_prefixes[section_num] = next_segment
                next_segment += 1

    def _build_item_index(self) -> None:
        """Constrói índice de itens para detectar headers."""
        planilha_candidates: Dict[str, Dict[int, int]] = {}

        for s in self.servicos:
            item_val = s.get("item")
            if item_val:
                base_item = strip_restart_prefix(str(item_val))
                if base_item:
                    self.item_set.add(base_item)
                    planilha_id = s.get("_planilha_id")
                    if planilha_id is not None:
                        counts = planilha_candidates.setdefault(base_item, {})
                        counts[planilha_id] = counts.get(planilha_id, 0) + 1

        for code, counts in planilha_candidates.items():
            self.planilha_by_code[code] = max(counts.items(), key=lambda x: x[1])[0]

    def _apply_restart_prefix(self, item_value: str, segment_idx: int) -> Tuple[str, str]:
        """Aplica prefixo de restart ao item."""
        item_str = strip_restart_prefix(str(item_value or "").strip())
        if not item_str:
            return "", ""
        if segment_idx <= 1:
            return item_str, ""
        prefix = f"S{segment_idx}"
        return f"{prefix}-{item_str}", prefix

    def _find_item_in_text(self, item_str: str) -> Tuple[bool, bool, bool]:
        """
        Busca um item no texto.

        Returns:
            Tupla (encontrado_antes, encontrado_depois, aditivo_tem_quantidade)
        """
        pattern = re.compile(rf"^\s*{re.escape(item_str)}(?:\s|$)", re.MULTILINE)
        found_before = False
        found_after = False
        aditivo_has_qty = False

        for i, line in enumerate(self.lines):
            if pattern.match(line):
                if i < self.aditivo_start_line:
                    found_before = True
                else:
                    found_after = True
                    if re.search(r"\b(?:UN|M|KG|M2|M3|L|VB|CJ)\s+\d+", line, re.IGNORECASE):
                        aditivo_has_qty = True

        return (found_before, found_after, aditivo_has_qty)

    def _is_header_item(self, item_str: str) -> bool:
        """Verifica se item é header (tem sub-itens)."""
        prefix = item_str + "."
        return any(other.startswith(prefix) for other in self.item_set)

    def _fase1_prefix_items(self) -> List[Dict[str, Any]]:
        """FASE 1: Prefixação de itens do aditivo."""
        logger.debug(f"[ADITIVO] Iniciando prefixação. Seções detectadas: {self.aditivo_prefixes}")
        logger.debug(f"[ADITIVO] Linha de início do aditivo: {self.aditivo_start_line}")

        result = []
        for s in self.servicos:
            item = s.get("item")
            if not item:
                result.append(s)
                continue

            item_tuple = parse_item_tuple(strip_restart_prefix(str(item)))
            if not item_tuple:
                result.append(s)
                continue

            major = item_tuple[0]

            # Só considerar itens com números baixos que são candidatos
            if major not in self.aditivo_prefixes:
                result.append(s)
                continue

            # Só processar itens de profundidade 2 (ex: 1.1, 2.3)
            if len(item_tuple) != 2:
                result.append(s)
                continue

            # Verificar onde o item aparece no texto
            item_str = strip_restart_prefix(str(item))
            found_before, found_after, _ = self._find_item_in_text(item_str)

            if found_after and not found_before:
                # Item exclusivo do aditivo
                result.append(self._create_aditivo_item(s, item, item_str, major))
            elif found_after and found_before:
                # Item em ambos - criar versões
                is_header = self._is_header_item(item_str)
                if not is_header:
                    result.append(s)
                result.append(self._create_aditivo_item(s, item, item_str, major))
            else:
                result.append(s)

        return result

    def _create_aditivo_item(
        self, original: Dict[str, Any], item: str, item_str: str, major: int
    ) -> Dict[str, Any]:
        """Cria versão do item para aditivo."""
        s_copy = original.copy()
        new_item, prefix = self._apply_restart_prefix(item, self.aditivo_prefixes.get(major, 1))
        s_copy["item"] = new_item
        s_copy["_section"] = "AD"
        if prefix:
            s_copy["_item_prefix"] = prefix

        # Extrair informações do texto
        aditivo_info = self.extractor.extract(item_str, major)
        text_desc = aditivo_info.get("descricao")

        if text_desc and is_good_description(text_desc):
            s_copy["descricao"] = text_desc
            s_copy["_desc_source"] = "texto"
        else:
            s_copy["_desc_source"] = "IA"

        if aditivo_info["quantidade"] is not None:
            s_copy["quantidade"] = aditivo_info["quantidade"]
        if aditivo_info["unidade"]:
            s_copy["unidade"] = aditivo_info["unidade"]

        return s_copy

    def _fase1_5_detect_contract_items(
        self, result: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """FASE 1.5: Detectar itens faltantes do contrato."""
        result_items = set(r.get("item", "") for r in result)
        logger.info(f"[CONTRATO-FASE1.5] Detectando itens faltantes do contrato (linhas 0-{self.aditivo_start_line})")

        contrato_item_pattern = re.compile(
            r"^\s*(\d{1,2}\.\d{1,2}(?:\.\d{1,2})?)\s+([A-ZÀ-ÚÇ][\w\sÀ-ÚÇ,.\-/()]+?)"
            r"(?:\s*,?\s*(UN|M|KG|M2|M3|M²|M³|L|VB|CJ|PC|GL|und|un|m|m²|m³|pç|pc)\s+([\d,.]+))?\s*$",
            re.IGNORECASE
        )

        items_added = 0
        for i, line in enumerate(self.lines):
            if self.aditivo_start_line and i >= self.aditivo_start_line:
                break

            match = contrato_item_pattern.match(line)
            if not match:
                continue

            item_str = match.group(1)
            descricao = match.group(2).strip() if match.group(2) else ""
            unidade = match.group(3) or ""
            quantidade_str = match.group(4) or ""

            if item_str in result_items or len(descricao) < 15:
                continue

            quantidade = 0.0
            if quantidade_str:
                try:
                    quantidade = float(quantidade_str.replace(",", "."))
                except ValueError:
                    quantidade = 0.0

            s_new = {
                "item": item_str,
                "_desc_source": "texto",
                "_auto_detected": True,
                "descricao": descricao,
                "quantidade": quantidade,
                "unidade": unidade.upper() if unidade else "",
            }
            result.append(s_new)
            result_items.add(item_str)
            items_added += 1

        if items_added > 0:
            logger.info(f"[CONTRATO-FASE1.5] {items_added} itens do contrato adicionados automaticamente")

        return result

    def _fase2_detect_aditivo_items(
        self, result: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """FASE 2: Detectar itens faltantes do aditivo."""
        result_items = set(r.get("item", "") for r in result)
        logger.info(f"[ADITIVO-FASE2] INICIANDO. Total itens: {len(result_items)}")

        aditivo_item_pattern = re.compile(
            r"^\s*(\d+\.\d+)\s+(\S.*?)"
            r"(?:\s+(UN|M|KG|M2|M3|M²|M³|L|VB|CJ|PC|GL|un|m|m²|m³)\s+([\d,.]+))?\s*$",
            re.IGNORECASE
        )

        for i, line in enumerate(self.lines):
            if i < self.aditivo_start_line:
                continue

            match = aditivo_item_pattern.match(line)
            embedded_match = None
            embedded_item_str = None

            if not match:
                # Detectar itens embutidos
                embedded_pattern = re.search(
                    r'(\d+\.\d+)\s+(UN|M|KG|M2|M3|M²|M³|L|VB|CJ|PC|GL)\s+([\d,.]+)\s*$',
                    line, re.IGNORECASE
                )
                if embedded_pattern and embedded_pattern.start(1) > 15:
                    before_text = line[:embedded_pattern.start(1)].strip()
                    before_text = re.sub(r'\s+\d+\.\d+\s*$', '', before_text).strip()
                    if re.search(r'[A-Za-zÀ-ÿ]{4,}', before_text) and len(before_text) > 15:
                        embedded_item_str = embedded_pattern.group(1)
                        embedded_match = embedded_pattern

            if not match and not embedded_match:
                continue

            item_str = match.group(1) if match else embedded_item_str
            if not item_str:
                continue
            item_tuple = parse_item_tuple(item_str)
            if not item_tuple or len(item_tuple) != 2:
                continue

            major = item_tuple[0]
            if major not in self.aditivo_prefixes:
                continue

            ad_item, ad_prefix = self._apply_restart_prefix(item_str, self.aditivo_prefixes.get(major, 1))

            # Verificar se item já existe
            existing_item = self._find_existing_item(result, item_str, ad_item)

            if existing_item:
                self._enrich_existing_item(existing_item, item_str, major)
                continue

            # Adicionar novo item
            if embedded_match:
                aditivo_info = self._extract_embedded_item(line, embedded_match)
            else:
                aditivo_info = self.extractor.extract(item_str, major)

            if aditivo_info.get("descricao") or aditivo_info.get("quantidade") is not None:
                s_new = {
                    "item": ad_item,
                    "_section": "AD",
                    "_desc_source": "texto",
                    "_auto_detected": True,
                    "descricao": aditivo_info.get("descricao") or "",
                    "quantidade": aditivo_info.get("quantidade") or 0,
                    "unidade": aditivo_info.get("unidade") or "",
                }
                if ad_prefix:
                    s_new["_item_prefix"] = ad_prefix
                base_planilha = self.planilha_by_code.get(item_str)
                if base_planilha is not None:
                    s_new["_planilha_id"] = base_planilha
                result.append(s_new)
                result_items.add(ad_item)

        return result

    def _find_existing_item(
        self, result: List[Dict[str, Any]], item_str: str, ad_item: str
    ) -> Optional[Dict[str, Any]]:
        """Procura item existente pelo código base."""
        for r in result:
            r_item = r.get("item", "")
            base_result = strip_restart_prefix(r_item)
            if base_result == item_str or r_item == ad_item:
                return r
        return None

    def _enrich_existing_item(
        self, existing: Dict[str, Any], item_str: str, major: int
    ) -> None:
        """Enriquece descrição de item existente se truncada."""
        existing_desc = (existing.get("descricao") or "").strip()

        continuation_words = (
            'E ', 'EM ', 'DE ', 'DO ', 'DA ', 'NO ', 'NA ', 'PARA ', 'COM ',
            'MM,', 'MM ', 'ELÁSTICA', 'ELASTICA', 'INCLUSIVE', 'INCLUINDO',
        )

        desc_looks_truncated = (
            len(existing_desc) < 40 or
            (existing_desc and existing_desc[0].islower()) or
            (existing_desc and existing_desc[0].isdigit()) or
            existing_desc.upper().startswith(continuation_words)
        )

        if desc_looks_truncated:
            aditivo_info = self.extractor.extract(item_str, major)
            enriched_desc = aditivo_info.get("descricao")
            if enriched_desc and len(enriched_desc) > len(existing_desc):
                if not is_contaminated_line(enriched_desc):
                    existing["descricao"] = enriched_desc
                    existing["_desc_source"] = "texto_enriquecido"

    def _extract_embedded_item(self, line: str, embedded_match) -> Dict[str, Any]:
        """Extrai informações de item embutido."""
        before_text = line[:embedded_match.start(1)].strip()
        before_text = re.sub(r'\s+\d+\.\d+\s*$', '', before_text).strip()
        unit_val = embedded_match.group(2).upper().replace("²", "2").replace("³", "3")
        qty_str = embedded_match.group(3).replace(",", ".")

        try:
            qty_val = float(qty_str)
        except ValueError:
            qty_val = 0

        return {
            "descricao": sanitize_description(before_text),
            "quantidade": qty_val,
            "unidade": unit_val,
            "_source": "text_embedded"
        }

    def _fase2_5_remove_exact_duplicates(
        self, result: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """FASE 2.5: Remover duplicatas exatas."""
        seen_exact: Set[tuple] = set()
        exact_deduped = []
        exact_removed = 0

        for r in result:
            item = r.get("item", "")
            desc = (r.get("descricao") or "").strip()[:100].lower()
            qty = r.get("quantidade", 0)
            unit = (r.get("unidade") or "").strip().upper()
            key = (item, desc, qty, unit)

            if key in seen_exact:
                exact_removed += 1
                continue
            seen_exact.add(key)
            exact_deduped.append(r)

        if exact_removed > 0:
            logger.info(f"[DEDUP-EXATO] {exact_removed} duplicatas exatas removidas")

        # Renomear duplicatas com sufixo
        item_counts: Dict[str, int] = {}
        deduped_result = []
        duplicates_renamed = 0

        for r in exact_deduped:
            item = r.get("item", "")
            if item:
                count = item_counts.get(item, 0)
                if count == 0:
                    item_counts[item] = 1
                else:
                    suffix = chr(ord('A') + count - 1)
                    r["item"] = f"{item}-{suffix}"
                    item_counts[item] = count + 1
                    duplicates_renamed += 1
            deduped_result.append(r)

        if duplicates_renamed > 0:
            logger.info(f"[DEDUP] {duplicates_renamed} itens duplicados renomeados com sufixo")

        return deduped_result

    def _fase3_validate_and_filter(
        self, result: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """FASE 3: Validação e filtragem."""
        # 3.1: Extrair seções X.Y do texto
        secoes_texto: Set[str] = set()
        for linha in self.lines:
            match = re.match(r"^\s*(\d{1,2}\.\d{1,2})\s+[A-Z]", linha)
            if match:
                secoes_texto.add(match.group(1))

        # Filtrar itens com seção pai inexistente
        filtered_result = []
        items_removed_secao = 0

        for r in result:
            item = r.get("item", "")
            if r.get("_section") == "AD":
                filtered_result.append(r)
                continue

            base_item = re.sub(r"-[A-Z]$", "", item)
            parts = base_item.split(".")

            if len(parts) == 3:
                parent = f"{parts[0]}.{parts[1]}"
                if parent not in secoes_texto:
                    siblings = [
                        r2.get("item", "") for r2 in result
                        if re.sub(r"-[A-Z]$", "", r2.get("item", "")).startswith(parent + ".")
                        and r2.get("item", "") != item
                    ]
                    if not siblings:
                        items_removed_secao += 1
                        continue
            filtered_result.append(r)

        if items_removed_secao > 0:
            logger.info(f"[VALIDACAO] {items_removed_secao} itens removidos por seção pai inexistente")

        # 3.2: Filtrar duplicatas contrato/aditivo
        aditivo_map: Dict[tuple, str] = {}
        for r in filtered_result:
            item = r.get("item", "")
            if r.get("_section") == "AD":
                desc = (r.get("descricao") or "").strip()[:50].lower()
                qtd = r.get("quantidade", 0)
                base_item = re.sub(r"-[A-Z]$", "", strip_restart_prefix(item))
                aditivo_map[(desc, qtd, base_item)] = item

        final_result = []
        items_removed_dup = 0

        for r in filtered_result:
            item = r.get("item", "")
            if r.get("_section") != "AD" and re.search(r"-[A-Z]$", item):
                desc = (r.get("descricao") or "").strip()[:50].lower()
                qtd = r.get("quantidade", 0)
                base_item = re.sub(r"-[A-Z]$", "", item)
                dup_key = (desc, qtd, base_item)

                if dup_key in aditivo_map:
                    items_removed_dup += 1
                    continue
            final_result.append(r)

        if items_removed_dup > 0:
            logger.info(f"[VALIDACAO] {items_removed_dup} itens removidos por duplicata contrato/aditivo")

        return final_result


def prefix_aditivo_items(servicos: List[Dict[str, Any]], texto: str) -> List[Dict[str, Any]]:
    """
    Prefixa itens do aditivo contratual para diferenciá-los do contrato.

    Função de conveniência que usa AditivoTransformer internamente.

    Args:
        servicos: Lista de serviços extraídos
        texto: Texto extraído do documento

    Returns:
        Lista de serviços com itens do aditivo prefixados
    """
    transformer = AditivoTransformer(servicos, texto)
    return transformer.transform()
