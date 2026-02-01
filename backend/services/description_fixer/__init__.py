"""
Corretor de descrições para garantir 100% de fidelidade ao PDF original.

Usa texto_extraido como fonte da verdade para corrigir descrições
que podem ter sido extraídas incorretamente ou de forma incompleta.
"""

from .core import fix_descriptions

__all__ = ['fix_descriptions']
