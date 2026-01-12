"""
Utilitários para processamento de tabelas extraídas de documentos.

Este módulo contém funções para detecção de cabeçalhos, mapeamento de colunas,
parsing de itens e construção de descrições a partir de células de tabela.

Usa lru_cache para melhorar performance em chamadas repetidas.
"""

import re
from functools import lru_cache
from typing import Optional, Any

from .text_normalizer import normalize_header, normalize_unit, normalize_description, UNIT_TOKENS


@lru_cache(maxsize=2048)
def parse_item_tuple(value: str) -> Optional[tuple]:
    """
    Converte string de item para tupla numérica.

    Args:
        value: Valor do item (ex: "1.2.3")

    Returns:
        Tupla de inteiros ou None se inválido
    """
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None

    cleaned = re.sub(r"[^0-9. ]", "", text)
    cleaned = cleaned.strip().strip(".")
    if not cleaned:
        return None

    parts = [p for p in re.split(r"[ .]+", cleaned) if p]
    if not parts or len(parts) > 4:
        return None
    if any(len(p) > 3 for p in parts):
        return None

    try:
        return tuple(int(p) for p in parts)
    except ValueError:
        return None


def item_tuple_to_str(value: tuple) -> str:
    """
    Converte tupla de item para string.

    Args:
        value: Tupla do item (ex: (1, 2, 3))

    Returns:
        String formatada (ex: "1.2.3")
    """
    return ".".join(str(v) for v in value)


def parse_quantity(value: Any) -> Optional[float]:
    """
    Converte string para quantidade numérica.

    Args:
        value: Valor a converter

    Returns:
        Quantidade como float ou None se inválido
    """
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)

    text = str(value).strip()
    if not text:
        return None

    # Remove separadores de milhar e troca vírgula por ponto
    text = text.replace(".", "").replace(",", ".")
    text = re.sub(r"[^\d.-]", "", text)

    try:
        return float(text)
    except ValueError:
        return None


def score_item_column(cells: list, col_index: int, total_cols: int) -> dict:
    """
    Calcula score de uma coluna como coluna de itens.

    Args:
        cells: Lista de valores da coluna
        col_index: Índice da coluna
        total_cols: Total de colunas na tabela

    Returns:
        Dict com scores de pattern_ratio, seq_ratio, unique_ratio e score total
    """
    non_empty = 0
    matches = 0
    tuples = []
    lengths = []

    for cell in cells:
        text = str(cell or "").strip()
        if not text:
            continue
        non_empty += 1
        item_tuple = parse_item_tuple(text)
        if item_tuple:
            matches += 1
            tuples.append(item_tuple)
            lengths.append(len(text))

    if non_empty == 0:
        return {"score": 0.0, "pattern_ratio": 0.0, "seq_ratio": 0.0, "unique_ratio": 0.0}

    pattern_ratio = matches / non_empty
    unique_ratio = (len(set(tuples)) / matches) if matches else 0.0

    # Verificar sequência ordenada
    ordered = 0
    total_pairs = 0
    prev = None
    for item_tuple in tuples:
        if prev is not None:
            total_pairs += 1
            if item_tuple >= prev:
                ordered += 1
        prev = item_tuple

    seq_ratio = (ordered / total_pairs) if total_pairs else 0.0

    # Bônus por comprimento curto
    avg_len = (sum(lengths) / len(lengths)) if lengths else 99
    if avg_len <= 6:
        length_bonus = 1.0
    elif avg_len <= 10:
        length_bonus = 0.5
    else:
        length_bonus = 0.0

    # Bias para colunas à esquerda
    left_bias = 1.0 - (col_index / max(1, total_cols - 1))

    score = (
        0.45 * pattern_ratio +
        0.2 * seq_ratio +
        0.2 * unique_ratio +
        0.1 * left_bias +
        0.05 * length_bonus
    )

    return {
        "score": round(score, 3),
        "pattern_ratio": round(pattern_ratio, 3),
        "seq_ratio": round(seq_ratio, 3),
        "unique_ratio": round(unique_ratio, 3)
    }


