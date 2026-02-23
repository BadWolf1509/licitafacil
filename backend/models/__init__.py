"""
Package de modelos SQLAlchemy.

Re-exporta todos os modelos para manter backward compatibility
com imports existentes: `from models import Usuario, Atestado, ...`
"""
from models.analise import Analise
from models.atestado import Atestado
from models.audit_log import AuditLog
from models.documento import (
    ChecklistEdital,
    DocumentoLicitacao,
    DocumentoStatus,
    DocumentoTipo,
)
from models.lembrete import (
    Lembrete,
    LembreteRecorrencia,
    LembreteStatus,
    LembreteTipo,
    Notificacao,
    NotificacaoTipo,
    PreferenciaNotificacao,
)
from models.licitacao import (
    Licitacao,
    LicitacaoFonte,
    LicitacaoHistorico,
    LicitacaoStatus,
    LicitacaoTag,
)
from models.pncp import PncpMonitoramento, PncpResultado, PncpResultadoStatus
from models.processing_job import ProcessingJobModel
from models.usuario import Usuario

__all__ = [
    "Usuario",
    "Atestado",
    "Analise",
    "ProcessingJobModel",
    "AuditLog",
    "Licitacao",
    "LicitacaoTag",
    "LicitacaoHistorico",
    "LicitacaoStatus",
    "LicitacaoFonte",
    "DocumentoLicitacao",
    "ChecklistEdital",
    "DocumentoTipo",
    "DocumentoStatus",
    "Lembrete",
    "LembreteStatus",
    "LembreteTipo",
    "LembreteRecorrencia",
    "Notificacao",
    "NotificacaoTipo",
    "PreferenciaNotificacao",
    "PncpMonitoramento",
    "PncpResultado",
    "PncpResultadoStatus",
]
