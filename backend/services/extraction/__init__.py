"""
Módulos de extração de dados de documentos.

Contém utilitários para normalização de texto, processamento de tabelas
e filtros de serviços extraídos.
"""

from .text_normalizer import (
    normalize_description,
    normalize_unit,
    normalize_header,
    normalize_desc_for_match,
    extract_keywords,
    description_similarity,
    UNIT_TOKENS,
)

from .table_processor import (
    parse_item_tuple,
    item_tuple_to_str,
    parse_quantity,
    score_item_column,
    detect_header_row,
    guess_columns_by_header,
    compute_column_stats,
    guess_columns_by_content,
    validate_column_mapping,
    build_description_from_cells,
)

from .service_filter import (
    filter_classification_paths,
    remove_duplicate_services,
    filter_servicos_by_item_length,
    filter_servicos_by_item_prefix,
    repair_missing_prefix,
    is_summary_row,
    filter_summary_rows,
    deduplicate_by_description,
    quantities_similar,
    descriptions_similar,
    items_similar,
    servico_key,
    merge_servicos_prefer_primary,
    dominant_item_length,
)

__all__ = [
    # text_normalizer
    'normalize_description',
    'normalize_unit',
    'normalize_header',
    'normalize_desc_for_match',
    'extract_keywords',
    'description_similarity',
    'UNIT_TOKENS',
    # table_processor
    'parse_item_tuple',
    'item_tuple_to_str',
    'parse_quantity',
    'score_item_column',
    'detect_header_row',
    'guess_columns_by_header',
    'compute_column_stats',
    'guess_columns_by_content',
    'validate_column_mapping',
    'build_description_from_cells',
    # service_filter
    'filter_classification_paths',
    'remove_duplicate_services',
    'filter_servicos_by_item_length',
    'filter_servicos_by_item_prefix',
    'repair_missing_prefix',
    'is_summary_row',
    'filter_summary_rows',
    'deduplicate_by_description',
    'quantities_similar',
    'descriptions_similar',
    'items_similar',
    'servico_key',
    'merge_servicos_prefer_primary',
    'dominant_item_length',
]
