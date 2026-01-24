"""
Processadores especializados para extração de documentos.

Contém processadores extraídos do DocumentProcessor para
melhor modularização e testabilidade.
"""

from .text_processor import TextProcessor, text_processor

__all__ = [
    "TextProcessor",
    "text_processor",
]
