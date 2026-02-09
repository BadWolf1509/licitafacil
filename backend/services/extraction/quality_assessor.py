"""
Avaliação de qualidade dos serviços extraídos.
"""
from collections import Counter
from typing import Dict, List, Tuple

from config import (
    AtestadoProcessingConfig as APC,
)
from config import (
    OCRNoiseConfig as ONC,
)
from config import (
    QualityScoreConfig as QSC,
)

from .table_processor import parse_quantity
from .text_normalizer import normalize_description


def compute_servicos_stats(servicos: List[dict]) -> Dict:
    """
    Computa estatísticas sobre os serviços extraídos.

    Args:
        servicos: Lista de serviços

    Returns:
        Dicionário com estatísticas
    """
    total = len(servicos)
    if total == 0:
        return {
            "total": 0,
            "with_item": 0,
            "with_unit": 0,
            "with_qty": 0,
            "duplicate_ratio": 0.0
        }

    with_item = sum(1 for s in servicos if s.get("item"))
    with_unit = sum(1 for s in servicos if s.get("unidade"))
    with_qty = sum(
        1 for s in servicos
        if parse_quantity(s.get("quantidade")) not in (None, 0)
    )

    normalized_desc = [
        normalize_description(s.get("descricao", ""))
        for s in servicos
    ]
    counts = Counter(d for d in normalized_desc if d)
    duplicates = sum(v - 1 for v in counts.values() if v > 1)
    duplicate_ratio = duplicates / max(1, total)

    return {
        "total": total,
        "with_item": with_item,
        "with_unit": with_unit,
        "with_qty": with_qty,
        "duplicate_ratio": round(duplicate_ratio, 4)
    }


def compute_description_quality(servicos: List[dict]) -> Dict:
    """
    Computa métricas de qualidade das descrições.

    Args:
        servicos: Lista de serviços

    Returns:
        Dicionário com métricas de qualidade
    """
    total = len(servicos)
    if total == 0:
        return {"avg_len": 0.0, "short_ratio": 0.0, "alpha_ratio": 0.0}

    short_len = ONC.SHORT_DESC_LEN

    lengths: List[int] = []
    short_count = 0
    alpha_ratios: List[float] = []

    for servico in servicos:
        desc = (servico.get("descricao") or "").strip()
        if not desc:
            short_count += 1
            continue

        length = len(desc)
        lengths.append(length)

        if length < short_len:
            short_count += 1

        letters = sum(1 for ch in desc if ch.isalpha())
        alnum = sum(1 for ch in desc if ch.isalnum())
        if alnum:
            alpha_ratios.append(letters / alnum)

    avg_len = sum(lengths) / len(lengths) if lengths else 0.0
    short_ratio = short_count / max(1, total)
    alpha_ratio = sum(alpha_ratios) / len(alpha_ratios) if alpha_ratios else 0.0

    return {
        "avg_len": round(avg_len, 2),
        "short_ratio": round(short_ratio, 3),
        "alpha_ratio": round(alpha_ratio, 3)
    }


def is_ocr_noisy(servicos: List[dict]) -> Tuple[bool, Dict]:
    """
    Detecta se os resultados de OCR são muito ruidosos.

    Args:
        servicos: Lista de serviços extraídos

    Returns:
        Tupla (é_ruidoso, debug_info)
    """
    stats = compute_servicos_stats(servicos)
    quality = compute_description_quality(servicos)
    total = max(1, stats.get("total", 0))
    unit_ratio = stats.get("with_unit", 0) / total
    qty_ratio = stats.get("with_qty", 0) / total

    # Carregar thresholds de configuração centralizada
    min_unit_ratio = ONC.MIN_UNIT_RATIO
    min_qty_ratio = ONC.MIN_QTY_RATIO
    min_avg_len = ONC.MIN_AVG_DESC_LEN
    max_short_ratio = ONC.MAX_SHORT_DESC_RATIO
    min_alpha_ratio = ONC.MIN_ALPHA_RATIO
    min_failures = ONC.MIN_FAILURES

    failures = 0
    reasons: Dict[str, float] = {}

    if unit_ratio < min_unit_ratio:
        failures += 1
        reasons["unit_ratio"] = round(unit_ratio, 3)
    if qty_ratio < min_qty_ratio:
        failures += 1
        reasons["qty_ratio"] = round(qty_ratio, 3)
    if quality["avg_len"] < min_avg_len:
        failures += 1
        reasons["avg_desc_len"] = quality["avg_len"]
    if quality["short_ratio"] > max_short_ratio:
        failures += 1
        reasons["short_desc_ratio"] = quality["short_ratio"]
    if quality["alpha_ratio"] < min_alpha_ratio:
        failures += 1
        reasons["alpha_ratio"] = quality["alpha_ratio"]

    noisy = failures >= min_failures
    debug = {
        "noisy": noisy,
        "failures": failures,
        "min_failures": min_failures,
        "unit_ratio": round(unit_ratio, 3),
        "qty_ratio": round(qty_ratio, 3),
        "quality": quality,
        "thresholds": {
            "min_unit_ratio": min_unit_ratio,
            "min_qty_ratio": min_qty_ratio,
            "min_avg_desc_len": min_avg_len,
            "max_short_desc_ratio": max_short_ratio,
            "min_alpha_ratio": min_alpha_ratio
        },
        "reasons": reasons
    }
    return noisy, debug


def compute_quality_score(stats: Dict) -> float:
    """
    Computa score geral de qualidade dos serviços extraídos.

    Args:
        stats: Estatísticas dos serviços (de compute_servicos_stats)

    Returns:
        Score entre 0.0 e 1.0
    """
    total = stats.get("total", 0)
    if total == 0:
        return 0.0

    score = 1.0

    with_unit_ratio = stats.get("with_unit", 0) / total
    with_qty_ratio = stats.get("with_qty", 0) / total
    with_item_ratio = stats.get("with_item", 0) / total

    if with_unit_ratio < QSC.MIN_UNIT_RATIO:
        score -= QSC.PENALTY_UNIT
    if with_qty_ratio < QSC.MIN_QTY_RATIO:
        score -= QSC.PENALTY_QTY
    if with_item_ratio < QSC.MIN_ITEM_RATIO:
        score -= QSC.PENALTY_ITEM
    if stats.get("duplicate_ratio", 0) > QSC.MAX_DUPLICATE_RATIO:
        score -= QSC.PENALTY_DUPLICATE

    if total < APC.MIN_ITEMS_FOR_CONFIDENCE:
        score -= QSC.PENALTY_FEW_ITEMS

    return max(0.0, min(1.0, round(score, 2)))
