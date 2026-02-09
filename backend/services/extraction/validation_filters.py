"""
Filtros de validação para serviços extraídos.

Contém funções para filtrar serviços por:
- Comprimento de código de item
- Prefixo de código de item
- Linhas de resumo/total
- Unidades de medida
"""

import re
from collections import Counter
from typing import Optional, Tuple

from config import DeduplicationConfig

from .table_processor import item_tuple_to_str, parse_item_tuple, parse_quantity
from .text_normalizer import normalize_description, normalize_unit

# Unidades de medida válidas para construção civil/engenharia
VALID_UNITS = {
    # Métricas lineares
    'M', 'M2', 'M3', 'ML', 'KM',
    # Unidades
    'UN', 'UND', 'UNID', 'UNIDADE', 'PC', 'PÇ', 'PECA', 'PEÇA',
    # Peso/Volume
    'KG', 'T', 'TON', 'L', 'LT', 'LITRO',
    # Conjuntos
    'CJ', 'CONJ', 'CONJUNTO', 'PAR', 'PARES', 'JG', 'JOGO',
    # Globais
    'VB', 'VERBA', 'GL', 'GLOBAL', 'SV', 'SERV',
    # Hora/Dia
    'H', 'HR', 'HORA', 'DIA', 'D', 'MES', 'MÊS',
    # Outros comuns
    'SC', 'SACO', 'PT', 'PONTO', 'FX', 'FAIXA', 'CX', 'CAIXA',
}


def is_valid_unit(unit: str) -> bool:
    """
    Verifica se uma unidade de medida é válida.

    Uma unidade válida é uma das unidades conhecidas de construção civil
    ou segue padrões comuns (M?, M², M3, etc).

    Args:
        unit: Unidade a verificar

    Returns:
        True se a unidade é válida
    """
    if not unit:
        return False

    normalized = normalize_unit(unit)
    if not normalized:
        return False

    # Verificar se está na lista de unidades válidas
    if normalized in VALID_UNITS:
        return True

    # Verificar padrões comuns (M?, M², etc podem ter variações)
    if len(normalized) <= 3:
        # Unidades curtas são geralmente válidas
        return True

    # Unidades muito longas (>5 chars) são provavelmente palavras do texto
    if len(normalized) > 5:
        return False

    return False


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
        unit_raw = servico.get("unidade") or ""
        desc = (servico.get("descricao") or "").strip()
        # Só manter item com comprimento diferente se tiver unidade VÁLIDA
        # Isso evita manter itens onde "CENTRO" ou "JOAOPESSOA" são interpretados como unidade
        if qty not in (None, 0) and is_valid_unit(unit_raw) and len(desc) >= min_desc_len:
            filtered.append(servico)
            info["kept_mismatch"] += 1

    info["applied"] = True
    info["filtered_out"] = len(servicos) - len(filtered)
    return filtered, info


def filter_servicos_by_item_prefix(servicos: list) -> Tuple[list, dict]:
    """
    Filtra serviços por prefixo dominante de item.

    Aceita prefixos contíguos (seções consecutivas como 2, 3, 4...) para não
    perder itens quando uma tabela contém múltiplas seções da planilha.

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

    # Construir conjunto de prefixos contíguos (seções consecutivas)
    # Ex: se temos prefixos [2, 3, 5], aceitamos 2 e 3 (contíguos), mas 5 é isolado
    unique_prefixes = sorted(counts.keys())
    contiguous_prefixes = set()
    if unique_prefixes:
        # Encontrar grupos contíguos que incluem o prefixo dominante
        for i, prefix in enumerate(unique_prefixes):
            if prefix == dominant_prefix:
                # Adicionar o dominante e seus vizinhos contíguos
                contiguous_prefixes.add(prefix)
                # Expandir para trás
                j = i - 1
                while j >= 0 and unique_prefixes[j] == unique_prefixes[j + 1] - 1:
                    contiguous_prefixes.add(unique_prefixes[j])
                    j -= 1
                # Expandir para frente
                j = i + 1
                while j < len(unique_prefixes) and unique_prefixes[j] == unique_prefixes[j - 1] + 1:
                    contiguous_prefixes.add(unique_prefixes[j])
                    j += 1
                break

    # Calcular ratio dos prefixos contíguos
    contiguous_count = sum(counts.get(p, 0) for p in contiguous_prefixes)
    contiguous_ratio = contiguous_count / max(1, len(prefixes))

    info = {
        "dominant_prefix": dominant_prefix,
        "ratio": round(ratio, 3),
        "contiguous_prefixes": sorted(contiguous_prefixes),
        "contiguous_ratio": round(contiguous_ratio, 3),
        "applied": False,
        "filtered_out": 0
    }

    # Só filtrar se o ratio dominante for muito alto (>= min_ratio)
    # E se os prefixos contíguos não cobrirem bem os dados
    if ratio < min_ratio:
        return servicos, info

    # Se os prefixos contíguos cobrem >= 95% dos itens, não filtrar (manter todos)
    if contiguous_ratio >= 0.95:
        info["applied"] = False
        info["reason"] = "contiguous_prefixes_cover_most"
        return servicos, info

    # Filtrar, mas aceitar todos os prefixos contíguos (não só o dominante)
    filtered = []
    for servico in servicos:
        item_val = servico.get("item")
        item_tuple = parse_item_tuple(str(item_val)) if item_val else None
        if not item_tuple or item_tuple[0] in contiguous_prefixes:
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
        item_str = str(item_val or "").strip()
        if re.match(r'^(AD|[A-Z]{1,3}\d+)-', item_str, re.IGNORECASE):
            continue
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
    if normalized.startswith("TOTAL"):
        return True
    if re.match(r'^(VALOR\s+)?TOTAL\s+(DA|DO)\b', normalized):
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
