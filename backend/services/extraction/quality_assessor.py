"""
Avaliação de qualidade dos serviços extraídos.
"""
import os
from typing import Dict, List, Tuple
from collections import Counter

from .text_normalizer import normalize_description
from .table_processor import parse_quantity


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

    try:
        short_len = int(os.getenv("ATTESTADO_OCR_NOISE_SHORT_DESC_LEN", "12"))
    except ValueError:
        short_len = 12

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

    # Carregar thresholds de variáveis de ambiente
    try:
        min_unit_ratio = float(os.getenv("ATTESTADO_OCR_NOISE_MIN_UNIT_RATIO", "0.5"))
    except ValueError:
        min_unit_ratio = 0.5
    try:
        min_qty_ratio = float(os.getenv("ATTESTADO_OCR_NOISE_MIN_QTY_RATIO", "0.35"))
    except ValueError:
        min_qty_ratio = 0.35
    try:
        min_avg_len = float(os.getenv("ATTESTADO_OCR_NOISE_MIN_AVG_DESC_LEN", "14"))
    except ValueError:
        min_avg_len = 14.0
    try:
        max_short_ratio = float(os.getenv("ATTESTADO_OCR_NOISE_MAX_SHORT_DESC_RATIO", "0.45"))
    except ValueError:
        max_short_ratio = 0.45
    try:
        min_alpha_ratio = float(os.getenv("ATTESTADO_OCR_NOISE_MIN_ALPHA_RATIO", "0.45"))
    except ValueError:
        min_alpha_ratio = 0.45
    try:
        min_failures = int(os.getenv("ATTESTADO_OCR_NOISE_MIN_FAILS", "2"))
    except ValueError:
        min_failures = 2

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

    if with_unit_ratio < 0.8:
        score -= 0.2
    if with_qty_ratio < 0.8:
        score -= 0.2
    if with_item_ratio < 0.4:
        score -= 0.2
    if stats.get("duplicate_ratio", 0) > 0.35:
        score -= 0.1

    min_items = int(os.getenv("ATTESTADO_MIN_ITEMS_FOR_CONFIDENCE", "25"))
    if total < min_items:
        score -= 0.2

    return max(0.0, min(1.0, round(score, 2)))
