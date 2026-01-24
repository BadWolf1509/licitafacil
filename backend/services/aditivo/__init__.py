"""
Pacote para processamento de aditivos contratuais.

Este pacote contém módulos para detectar e processar seções de aditivos
em documentos de atestado de capacidade técnica.
"""

from .detector import detect_aditivo_sections, get_aditivo_start_line
from .transformer import prefix_aditivo_items, AditivoTransformer
from .validators import is_contaminated_line, is_good_description
from .extractors import AditivoItemExtractor

__all__ = [
    # Funções principais
    "detect_aditivo_sections",
    "prefix_aditivo_items",
    # Classes
    "AditivoTransformer",
    "AditivoItemExtractor",
    # Utilitários
    "get_aditivo_start_line",
    "is_contaminated_line",
    "is_good_description",
]
