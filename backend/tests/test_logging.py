"""
Testes para o módulo de logging.
"""
import logging
import pytest

from logging_config import (
    sanitize_dict,
    SanitizingFilter,
    SENSITIVE_KEYS,
    SENSITIVE_PATTERNS,
)


class TestSanitizeDict:
    """Testes para sanitização de dicionários."""

    def test_sanitizes_password(self):
        """Verifica que senha é mascarada."""
        data = {"username": "user", "password": "secret123"}
        result = sanitize_dict(data)

        assert result["username"] == "user"
        assert result["password"] == "***"

    def test_sanitizes_token(self):
        """Verifica que token é mascarado."""
        data = {"access_token": "eyJ...", "refresh_token": "abc123"}
        result = sanitize_dict(data)

        assert result["access_token"] == "***"
        assert result["refresh_token"] == "***"

    def test_sanitizes_nested_dict(self):
        """Verifica sanitização em dicionários aninhados."""
        data = {
            "user": {
                "email": "test@test.com",
                "config": {"password": "secret", "name": "test"}
            }
        }
        result = sanitize_dict(data)

        assert result["user"]["email"] == "test@test.com"
        assert result["user"]["config"]["password"] == "***"
        assert result["user"]["config"]["name"] == "test"

    def test_sanitizes_list_of_dicts(self):
        """Verifica sanitização em listas de dicionários."""
        data = {
            "users": [
                {"name": "User1", "senha": "pass1"},
                {"name": "User2", "senha": "pass2"},
            ]
        }
        result = sanitize_dict(data)

        assert result["users"][0]["name"] == "User1"
        assert result["users"][0]["senha"] == "***"
        assert result["users"][1]["senha"] == "***"

    def test_preserves_non_sensitive_data(self):
        """Verifica que dados não-sensíveis são preservados."""
        data = {"name": "Test", "age": 25, "active": True}
        result = sanitize_dict(data)

        assert result == data

    def test_case_insensitive_matching(self):
        """Verifica que matching é case-insensitive."""
        data = {"PASSWORD": "secret", "Token": "abc", "API_KEY": "xyz"}
        result = sanitize_dict(data)

        assert result["PASSWORD"] == "***"
        assert result["Token"] == "***"
        assert result["API_KEY"] == "***"


class TestSanitizingFilter:
    """Testes para o filtro de sanitização de logs."""

    def test_sanitizes_jwt_token(self):
        """Verifica que JWT tokens são sanitizados."""
        filter_instance = SanitizingFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Received JWT eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.abc123",
            args=(),
            exc_info=None,
        )

        filter_instance.filter(record)
        assert "[JWT_TOKEN]" in record.msg
        assert "eyJhbG" not in record.msg

    def test_sanitizes_bearer_token(self):
        """Verifica que Bearer tokens são sanitizados."""
        filter_instance = SanitizingFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Authorization: Bearer abc123xyz",
            args=(),
            exc_info=None,
        )

        filter_instance.filter(record)
        assert "Bearer [TOKEN]" in record.msg
        assert "abc123xyz" not in record.msg

    def test_sanitizes_password_in_message(self):
        """Verifica que senha em mensagem é sanitizada."""
        filter_instance = SanitizingFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Login attempt with password=secret123",
            args=(),
            exc_info=None,
        )

        filter_instance.filter(record)
        assert "[REDACTED]" in record.msg
        assert "secret123" not in record.msg

    def test_preserves_normal_messages(self):
        """Verifica que mensagens normais são preservadas."""
        filter_instance = SanitizingFilter()
        original_msg = "User logged in successfully"
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg=original_msg,
            args=(),
            exc_info=None,
        )

        filter_instance.filter(record)
        assert record.msg == original_msg

    def test_sanitizes_args(self):
        """Verifica que args também são sanitizados."""
        filter_instance = SanitizingFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Processing %s",
            args=("token=abc123secret",),
            exc_info=None,
        )

        filter_instance.filter(record)
        assert "[REDACTED]" in record.args[0]


class TestSensitiveKeys:
    """Testes para verificar que chaves sensíveis estão definidas."""

    def test_common_sensitive_keys_defined(self):
        """Verifica que chaves comuns estão na lista."""
        expected_keys = ["password", "senha", "token", "secret", "api_key"]
        for key in expected_keys:
            assert key in SENSITIVE_KEYS

    def test_jwt_keys_defined(self):
        """Verifica que chaves JWT estão na lista."""
        jwt_keys = ["access_token", "refresh_token", "jwt"]
        for key in jwt_keys:
            assert key in SENSITIVE_KEYS


class TestSensitivePatterns:
    """Testes para verificar padrões de sanitização."""

    def test_patterns_defined(self):
        """Verifica que padrões estão definidos."""
        assert len(SENSITIVE_PATTERNS) >= 3

    def test_jwt_pattern_matches(self):
        """Verifica que padrão JWT funciona."""
        jwt = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.Rq8IjqbeP"
        pattern, replacement = SENSITIVE_PATTERNS[0]
        result = pattern.sub(replacement, jwt)
        assert result == "[JWT_TOKEN]"

    def test_bearer_pattern_matches(self):
        """Verifica que padrão Bearer funciona."""
        bearer = "Bearer abc123xyz"
        pattern, replacement = SENSITIVE_PATTERNS[1]
        result = pattern.sub(replacement, bearer)
        assert result == "Bearer [TOKEN]"
