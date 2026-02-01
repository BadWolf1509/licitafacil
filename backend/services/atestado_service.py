"""
Serviço para operações de atestados.

NOTA: Este módulo foi movido para services.atestado.
Este arquivo existe para compatibilidade com imports existentes.
"""
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
