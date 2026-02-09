"""
Testes para o script seed.py.

Valida validacao de entrada e comportamento basico.
NOTA: Testes de criacao de admin dependem de bcrypt que pode ter
problemas de compatibilidade em algumas versoes do Python.
"""
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.orm import Session

# Importar o modulo seed para poder mockar corretamente
import seed as seed_module
from config.defaults import DEFAULT_ADMIN_EMAIL, DEFAULT_ADMIN_NAME, MIN_PASSWORD_LENGTH
from models import Usuario


class TestSeedValidation:
    """Testes de validacao de entrada do seed."""

    def _mock_getenv(self, env_dict):
        """Helper para criar mock de os.getenv com valores especificos."""
        def mock_getenv(key, default=None):
            return env_dict.get(key, default)
        return mock_getenv

    def test_seed_requires_password(self, db_session: Session):
        """Seed deve rejeitar quando senha nao esta definida."""
        env = {
            "ADMIN_EMAIL": "admin@nopass.com",
            "ADMIN_NAME": "Admin NoPass"
            # Sem ADMIN_PASSWORD
        }
        with patch.object(seed_module.os, 'getenv', self._mock_getenv(env)):
            with patch.object(seed_module, 'SessionLocal', return_value=db_session):
                db_session.close = MagicMock()  # type: ignore[method-assign]

                seed_module.create_admin()

                admin = db_session.query(Usuario).filter(
                    Usuario.email == "admin@nopass.com"
                ).first()

                # Sem senha = nao cria admin
                assert admin is None

    def test_seed_requires_strong_password(self, db_session: Session):
        """Seed deve rejeitar senha fraca (menos de 8 caracteres)."""
        env = {
            "ADMIN_EMAIL": "admin@weakpass.com",
            "ADMIN_PASSWORD": "1234567",  # 7 caracteres
            "ADMIN_NAME": "Admin WeakPass"
        }
        with patch.object(seed_module.os, 'getenv', self._mock_getenv(env)):
            with patch.object(seed_module, 'SessionLocal', return_value=db_session):
                db_session.close = MagicMock()  # type: ignore[method-assign]

                seed_module.create_admin()

                admin = db_session.query(Usuario).filter(
                    Usuario.email == "admin@weakpass.com"
                ).first()

                # Senha muito curta = nao cria admin
                assert admin is None


class TestSeedDefaults:
    """Testes para valores default do seed."""

    def test_default_admin_email_constant(self):
        """Verifica que o default de email esta correto."""
        assert DEFAULT_ADMIN_EMAIL == "admin@licitafacil.com.br"

    def test_default_admin_name_constant(self):
        """Verifica que o default de nome esta correto."""
        assert DEFAULT_ADMIN_NAME == "Administrador"

    def test_min_password_length_constant(self):
        """Verifica que o comprimento minimo de senha esta correto."""
        assert MIN_PASSWORD_LENGTH == 8


class TestPasswordHash:
    """Testes para funcao de hash de senha."""

    def test_get_password_hash_returns_string(self):
        """get_password_hash deve retornar uma string."""
        # Pular se bcrypt nao funcionar
        try:
            result = seed_module.get_password_hash("testpassword")
            assert isinstance(result, str)
            assert len(result) > 0
        except Exception as e:
            if "72 bytes" in str(e):
                pytest.skip("bcrypt tem problema de compatibilidade neste ambiente")
            raise

    def test_get_password_hash_bcrypt_format(self):
        """Hash deve estar no formato bcrypt ($2...)."""
        try:
            result = seed_module.get_password_hash("testpassword")
            assert result.startswith("$2")
        except Exception as e:
            if "72 bytes" in str(e):
                pytest.skip("bcrypt tem problema de compatibilidade neste ambiente")
            raise

    def test_get_password_hash_not_plaintext(self):
        """Hash nao deve ser igual a senha original."""
        try:
            password = "testpassword"
            result = seed_module.get_password_hash(password)
            assert result != password
        except Exception as e:
            if "72 bytes" in str(e):
                pytest.skip("bcrypt tem problema de compatibilidade neste ambiente")
            raise
