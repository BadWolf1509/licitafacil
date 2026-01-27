"""
Utilitários de deduplicação de serviços.

Contém funções para construir índices invertidos e remover
duplicatas de listas de serviços.
"""

from typing import Dict, List, Set
from collections import defaultdict

from .text_normalizer import (
    normalize_description,
    extract_keywords,
)
from .similarity import (
    items_similar,
    servico_key,
)


def build_keyword_index(servicos: list) -> Dict[str, List[int]]:
    """
    Constrói índice invertido de keywords -> índices de serviços.

    Usado para busca rápida de candidatos similares sem O(n²).

    Args:
        servicos: Lista de serviços

    Returns:
        Dict mapeando keyword para lista de índices
    """
    index: Dict[str, List[int]] = defaultdict(list)
    for i, servico in enumerate(servicos):
        desc = str(servico.get("descricao", "") or "").strip()
        if desc:
            keywords = extract_keywords(desc)
            for kw in keywords:
                index[kw].append(i)
    return index


def remove_duplicate_services(servicos: list) -> list:
    """
    Remove serviços duplicados do OCR que não têm código de item.

    Mantém serviços com código de item e remove sem código que têm
    descrição similar a algum serviço com código.

    Otimizado com índice invertido para O(n) ao invés de O(n²).

    Args:
        servicos: Lista de serviços

    Returns:
        Lista sem duplicatas
    """
    if not servicos:
        return []

    # Separar serviços com e sem código de item
    com_item = []
    sem_item = []
    for servico in servicos:
        if servico.get("item"):
            com_item.append(servico)
        else:
            sem_item.append(servico)

    if not com_item:
        # Sem serviços com item, apenas deduplicar sem_item
        seen: Set[str] = set()
        result = []
        for servico in sem_item:
            desc = str(servico.get("descricao", "") or "").strip()
            desc_norm = normalize_description(desc)[:50] if desc else ""
            if desc_norm and desc_norm not in seen:
                seen.add(desc_norm)
                result.append(servico)
        return result

    # Construir índice invertido e conjunto de keywords distintas
    com_item_index = build_keyword_index(com_item)
    com_item_keywords_list = []
    com_item_distinctive: Set[str] = set()

    common_terms = {
        "execucao", "fornecimento", "instalacao", "servico", "servicos",
        "material", "materiais", "equipamento", "equipamentos", "construcao",
        "obra", "obras", "manutencao", "reforma", "reparo", "sistema",
        "estrutura", "revestimento", "pintura", "acabamento", "fundacao",
        "concreto", "armado", "simples", "duplo", "triplo", "completo",
        "conforme", "projeto", "norma", "padrao", "modelo", "tipo",
    }

    for servico in com_item:
        desc = str(servico.get("descricao", "") or "").strip()
        if desc:
            keywords = extract_keywords(desc)
            com_item_keywords_list.append(keywords)
            for kw in keywords:
                if len(kw) >= 6 and kw.lower() not in common_terms:
                    com_item_distinctive.add(kw.lower())

    def is_similar_to_any_com_item_optimized(desc: str, threshold: float = 0.5) -> bool:
        """Usa índice invertido para encontrar candidatos rapidamente."""
        keywords = extract_keywords(desc)
        if not keywords:
            return False

        # Encontrar índices de serviços com_item que compartilham keywords
        candidate_indices: Set[int] = set()
        for kw in keywords:
            if kw in com_item_index:
                candidate_indices.update(com_item_index[kw])

        # Verificar similaridade apenas com candidatos
        for idx in candidate_indices:
            if idx >= len(com_item_keywords_list):
                continue
            com_kw = com_item_keywords_list[idx]
            if not com_kw:
                continue
            intersection = len(keywords & com_kw)
            union = len(keywords | com_kw)
            similarity = intersection / union if union > 0 else 0
            if similarity >= threshold:
                return True
        return False

    def shares_distinctive_keyword(desc: str) -> bool:
        keywords = extract_keywords(desc)
        if not keywords:
            return False
        for kw in keywords:
            if len(kw) >= 6 and kw.lower() in com_item_distinctive:
                return True
        return False

    # Filtrar serviços SEM item
    sem_item_filtrado = []
    desc_sem_item_vistos: Set[str] = set()

    for servico in sem_item:
        desc = str(servico.get("descricao", "") or "").strip()
        desc_norm = normalize_description(desc)[:50] if desc else ""

        if not desc_norm:
            continue
        if desc_norm in desc_sem_item_vistos:
            continue
        if is_similar_to_any_com_item_optimized(desc):
            continue
        if shares_distinctive_keyword(desc):
            continue

        desc_sem_item_vistos.add(desc_norm)
        sem_item_filtrado.append(servico)

    return com_item + sem_item_filtrado


def deduplicate_by_description(servicos: list) -> list:
    """
    Remove duplicatas baseado em descrição normalizada.

    Args:
        servicos: Lista de serviços

    Returns:
        Lista sem duplicatas
    """
    if not servicos:
        return []

    seen: Set[str] = set()
    result = []

    for servico in servicos:
        desc = normalize_description(servico.get("descricao", ""))[:100]
        if desc in seen:
            continue
        seen.add(desc)
        result.append(servico)

    return result


def merge_servicos_prefer_primary(primary: list, secondary: list) -> list:
    """
    Mescla duas listas de serviços dando preferência à lista primária.

    Otimizado com índice invertido para O(n) ao invés de O(n²).

    Args:
        primary: Lista primária (preferida)
        secondary: Lista secundária

    Returns:
        Lista mesclada
    """
    if not secondary:
        return primary
    if not primary:
        return secondary

    # Chaves dos serviços primários
    primary_keys = {servico_key(s) for s in primary}

    # Construir índice invertido para busca rápida de similaridade
    primary_index = build_keyword_index(primary)

    # Adicionar serviços secundários que não estão no primário
    result = list(primary)
    for servico in secondary:
        key = servico_key(servico)
        if key not in primary_keys:
            # Usar índice para encontrar candidatos rapidamente
            desc = str(servico.get("descricao", "") or "").strip()
            keywords = extract_keywords(desc) if desc else set()

            # Encontrar candidatos que compartilham keywords
            candidate_indices: Set[int] = set()
            for kw in keywords:
                if kw in primary_index:
                    candidate_indices.update(primary_index[kw])

            # Verificar similaridade apenas com candidatos
            is_dup = False
            for idx in candidate_indices:
                if idx < len(primary) and items_similar(servico, primary[idx]):
                    is_dup = True
                    break

            if not is_dup:
                result.append(servico)
                primary_keys.add(key)

    return result
