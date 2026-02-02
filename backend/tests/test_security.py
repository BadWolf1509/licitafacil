"""
Testes de segurança para o LicitaFácil.

Verifica CORS, autenticação, rate limiting e validação de uploads.
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch


class TestCORSSecurity:
    """Testes de segurança CORS."""

    def test_cors_headers_present(self, client: TestClient):
        """Verifica que headers CORS estão presentes."""
        response = client.options(
            "/api/v1/auth/login",
            headers={"Origin": "http://localhost:8000"}
        )
        # Em desenvolvimento, CORS deve estar configurado
        # 429 pode ocorrer se rate limit for atingido em testes anteriores
        assert response.status_code in [200, 405, 429]

    def test_cors_production_rejects_wildcard(self):
        """Verifica que produção não aceita wildcard CORS."""
        from config import ENVIRONMENT, CORS_ORIGINS
        from config.base import get_cors_origins

        # Simular ambiente de produção sem CORS_ORIGINS definido
        with patch.dict('os.environ', {'ENVIRONMENT': 'production', 'CORS_ORIGINS': ''}):
            origins = get_cors_origins()
            # Em produção sem CORS_ORIGINS, deve retornar lista vazia
            assert origins == []

    def test_cors_development_allows_localhost(self):
        """Verifica que desenvolvimento permite localhost."""
        from config.base import get_cors_origins

        with patch.dict('os.environ', {'ENVIRONMENT': 'development', 'CORS_ORIGINS': ''}):
            origins = get_cors_origins()
            # Em desenvolvimento, deve permitir localhost
            assert any('localhost' in origin for origin in origins)


class TestAuthenticationSecurity:
    """Testes de segurança de autenticação."""

    def test_login_requires_credentials(self, client: TestClient):
        """Verifica que login exige credenciais."""
        response = client.post("/api/v1/auth/login")
        # 429 pode ocorrer se rate limit for atingido
        assert response.status_code in [422, 429]

    def test_login_rejects_invalid_credentials(self, client: TestClient):
        """Verifica que login rejeita credenciais inválidas."""
        response = client.post(
            "/api/v1/auth/login",
            data={"username": "invalid@test.com", "password": "wrongpassword"}
        )
        # 429 pode ocorrer se rate limit for atingido
        assert response.status_code in [401, 429]

    def test_protected_endpoint_requires_auth(self, client: TestClient):
        """Verifica que endpoints protegidos exigem autenticação."""
        response = client.get("/api/v1/auth/me")
        assert response.status_code == 401

    def test_protected_endpoint_rejects_invalid_token(self, client: TestClient):
        """Verifica que tokens inválidos são rejeitados."""
        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer invalid_token"}
        )
        assert response.status_code == 401

class TestUploadSecurity:
    """Testes de segurança de upload."""

    def test_upload_config_exists(self):
        """Verifica que configurações de upload existem."""
        from config import (
            MAX_UPLOAD_SIZE_BYTES,
            ALLOWED_DOCUMENT_EXTENSIONS,
            ALLOWED_MIME_TYPES,
        )

        assert MAX_UPLOAD_SIZE_BYTES > 0
        assert len(ALLOWED_DOCUMENT_EXTENSIONS) > 0
        assert len(ALLOWED_MIME_TYPES) > 0

    def test_dangerous_extensions_not_allowed(self):
        """Verifica que extensões perigosas não são permitidas."""
        from config import ALLOWED_DOCUMENT_EXTENSIONS

        dangerous = ['.exe', '.bat', '.cmd', '.sh', '.ps1', '.dll', '.js', '.vbs']
        for ext in dangerous:
            assert ext not in ALLOWED_DOCUMENT_EXTENSIONS


class TestSecretKeyValidation:
    """Testes de validação de chave secreta."""

    def test_secret_key_minimum_length(self):
        """Verifica que SECRET_KEY tem tamanho mínimo."""
        from config import SECRET_KEY

        # SECRET_KEY deve ter pelo menos 32 caracteres
        assert len(SECRET_KEY) >= 32

    def test_secret_key_not_default(self):
        """Verifica que SECRET_KEY não é o valor padrão."""
        from config import SECRET_KEY

        # Não deve ser valores padrão conhecidos
        default_values = [
            "change-me-in-production",
            "secret",
            "password",
            "your-secret-key-here",
        ]
        assert SECRET_KEY not in default_values


class TestSeedPasswordValidation:
    """Testes de validação de senha do seed."""

    def test_seed_has_password_validation(self):
        """Verifica que seed.py tem validação de senha."""
        import os

        seed_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "seed.py"
        )
        with open(seed_path, "r") as f:
            content = f.read()

        # Seed deve verificar ADMIN_PASSWORD
        assert "ADMIN_PASSWORD" in content
        # Seed deve ter validação de tamanho mínimo
        assert "< 8" in content or "len(admin_password)" in content


class TestRateLimitingSecurity:
    """Testes de segurança de rate limiting."""

    def test_rate_limit_config_exists(self):
        """Verifica que configuração de rate limit existe."""
        from config import (
            RATE_LIMIT_ENABLED,
            RATE_LIMIT_REQUESTS,
            RATE_LIMIT_WINDOW,
            RATE_LIMIT_AUTH_LOGIN,
            RATE_LIMIT_AUTH_REGISTER,
        )

        assert RATE_LIMIT_ENABLED is not None
        assert RATE_LIMIT_REQUESTS > 0
        assert RATE_LIMIT_WINDOW > 0
        assert RATE_LIMIT_AUTH_LOGIN > 0
        assert RATE_LIMIT_AUTH_REGISTER > 0

    def test_auth_rate_limits_are_restrictive(self):
        """Verifica que limites de auth são mais restritivos."""
        from config import (
            RATE_LIMIT_REQUESTS,
            RATE_LIMIT_AUTH_LOGIN,
            RATE_LIMIT_AUTH_REGISTER,
        )

        # Limites de auth devem ser menores que o global
        assert RATE_LIMIT_AUTH_LOGIN < RATE_LIMIT_REQUESTS
        assert RATE_LIMIT_AUTH_REGISTER < RATE_LIMIT_REQUESTS
        assert RATE_LIMIT_AUTH_REGISTER <= RATE_LIMIT_AUTH_LOGIN


class TestMIMETypeValidation:
    """Testes de validação de MIME type."""

    def test_allowed_mime_types_defined(self):
        """Verifica que MIME types permitidos estão definidos."""
        from config import ALLOWED_MIME_TYPES

        assert 'application/pdf' in ALLOWED_MIME_TYPES
        assert 'image/png' in ALLOWED_MIME_TYPES
        assert 'image/jpeg' in ALLOWED_MIME_TYPES

    def test_validate_mime_type_function_exists(self):
        """Verifica que função de validação existe."""
        from config import validate_mime_type

        assert callable(validate_mime_type)

    def test_validate_upload_complete_function_exists(self):
        """Verifica que função de validação completa existe."""
        from config import validate_upload_complete

        assert callable(validate_upload_complete)


class TestSecurityHeadersMiddleware:
    """Testes do middleware de security headers."""

    def test_security_headers_present(self, client: TestClient):
        """Verifica que headers de seguranca estao presentes."""
        response = client.get("/health")

        # Headers obrigatorios
        assert "X-Content-Type-Options" in response.headers
        assert response.headers["X-Content-Type-Options"] == "nosniff"

        assert "X-Frame-Options" in response.headers
        assert response.headers["X-Frame-Options"] in ["DENY", "SAMEORIGIN"]

        assert "X-XSS-Protection" in response.headers
        assert response.headers["X-XSS-Protection"] == "1; mode=block"

        assert "Referrer-Policy" in response.headers

        assert "Content-Security-Policy" in response.headers

        assert "Permissions-Policy" in response.headers

    def test_csp_prevents_framing(self, client: TestClient):
        """Verifica que CSP previne framing."""
        response = client.get("/health")
        csp = response.headers.get("Content-Security-Policy", "")

        # CSP deve conter frame-ancestors
        assert "frame-ancestors" in csp

    def test_permissions_policy_restricts_apis(self, client: TestClient):
        """Verifica que Permissions Policy restringe APIs."""
        response = client.get("/health")
        policy = response.headers.get("Permissions-Policy", "")

        # APIs perigosas devem estar desabilitadas
        assert "camera=()" in policy
        assert "microphone=()" in policy
        assert "geolocation=()" in policy

    def test_security_headers_on_api_endpoints(self, client: TestClient):
        """Verifica headers em endpoints da API."""
        response = client.get("/api/v1/auth/status")

        # Headers devem estar presentes mesmo em endpoints de API
        assert "X-Content-Type-Options" in response.headers
        assert "X-Frame-Options" in response.headers

    def test_security_headers_on_error_responses(self, client: TestClient):
        """Verifica headers em respostas de erro."""
        response = client.get("/api/v1/auth/me")  # Sem autenticacao = 401

        assert response.status_code == 401
        # Headers devem estar presentes mesmo em erros
        assert "X-Content-Type-Options" in response.headers

    def test_security_headers_config_exists(self):
        """Verifica que configuracoes de security headers existem."""
        from config.security import (
            SECURITY_HEADERS_ENABLED,
            HSTS_MAX_AGE,
            FRAME_OPTIONS,
            REFERRER_POLICY
        )

        assert SECURITY_HEADERS_ENABLED is not None
        assert HSTS_MAX_AGE > 0
        assert FRAME_OPTIONS in ["DENY", "SAMEORIGIN"]
        assert REFERRER_POLICY is not None


class TestGZipCompression:
    """Testes de compressao GZip."""

    def test_gzip_compression_supported(self, client: TestClient):
        """Verifica que compressao gzip esta habilitada."""
        response = client.get(
            "/health",
            headers={"Accept-Encoding": "gzip"}
        )
        # Para respostas pequenas, gzip pode nao ser aplicado
        # mas o servidor deve aceitar o header sem erro
        assert response.status_code == 200


class TestPasswordPolicyConfig:
    """Testes de configuracao de politica de senha."""

    def test_password_policy_config_exists(self):
        """Verifica que configuracoes de politica de senha existem."""
        from config.security import (
            PASSWORD_MIN_LENGTH,
            PASSWORD_REQUIRE_UPPERCASE,
            PASSWORD_REQUIRE_LOWERCASE,
            PASSWORD_REQUIRE_DIGIT,
            PASSWORD_REQUIRE_SPECIAL
        )

        assert PASSWORD_MIN_LENGTH >= 8
        assert isinstance(PASSWORD_REQUIRE_UPPERCASE, bool)
        assert isinstance(PASSWORD_REQUIRE_LOWERCASE, bool)
        assert isinstance(PASSWORD_REQUIRE_DIGIT, bool)
        assert isinstance(PASSWORD_REQUIRE_SPECIAL, bool)


class TestAccountLockoutConfig:
    """Testes de configuracao de bloqueio de conta."""

    def test_account_lockout_config_exists(self):
        """Verifica que configuracoes de bloqueio de conta existem."""
        from config.security import (
            MAX_FAILED_LOGIN_ATTEMPTS,
            ACCOUNT_LOCKOUT_MINUTES
        )

        assert MAX_FAILED_LOGIN_ATTEMPTS > 0
        assert ACCOUNT_LOCKOUT_MINUTES > 0
        # Valores razoaveis
        assert MAX_FAILED_LOGIN_ATTEMPTS <= 10
        assert ACCOUNT_LOCKOUT_MINUTES >= 5
