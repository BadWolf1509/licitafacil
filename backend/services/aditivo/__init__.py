"""
Pacote para processamento de aditivos contratuais.

Este pacote contém módulos para detectar e processar seções de aditivos
em documentos de atestado de capacidade técnica.
"""

from .detector import detect_aditivo_sections, get_aditivo_start_line
from .extractors import AditivoItemExtractor
from .transformer import AditivoTransformer, prefix_aditivo_items
from .validators import is_contaminated_line, is_good_description

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
