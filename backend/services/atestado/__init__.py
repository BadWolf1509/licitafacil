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

from .service import (
    parse_date,
    sort_key_item,
    ordenar_servicos,
    atestados_to_dict,
)
from .persistence import salvar_atestado_processado
from .processor import AtestadoProcessor, atestado_processor
from .pipeline import AtestadoPipeline

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
