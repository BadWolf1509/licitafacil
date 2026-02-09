"""
Modulo de processamento de atestados de capacidade tecnica.

Este modulo fornece todas as funcionalidades necessarias para
processar, extrair e persistir dados de atestados.

Componentes:
- service: Funcoes de utilidade (parsing, ordenacao, conversao)
- persistence: Persistencia no banco de dados
- processor: Processador principal de atestados
- pipeline: Pipeline completo de processamento
"""

from .persistence import salvar_atestado_processado
from .pipeline import AtestadoPipeline
from .processor import AtestadoProcessor, atestado_processor
from .service import (
    atestados_to_dict,
    ordenar_servicos,
    parse_date,
    sort_key_item,
)

__all__ = [
    # service
    'parse_date',
    'sort_key_item',
    'ordenar_servicos',
    'atestados_to_dict',
    # persistence
    'salvar_atestado_processado',
    # processor
    'AtestadoProcessor',
    'atestado_processor',
    # pipeline
    'AtestadoPipeline',
]
