"""
Módulos de extração de dados de documentos.

Contém utilitários para normalização de texto, processamento de tabelas
e filtros de serviços extraídos.
"""

from .constants import (
    KNOWN_CATEGORIES,
    KNOWN_CATEGORIES_NORMALIZED,
    SECTION_HEADERS,
    NARRATIVE_TOKENS,
    VALID_UNITS,
    IGNORE_UNITS,
    FOOTER_TOKENS,
    INSTITUTIONAL_TOKENS,
    STOP_PREFIXES,
)

from .patterns import Patterns

from .text_normalizer import (
    normalize_description,
    normalize_unit,
    normalize_header,
    normalize_desc_for_match,
    normalize_accents,
    normalize_pt_morphology,
    extract_keywords,
    description_similarity,
    is_garbage_text,
    is_corrupted_text,
    UNIT_TOKENS,
)

from .table_processor import (
    parse_item_tuple,
    item_tuple_to_str,
    parse_quantity,
    is_valid_item_context,
    score_item_column,
    detect_header_row,
    guess_columns_by_header,
    compute_column_stats,
    guess_columns_by_content,
    validate_column_mapping,
    build_description_from_cells,
)

# Filtros de classificação
from .classification_filters import (
    filter_classification_paths,
    is_classification_path,
)

# Filtros de validação
from .validation_filters import (
    filter_servicos_by_item_length,
    filter_servicos_by_item_prefix,
    repair_missing_prefix,
    is_summary_row,
    filter_summary_rows,
    dominant_item_length,
    is_valid_unit,
)

# Funções de deduplicação (único local de implementação)
from .deduplication_utils import (
    build_keyword_index,
    remove_duplicate_services,
    deduplicate_by_description,
    merge_servicos_prefer_primary,
)

from .similarity import (
    quantities_similar,
    descriptions_similar,
    items_similar,
    servico_key,
)

from .quality_assessor import (
    compute_servicos_stats,
    compute_description_quality,
    is_ocr_noisy,
    compute_quality_score,
)

from .normalizers import (
    DescriptionNormalizer,
)

from .item_utils import (
    normalize_item_code,
    strip_restart_prefix,
    split_restart_prefix,
    item_code_in_text,
    max_restart_prefix_index,
    extract_item_code,
    split_item_description,
    item_qty_matches_code,
    clear_item_code_quantities,
)

__all__ = [
    # constants
    'KNOWN_CATEGORIES',
    'KNOWN_CATEGORIES_NORMALIZED',
    'SECTION_HEADERS',
    'NARRATIVE_TOKENS',
    'VALID_UNITS',
    'IGNORE_UNITS',
    'FOOTER_TOKENS',
    'INSTITUTIONAL_TOKENS',
    'STOP_PREFIXES',
    # patterns
    'Patterns',
    # text_normalizer
    'normalize_description',
    'normalize_unit',
    'normalize_header',
    'normalize_desc_for_match',
    'normalize_accents',
    'normalize_pt_morphology',
    'extract_keywords',
    'description_similarity',
    'is_garbage_text',
    'is_corrupted_text',
    'UNIT_TOKENS',
    # table_processor
    'parse_item_tuple',
    'item_tuple_to_str',
    'parse_quantity',
    'is_valid_item_context',
    'score_item_column',
    'detect_header_row',
    'guess_columns_by_header',
    'compute_column_stats',
    'guess_columns_by_content',
    'validate_column_mapping',
    'build_description_from_cells',
    # classification_filters
    'filter_classification_paths',
    'is_classification_path',
    # validation_filters
    'filter_servicos_by_item_length',
    'filter_servicos_by_item_prefix',
    'repair_missing_prefix',
    'is_summary_row',
    'filter_summary_rows',
    'dominant_item_length',
    'is_valid_unit',
    # deduplication_utils
    'build_keyword_index',
    'remove_duplicate_services',
    'deduplicate_by_description',
    'merge_servicos_prefer_primary',
    # similarity
    'quantities_similar',
    'descriptions_similar',
    'items_similar',
    'servico_key',
    # quality_assessor
    'compute_servicos_stats',
    'compute_description_quality',
    'is_ocr_noisy',
    'compute_quality_score',
    # item_utils
    'normalize_item_code',
    'strip_restart_prefix',
    'split_restart_prefix',
    'item_code_in_text',
    'max_restart_prefix_index',
    'extract_item_code',
    'split_item_description',
    'item_qty_matches_code',
    'clear_item_code_quantities',
    # normalizers
    'DescriptionNormalizer',
]
