"""
Modelos compartilhados para os serviços do LicitaFácil.

Centraliza enums e dataclasses usados por múltiplos módulos
para evitar dependências circulares e facilitar manutenção.
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Dict, Any, Optional, List


# === Modelos do Processing Queue ===

class JobStatus(str, Enum):
    """Status de um job de processamento."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ProcessingJob:
    """Representa um job de processamento."""
    id: str
    user_id: int
    file_path: str
    original_filename: Optional[str] = None
    job_type: str = "atestado"
    status: JobStatus = JobStatus.PENDING
    created_at: str = ""
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    canceled_at: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    attempts: int = 0
    max_attempts: int = 3
    progress_current: int = 0
    progress_total: int = 0
    progress_stage: Optional[str] = None
    progress_message: Optional[str] = None
    pipeline: Optional[str] = None

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        """Converte para dicionário."""
        return asdict(self)


# === Modelos do Cascade Pipeline ===

class PipelineStage(str, Enum):
    """Estágios do pipeline de extração."""
    QUALITY_CHECK = "quality_check"
    NATIVE_EXTRACTION = "native_extraction"
    PREPROCESSING = "preprocessing"
    LOCAL_OCR = "local_ocr"
    CLOUD_OCR = "cloud_ocr"
    VISION_AI = "vision_ai"
    AI_ANALYSIS = "ai_analysis"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class PipelineResult:
    """Resultado do pipeline de extração."""
    success: bool
    text: str
    data: Dict[str, Any]
    pipeline_used: Any  # ExtractionPipeline (evita import circular)
    stages_executed: List[str]
    quality_report: Optional[Any]  # QualityReport (evita import circular)
    processing_time: float
    cost_estimate: float
    errors: List[str] = field(default_factory=list)
    debug_info: Dict[str, Any] = field(default_factory=dict)


# === Modelos de Extração ===

@dataclass
class ExtractionResult:
    """Resultado de uma extração de texto."""
    text: str
    confidence: float
    method: str
    pages_processed: int = 0
    errors: List[str] = field(default_factory=list)


@dataclass
class ServiceItem:
    """Item de serviço extraído de um atestado."""
    item: Optional[str] = None
    descricao: str = ""
    quantidade: Optional[float] = None
    unidade: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Converte para dicionário."""
        return {
            "item": self.item,
            "descricao": self.descricao,
            "quantidade": self.quantidade,
            "unidade": self.unidade
        }


@dataclass
class AtestadoData:
    """Dados extraídos de um atestado."""
    descricao_servico: Optional[str] = None
    quantidade: Optional[float] = None
    unidade: Optional[str] = None
    contratante: Optional[str] = None
    data_emissao: Optional[str] = None
    servicos: List[ServiceItem] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Converte para dicionário."""
        return {
            "descricao_servico": self.descricao_servico,
            "quantidade": self.quantidade,
            "unidade": self.unidade,
            "contratante": self.contratante,
            "data_emissao": self.data_emissao,
            "servicos": [s.to_dict() for s in self.servicos]
        }
