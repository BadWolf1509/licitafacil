"""
Serviço para operações de atestados.

DEPRECATED: Este modulo foi movido para services.atestado.service.
Este arquivo existe para compatibilidade com imports existentes.
Sera removido em versao futura.

Use:
    from services.atestado.service import parse_date, sort_key_item, ordenar_servicos
    from services.atestado.persistence import salvar_atestado_processado
"""
import warnings

warnings.warn(
    "services.atestado_service esta deprecado. "
    "Use services.atestado.service e services.atestado.persistence em vez disso.",
    DeprecationWarning,
    stacklevel=2
)

from services.atestado.service import (
    parse_date,
    sort_key_item,
    ordenar_servicos,
    atestados_to_dict,
)
from services.atestado.persistence import salvar_atestado_processado

__all__ = [
    'parse_date',
    'sort_key_item',
    'ordenar_servicos',
    'atestados_to_dict',
    'salvar_atestado_processado',
]
