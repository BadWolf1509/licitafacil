"""
Serviços de deduplicação de itens extraídos.

Extrai e centraliza toda lógica de deduplicação do DocumentProcessor,
oferecendo múltiplas estratégias para remover duplicatas.
"""

from typing import Any, Dict, List, Set
import logging

from services.extraction import (
    normalize_description,
    normalize_unit,
    normalize_desc_for_match,
    parse_quantity,
    extract_keywords,
    quantities_similar,
    description_similarity,
    extract_item_code,
)
from config import AtestadoProcessingConfig as APC
from services.processing_helpers import (
    normalize_item_code,
    split_restart_prefix,
    is_section_header_desc,
)
from services.extraction.patterns import Patterns

logger = logging.getLogger(__name__)


class ServiceDeduplicator:
    """
    Remove duplicatas de listas de serviços usando múltiplas estratégias.

    Estratégias disponíveis:
    - remove_duplicate_pairs: Remove pares X.Y e X.Y.1
    - dedupe_by_restart_prefix: Remove duplicatas com prefixos S1-, S2-
    - dedupe_within_planilha: Remove duplicatas por código na mesma planilha
    - dedupe_by_desc_unit: Remove duplicatas por descrição e unidade
    """

    def __init__(self, servicos: List[Dict[str, Any]]):
        """
        Inicializa o deduplicador com a lista de serviços.

        Args:
            servicos: Lista de dicionários de serviços
        """
        self.servicos = servicos if servicos else []

    def remove_duplicate_pairs(self) -> List[Dict[str, Any]]:
        """
        Remove duplicatas entre pares X.Y e X.Y.1 que representam o mesmo serviço.

        Quando ambos existem com quantidade igual e descrições similares:
        - Calcula similaridade baseada em keywords em comum
        - Se similaridade >= 50%, são considerados duplicados
        - Mantém apenas o item com código mais curto (X.Y) pois geralmente é o original
        - Exceto quando o pai é um header curto (< 20 chars), aí mantém o filho (X.Y.1)

        Returns:
            Lista filtrada sem duplicatas pai/filho
        """
        if not self.servicos:
            return self.servicos

        # Indexar serviços por código de item
        by_item_code: Dict[tuple, Dict] = {}
        for s in self.servicos:
            item = s.get("item")
            if item:
                planilha_id = s.get("_planilha_id") or 0
                by_item_code[(planilha_id, str(item))] = s

        # Identificar itens a remover
        items_to_remove: Set[tuple] = set()

        for item_key, servico in by_item_code.items():
            planilha_id, item_code = item_key
            # Verificar se existe item pai (X.Y para X.Y.1)
            parts = item_code.split(".")
            if len(parts) >= 2:
                parent_code = ".".join(parts[:-1])
                parent_key = (planilha_id, parent_code)
                if parent_key in by_item_code:
                    parent = by_item_code[parent_key]

                    # Comparar quantidade
                    qty_filho = parse_quantity(servico.get("quantidade"))
                    qty_pai = parse_quantity(parent.get("quantidade"))

                    if not (qty_filho is not None and qty_pai is not None):
                        continue

                    # Verificar se quantidades são iguais ou similares
                    if not quantities_similar(qty_filho, qty_pai):
                        continue

                    # Calcular similaridade de descrições via keywords
                    desc_filho = servico.get("descricao") or ""
                    desc_pai = parent.get("descricao") or ""
                    kw_filho = extract_keywords(desc_filho)
                    kw_pai = extract_keywords(desc_pai)

                    if not kw_filho or not kw_pai:
                        continue

                    # Calcular Jaccard similarity
                    intersection = len(kw_filho & kw_pai)
                    union = len(kw_filho | kw_pai)
                    similarity = intersection / union if union > 0 else 0

                    # Se similaridade >= 50%, são duplicados
                    if similarity >= 0.5:
                        # Decidir qual remover baseado no contexto
                        desc_pai_norm = normalize_description(desc_pai)

                        # Caso 1: Pai é header curto - remover pai, manter filho
                        if len(desc_pai_norm) < 20:
                            items_to_remove.add(parent_key)
                        # Caso 2: Itens do aditivo (11.x) - manter filho
                        elif parent_code.startswith("11"):
                            items_to_remove.add(parent_key)
                        # Caso 3: Itens do contrato - remover filho
                        else:
                            items_to_remove.add(item_key)

        # Filtrar serviços removendo os duplicados
        return [
            s for s in self.servicos
            if (s.get("_planilha_id") or 0, s.get("item")) not in items_to_remove
        ]

    def dedupe_by_restart_prefix(self) -> List[Dict[str, Any]]:
        """
        Remove duplicatas com prefixos de restart (S1-, S2-, etc).

        Agrupa itens pelo código normalizado (sem prefixo) e mantém
        o item com melhor score baseado em:
        - Tamanho da descrição
        - Se descrição não é header de seção
        - Se descrição veio do texto
        - Fonte do item (text_section, text_line)

        Returns:
            Lista filtrada sem duplicatas de restart
        """
        if not self.servicos:
            return self.servicos

        groups: Dict[tuple, list] = {}
        for idx, servico in enumerate(self.servicos):
            item_val = servico.get("item")
            if not item_val:
                continue
            item_str = str(item_val).strip()
            if not item_str:
                continue
            if item_str.upper().startswith("AD-"):
                continue
            prefix, core = split_restart_prefix(item_str)
            code = normalize_item_code(core)
            if not code:
                continue
            planilha_id = servico.get("_planilha_id") or 0
            section = servico.get("_section") or ""
            unit = normalize_unit(servico.get("unidade") or "")
            qty = parse_quantity(servico.get("quantidade"))
            if not unit or qty in (None, 0):
                continue
            key = (section, planilha_id, code, unit, qty)
            groups.setdefault(key, []).append((idx, servico, prefix))

        to_drop: Set[int] = set()
        for key, entries in groups.items():
            if len(entries) < 2:
                continue
            prefixes = {entry[2] for entry in entries}
            if len(prefixes) < 2:
                continue

            def score(entry: tuple) -> float:
                _, servico, prefix = entry
                desc = (servico.get("descricao") or "").strip()
                score_val = 0.0
                if desc:
                    score_val += min(len(desc), 120)
                    if not is_section_header_desc(desc):
                        score_val += 10
                if servico.get("_desc_from_text"):
                    score_val += 6
                if servico.get("_source") in ("text_section", "text_line"):
                    score_val += 4
                if servico.get("_desc_recovered"):
                    score_val -= 8
                segment_num = 1
                if prefix:
                    try:
                        segment_num = int(prefix[1:])
                    except ValueError:
                        segment_num = 1
                score_val -= segment_num * 0.01
                return score_val

            best = max(entries, key=score)
            for entry in entries:
                if entry is best:
                    continue
                to_drop.add(entry[0])

        if not to_drop:
            return self.servicos
        return [s for idx, s in enumerate(self.servicos) if idx not in to_drop]

    def dedupe_within_planilha(self) -> List[Dict[str, Any]]:
        """
        Remove duplicatas de itens com mesmo código dentro da mesma planilha.

        Mantém o item com melhor descrição e dados mais completos,
        usando score baseado em:
        - Tamanho da descrição
        - Se descrição não é header de seção
        - Presença de unidade e quantidade
        - Fonte do item (document_ai, table, pdfplumber)
        - Presença de página definida

        Returns:
            Lista filtrada sem duplicatas por código/planilha
        """
        if not self.servicos:
            return self.servicos

        # Agrupa por (planilha_id, código normalizado)
        groups: Dict[tuple, list] = {}
        for idx, servico in enumerate(self.servicos):
            item_val = servico.get("item")
            if not item_val:
                continue
            item_str = str(item_val).strip()
            if not item_str:
                continue
            # Extrair código sem prefixo
            prefix, core = split_restart_prefix(item_str)
            code = normalize_item_code(core)
            if not code:
                continue
            planilha_id = servico.get("_planilha_id") or 0
            key = (planilha_id, code)
            groups.setdefault(key, []).append((idx, servico))

        to_drop: Set[int] = set()
        for key, entries in groups.items():
            if len(entries) < 2:
                continue

            # Função de score para escolher o melhor item
            def score(entry: tuple) -> float:
                _, servico = entry
                score_val = 0.0
                # Preferir descrição mais longa e completa
                desc = (servico.get("descricao") or "").strip()
                if desc:
                    score_val += min(len(desc), 150)
                    if not is_section_header_desc(desc):
                        score_val += 20
                # Preferir itens com unidade e quantidade
                if servico.get("unidade"):
                    score_val += 10
                if servico.get("quantidade"):
                    score_val += 10
                # Preferir itens do Document AI / tabela
                source = servico.get("_source", "")
                if source in ("document_ai", "table", "pdfplumber"):
                    score_val += 15
                elif source in ("text_section", "text_line"):
                    score_val += 5
                # Preferir itens com página definida
                if servico.get("_page"):
                    score_val += 5
                return score_val

            # Manter o melhor, remover os outros
            best = max(entries, key=score)
            for entry in entries:
                if entry is best:
                    continue
                to_drop.add(entry[0])

        if not to_drop:
            return self.servicos

        logger.info(f"[DEDUP-CODIGO] {len(to_drop)} itens duplicados removidos por código")
        return [s for idx, s in enumerate(self.servicos) if idx not in to_drop]

    def dedupe_by_desc_unit(self) -> List[Dict[str, Any]]:
        """
        Remove duplicatas por descrição e unidade (para itens sem código).

        Agrupa itens pela chave (descrição normalizada + unidade) e
        mantém o item com melhor score baseado em:
        - Tamanho da descrição
        - Presença de quantidade válida
        - Presença de unidade

        Returns:
            Lista filtrada sem duplicatas por descrição/unidade
        """
        if not self.servicos:
            return self.servicos

        deduped: Dict[str, Dict] = {}
        extras: List[Dict] = []

        def score(item: dict) -> int:
            score_val = len((item.get("descricao") or "").strip())
            if parse_quantity(item.get("quantidade")) not in (None, 0):
                score_val += 50
            if item.get("unidade"):
                score_val += 10
            return score_val

        for servico in self.servicos:
            key = self._servico_match_key(servico)
            if not key:
                extras.append(servico)
                continue
            existing = deduped.get(key)
            if not existing or score(servico) > score(existing):
                deduped[key] = servico

        return list(deduped.values()) + extras

    def cleanup_orphan_suffixes(self) -> List[Dict[str, Any]]:
        """
        Remove sufixos órfãos (-A, -B, etc.) quando não há item base
        na mesma planilha.
        """
        if not self.servicos:
            return self.servicos

        base_codes_by_planilha: Set[tuple] = set()
        for servico in self.servicos:
            item = servico.get("item", "")
            if item and not Patterns.ITEM_SUFFIX.search(item):
                planilha_id = int(servico.get("_planilha_id") or 0)
                base_codes_by_planilha.add((item, planilha_id))

        cleaned_count = 0
        for servico in self.servicos:
            item = servico.get("item", "")
            if not item:
                continue
            if not Patterns.ITEM_SUFFIX.search(item):
                continue

            base = item[:-2]  # Remove "-X"
            planilha_id = int(servico.get("_planilha_id") or 0)

            if (base, planilha_id) not in base_codes_by_planilha:
                servico["item"] = base
                cleaned_count += 1

        if cleaned_count > 0:
            logger.info(f"[SUFIXO] {cleaned_count} sufixos órfãos removidos")

        return self.servicos

    def _servico_match_key(self, servico: dict) -> str:
        """Gera chave de match baseada em descrição e unidade."""
        desc = normalize_desc_for_match(servico.get("descricao") or "")
        unit = normalize_unit(servico.get("unidade") or "")
        if not desc:
            return ""
        return f"{desc}|||{unit}"

    def _servico_desc_key(self, servico: dict) -> str:
        """Gera chave baseada apenas na descrição normalizada."""
        return normalize_desc_for_match(servico.get("descricao") or "")

    # _extract_item_code → extraction.item_utils.extract_item_code (standalone)

    def prefer_items_with_code(self) -> List[Dict[str, Any]]:
        """
        Prioriza itens com código sobre itens sem código.

        Separa itens em dois grupos (com código e sem código), depois
        filtra os sem código que sejam duplicatas dos com código
        baseado em similaridade de descrição e match de unidade/quantidade.

        Returns:
            Lista com itens priorizados por código
        """
        servicos = self.servicos
        if not servicos:
            return servicos if isinstance(servicos, list) else []

        if isinstance(servicos, dict):
            nested = servicos.get("servicos")
            if isinstance(nested, list):
                servicos = nested
            else:
                servicos = [servicos]

        if not isinstance(servicos, list):
            return []

        servicos = [servico for servico in servicos if isinstance(servico, dict)]
        if not servicos:
            return []

        coded = []
        no_code = []
        for servico in servicos:
            item = servico.get("item") or extract_item_code(servico.get("descricao") or "")
            if item:
                servico["item"] = item
                coded.append(servico)
            else:
                no_code.append(servico)

        if not coded:
            return ServiceDeduplicator(no_code).dedupe_by_desc_unit()

        coded_keys = {self._servico_match_key(servico) for servico in coded}
        coded_desc_keys = {self._servico_desc_key(servico) for servico in coded if self._servico_desc_key(servico)}
        coded_entries = [
            {
                "descricao": servico.get("descricao") or "",
                "unidade": normalize_unit(servico.get("unidade") or ""),
                "quantidade": parse_quantity(servico.get("quantidade"))
            }
            for servico in coded
        ]
        similarity_threshold = APC.DESC_SIM_THRESHOLD

        filtered_no_code = [
            servico for servico in no_code
            if self._servico_match_key(servico) not in coded_keys
            and self._servico_desc_key(servico) not in coded_desc_keys
        ]
        refined_no_code = []
        for servico in filtered_no_code:
            desc = servico.get("descricao") or ""
            unit = normalize_unit(servico.get("unidade") or "")
            qty = parse_quantity(servico.get("quantidade"))
            drop = False
            for coded_entry in coded_entries:
                coded_desc = str(coded_entry.get("descricao") or "")
                if description_similarity(desc, coded_desc) < similarity_threshold:
                    continue
                unit_match = bool(unit and coded_entry["unidade"] and unit == coded_entry["unidade"])
                qty_match = False
                coded_qty = coded_entry.get("quantidade")
                if qty is not None and coded_qty is not None and isinstance(qty, (int, float)) and isinstance(coded_qty, (int, float)) and qty != 0 and coded_qty != 0:
                    diff = abs(qty - coded_qty)
                    denom = max(abs(qty), abs(coded_qty))
                    if denom > 0:
                        qty_match = (diff / denom) <= 0.02 or diff <= 0.01
                if unit_match or qty_match:
                    drop = True
                    break
            if not drop:
                refined_no_code.append(servico)

        refined_no_code = ServiceDeduplicator(refined_no_code).dedupe_by_desc_unit()
        return coded + refined_no_code

    def dedupe_all(self) -> List[Dict[str, Any]]:
        """
        Executa todas as estratégias de deduplicação em ordem.

        Ordem de execução:
        1. remove_duplicate_pairs - Remove pares pai/filho
        2. dedupe_by_restart_prefix - Remove duplicatas com prefixos S1-, S2-
        3. dedupe_within_planilha - Remove duplicatas por código/planilha
        4. cleanup_orphan_suffixes - Remove sufixos órfãos (-A, -B, etc.)

        Returns:
            Lista com todas as deduplicações aplicadas
        """
        result = self.remove_duplicate_pairs()
        result = ServiceDeduplicator(result).dedupe_by_restart_prefix()
        result = ServiceDeduplicator(result).dedupe_within_planilha()
        result = ServiceDeduplicator(result).cleanup_orphan_suffixes()
        return result


# Instância singleton para uso direto
service_deduplicator = ServiceDeduplicator([])


def dedupe_servicos(servicos: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Função de conveniência para aplicar todas as deduplicações.

    Args:
        servicos: Lista de serviços

    Returns:
        Lista deduplicada
    """
    return ServiceDeduplicator(servicos).dedupe_all()


# Re-exportar funções standalone de extraction/deduplication_utils
# para manter compatibilidade com código existente
from services.extraction.deduplication_utils import (  # noqa: F401, E402
    build_keyword_index,
    remove_duplicate_services,
    deduplicate_by_description,
    merge_servicos_prefer_primary,
)
