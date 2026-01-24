"""
Modulo de servicos de IA unificados.

Fornece uma camada de abstracao sobre os provedores de IA,
centralizando logica de extracao e prompts.
"""

from .extraction_service import AIExtractionService, extraction_service

__all__ = [
    "AIExtractionService",
    "extraction_service",
]
