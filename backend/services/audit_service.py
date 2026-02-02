"""
Servico de auditoria para rastrear acoes administrativas.

Registra todas as acoes importantes realizadas no sistema para
fins de compliance e seguranca.
"""
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session

from models import AuditLog
from logging_config import get_logger

logger = get_logger(__name__)


class AuditAction:
    """Constantes para tipos de acoes de auditoria."""
    # Acoes de usuario
    USER_APPROVED = "user_approved"
    USER_REJECTED = "user_rejected"
    USER_DEACTIVATED = "user_deactivated"
    USER_REACTIVATED = "user_reactivated"
    USER_PROMOTED_ADMIN = "user_promoted_admin"
    USER_DEMOTED_ADMIN = "user_demoted_admin"
    USER_DELETED = "user_deleted"

    # Acoes de atestado
    ATESTADO_DELETED = "atestado_deleted"
    ATESTADO_UPDATED = "atestado_updated"

    # Acoes de analise
    ANALISE_DELETED = "analise_deleted"

    # Acoes de login
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILED = "login_failed"
    LOGIN_BLOCKED = "login_blocked"

    # Acoes de sistema
    CONFIG_CHANGED = "config_changed"


class AuditService:
    """
    Servico para registrar e consultar logs de auditoria.

    Uso:
        audit_service.log_action(
            db=db,
            user_id=admin.id,
            action=AuditAction.USER_APPROVED,
            resource_type="usuario",
            resource_id=user.id,
            details={"email": user.email},
            ip_address=request.client.host
        )
    """

    def log_action(
        self,
        db: Session,
        user_id: int,
        action: str,
        resource_type: str,
        resource_id: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None
    ) -> AuditLog:
        """
        Registra uma acao de auditoria.

        Args:
            db: Sessao do banco de dados
            user_id: ID do usuario que realizou a acao
            action: Tipo de acao (usar constantes de AuditAction)
            resource_type: Tipo do recurso afetado (usuario, atestado, etc)
            resource_id: ID do recurso afetado (opcional)
            details: Detalhes adicionais em dict (opcional)
            ip_address: IP do cliente (opcional)

        Returns:
            AuditLog criado
        """
        log = AuditLog(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
            ip_address=ip_address
        )
        db.add(log)
        db.commit()
        db.refresh(log)

        logger.info(
            f"Audit: user={user_id} action={action} "
            f"resource={resource_type}:{resource_id} ip={ip_address}"
        )

        return log

    def get_logs_by_user(
        self,
        db: Session,
        user_id: int,
        limit: int = 100
    ) -> List[AuditLog]:
        """
        Busca logs de auditoria por usuario.

        Args:
            db: Sessao do banco de dados
            user_id: ID do usuario
            limit: Limite de registros

        Returns:
            Lista de AuditLog
        """
        return db.query(AuditLog).filter(
            AuditLog.user_id == user_id
        ).order_by(
            AuditLog.created_at.desc()
        ).limit(limit).all()

    def get_logs_by_action(
        self,
        db: Session,
        action: str,
        limit: int = 100
    ) -> List[AuditLog]:
        """
        Busca logs de auditoria por tipo de acao.

        Args:
            db: Sessao do banco de dados
            action: Tipo de acao
            limit: Limite de registros

        Returns:
            Lista de AuditLog
        """
        return db.query(AuditLog).filter(
            AuditLog.action == action
        ).order_by(
            AuditLog.created_at.desc()
        ).limit(limit).all()

    def get_recent_logs(
        self,
        db: Session,
        hours: int = 24,
        limit: int = 100
    ) -> List[AuditLog]:
        """
        Busca logs de auditoria recentes.

        Args:
            db: Sessao do banco de dados
            hours: Numero de horas para buscar
            limit: Limite de registros

        Returns:
            Lista de AuditLog
        """
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        return db.query(AuditLog).filter(
            AuditLog.created_at >= cutoff
        ).order_by(
            AuditLog.created_at.desc()
        ).limit(limit).all()

    def get_logs_for_resource(
        self,
        db: Session,
        resource_type: str,
        resource_id: int,
        limit: int = 50
    ) -> List[AuditLog]:
        """
        Busca logs de auditoria para um recurso especifico.

        Args:
            db: Sessao do banco de dados
            resource_type: Tipo do recurso
            resource_id: ID do recurso
            limit: Limite de registros

        Returns:
            Lista de AuditLog
        """
        return db.query(AuditLog).filter(
            AuditLog.resource_type == resource_type,
            AuditLog.resource_id == resource_id
        ).order_by(
            AuditLog.created_at.desc()
        ).limit(limit).all()


# Instancia singleton do servico
audit_service = AuditService()
