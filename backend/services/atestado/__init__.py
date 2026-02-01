"""
Módulo de processamento de atestados de capacidade técnica.

Este módulo fornece todas as funcionalidades necessárias para
processar, extrair e persistir dados de atestados.

Componentes:
- service: Funções de utilidade (parsing, ordenação, conversão)
- persistence: Persistência no banco de dados
- processor: Processador simplificado (wrapper)
- pipeline: Pipeline completo de processamento
- stages: Classes base para estágios do pipeline (Strategy pattern)
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
from .stages import (
    PipelineContext,
    PipelineStage,
    PipelineRunner,
    TextExtractionStage,
    TableExtractionStage,
    AIAnalysisStage,
    TextEnrichmentStage,
    PostProcessStage,
    FinalizationStage,
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
    # stages (Strategy pattern)
    'PipelineContext',
    'PipelineStage',
    'PipelineRunner',
    'TextExtractionStage',
    'TableExtractionStage',
    'AIAnalysisStage',
    'TextEnrichmentStage',
    'PostProcessStage',
    'FinalizationStage',
]
