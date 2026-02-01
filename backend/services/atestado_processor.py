"""
Processador de atestados de capacidade técnica.

NOTA: Este módulo foi movido para services.atestado.
Este arquivo existe para compatibilidade com imports existentes.
"""
from services.atestado.processor import AtestadoProcessor, atestado_processor

__all__ = [
    'AtestadoProcessor',
    'atestado_processor',
]