def detect_header_row(rows: list) -> Optional[int]:
    """
    Detecta a linha de cabeçalho em uma tabela.

    Args:
        rows: Lista de linhas da tabela

    Returns:
        Índice da linha de cabeçalho ou None se não encontrado
    """
    if not rows:
        return None

    header_keywords = {
        "ITEM", "ITENS", "COD", "CODIGO", "DESCRICAO", "DISCRIMINACAO",
        "SERVICO", "SERVICOS", "UNID", "UNIDADE", "QTD", "QTE", "QUANT", "QUANTIDADE",
        "EXECUTADA", "EXECUTADO", "VALOR", "CUSTO", "PRECO"
    }

    best_score = 0
    best_index = None

    for idx, row in enumerate(rows[:5]):
        score = 0
        for cell in row:
            text = normalize_header(cell)
            if not text:
                continue
            for kw in header_keywords:
                if kw in text:
                    score += 1
                    break
        if score > best_score:
            best_score = score
            best_index = idx

    if best_score >= 2:
        return best_index
    return None


def guess_columns_by_header(header_row: list) -> dict:
    """
    Adivinha mapeamento de colunas baseado no cabeçalho.

    Args:
        header_row: Linha de cabeçalho

    Returns:
        Dict com mapeamento {nome_coluna: índice}
    """
    mapping: dict = {"item": None, "descricao": None, "unidade": None, "quantidade": None, "valor": None}

    for idx, cell in enumerate(header_row):
        text = normalize_header(cell)
        if not text:
            continue

        if mapping["item"] is None and ("ITEM" in text or "COD" in text):
            mapping["item"] = idx
        if mapping["descricao"] is None and ("DESCRICAO" in text or "DISCRIMINACAO" in text or "SERVICO" in text):
            mapping["descricao"] = idx
        if mapping["unidade"] is None and ("UNID" in text or "UNIDADE" in text):
            mapping["unidade"] = idx
        if mapping["quantidade"] is None and ("QUANT" in text or "QTD" in text or "QTE" in text or "EXECUTAD" in text):
            mapping["quantidade"] = idx
        if mapping["valor"] is None and ("VALOR" in text or "CUSTO" in text or "PRECO" in text):
            mapping["valor"] = idx

    return mapping


def compute_column_stats(rows: list, total_cols: int) -> list:
    """
    Computa estatísticas de cada coluna.

    Args:
        rows: Lista de linhas da tabela
        total_cols: Total de colunas

    Returns:
        Lista de dicts com estatísticas por coluna
    """
    col_stats = []

    for col in range(total_cols):
        non_empty = 0
        numeric = 0
        unit_hits = 0
        text_len = 0

        for row in rows:
            if col >= len(row):
                continue
            cell = str(row[col] or "").strip()
            if not cell:
                continue

            non_empty += 1
            if parse_quantity(cell) is not None:
                numeric += 1

            unit_norm = normalize_unit(cell)
            unit_norm = normalize_description(unit_norm).replace(" ", "")
            if unit_norm in UNIT_TOKENS:
                unit_hits += 1
            text_len += len(cell)

        if non_empty == 0:
            col_stats.append({"non_empty": 0, "numeric_ratio": 0.0, "unit_ratio": 0.0, "avg_len": 0.0})
            continue

        col_stats.append({
            "non_empty": non_empty,
            "numeric_ratio": numeric / non_empty,
            "unit_ratio": unit_hits / non_empty,
            "avg_len": text_len / non_empty
        })

    return col_stats


