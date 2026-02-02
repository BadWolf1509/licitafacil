"""Extratores de servicos de diferentes fontes."""

from .base import ExtractionStrategy, ExtractionResult
from .table import TableExtractor
from .helpers import (
    extract_hidden_item_from_text,
    extract_trailing_unit,
    infer_missing_units,
)
from .column_detector import ColumnDetector, column_detector
from .confidence_calculator import ConfidenceCalculator, confidence_calculator
from .row_processor import RowProcessor, row_processor
from .ocr_helpers import (
    median,
    build_table_from_ocr_words,
    infer_item_column_from_words,
    item_sequence_suspicious,
    assign_itemless_items,
    is_retry_result_better,
    extract_from_ocr_words,
)
# Submodules podem ser importados diretamente:
# from .ocr_table_builder import build_table_from_ocr_words
# from .ocr_column_detector import infer_item_column_from_words
# from .ocr_quality import item_sequence_suspicious, is_retry_result_better
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
    # Column detection
    "ColumnDetector",
    "column_detector",
    # Confidence calculation
    "ConfidenceCalculator",
    "confidence_calculator",
    # Row processing
    "RowProcessor",
    "row_processor",
    # OCR helpers
    "median",
    "build_table_from_ocr_words",
    "infer_item_column_from_words",
    "item_sequence_suspicious",
    "assign_itemless_items",
    "is_retry_result_better",
    "extract_from_ocr_words",
]
