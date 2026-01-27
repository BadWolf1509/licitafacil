"""
Pacote para extração de tabelas de documentos.

Este pacote contém módulos para extrair serviços de tabelas em PDFs,
usando múltiplas estratégias (pdfplumber, Document AI, OCR).

Estrutura:
- parsers/: Funções de parsing de texto
- filters/: Filtros para detecção de ruído e headers
- extractors/: Extratores de serviços
- analyzers/: Análise de qualidade e tipo de documento
- utils/: Utilitários (planilha, merge)
"""

from .parsers import (
    parse_unit_qty_from_text,
    find_unit_qty_pairs,
)

from .filters import (
    is_row_noise,
    is_section_header_row,
    is_page_metadata,
    is_header_row,
    strip_section_header_prefix,
)

from .extractors import (
    TableExtractor,
    extract_hidden_item_from_text,
    extract_trailing_unit,
    infer_missing_units,
)

from .utils import (
    build_table_signature,
    should_start_new_planilha,
    collect_item_codes,
    should_restart_prefix,
    apply_restart_prefix,
    first_last_item_tuple,
    merge_table_sources,
)

# Métricas de qualidade (fonte única em utils/)
from .utils import (
    calc_qty_ratio,
    calc_complete_ratio,
    calc_quality_metrics,
)

# Análise de documento
from .analyzers import analyze_document_type

# Estratégia de cascata
from .cascade import CascadeStrategy

__all__ = [
    # Parsers
    "parse_unit_qty_from_text",
    "find_unit_qty_pairs",
    # Filters
    "is_row_noise",
    "is_section_header_row",
    "is_page_metadata",
    "is_header_row",
    "strip_section_header_prefix",
    # Extractors
    "TableExtractor",
    "extract_hidden_item_from_text",
    "extract_trailing_unit",
    "infer_missing_units",
    # Utils
    "build_table_signature",
    "should_start_new_planilha",
    "collect_item_codes",
    "should_restart_prefix",
    "apply_restart_prefix",
    "first_last_item_tuple",
    "merge_table_sources",
    "calc_qty_ratio",
    "calc_complete_ratio",
    "calc_quality_metrics",
    "analyze_document_type",
    # Cascade strategy
    "CascadeStrategy",
]
