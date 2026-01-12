"""
Utilitários para filtro e deduplicação de serviços extraídos.

Este módulo contém funções para remover duplicatas, filtrar serviços
inválidos, e comparar serviços por similaridade.

Otimizado para performance usando índices invertidos em vez de O(n²).
"""

from typing import Optional, Set, Tuple, Dict, List
from collections import Counter, defaultdict

from .text_normalizer import (
    normalize_description,
    normalize_unit,
    extract_keywords,
)
from .table_processor import parse_item_tuple, item_tuple_to_str, parse_quantity
from config import DeduplicationConfig


def _build_keyword_index(servicos: list) -> Dict[str, List[int]]:
    """
    Constrói índice invertido de keywords -> índices de serviços.

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


def _has_valid_item_and_quantity(servico: dict) -> bool:
    """
    Verifica se o serviço tem código de item válido e quantidade.

    Itens com código e quantidade válidos devem ser preservados
    mesmo que a descrição esteja incompleta (podem ser recuperados depois).

    Args:
        servico: Dicionário do serviço

    Returns:
        True se tem item válido e quantidade
    """
    import re
    item = servico.get("item")
    quantidade = servico.get("quantidade")

    # Verificar se tem código de item válido (ex: "1.1", "6.3.4")
    if not item:
        return False
    if not re.match(r'^\d+(\.\d+)+$', str(item)):
        return False

    # Verificar se tem quantidade válida
    if quantidade is None:
        return False
    try:
        qty = float(quantidade)
        return qty > 0
    except (TypeError, ValueError):
        return False


def filter_classification_paths(servicos: list) -> list:
    """
    Remove serviços que são caminhos de classificação (não serviços reais).

    Isso inclui itens que contêm ">" (caminho de classificação) ou
    começam com padrões de classificação de CAT.

    Preserva itens com código válido e quantidade mesmo se descrição curta.

    Args:
        servicos: Lista de serviços

    Returns:
        Lista filtrada
    """
    if not servicos:
        return []

    filtered = []
    for servico in servicos:
        descricao = servico.get("descricao", "") or ""

        # Preservar itens com código e quantidade válidos (descrição pode ser recuperada)
        has_valid_item_qty = _has_valid_item_and_quantity(servico)

        if not descricao.strip():
            # Só continuar se tiver item e quantidade válidos
            if has_valid_item_qty:
                filtered.append(servico)
            continue

        # Ignorar itens que contêm ">" (caminho de classificação)
        if ">" in descricao:
            continue

        desc_upper = descricao.upper().strip()

        # Prefixos que SEMPRE são classificação (não serviços reais)
        invalid_prefixes = [
            "DIRETA OBRAS", "1 - DIRETA",
            "2 - DIRETA", "ATIVIDADE TÉCNICA", "CLASSIFICAÇÃO",
        ]

        is_invalid = False
        for prefix in invalid_prefixes:
            if desc_upper.startswith(prefix):
                is_invalid = True
                break

        # "EXECUÇÃO" é inválido APENAS se seguido de ">" (classificação)
        if desc_upper.startswith("EXECUÇÃO") and ">" in desc_upper:
            is_invalid = True

        if is_invalid:
            continue

        # Ignorar itens muito curtos, MAS preservar se tiver código e quantidade
        if len(descricao.strip()) < 5:
            if has_valid_item_qty:
                filtered.append(servico)
            continue

        filtered.append(servico)

    return filtered


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
    com_item_index = _build_keyword_index(com_item)
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


def filter_servicos_by_item_length(servicos: list) -> Tuple[list, dict]:
    """
    Filtra serviços por comprimento dominante de item.

    Args:
        servicos: Lista de serviços

    Returns:
        Tupla (lista filtrada, info de debug)
    """
    if not servicos:
        return servicos, {"applied": False, "ratio": 0.0}

    lengths = []
    for servico in servicos:
        item_val = servico.get("item")
        item_tuple = parse_item_tuple(str(item_val)) if item_val else None
        if item_tuple:
            lengths.append(len(item_tuple))

    if not lengths:
        return servicos, {"applied": False, "ratio": 0.0}

    counts = Counter(lengths)
    dominant_len, dominant_count = max(counts.items(), key=lambda kv: kv[1])
    ratio = dominant_count / max(1, len(lengths))

    min_ratio = DeduplicationConfig.ITEM_LENGTH_RATIO

    info = {
        "dominant_len": dominant_len,
        "ratio": round(ratio, 3),
        "applied": False,
        "filtered_out": 0,
        "kept_mismatch": 0
    }

    if ratio < min_ratio or dominant_len < 2:
        return servicos, info

    min_desc_len = DeduplicationConfig.ITEM_LENGTH_KEEP_MIN_DESC

    filtered = []
    for servico in servicos:
        item_val = servico.get("item")
        item_tuple = parse_item_tuple(str(item_val)) if item_val else None
        if not item_tuple or len(item_tuple) == dominant_len:
            filtered.append(servico)
            continue
        qty = parse_quantity(servico.get("quantidade"))
        unit = normalize_unit(servico.get("unidade") or "")
        desc = (servico.get("descricao") or "").strip()
        if qty not in (None, 0) and unit and len(desc) >= min_desc_len:
            filtered.append(servico)
            info["kept_mismatch"] += 1

    info["applied"] = True
    info["filtered_out"] = len(servicos) - len(filtered)
    return filtered, info


def filter_servicos_by_item_prefix(servicos: list) -> Tuple[list, dict]:
    """
    Filtra serviços por prefixo dominante de item.

    Args:
        servicos: Lista de serviços

    Returns:
        Tupla (lista filtrada, info de debug)
    """
    if not servicos:
        return servicos, {"applied": False, "ratio": 0.0}

    prefixes = []
    for servico in servicos:
        item_val = servico.get("item")
        item_tuple = parse_item_tuple(str(item_val)) if item_val else None
        if item_tuple:
            prefixes.append(item_tuple[0])

    if not prefixes:
        return servicos, {"applied": False, "ratio": 0.0}

    counts = Counter(prefixes)
    dominant_prefix, dominant_count = max(counts.items(), key=lambda kv: kv[1])
    ratio = dominant_count / max(1, len(prefixes))

    min_ratio = DeduplicationConfig.ITEM_PREFIX_RATIO

    info = {
        "dominant_prefix": dominant_prefix,
        "ratio": round(ratio, 3),
        "applied": False,
        "filtered_out": 0
    }

    if ratio < min_ratio:
        return servicos, info

    filtered = []
    for servico in servicos:
        item_val = servico.get("item")
        item_tuple = parse_item_tuple(str(item_val)) if item_val else None
        if not item_tuple or item_tuple[0] == dominant_prefix:
            filtered.append(servico)

    info["applied"] = True
    info["filtered_out"] = len(servicos) - len(filtered)
    return filtered, info


def dominant_item_length(servicos: list) -> Tuple[Optional[int], float]:
    """
    Calcula o comprimento dominante dos itens.

    Args:
        servicos: Lista de serviços

    Returns:
        Tupla (comprimento dominante, ratio)
    """
    lengths = []
    for servico in servicos:
        item_val = servico.get("item")
        item_tuple = parse_item_tuple(str(item_val)) if item_val else None
        if item_tuple:
            lengths.append(len(item_tuple))

    if not lengths:
        return None, 0.0

    counts = Counter(lengths)
    dominant_len, dominant_count = max(counts.items(), key=lambda kv: kv[1])
    ratio = dominant_count / max(1, len(lengths))
    return dominant_len, ratio


def repair_missing_prefix(servicos: list, dominant_prefix: Optional[int]) -> Tuple[list, dict]:
    """
    Repara itens com prefixo faltando.

    Args:
        servicos: Lista de serviços
        dominant_prefix: Prefixo dominante

    Returns:
        Tupla (lista reparada, info de debug)
    """
    if not servicos or dominant_prefix is None:
        return servicos, {"applied": False, "repaired": 0}

    existing = {s.get("item") for s in servicos if s.get("item")}
    repaired = 0

    for servico in servicos:
        item_val = servico.get("item")
        item_tuple = parse_item_tuple(str(item_val)) if item_val else None
        if not item_tuple or len(item_tuple) != 2:
            continue
        new_item = f"{dominant_prefix}.{item_tuple_to_str(item_tuple)}"
        if new_item in existing:
            continue
        servico["item"] = new_item
        existing.add(new_item)
        repaired += 1

    return servicos, {"applied": repaired > 0, "repaired": repaired}


def is_summary_row(desc: str) -> bool:
    """
    Verifica se uma descrição é linha de resumo/total.

    Args:
        desc: Descrição a verificar

    Returns:
        True se for linha de resumo
    """
    if not desc:
        return False
    normalized = normalize_description(desc)
    if not normalized:
        return False
    if normalized.startswith("TOTAL") or "TOTAL DA" in normalized or "TOTAL DO" in normalized:
        return True
    if normalized.startswith("SUBTOTAL"):
        return True
    if normalized.startswith("RESUMO"):
        return True
    if normalized.startswith("#"):
        return True
    if normalized in {"ITEM", "DISCRIMINACAO", "DISCRIMINACAO DOS SERVICOS EXECUTADOS"}:
        return True
    return False


def filter_summary_rows(servicos: list) -> list:
    """
    Remove linhas de resumo/total.

    Args:
        servicos: Lista de serviços

    Returns:
        Lista sem linhas de resumo
    """
    if not servicos:
        return servicos
    return [s for s in servicos if not is_summary_row(s.get("descricao", ""))]


def quantities_similar(qty_a: Optional[float], qty_b: Optional[float]) -> bool:
    """
    Verifica se duas quantidades são similares (20% tolerância).

    Args:
        qty_a: Primeira quantidade
        qty_b: Segunda quantidade

    Returns:
        True se similares
    """
    if qty_a is None or qty_b is None:
        return True
    if qty_a == 0 or qty_b == 0:
        return False
    diff = abs(qty_a - qty_b)
    if diff <= 1.0:
        return True
    base = max(abs(qty_a), abs(qty_b))
    if base > 0 and diff / base <= 0.2:
        return True
    return False


def descriptions_similar(desc_a: str, desc_b: str) -> bool:
    """
    Verifica se duas descrições são similares.

    Args:
        desc_a: Primeira descrição
        desc_b: Segunda descrição

    Returns:
        True se similares
    """
    if not desc_a or not desc_b:
        return False
    norm_a = normalize_description(desc_a)
    norm_b = normalize_description(desc_b)
    if norm_a == norm_b:
        return True
    if norm_a in norm_b or norm_b in norm_a:
        return True
    kw_a = extract_keywords(desc_a)
    kw_b = extract_keywords(desc_b)
    if not kw_a or not kw_b:
        return False
    common = len(kw_a & kw_b)
    min_len = min(len(kw_a), len(kw_b))
    return common >= max(1, min_len // 2)


def items_similar(item_a: dict, item_b: dict) -> bool:
    """
    Verifica se dois itens são similares.

    Args:
        item_a: Primeiro item
        item_b: Segundo item

    Returns:
        True se similares
    """
    desc_a = (item_a.get("descricao") or "").strip()
    desc_b = (item_b.get("descricao") or "").strip()
    if not descriptions_similar(desc_a, desc_b):
        return False
    unit_a = normalize_unit(item_a.get("unidade") or "")
    unit_b = normalize_unit(item_b.get("unidade") or "")
    if unit_a and unit_b and unit_a != unit_b:
        return False
    qty_a = parse_quantity(item_a.get("quantidade"))
    qty_b = parse_quantity(item_b.get("quantidade"))
    return quantities_similar(qty_a, qty_b)


def servico_key(servico: dict) -> tuple:
    """
    Cria chave única para um serviço baseado em item e descrição normalizada.

    Args:
        servico: Dicionário do serviço

    Returns:
        Tupla (item, descrição_normalizada)
    """
    item = servico.get("item") or ""
    desc = normalize_description(servico.get("descricao", ""))
    return (item, desc[:50])


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
    primary_index = _build_keyword_index(primary)

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
