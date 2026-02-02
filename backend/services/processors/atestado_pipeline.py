"""
Pipeline de processamento de atestados.

DEPRECATED: Este modulo foi movido para services.atestado.pipeline.
Este arquivo existe para compatibilidade com imports existentes.
Sera removido em versao futura.

Use:
    from services.atestado.pipeline import AtestadoPipeline
"""
import warnings

warnings.warn(
    "services.processors.atestado_pipeline esta deprecado. "
    "Use services.atestado.pipeline em vez disso.",
    DeprecationWarning,
    stacklevel=2
)

from services.atestado.pipeline import AtestadoPipeline

__all__ = ['AtestadoPipeline']
