"""Extratores de servicos de diferentes fontes."""

from .base import ExtractionStrategy, ExtractionResult
from .table import TableExtractor
from .helpers import (
    extract_hidden_item_from_text,
    extract_trailing_unit,
    infer_missing_units,
)
from .ocr_helpers import (
    build_table_from_ocr_words,
    infer_item_column_from_words,
    item_sequence_suspicious,
    assign_itemless_items,
    is_retry_result_better,
    extract_from_ocr_words,
)
from .pdfplumber import extract_servicos_from_tables
from .document_ai import extract_servicos_from_document_ai
from .grid_ocr import extract_servicos_from_grid_ocr
from .ocr_layout import extract_servicos_from_ocr_layout

__all__ = [
    # Base
    "ExtractionStrategy",
    "ExtractionResult",
    # Extractors
    "TableExtractor",
    # Extractor functions
    "extract_servicos_from_tables",
    "extract_servicos_from_document_ai",
    "extract_servicos_from_grid_ocr",
    "extract_servicos_from_ocr_layout",
    # Helpers
    "extract_hidden_item_from_text",
    "extract_trailing_unit",
    "infer_missing_units",
    # OCR helpers
    "build_table_from_ocr_words",
    "infer_item_column_from_words",
    "item_sequence_suspicious",
    "assign_itemless_items",
    "is_retry_result_better",
    "extract_from_ocr_words",
]
