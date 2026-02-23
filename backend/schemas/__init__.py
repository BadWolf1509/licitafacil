"""
Package de schemas Pydantic.

Re-exporta todos os schemas para manter backward compatibility
com imports existentes: `from schemas import AtestadoResponse, ...`
"""
# Base
# Admin
from schemas.admin import AdminStatsResponse

# Analise
from schemas.analise import (
    AnaliseCreate,
    AnaliseManualCreate,
    AnaliseResponse,
    AtestadoMatch,
    ExigenciaEdital,
    PaginatedAnaliseResponse,
    ResultadoExigencia,
)

# Atestado
from schemas.atestado import (
    AtestadoBase,
    AtestadoCreate,
    AtestadoResponse,
    AtestadoServicosUpdate,
    AtestadoUpdate,
    PaginatedAtestadoResponse,
    ServicoAtestado,
)

# Auth
from schemas.auth import (
    AuthConfigResponse,
    PasswordPolicy,
    PasswordRequirementsResponse,
    Token,
    UserStatusResponse,
)
from schemas.base import JobResponse, Mensagem, PaginatedResponse

# Documento / Checklist
from schemas.documento import (
    ChecklistItemCreate,
    ChecklistItemResponse,
    ChecklistItemToggle,
    ChecklistItemUpdate,
    ChecklistResumoResponse,
    DocumentoCreate,
    DocumentoResponse,
    DocumentoResumoResponse,
    DocumentoUpdate,
    PaginatedDocumentoResponse,
)

# Lembrete / Notificação
from schemas.lembrete import (
    CalendarioQuery,
    LembreteCreate,
    LembreteResponse,
    LembreteStatusUpdate,
    LembreteUpdate,
    NotificacaoCountResponse,
    NotificacaoResponse,
    PaginatedLembreteResponse,
    PaginatedNotificacaoResponse,
    PreferenciaNotificacaoResponse,
    PreferenciaNotificacaoUpdate,
)

# Licitação
from schemas.licitacao import (
    LicitacaoBase,
    LicitacaoCreate,
    LicitacaoDetalheResponse,
    LicitacaoEstatisticasResponse,
    LicitacaoHistoricoResponse,
    LicitacaoResponse,
    LicitacaoStatusUpdate,
    LicitacaoTagCreate,
    LicitacaoTagResponse,
    LicitacaoUpdate,
    PaginatedLicitacaoResponse,
)

# PNCP
from schemas.pncp import (
    PaginatedMonitoramentoResponse,
    PaginatedResultadoResponse,
    PncpBuscaResponse,
    PncpImportarRequest,
    PncpMonitoramentoCreate,
    PncpMonitoramentoResponse,
    PncpMonitoramentoUpdate,
    PncpResultadoResponse,
    PncpResultadoStatusUpdate,
)

# Processing
from schemas.processing import (
    AIProviderStatus,
    AIStatistics,
    AIStatusResponse,
    JobBulkDeleteResponse,
    JobCancelResponse,
    JobCleanupResponse,
    JobDeleteResponse,
    JobStatusResponse,
    ProcessingJobDetail,
    ProcessingStatsResponse,
    QueueInfoResponse,
    QueueStatusResponse,
    UserJobsResponse,
)

# Usuario
from schemas.usuario import (
    PaginatedUsuarioResponse,
    UsuarioAdminResponse,
    UsuarioBase,
    UsuarioCreate,
    UsuarioLogin,
    UsuarioResponse,
    UsuarioUpdate,
)

__all__ = [
    # Base
    "Mensagem", "JobResponse", "PaginatedResponse",
    # Usuario
    "UsuarioBase", "UsuarioCreate", "UsuarioLogin", "UsuarioUpdate",
    "UsuarioResponse", "UsuarioAdminResponse", "PaginatedUsuarioResponse",
    # Auth
    "Token", "AuthConfigResponse", "UserStatusResponse",
    "PasswordPolicy", "PasswordRequirementsResponse",
    # Atestado
    "ServicoAtestado", "AtestadoBase", "AtestadoCreate", "AtestadoUpdate",
    "AtestadoServicosUpdate", "AtestadoResponse", "PaginatedAtestadoResponse",
    # Analise
    "ExigenciaEdital", "AtestadoMatch", "ResultadoExigencia",
    "AnaliseCreate", "AnaliseManualCreate", "AnaliseResponse", "PaginatedAnaliseResponse",
    # Processing
    "ProcessingJobDetail", "UserJobsResponse", "JobStatusResponse",
    "JobCancelResponse", "ProcessingStatsResponse", "JobDeleteResponse",
    "JobCleanupResponse", "JobBulkDeleteResponse",
    "QueueInfoResponse", "QueueStatusResponse",
    "AIProviderStatus", "AIStatistics", "AIStatusResponse",
    # Licitação
    "LicitacaoBase", "LicitacaoCreate", "LicitacaoUpdate", "LicitacaoStatusUpdate",
    "LicitacaoTagCreate", "LicitacaoTagResponse", "LicitacaoHistoricoResponse",
    "LicitacaoResponse", "LicitacaoDetalheResponse", "PaginatedLicitacaoResponse",
    "LicitacaoEstatisticasResponse",
    # Lembrete / Notificação
    "LembreteCreate", "LembreteUpdate", "LembreteStatusUpdate",
    "LembreteResponse", "PaginatedLembreteResponse",
    "NotificacaoResponse", "NotificacaoCountResponse", "PaginatedNotificacaoResponse",
    "PreferenciaNotificacaoResponse", "PreferenciaNotificacaoUpdate",
    "CalendarioQuery",
    # Documento / Checklist
    "DocumentoCreate", "DocumentoUpdate", "DocumentoResponse",
    "PaginatedDocumentoResponse", "DocumentoResumoResponse",
    "ChecklistItemCreate", "ChecklistItemUpdate", "ChecklistItemToggle",
    "ChecklistItemResponse", "ChecklistResumoResponse",
    # PNCP
    "PncpMonitoramentoCreate", "PncpMonitoramentoUpdate", "PncpMonitoramentoResponse",
    "PaginatedMonitoramentoResponse",
    "PncpResultadoResponse", "PaginatedResultadoResponse",
    "PncpResultadoStatusUpdate", "PncpBuscaResponse", "PncpImportarRequest",
    # Admin
    "AdminStatsResponse",
]
