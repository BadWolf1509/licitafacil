"""
Processador de atestados de capacidade técnica.

DEPRECATED: Este modulo foi movido para services.atestado.processor.
Este arquivo existe para compatibilidade com imports existentes.
Sera removido em versao futura.

Use:
    from services.atestado.processor import AtestadoProcessor, atestado_processor
"""
import warnings

warnings.warn(
    "services.atestado_processor esta deprecado. "
    "Use services.atestado.processor em vez disso.",
    DeprecationWarning,
    stacklevel=2
)

from services.atestado.processor import AtestadoProcessor, atestado_processor

__all__ = [
    'AtestadoProcessor',
    'atestado_processor',
]
