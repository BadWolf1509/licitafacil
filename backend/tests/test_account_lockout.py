"""
Testes para bloqueio de conta apos tentativas de login falhas.
"""
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from auth import (
    is_account_locked,
    get_lockout_remaining_seconds,
    record_failed_login,
    reset_failed_attempts,
)
from models import Usuario


class TestIsAccountLocked:
    """Testes da funcao is_account_locked."""

    def test_not_locked_when_locked_until_is_none(self, test_user):
        """Conta nao esta bloqueada quando locked_until e None."""
        test_user.locked_until = None
        assert is_account_locked(test_user) is False

    def test_locked_when_locked_until_in_future(self, test_user):
        """Conta esta bloqueada quando locked_until e no futuro."""
        test_user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=10)
        assert is_account_locked(test_user) is True

    def test_not_locked_when_locked_until_in_past(self, test_user):
        """Conta nao esta bloqueada quando locked_until e no passado."""
        test_user.locked_until = datetime.now(timezone.utc) - timedelta(minutes=10)
        assert is_account_locked(test_user) is False


class TestGetLockoutRemainingSeconds:
    """Testes da funcao get_lockout_remaining_seconds."""

    def test_returns_zero_when_not_locked(self, test_user):
        """Retorna 0 quando nao esta bloqueado."""
        test_user.locked_until = None
        assert get_lockout_remaining_seconds(test_user) == 0

    def test_returns_remaining_time(self, test_user):
        """Retorna tempo restante em segundos."""
        test_user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=5)
        remaining = get_lockout_remaining_seconds(test_user)
        # Deve estar entre 4 e 5 minutos (300 segundos aproximadamente)
        assert 240 < remaining <= 300

    def test_returns_zero_when_expired(self, test_user):
        """Retorna 0 quando bloqueio expirou."""
        test_user.locked_until = datetime.now(timezone.utc) - timedelta(minutes=1)
        assert get_lockout_remaining_seconds(test_user) == 0


class TestRecordFailedLogin:
    """Testes da funcao record_failed_login."""

    def test_increments_failed_attempts(self, db_session, test_user):
        """Incrementa contador de tentativas falhas."""
        initial_attempts = test_user.failed_login_attempts
        record_failed_login(db_session, test_user)
        assert test_user.failed_login_attempts == initial_attempts + 1

    def test_locks_account_after_max_attempts(self, db_session, test_user):
        """Bloqueia conta apos atingir limite de tentativas."""
        from config.security import MAX_FAILED_LOGIN_ATTEMPTS

        test_user.failed_login_attempts = MAX_FAILED_LOGIN_ATTEMPTS - 1
        test_user.locked_until = None

        record_failed_login(db_session, test_user)

        assert test_user.failed_login_attempts == MAX_FAILED_LOGIN_ATTEMPTS
        assert test_user.locked_until is not None
        # Comparar timestamps - locked_until deve ser no futuro
        now = datetime.now(timezone.utc)
        locked = test_user.locked_until
        if locked.tzinfo is None:
            locked = locked.replace(tzinfo=timezone.utc)
        assert locked > now


class TestResetFailedAttempts:
    """Testes da funcao reset_failed_attempts."""

    def test_resets_counter_after_successful_login(self, db_session, test_user):
        """Reseta contador apos login bem sucedido."""
        test_user.failed_login_attempts = 3
        test_user.locked_until = None

        reset_failed_attempts(db_session, test_user)

        assert test_user.failed_login_attempts == 0

    def test_clears_lockout_after_successful_login(self, db_session, test_user):
        """Remove bloqueio apos login bem sucedido."""
        test_user.failed_login_attempts = 5
        test_user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=10)

        reset_failed_attempts(db_session, test_user)

        assert test_user.failed_login_attempts == 0
        assert test_user.locked_until is None

    def test_no_commit_if_already_clean(self, db_session, test_user):
        """Nao faz commit se ja esta limpo."""
        test_user.failed_login_attempts = 0
        test_user.locked_until = None

        # Nao deve fazer commit desnecessario
        reset_failed_attempts(db_session, test_user)

        assert test_user.failed_login_attempts == 0
        assert test_user.locked_until is None


class TestAccountLockoutConfig:
    """Testes de configuracao de bloqueio de conta."""

    def test_max_attempts_config_exists(self):
        """Verifica que configuracao de tentativas maximas existe."""
        from config.security import MAX_FAILED_LOGIN_ATTEMPTS
        assert MAX_FAILED_LOGIN_ATTEMPTS > 0
        assert MAX_FAILED_LOGIN_ATTEMPTS <= 10

    def test_lockout_minutes_config_exists(self):
        """Verifica que configuracao de duracao do bloqueio existe."""
        from config.security import ACCOUNT_LOCKOUT_MINUTES
        assert ACCOUNT_LOCKOUT_MINUTES > 0
        assert ACCOUNT_LOCKOUT_MINUTES >= 5
