from typing import List, Optional

from pydantic import BaseModel


class ProcessingJobDetail(BaseModel):
    """Detalhes de um job de processamento."""
    id: str
    status: str
    user_id: int
    job_type: str
    file_path: Optional[str] = None
    original_filename: Optional[str] = None
    progress_current: int = 0
    progress_total: int = 0
    progress_stage: Optional[str] = None
    progress_message: Optional[str] = None
    pipeline: Optional[str] = None
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    canceled_at: Optional[str] = None
    error: Optional[str] = None
    result: Optional[dict] = None


class UserJobsResponse(BaseModel):
    """Lista de jobs do usuário."""
    status: str = "ok"
    jobs: List[ProcessingJobDetail]


class JobStatusResponse(BaseModel):
    """Status de um job específico."""
    status: str = "ok"
    job: ProcessingJobDetail


class JobCancelResponse(BaseModel):
    """Resposta de cancelamento de job."""
    status: str = "ok"
    message: str
    job: Optional[ProcessingJobDetail] = None


class ProcessingStatsResponse(BaseModel):
    """Estatísticas de processamento."""
    total_atestados: int
    total_servicos: int
    total_analises: int
    atestados_por_usuario: int
    servicos_por_atestado: float
    exigencias_por_analise: float


class JobDeleteResponse(BaseModel):
    """Resposta de exclusão de job."""
    status: str = "ok"
    deleted: bool


class JobCleanupResponse(BaseModel):
    """Resposta de limpeza de jobs órfãos."""
    status: str = "ok"
    orphaned_files: int
    stuck_processing: int
    total_cleaned: int
    message: str


class JobBulkDeleteResponse(BaseModel):
    """Resposta de exclusão em massa de jobs."""
    status: str = "ok"
    deleted: int
    message: str


class QueueInfoResponse(BaseModel):
    """Informações da fila de processamento."""
    is_running: bool
    queue_size: int
    processing_count: int
    max_concurrent: int
    poll_interval: Optional[float] = None


class QueueStatusResponse(BaseModel):
    """Status da fila de processamento."""
    status: str = "ok"
    queue: QueueInfoResponse


class AIProviderStatus(BaseModel):
    """Status de um provedor de IA."""
    name: str
    available: bool
    model: Optional[str] = None


class AIStatistics(BaseModel):
    """Estatísticas de uso de IA."""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0


class AIStatusResponse(BaseModel):
    """Status dos serviços de IA."""
    status: str = "ok"
    providers: dict
    statistics: dict
