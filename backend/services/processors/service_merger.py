"""
Mesclagem e normalização de planilhas fragmentadas.

Extrai e centraliza lógica de mesclagem de planilhas do DocumentProcessor,
oferecendo estratégias para unificar planilhas fragmentadas e normalizar prefixos.
"""

from typing import Any, Dict, List, Set
import logging

from config import AtestadoProcessingConfig as APC
from services.processing_helpers import (
    normalize_item_code,
    split_restart_prefix,
)

logger = logging.getLogger(__name__)


class ServiceMerger:
    """
    Mescla planilhas fragmentadas e normaliza prefixos de reinício.

    Estratégias disponíveis:
    - merge_fragmented: Mescla planilhas fragmentadas em uma única
    - normalize_prefixes: Normaliza prefixos S1-, S2- baseado em overlap
    """

    def __init__(self, servicos: List[Dict[str, Any]]):
        """
        Inicializa o merger com a lista de serviços.

        Args:
            servicos: Lista de dicionários de serviços
        """
        self.servicos = servicos if servicos else []

    def _collect_planilha_data(self) -> tuple:
        """
        Coleta dados agrupados por planilha.

        Returns:
            Tupla (servicos_by_planilha, codes_by_planilha, pages_by_planilha)
        """
        servicos_by_planilha: Dict[int, List[Dict]] = {}
        codes_by_planilha: Dict[int, Set[str]] = {}
        pages_by_planilha: Dict[int, Set[int]] = {}

        for servico in self.servicos:
            planilha_id = int(servico.get("_planilha_id") or 0)
            servicos_by_planilha.setdefault(planilha_id, []).append(servico)

            # Coleta códigos de item
            item_val = servico.get("item")
            if item_val:
                prefix, core = split_restart_prefix(item_val)
                code = normalize_item_code(core or item_val)
                if code:
                    codes_by_planilha.setdefault(planilha_id, set()).add(code)

            # Coleta páginas
            page = servico.get("_page")
            if page:
                pages_by_planilha.setdefault(planilha_id, set()).add(page)

        return servicos_by_planilha, codes_by_planilha, pages_by_planilha

    def merge_fragmented(self) -> List[Dict[str, Any]]:
        """
        Mescla planilhas fragmentadas que deveriam ser uma só.

        Critério de mesclagem:
        - Planilhas com baixo overlap (< MIN_OVERLAP) são candidatas a mesclagem
        - Planilhas sem _page são mescladas com a planilha principal (maior)
        - Resultado: planilhas corretamente agrupadas

        Returns:
            Lista de serviços com planilhas mescladas
        """
        if not self.servicos:
            return self.servicos

        servicos_by_planilha, codes_by_planilha, pages_by_planilha = self._collect_planilha_data()

        planilha_ids = sorted(servicos_by_planilha.keys())
        if len(planilha_ids) <= 1:
            return self.servicos

        # Identifica planilha principal (maior quantidade de itens)
        main_planilha = max(planilha_ids, key=lambda pid: len(servicos_by_planilha.get(pid, [])))
        main_codes = codes_by_planilha.get(main_planilha, set())
        main_pages = pages_by_planilha.get(main_planilha, set())

        # Identifica planilhas a mesclar com a principal
        # Critérios: sem páginas OU baixo overlap com principal
        planilhas_to_merge: List[int] = []
        for pid in planilha_ids:
            if pid == main_planilha:
                continue

            pid_pages = pages_by_planilha.get(pid, set())
            pid_codes = codes_by_planilha.get(pid, set())

            # Calcula overlap com a principal
            overlap = pid_codes & main_codes
            overlap_count = len(overlap)

            # Regra fundamental: NUNCA mesclar planilhas com alto overlap
            # Alto overlap significa que são planilhas DIFERENTES com itens repetidos
            # Só mesclar se overlap < MIN_OVERLAP (indica continuação, não nova planilha)
            if overlap_count >= APC.RESTART_MIN_OVERLAP:
                # Alto overlap - são planilhas diferentes, não mesclar
                continue

            # Mesclar apenas se overlap é baixo E uma das condições:
            # 1. Ambas sem páginas
            # 2. Uma tem páginas e são adjacentes/contidas no range da principal
            # IMPORTANTE: Não mesclar se há evidência de reinício de numeração
            should_merge = False

            # Verificar se há reinício de numeração entre as planilhas
            # (menor código de pid é menor que maior código de main)
            has_restart = False
            if pid_codes and main_codes:
                try:
                    pid_tuples = [tuple(int(p) for p in c.split('.')) for c in pid_codes if c]
                    main_tuples = [tuple(int(p) for p in c.split('.')) for c in main_codes if c]
                    if pid_tuples and main_tuples:
                        pid_min = min(pid_tuples)
                        main_max = max(main_tuples)
                        # Reinício se seção (primeiro componente) diminuiu
                        if pid_min[0] < main_max[0]:
                            has_restart = True
                        # Ou se mesma seção com grande regressão
                        elif (len(pid_min) > 1 and len(main_max) > 1 and
                              pid_min[0] == main_max[0] and
                              main_max[1] - pid_min[1] >= 5 and pid_min[1] <= 3):
                            has_restart = True
                except (ValueError, TypeError):
                    pass

            # Não mesclar se há reinício de numeração
            if has_restart:
                continue

            if not pid_pages and not main_pages:
                # Ambas sem página e baixo overlap - mesclar
                should_merge = True
            elif not pid_pages or not main_pages:
                # Uma sem página e baixo overlap - provavelmente fragmentada
                should_merge = True
            else:
                # Ambas têm páginas - verificar se são consecutivas ou sobrepostas
                min_main = min(main_pages)
                max_main = max(main_pages)
                min_pid = min(pid_pages)
                max_pid = max(pid_pages)

                # Páginas dentro ou adjacentes ao range da principal
                pages_adjacent = (min_pid >= min_main - 1 and max_pid <= max_main + 1)
                if pages_adjacent:
                    should_merge = True

            if should_merge:
                planilhas_to_merge.append(pid)

        # Mescla planilhas
        if planilhas_to_merge:
            for servico in self.servicos:
                pid = int(servico.get("_planilha_id") or 0)
                if pid in planilhas_to_merge:
                    servico["_planilha_id"] = main_planilha
                    servico["_merged_from"] = pid

        return self.servicos

    def normalize_prefixes(self) -> List[Dict[str, Any]]:
        """
        Normaliza prefixos de reinício baseado em overlap ACUMULATIVO de códigos.

        Critério:
        - Processa planilhas em ordem de ID
        - Planilhas sem overlap com códigos já vistos NÃO recebem prefixo
        - Planilhas com overlap (>= MIN_OVERLAP) recebem prefixo Sx-
        - O conjunto de códigos é ACUMULATIVO (inclui todas as planilhas sem prefixo)

        Returns:
            Lista de serviços com prefixos normalizados
        """
        if not self.servicos:
            return self.servicos

        # Passo 1: Mesclar planilhas fragmentadas antes de processar
        self.servicos = self.merge_fragmented()

        # Agrupa serviços por planilha e coleta códigos
        servicos_by_planilha: Dict[int, List[Dict]] = {}
        codes_by_planilha: Dict[int, Set[str]] = {}
        for servico in self.servicos:
            planilha_id = int(servico.get("_planilha_id") or 0)
            servicos_by_planilha.setdefault(planilha_id, []).append(servico)
            item_val = servico.get("item")
            if item_val:
                prefix, core = split_restart_prefix(item_val)
                code = normalize_item_code(core or item_val)
                if code:
                    codes_by_planilha.setdefault(planilha_id, set()).add(code)

        planilha_ids = sorted(servicos_by_planilha.keys())
        if len(planilha_ids) <= 1:
            # Só uma planilha, remove todos os prefixos
            for servico in self.servicos:
                item_val = servico.get("item")
                if not item_val:
                    continue
                prefix, core = split_restart_prefix(item_val)
                if prefix:
                    servico["item"] = core
                    servico.pop("_item_prefix", None)
            return self.servicos

        # Processa planilhas em ORDEM DE ID (ordem de aparição no documento)
        # Mantém conjunto ACUMULATIVO de códigos das planilhas sem prefixo
        accumulated_codes: Set[str] = set()
        planilhas_with_prefix: Dict[int, int] = {}  # planilha_id -> prefix_idx
        prefix_counter = 0

        for planilha_id in planilha_ids:
            planilha_codes = codes_by_planilha.get(planilha_id, set())

            if not accumulated_codes:
                # Primeira planilha nunca recebe prefixo
                accumulated_codes.update(planilha_codes)
                continue

            # Verificar overlap com códigos acumulados
            overlap = planilha_codes & accumulated_codes
            if overlap and len(overlap) >= APC.RESTART_MIN_OVERLAP:
                # Tem overlap significativo - precisa de prefixo
                prefix_counter += 1
                planilhas_with_prefix[planilha_id] = prefix_counter
            else:
                # Sem overlap - é continuação da planilha anterior
                # Adiciona seus códigos ao acumulado
                accumulated_codes.update(planilha_codes)

        # Aplica prefixos apenas onde necessário
        for servico in self.servicos:
            item_val = servico.get("item")
            if not item_val:
                continue
            prefix, core = split_restart_prefix(item_val)
            item_str = str(core or item_val).strip()
            if item_str.upper().startswith("AD-"):
                item_str = item_str[3:].strip()
            if not item_str:
                continue
            planilha_id = int(servico.get("_planilha_id") or 0)
            prefix_idx = planilhas_with_prefix.get(planilha_id)
            if prefix_idx:
                servico["item"] = f"S{prefix_idx}-{item_str}"
                servico["_item_prefix"] = f"S{prefix_idx}"
            else:
                servico["item"] = item_str
                if "_item_prefix" in servico:
                    servico.pop("_item_prefix", None)

        return self.servicos

    def merge_and_normalize(self) -> List[Dict[str, Any]]:
        """
        Executa mesclagem e normalização de prefixos em sequência.

        Returns:
            Lista com planilhas mescladas e prefixos normalizados
        """
        return self.normalize_prefixes()


def merge_planilhas(servicos: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Função de conveniência para mesclar planilhas fragmentadas.

    Args:
        servicos: Lista de serviços

    Returns:
        Lista com planilhas mescladas
    """
    return ServiceMerger(servicos).merge_fragmented()


def normalize_planilha_prefixes(servicos: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Função de conveniência para normalizar prefixos de planilhas.

    Args:
        servicos: Lista de serviços

    Returns:
        Lista com prefixos normalizados
    """
    return ServiceMerger(servicos).normalize_prefixes()
