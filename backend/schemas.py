from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Generic, TypeVar, Any, Sequence
from datetime import datetime
from decimal import Decimal

T = TypeVar('T')


# ============== USUÁRIO ==============

class UsuarioBase(BaseModel):
    email: EmailStr
    nome: str


class UsuarioCreate(UsuarioBase):
    senha: str


class UsuarioLogin(BaseModel):
    email: EmailStr
    senha: str


class UsuarioUpdate(BaseModel):
    nome: Optional[str] = None
    tema_preferido: Optional[str] = None


class UsuarioResponse(UsuarioBase):
    id: int
    is_admin: bool
    is_approved: bool
    is_active: bool
    tema_preferido: str
    created_at: datetime
    approved_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class UsuarioAdminResponse(UsuarioResponse):
    """Resposta com mais detalhes para admin."""
    approved_by: Optional[int] = None


# ============== AUTENTICAÇÃO ==============

class Token(BaseModel):
    access_token: str
    token_type: str


# ============== ATESTADO ==============

class ServicoAtestado(BaseModel):
    """Representa um serviço individual dentro de um atestado."""
    item: Optional[str] = None
    descricao: Optional[str] = None
    quantidade: Optional[float] = None
    unidade: Optional[str] = None



class AtestadoBase(BaseModel):
    descricao_servico: str
    quantidade: Optional[Decimal] = None
    unidade: Optional[str] = None
    contratante: Optional[str] = None
    data_emissao: Optional[datetime] = None


class AtestadoCreate(AtestadoBase):
    pass


class AtestadoUpdate(BaseModel):
    descricao_servico: Optional[str] = None
    quantidade: Optional[Decimal] = None
    unidade: Optional[str] = None
    contratante: Optional[str] = None
    data_emissao: Optional[datetime] = None


class AtestadoServicosUpdate(BaseModel):
    """Schema para atualizar apenas os serviços de um atestado."""
    servicos_json: List[ServicoAtestado]


class AtestadoResponse(AtestadoBase):
    id: int
    user_id: int
    arquivo_path: Optional[str] = None
    texto_extraido: Optional[str] = None
    servicos_json: Optional[List[ServicoAtestado]] = None  # Lista de serviços detalhados
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ============== ANÁLISE ==============

class ExigenciaEdital(BaseModel):
    """Representa uma exigência extraída do edital."""
    descricao: Optional[str] = None
    quantidade_minima: Optional[Decimal] = None
    unidade: Optional[str] = None
    permitir_soma: Optional[bool] = None
    exige_unico: Optional[bool] = None


class AtestadoMatch(BaseModel):
    """Representa um atestado que pode atender uma exigência."""
    atestado_id: int
    descricao_servico: str
    quantidade: Decimal
    unidade: str
    percentual_cobertura: float
    itens: Optional[List[ServicoAtestado]] = None


class ResultadoExigencia(BaseModel):
    """Resultado da análise de uma exigência específica."""
    exigencia: ExigenciaEdital
    status: str  # "atende", "parcial", "nao_atende"
    atestados_recomendados: List[AtestadoMatch]
    soma_quantidades: Decimal
    percentual_total: float


class AnaliseCreate(BaseModel):
    nome_licitacao: str


class AnaliseManualCreate(BaseModel):
    """Schema para criar análise manualmente (sem PDF)."""
    nome_licitacao: str
    exigencias: List[ExigenciaEdital]


class AnaliseResponse(BaseModel):
    id: int
    user_id: int
    nome_licitacao: str
    arquivo_path: Optional[str] = None
    exigencias_json: Optional[List[ExigenciaEdital]] = None
    resultado_json: Optional[List[ResultadoExigencia]] = None
    created_at: datetime

    class Config:
        from_attributes = True


# ============== MENSAGENS ==============

class Mensagem(BaseModel):
    mensagem: str
    sucesso: bool = True

class JobResponse(BaseModel):
    mensagem: str
    sucesso: bool = True
    job_id: str


# ============== PAGINAÇÃO ==============

class PaginatedResponse(BaseModel, Generic[T]):
    """Resposta paginada genérica."""
    items: List[T]
    total: int
    page: int = Field(ge=1)
    page_size: int = Field(ge=1)
    total_pages: int = Field(ge=0)

    @classmethod
    def create(
        cls,
        items: Sequence[Any],
        total: int,
        page: int,
        page_size: int
    ) -> "PaginatedResponse[T]":
        """Cria uma resposta paginada."""
        total_pages = (total + page_size - 1) // page_size if page_size > 0 else 0
        return cls(
            items=list(items),
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages
        )


class PaginatedAtestadoResponse(PaginatedResponse[AtestadoResponse]):
    """Resposta paginada de atestados."""
    pass


class PaginatedAnaliseResponse(PaginatedResponse[AnaliseResponse]):
    """Resposta paginada de análises."""
    pass


class PaginatedUsuarioResponse(PaginatedResponse[UsuarioAdminResponse]):
    """Resposta paginada de usuários (admin)."""
    pass


# ============== API RESPONSES ==============

class AuthConfigResponse(BaseModel):
    """Configuração de autenticação para o frontend."""
    mode: str
    supabase_enabled: bool
    supabase_url: Optional[str] = None
    supabase_anon_key: Optional[str] = None


class UserStatusResponse(BaseModel):
    """Status do usuário logado."""
    aprovado: bool
    admin: bool
    nome: str
    auth_mode: str


class PasswordRequirementsResponse(BaseModel):
    """Requisitos de senha."""
    requisitos: List[str]


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


class AdminStatsResponse(BaseModel):
    """Estatísticas de usuários do sistema."""
    total_usuarios: int
    usuarios_aprovados: int
    usuarios_pendentes: int
    usuarios_inativos: int


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
