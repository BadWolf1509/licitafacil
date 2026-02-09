"""
Helpers para extracao baseada em OCR.

Este modulo serve como ponto de entrada e orquestrador para
extracao de servicos a partir de palavras OCR.

Os modulos individuais sao:
- ocr_table_builder: Construcao de tabelas a partir de palavras OCR
- ocr_column_detector: Inferencia da coluna de item
- ocr_quality: Verificacoes de qualidade e comparacao de resultados
"""

from typing import Any, Dict, List, Tuple

from config import AtestadoProcessingConfig as APC

from .ocr_column_detector import infer_item_column_from_words
from .ocr_quality import (
    assign_itemless_items,
    is_retry_result_better,
    item_sequence_suspicious,
)

# Re-exportar funcoes dos modulos individuais para compatibilidade
from .ocr_table_builder import build_table_from_ocr_words, median


def extract_from_ocr_words(
    service: Any,
    words: List[Dict[str, Any]],
    row_tol_factor: float = 0.6,
    col_tol_factor: float = 0.7,
    enable_refine: bool = True
) -> Tuple[List[Dict], float, Dict[str, Any], Dict[str, Any]]:
    """
    Extrai servicos a partir de palavras OCR.

    Esta e a funcao principal de orquestracao que:
    1. Constroi tabela a partir das palavras OCR
    2. Infere a coluna de item
    3. Extrai servicos usando modo normal e itemless
    4. Avalia qualidade e decide qual resultado usar
    5. Opcionalmente refina com tolerancia menor

    Args:
        service: Instancia do TableExtractionService
        words: Lista de palavras OCR com coordenadas
        row_tol_factor: Fator de tolerancia para agrupamento de linhas
        col_tol_factor: Fator de tolerancia para agrupamento de colunas
        enable_refine: Habilita refinamento com tolerancia menor

    Returns:
        Tupla (servicos, confidence, debug, metrics)
    """
    # Construir tabela a partir das palavras OCR
    table_rows, col_centers = build_table_from_ocr_words(
        words,
        row_tol_factor=row_tol_factor,
        col_tol_factor=col_tol_factor
    )
    preferred_item_col, item_col_debug = infer_item_column_from_words(words, col_centers)

    # Extracao normal (com item)
    servicos, confidence, debug = service.extract_servicos_from_table(
        table_rows,
        preferred_item_col=preferred_item_col
    )

    # Extracao itemless
    servicos_itemless, conf_itemless, debug_itemless = service.extract_servicos_from_table(
        table_rows,
        preferred_item_col=None,
        allow_itemless=True,
        ignore_item_numbers=True
    )

    # Verificar se sequencia de itens e suspeita
    item_suspicious, item_suspicious_info = item_sequence_suspicious(servicos)

    # Decidir entre modo normal e itemless
    if servicos_itemless:
        qty_ratio_itemless = service.calc_qty_ratio(servicos_itemless)
        qty_ratio_regular = service.calc_qty_ratio(servicos)
        prefer_itemless = (
            len(servicos_itemless) >= len(servicos) + 3
            and qty_ratio_itemless >= max(0.6, qty_ratio_regular)
        )
        if qty_ratio_itemless >= max(0.9, qty_ratio_regular + 0.4):
            prefer_itemless = True

        if item_suspicious:
            servicos = servicos_itemless
            confidence = conf_itemless
            debug = debug_itemless
            debug["itemless_forced"] = True
        elif prefer_itemless:
            servicos = servicos_itemless
            confidence = conf_itemless
            debug = debug_itemless
            debug["itemless_mode"] = True

    debug["item_suspicious"] = item_suspicious_info

    # Calcular metricas
    stats = debug.get("stats") or {}
    dominant = debug.get("dominant_item") or {}
    total_page_items = stats.get("total", 0)
    item_ratio = stats.get("with_item", 0) / max(1, total_page_items)
    unit_ratio = stats.get("with_unit", 0) / max(1, total_page_items)
    dominant_len = dominant.get("dominant_len", 0) or 0
    qty_ratio = service.calc_qty_ratio(servicos)

    metrics = {
        "row_count": len(table_rows),
        "word_count": len(words),
        "item_col": item_col_debug,
        "total_page_items": total_page_items,
        "item_ratio": item_ratio,
        "unit_ratio": unit_ratio,
        "dominant_len": dominant_len,
        "qty_ratio": qty_ratio
    }

    # Tentar refinamento com tolerancia menor se necessario
    if enable_refine and row_tol_factor >= 0.6:
        refine_min_words = max(40, int(APC.OCR_LAYOUT_RETRY_MIN_WORDS * 0.6))
        needs_refine = (
            metrics.get("total_page_items", 0) < APC.OCR_LAYOUT_RETRY_MIN_ITEMS
            and metrics.get("word_count", 0) >= refine_min_words
        )
        if needs_refine:
            refined_servicos, refined_conf, refined_debug, refined_metrics = extract_from_ocr_words(
                service,
                words,
                row_tol_factor=0.45,
                col_tol_factor=col_tol_factor,
                enable_refine=False
            )
            refine_info = {
                "attempted": True,
                "used": False,
                "base": {
                    "items": len(servicos),
                    "row_count": metrics.get("row_count", 0),
                    "qty_ratio": round(metrics.get("qty_ratio", 0.0), 3)
                },
                "refined": {
                    "items": len(refined_servicos),
                    "row_count": refined_metrics.get("row_count", 0),
                    "qty_ratio": round(refined_metrics.get("qty_ratio", 0.0), 3)
                }
            }

            # Verificar se refinamento e melhor
            use_refine = is_retry_result_better(
                refined_servicos, servicos, refined_metrics, metrics
            )

            if use_refine:
                refine_info["used"] = True
                refined_debug["row_refine"] = refine_info
                return refined_servicos, refined_conf, refined_debug, refined_metrics

            debug["row_refine"] = refine_info

    return servicos, confidence, debug, metrics


# Exportar todas as funcoes para facilitar imports
__all__ = [
    'median',
    'build_table_from_ocr_words',
    'infer_item_column_from_words',
    'item_sequence_suspicious',
    'assign_itemless_items',
    'is_retry_result_better',
    'extract_from_ocr_words',
]
