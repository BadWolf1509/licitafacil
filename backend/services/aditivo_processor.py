"""
Processamento de aditivos contratuais.

Este módulo é um wrapper de compatibilidade. A funcionalidade foi movida para
o pacote services.aditivo para melhor organização do código.

Uso recomendado:
    from services.aditivo import detect_aditivo_sections, prefix_aditivo_items
"""

from services.aditivo import (
    detect_aditivo_sections,
    prefix_aditivo_items,
)
from services.aditivo.validators import is_contaminated_line as _is_contaminated_line

__all__ = [
    "detect_aditivo_sections",
    "prefix_aditivo_items",
    "_is_contaminated_line",
]
