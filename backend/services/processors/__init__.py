"""
Processadores especializados para extração de documentos.

Contém processadores extraídos do DocumentProcessor para
melhor modularização e testabilidade.
"""

from .text_processor import TextProcessor, text_processor
from .quantity_extractor import QuantityExtractor, quantity_extractor
from .deduplication import ServiceDeduplicator, dedupe_servicos
from .service_merger import (
    ServiceMerger,
    merge_planilhas,
    normalize_planilha_prefixes,
)
from .validation_filter import (
    ServiceFilter,
    filter_servicos,
    filter_headers,
    filter_no_quantity,
    filter_no_code,
)
from .item_code_refiner import ItemCodeRefiner, item_code_refiner
from .text_line_parser import TextLineParser, text_line_parser

__all__ = [
    "TextProcessor",
    "text_processor",
    "QuantityExtractor",
    "quantity_extractor",
    "ServiceDeduplicator",
    "dedupe_servicos",
    "ServiceMerger",
    "merge_planilhas",
    "normalize_planilha_prefixes",
    "ServiceFilter",
    "filter_servicos",
    "filter_headers",
    "filter_no_quantity",
    "filter_no_code",
    "ItemCodeRefiner",
    "item_code_refiner",
    "TextLineParser",
    "text_line_parser",
]
