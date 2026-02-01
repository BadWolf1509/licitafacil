"""
Classes base para estágios do pipeline de processamento.

Implementa o padrão Strategy para permitir extensibilidade
e customização do processamento de atestados.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from logging_config import get_logger

logger = get_logger('services.atestado.stages')

# Type aliases
ProgressCallback = Optional[Callable[[int, int, str, str], None]]
CancelCheck = Optional[Callable[[], bool]]


@dataclass
class PipelineContext:
    """
    Contexto compartilhado entre estágios do pipeline.

    Contém todos os dados necessários para processamento,
    permitindo que estágios se comuniquem através deste objeto.
    """
    # Entrada
    file_path: str
    file_ext: str
    use_vision: bool = True
    progress_callback: ProgressCallback = None
    cancel_check: CancelCheck = None

    # Referência ao processador (para métodos auxiliares)
    processor: Any = None

    # Estado do pipeline
    texto: Optional[str] = None
    doc_analysis: Optional[Dict] = None
    images: Optional[List[bytes]] = None

    # Dados de tabela
    servicos_table: List[Dict] = field(default_factory=list)
    table_confidence: float = 0.0
    table_debug: Dict[str, Any] = field(default_factory=dict)
    table_attempts: Dict[str, Any] = field(default_factory=dict)
    table_used: bool = False
    qty_ratio: float = 0.0
    cascade_stage: int = 0

    # Resultado
    dados: Dict[str, Any] = field(default_factory=dict)
    servicos_raw: List[Dict] = field(default_factory=list)
    text_items: List[Dict] = field(default_factory=list)

    # Flags de processamento
    itemless_mode: bool = False
    text_section_enabled: bool = True
    text_section_reason: Optional[str] = None
    strict_item_gate: bool = False


class PipelineStage(ABC):
    """
    Classe base abstrata para estágios do pipeline.

    Cada estágio executa uma parte específica do processamento
    e modifica o contexto compartilhado.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Nome do estágio para logging."""
        pass

    @abstractmethod
    def execute(self, context: PipelineContext) -> None:
        """
        Executa o estágio de processamento.

        Args:
            context: Contexto compartilhado do pipeline

        Raises:
            ProcessingCancelled: Se o processamento foi cancelado
            ProcessingError: Se ocorrer erro no processamento
        """
        pass

    def _log_start(self) -> None:
        """Loga início do estágio."""
        logger.debug(f"[STAGE] Iniciando: {self.name}")

    def _log_end(self, details: str = "") -> None:
        """Loga fim do estágio."""
        suffix = f" - {details}" if details else ""
        logger.debug(f"[STAGE] Concluído: {self.name}{suffix}")


class TextExtractionStage(PipelineStage):
    """
    Estágio de extração de texto do documento.

    Detecta tipo de documento (digital/escaneado) e extrai texto
    usando a estratégia apropriada (texto direto ou OCR).
    """

    @property
    def name(self) -> str:
        return "Extração de Texto"

    def execute(self, context: PipelineContext) -> None:
        self._log_start()
        # Implementação delegada ao pipeline principal
        # Este é um exemplo de como o estágio seria estruturado
        self._log_end(f"{len(context.texto or '')} chars")


class TableExtractionStage(PipelineStage):
    """
    Estágio de extração de tabelas.

    Usa cascata de fontes (pdfplumber → Document AI → Vision)
    para extrair serviços de tabelas no documento.
    """

    @property
    def name(self) -> str:
        return "Extração de Tabelas"

    def execute(self, context: PipelineContext) -> None:
        self._log_start()
        # Implementação delegada ao pipeline principal
        self._log_end(f"{len(context.servicos_table)} itens")


class AIAnalysisStage(PipelineStage):
    """
    Estágio de análise com IA.

    Usa LLM/Vision para extrair e validar dados
    quando as fontes anteriores não são suficientes.
    """

    @property
    def name(self) -> str:
        return "Análise com IA"

    def execute(self, context: PipelineContext) -> None:
        self._log_start()
        # Implementação delegada ao pipeline principal
        servicos_count = len(context.dados.get('servicos') or [])
        self._log_end(f"{servicos_count} serviços")


class TextEnrichmentStage(PipelineStage):
    """
    Estágio de enriquecimento via texto.

    Extrai informações adicionais do texto bruto
    para complementar dados extraídos de tabelas/IA.
    """

    @property
    def name(self) -> str:
        return "Enriquecimento via Texto"

    def execute(self, context: PipelineContext) -> None:
        self._log_start()
        # Implementação delegada ao pipeline principal
        self._log_end(f"{len(context.servicos_raw)} serviços")


class PostProcessStage(PipelineStage):
    """
    Estágio de pós-processamento.

    Aplica filtros, deduplicação e validação final
    aos serviços extraídos.
    """

    @property
    def name(self) -> str:
        return "Pós-processamento"

    def execute(self, context: PipelineContext) -> None:
        self._log_start()
        # Implementação delegada ao pipeline principal
        final_count = len(context.dados.get('servicos') or [])
        self._log_end(f"{final_count} serviços após filtros")


class FinalizationStage(PipelineStage):
    """
    Estágio de finalização.

    Corrige descrições usando texto original
    e prepara resultado final.
    """

    @property
    def name(self) -> str:
        return "Finalização"

    def execute(self, context: PipelineContext) -> None:
        self._log_start()
        # Implementação delegada ao pipeline principal
        self._log_end()


class PipelineRunner:
    """
    Executor do pipeline com estágios configuráveis.

    Permite customizar quais estágios são executados
    e em qual ordem.
    """

    def __init__(self, stages: Optional[List[PipelineStage]] = None):
        """
        Inicializa o runner com estágios.

        Args:
            stages: Lista de estágios a executar.
                   Se None, usa estágios padrão.
        """
        self.stages = stages or self._default_stages()

    def _default_stages(self) -> List[PipelineStage]:
        """Retorna estágios padrão do pipeline."""
        return [
            TextExtractionStage(),
            TableExtractionStage(),
            AIAnalysisStage(),
            TextEnrichmentStage(),
            PostProcessStage(),
            FinalizationStage(),
        ]

    def run(self, context: PipelineContext) -> Dict[str, Any]:
        """
        Executa todos os estágios do pipeline.

        Args:
            context: Contexto inicial do pipeline

        Returns:
            Dicionário com dados extraídos
        """
        logger.info(f"[PIPELINE] Iniciando com {len(self.stages)} estágios")

        for i, stage in enumerate(self.stages, 1):
            logger.debug(f"[PIPELINE] Estágio {i}/{len(self.stages)}: {stage.name}")
            stage.execute(context)

        logger.info(f"[PIPELINE] Concluído: {len(context.dados.get('servicos') or [])} serviços")
        return context.dados
