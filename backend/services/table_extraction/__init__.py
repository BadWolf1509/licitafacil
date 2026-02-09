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

# Análise de documento
from .analyzers import analyze_document_type

# Estratégia de cascata
from .cascade import CascadeStrategy
from .extractors import (
    TableExtractor,
    extract_hidden_item_from_text,
    extract_trailing_unit,
    infer_missing_units,
)
from .filters import (
    is_header_row,
    is_page_metadata,
    is_row_noise,
    is_section_header_row,
    strip_section_header_prefix,
)
from .parsers import (
    find_unit_qty_pairs,
    parse_unit_qty_from_text,
)

# Métricas de qualidade (fonte única em utils/)
from .utils import (
    apply_restart_prefix,
    build_table_signature,
    calc_complete_ratio,
    calc_qty_ratio,
    calc_quality_metrics,
    collect_item_codes,
    first_last_item_tuple,
    merge_table_sources,
    should_restart_prefix,
    should_start_new_planilha,
)

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