def guess_columns_by_content(rows: list, total_cols: int, mapping: dict, col_stats: Optional[list] = None) -> dict:
    """
    Adivinha mapeamento de colunas baseado no conteúdo.

    Args:
        rows: Lista de linhas da tabela
        total_cols: Total de colunas
        mapping: Mapeamento inicial (pode ter valores None)
        col_stats: Estatísticas pré-calculadas (opcional)

    Returns:
        Dict com mapeamento atualizado
    """
    if col_stats is None:
        col_stats = compute_column_stats(rows, total_cols)

    # Encontrar coluna de descrição
    if mapping.get("descricao") is None:
        best_col = None
        best_len = 0
        for col, stats in enumerate(col_stats):
            if col in (mapping.get("item"), mapping.get("unidade"), mapping.get("quantidade"), mapping.get("valor")):
                continue
            if stats["avg_len"] > best_len and stats["numeric_ratio"] < 0.7:
                best_len = stats["avg_len"]
                best_col = col
        mapping["descricao"] = best_col

    # Encontrar coluna de unidade
    if mapping.get("unidade") is None:
        best_col = None
        best_ratio = 0
        for col, stats in enumerate(col_stats):
            if col in (mapping.get("item"), mapping.get("descricao"), mapping.get("quantidade"), mapping.get("valor")):
                continue
            if stats["unit_ratio"] > best_ratio:
                best_ratio = stats["unit_ratio"]
                best_col = col
        mapping["unidade"] = best_col

    # Encontrar coluna de quantidade
    if mapping.get("quantidade") is None:
        best_col = None
        best_ratio = 0
        for col, stats in enumerate(col_stats):
            if col in (mapping.get("item"), mapping.get("descricao"), mapping.get("unidade"), mapping.get("valor")):
                continue
            if stats["numeric_ratio"] > best_ratio:
                best_ratio = stats["numeric_ratio"]
                best_col = col
        mapping["quantidade"] = best_col

    return mapping


def validate_column_mapping(mapping: dict, col_stats: list) -> dict:
    """
    Valida e corrige mapeamento de colunas.

    Args:
        mapping: Mapeamento atual
        col_stats: Estatísticas das colunas

    Returns:
        Mapeamento validado
    """
    if not col_stats:
        return mapping

    def ratio(idx: Optional[int], key: str) -> float:
        if idx is None or idx >= len(col_stats):
            return 0.0
        return float(col_stats[idx].get(key, 0.0))

    def avg_len(idx: Optional[int]) -> float:
        if idx is None or idx >= len(col_stats):
            return 0.0
        return float(col_stats[idx].get("avg_len", 0.0))

    min_unit_ratio = 0.2
    min_qty_ratio = 0.35
    min_desc_len = 10.0
    max_desc_numeric = 0.6

    item_col = mapping.get("item")
    desc_col = mapping.get("descricao")
    unit_col = mapping.get("unidade")
    qty_col = mapping.get("quantidade")

    # Remover conflitos
    if desc_col in {item_col, unit_col, qty_col}:
        mapping["descricao"] = None
    if unit_col in {item_col, desc_col, qty_col}:
        mapping["unidade"] = None
    if qty_col in {item_col, desc_col, unit_col}:
        mapping["quantidade"] = None

    # Validar ratios mínimos
    if unit_col is not None and ratio(unit_col, "unit_ratio") < min_unit_ratio:
        mapping["unidade"] = None
    if qty_col is not None and ratio(qty_col, "numeric_ratio") < min_qty_ratio:
        mapping["quantidade"] = None
    if desc_col is not None:
        if avg_len(desc_col) < min_desc_len or ratio(desc_col, "numeric_ratio") > max_desc_numeric:
            mapping["descricao"] = None

    # Validar ordem unidade < quantidade
    unit_col = mapping.get("unidade")
    qty_col = mapping.get("quantidade")
    if unit_col is not None and qty_col is not None and qty_col < unit_col:
        best_col = None
        best_ratio = 0.0
        for col in range(unit_col + 1, len(col_stats)):
            if col in {mapping.get("item"), mapping.get("descricao")}:
                continue
            col_ratio = ratio(col, "numeric_ratio")
            if col_ratio >= min_qty_ratio and col_ratio > best_ratio:
                best_ratio = col_ratio
                best_col = col
        if best_col is not None:
            mapping["quantidade"] = best_col

    return mapping


def build_description_from_cells(cells: list, exclude_cols: set) -> str:
    """
    Constrói descrição a partir de células não mapeadas.

    Args:
        cells: Lista de células da linha
        exclude_cols: Índices de colunas a excluir

    Returns:
        Descrição concatenada
    """
    parts = []
    for idx, cell in enumerate(cells):
        if idx in exclude_cols:
            continue
        text = str(cell or "").strip()
        if text and len(text) > 2:
            parts.append(text)
    return " ".join(parts)
