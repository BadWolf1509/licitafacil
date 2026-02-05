"""
Testes para o servico de auditoria.

Testa as funcoes em services/audit_service.py.

Usa o db_session fixture do conftest.py com SQLite de teste para
verificar que os registros de auditoria sao criados e consultados
corretamente no banco de dados.
"""
import pytest
from datetime import datetime, timedelta, timezone
from typing import Optional
from unittest.mock import MagicMock, patch
from sqlalchemy.orm import Session

from services.audit_service import AuditService, AuditAction, audit_service
from models import AuditLog, Usuario


# === Helpers ===

def _create_test_user(db_session: Session, email: str = "audit_test@test.com") -> Usuario:
    """Cria um usuario de teste para associar aos logs de auditoria."""
    import uuid
    user = Usuario(
        email=email,
        nome="Audit Test User",
        supabase_id=str(uuid.uuid4()),
        is_active=True,
        is_approved=True,
        is_admin=True
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _create_audit_log(
    db_session: Session,
    user_id: int,
    action: str = AuditAction.USER_APPROVED,
    resource_type: str = "usuario",
    resource_id: Optional[int] = None,
    details: Optional[dict] = None,
    ip_address: Optional[str] = None,
    created_at: Optional[datetime] = None
) -> AuditLog:
    """Cria um AuditLog diretamente no banco para testes de consulta."""
    log = AuditLog(
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details=details,
        ip_address=ip_address,
    )
    db_session.add(log)
    db_session.commit()
    db_session.refresh(log)

    # Se created_at customizado, atualizar manualmente
    if created_at:
        log.created_at = created_at
        db_session.commit()
        db_session.refresh(log)

    return log


# === Fixtures ===

@pytest.fixture
def service():
    """Instancia do AuditService."""
    return AuditService()


@pytest.fixture
def audit_user(db_session: Session) -> Usuario:
    """Usuario admin para testes de auditoria."""
    return _create_test_user(db_session, email="audit_admin@test.com")


@pytest.fixture(autouse=True)
def cleanup_audit_logs(db_session: Session):
    """Limpa logs de auditoria apos cada teste."""
    yield
    db_session.execute(AuditLog.__table__.delete())
    db_session.commit()


# === TestAuditService ===

class TestAuditServiceLogAction:
    """Testes para registro de acoes de auditoria."""

    def test_log_action_creates_record(self, service, db_session, audit_user):
        """log_action cria registro de auditoria no banco."""
        log = service.log_action(
            db=db_session,
            user_id=audit_user.id,
            action=AuditAction.USER_APPROVED,
            resource_type="usuario",
            resource_id=42,
            details={"email": "novo@test.com"},
            ip_address="192.168.1.1"
        )

        assert log is not None
        assert isinstance(log, AuditLog)
        assert log.id is not None
        assert log.user_id == audit_user.id
        assert log.action == AuditAction.USER_APPROVED
        assert log.resource_type == "usuario"
        assert log.resource_id == 42
        assert log.details == {"email": "novo@test.com"}
        assert log.ip_address == "192.168.1.1"

    def test_log_action_persists_in_database(self, service, db_session, audit_user):
        """log_action persiste o registro no banco de dados."""
        log = service.log_action(
            db=db_session,
            user_id=audit_user.id,
            action=AuditAction.ATESTADO_DELETED,
            resource_type="atestado",
            resource_id=100
        )

        # Consultar diretamente no banco
        found = db_session.query(AuditLog).filter(
            AuditLog.id == log.id
        ).first()

        assert found is not None
        assert found.action == AuditAction.ATESTADO_DELETED
        assert found.resource_type == "atestado"
        assert found.resource_id == 100

    def test_log_action_without_optional_fields(self, service, db_session, audit_user):
        """log_action funciona sem campos opcionais."""
        log = service.log_action(
            db=db_session,
            user_id=audit_user.id,
            action=AuditAction.SYSTEM_CLEANUP,
            resource_type="sistema"
        )

        assert log is not None
        assert log.resource_id is None
        assert log.details is None
        assert log.ip_address is None

    def test_log_action_with_complex_details(self, service, db_session, audit_user):
        """log_action armazena detalhes complexos em JSON."""
        details = {
            "before": {"is_admin": False, "is_active": True},
            "after": {"is_admin": True, "is_active": True},
            "changed_fields": ["is_admin"]
        }

        log = service.log_action(
            db=db_session,
            user_id=audit_user.id,
            action=AuditAction.USER_PROMOTED_ADMIN,
            resource_type="usuario",
            resource_id=5,
            details=details
        )

        assert log.details == details
        assert log.details["changed_fields"] == ["is_admin"]

    def test_log_action_all_action_types(self, service, db_session, audit_user):
        """Todos os tipos de acao podem ser registrados."""
        actions = [
            AuditAction.USER_APPROVED,
            AuditAction.USER_REJECTED,
            AuditAction.USER_DEACTIVATED,
            AuditAction.USER_REACTIVATED,
            AuditAction.USER_PROMOTED_ADMIN,
            AuditAction.USER_DEMOTED_ADMIN,
            AuditAction.USER_DELETED,
            AuditAction.ATESTADO_DELETED,
            AuditAction.ATESTADO_UPDATED,
            AuditAction.ANALISE_DELETED,
            AuditAction.LOGIN_SUCCESS,
            AuditAction.LOGIN_FAILED,
            AuditAction.LOGIN_BLOCKED,
            AuditAction.CONFIG_CHANGED,
            AuditAction.SYSTEM_CLEANUP,
        ]

        for action in actions:
            log = service.log_action(
                db=db_session,
                user_id=audit_user.id,
                action=action,
                resource_type="teste"
            )
            assert log.action == action

    def test_log_action_has_created_at(self, service, db_session, audit_user):
        """log_action cria registro com timestamp."""
        log = service.log_action(
            db=db_session,
            user_id=audit_user.id,
            action=AuditAction.LOGIN_SUCCESS,
            resource_type="sessao"
        )

        assert log.created_at is not None


class TestAuditServiceGetLogsByUser:
    """Testes para consulta de logs por usuario."""

    def test_get_logs_by_user(self, service, db_session, audit_user):
        """get_logs_by_user retorna logs do usuario."""
        # Criar alguns logs
        service.log_action(
            db=db_session,
            user_id=audit_user.id,
            action=AuditAction.USER_APPROVED,
            resource_type="usuario",
            resource_id=10
        )
        service.log_action(
            db=db_session,
            user_id=audit_user.id,
            action=AuditAction.ATESTADO_DELETED,
            resource_type="atestado",
            resource_id=20
        )

        logs = service.get_logs_by_user(db_session, audit_user.id)

        assert len(logs) == 2
        assert all(log.user_id == audit_user.id for log in logs)

    def test_get_logs_by_user_empty(self, service, db_session):
        """get_logs_by_user retorna lista vazia para usuario sem logs."""
        logs = service.get_logs_by_user(db_session, user_id=99999)

        assert logs == []

    def test_get_logs_by_user_with_limit(self, service, db_session, audit_user):
        """get_logs_by_user respeita o limite."""
        # Criar 5 logs
        for i in range(5):
            service.log_action(
                db=db_session,
                user_id=audit_user.id,
                action=AuditAction.LOGIN_SUCCESS,
                resource_type="sessao"
            )

        logs = service.get_logs_by_user(db_session, audit_user.id, limit=3)

        assert len(logs) == 3

    def test_get_logs_by_user_ordered_desc(self, service, db_session, audit_user):
        """get_logs_by_user retorna logs ordenados por created_at desc."""
        log1 = service.log_action(
            db=db_session,
            user_id=audit_user.id,
            action=AuditAction.USER_APPROVED,
            resource_type="usuario"
        )
        log2 = service.log_action(
            db=db_session,
            user_id=audit_user.id,
            action=AuditAction.USER_REJECTED,
            resource_type="usuario"
        )

        logs = service.get_logs_by_user(db_session, audit_user.id)

        # Mais recente primeiro
        assert logs[0].id == log2.id
        assert logs[1].id == log1.id

    def test_get_logs_by_user_does_not_return_other_users(
        self, service, db_session, audit_user
    ):
        """get_logs_by_user nao retorna logs de outros usuarios."""
        other_user = _create_test_user(db_session, email="other_user@test.com")

        service.log_action(
            db=db_session,
            user_id=audit_user.id,
            action=AuditAction.USER_APPROVED,
            resource_type="usuario"
        )
        service.log_action(
            db=db_session,
            user_id=other_user.id,
            action=AuditAction.ATESTADO_DELETED,
            resource_type="atestado"
        )

        logs = service.get_logs_by_user(db_session, audit_user.id)

        assert len(logs) == 1
        assert logs[0].user_id == audit_user.id


class TestAuditServiceGetLogsByAction:
    """Testes para consulta de logs por tipo de acao."""

    def test_get_logs_by_action(self, service, db_session, audit_user):
        """get_logs_by_action retorna logs com a acao especificada."""
        service.log_action(
            db=db_session,
            user_id=audit_user.id,
            action=AuditAction.USER_APPROVED,
            resource_type="usuario"
        )
        service.log_action(
            db=db_session,
            user_id=audit_user.id,
            action=AuditAction.ATESTADO_DELETED,
            resource_type="atestado"
        )
        service.log_action(
            db=db_session,
            user_id=audit_user.id,
            action=AuditAction.USER_APPROVED,
            resource_type="usuario"
        )

        logs = service.get_logs_by_action(db_session, AuditAction.USER_APPROVED)

        assert len(logs) == 2
        assert all(log.action == AuditAction.USER_APPROVED for log in logs)

    def test_get_logs_by_action_empty(self, service, db_session):
        """get_logs_by_action retorna lista vazia quando nao ha logs."""
        logs = service.get_logs_by_action(db_session, AuditAction.CONFIG_CHANGED)

        assert logs == []


class TestAuditServiceGetRecentLogs:
    """Testes para consulta de logs recentes."""

    def test_get_recent_logs(self, service, db_session, audit_user):
        """get_recent_logs retorna logs criados recentemente."""
        service.log_action(
            db=db_session,
            user_id=audit_user.id,
            action=AuditAction.LOGIN_SUCCESS,
            resource_type="sessao"
        )

        logs = service.get_recent_logs(db_session, hours=24)

        assert len(logs) >= 1

    def test_get_recent_logs_with_limit(self, service, db_session, audit_user):
        """get_recent_logs respeita o limite."""
        for _ in range(5):
            service.log_action(
                db=db_session,
                user_id=audit_user.id,
                action=AuditAction.LOGIN_SUCCESS,
                resource_type="sessao"
            )

        logs = service.get_recent_logs(db_session, hours=24, limit=2)

        assert len(logs) == 2

    def test_get_recent_logs_default_params(self, service, db_session, audit_user):
        """get_recent_logs funciona com parametros default."""
        service.log_action(
            db=db_session,
            user_id=audit_user.id,
            action=AuditAction.LOGIN_SUCCESS,
            resource_type="sessao"
        )

        logs = service.get_recent_logs(db_session)

        assert len(logs) >= 1


class TestAuditServiceGetLogsForResource:
    """Testes para consulta de logs por recurso especifico."""

    def test_get_logs_for_resource(self, service, db_session, audit_user):
        """get_logs_for_resource retorna logs de um recurso especifico."""
        service.log_action(
            db=db_session,
            user_id=audit_user.id,
            action=AuditAction.ATESTADO_UPDATED,
            resource_type="atestado",
            resource_id=42
        )
        service.log_action(
            db=db_session,
            user_id=audit_user.id,
            action=AuditAction.ATESTADO_DELETED,
            resource_type="atestado",
            resource_id=42
        )
        service.log_action(
            db=db_session,
            user_id=audit_user.id,
            action=AuditAction.ATESTADO_UPDATED,
            resource_type="atestado",
            resource_id=99
        )

        logs = service.get_logs_for_resource(db_session, "atestado", 42)

        assert len(logs) == 2
        assert all(log.resource_id == 42 for log in logs)

    def test_get_logs_for_resource_empty(self, service, db_session):
        """get_logs_for_resource retorna lista vazia quando recurso nao tem logs."""
        logs = service.get_logs_for_resource(db_session, "atestado", 99999)

        assert logs == []

    def test_get_logs_for_resource_with_limit(self, service, db_session, audit_user):
        """get_logs_for_resource respeita o limite."""
        for _ in range(5):
            service.log_action(
                db=db_session,
                user_id=audit_user.id,
                action=AuditAction.ATESTADO_UPDATED,
                resource_type="atestado",
                resource_id=42
            )

        logs = service.get_logs_for_resource(db_session, "atestado", 42, limit=3)

        assert len(logs) == 3


class TestAuditActionConstants:
    """Testes para as constantes de acoes de auditoria."""

    def test_user_actions_defined(self):
        """Acoes de usuario estao definidas."""
        assert AuditAction.USER_APPROVED == "user_approved"
        assert AuditAction.USER_REJECTED == "user_rejected"
        assert AuditAction.USER_DEACTIVATED == "user_deactivated"
        assert AuditAction.USER_REACTIVATED == "user_reactivated"
        assert AuditAction.USER_PROMOTED_ADMIN == "user_promoted_admin"
        assert AuditAction.USER_DEMOTED_ADMIN == "user_demoted_admin"
        assert AuditAction.USER_DELETED == "user_deleted"

    def test_atestado_actions_defined(self):
        """Acoes de atestado estao definidas."""
        assert AuditAction.ATESTADO_DELETED == "atestado_deleted"
        assert AuditAction.ATESTADO_UPDATED == "atestado_updated"

    def test_analise_actions_defined(self):
        """Acoes de analise estao definidas."""
        assert AuditAction.ANALISE_DELETED == "analise_deleted"

    def test_login_actions_defined(self):
        """Acoes de login estao definidas."""
        assert AuditAction.LOGIN_SUCCESS == "login_success"
        assert AuditAction.LOGIN_FAILED == "login_failed"
        assert AuditAction.LOGIN_BLOCKED == "login_blocked"

    def test_system_actions_defined(self):
        """Acoes de sistema estao definidas."""
        assert AuditAction.CONFIG_CHANGED == "config_changed"
        assert AuditAction.SYSTEM_CLEANUP == "system_cleanup"


class TestAuditServiceSingleton:
    """Testes para a instancia singleton do servico."""

    def test_singleton_instance_exists(self):
        """Instancia singleton do audit_service existe."""
        assert audit_service is not None
        assert isinstance(audit_service, AuditService)

    def test_singleton_is_same_instance(self):
        """Import do audit_service retorna a mesma instancia."""
        from services.audit_service import audit_service as audit_service2
        assert audit_service is audit_service2
