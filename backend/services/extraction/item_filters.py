"""
Utilitários para filtro de serviços extraídos.

NOTA: Este módulo foi reorganizado. As funções foram movidas para:
- classification_filters.py: filter_classification_paths, is_classification_path
- validation_filters.py: filter_servicos_by_item_length, filter_servicos_by_item_prefix, etc.

Este arquivo re-exporta as funções para manter compatibilidade retroativa.
"""

# Re-exportar de classification_filters
from .classification_filters import (
    _has_valid_item_and_quantity,
    _is_technical_comparison,
    filter_classification_paths,
    is_classification_path,
)

# Re-exportar de validation_filters
from .validation_filters import (
    VALID_UNITS,
    dominant_item_length,
    filter_servicos_by_item_length,
    filter_servicos_by_item_prefix,
    filter_summary_rows,
    is_summary_row,
    is_valid_unit,
    repair_missing_prefix,
)

__all__ = [
    # classification_filters
    'filter_classification_paths',
    'is_classification_path',
    '_is_technical_comparison',
    '_has_valid_item_and_quantity',
    # validation_filters
    'VALID_UNITS',
    'is_valid_unit',
    'filter_servicos_by_item_length',
    'filter_servicos_by_item_prefix',
    'dominant_item_length',
    'repair_missing_prefix',
    'is_summary_row',
    'filter_summary_rows',
]
