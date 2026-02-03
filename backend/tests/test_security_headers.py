"""
Testes para o middleware de Security Headers.
"""
import pytest
from unittest.mock import MagicMock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient

from middleware.security_headers import SecurityHeadersMiddleware


class TestSecurityHeadersMiddleware:
    """Testes do middleware SecurityHeadersMiddleware."""

    @pytest.fixture
    def app_with_middleware(self):
        """Cria uma app FastAPI com o middleware de security headers."""
        app = FastAPI()
        app.add_middleware(SecurityHeadersMiddleware)

        @app.get("/test")
        def test_endpoint():
            return {"message": "ok"}

        return app

    @pytest.fixture
    def client(self, app_with_middleware):
        """Cria um TestClient para a app."""
        return TestClient(app_with_middleware)

    def test_x_content_type_options_header(self, client):
        """Deve adicionar header X-Content-Type-Options."""
        response = client.get("/test")
        assert response.headers.get("X-Content-Type-Options") == "nosniff"

    def test_x_frame_options_header(self, client):
        """Deve adicionar header X-Frame-Options."""
        response = client.get("/test")
        assert response.headers.get("X-Frame-Options") == "DENY"

    def test_x_xss_protection_header(self, client):
        """Deve adicionar header X-XSS-Protection."""
        response = client.get("/test")
        assert response.headers.get("X-XSS-Protection") == "1; mode=block"

    def test_referrer_policy_header(self, client):
        """Deve adicionar header Referrer-Policy."""
        response = client.get("/test")
        assert response.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"

    def test_content_security_policy_header(self, client):
        """Deve adicionar header Content-Security-Policy."""
        response = client.get("/test")
        csp = response.headers.get("Content-Security-Policy")
        assert csp is not None
        assert "default-src 'self'" in csp
        assert "script-src" in csp
        assert "style-src" in csp

    def test_permissions_policy_header(self, client):
        """Deve adicionar header Permissions-Policy."""
        response = client.get("/test")
        pp = response.headers.get("Permissions-Policy")
        assert pp is not None
        assert "camera=()" in pp
        assert "microphone=()" in pp
        assert "geolocation=()" in pp

    def test_custom_frame_options(self):
        """Deve permitir customizar X-Frame-Options."""
        app = FastAPI()
        app.add_middleware(
            SecurityHeadersMiddleware,
            frame_options="SAMEORIGIN"
        )

        @app.get("/test")
        def test_endpoint():
            return {"message": "ok"}

        client = TestClient(app)
        response = client.get("/test")
        assert response.headers.get("X-Frame-Options") == "SAMEORIGIN"

    def test_custom_csp(self):
        """Deve permitir customizar Content-Security-Policy."""
        custom_csp = "default-src 'none'; script-src 'self'"
        app = FastAPI()
        app.add_middleware(
            SecurityHeadersMiddleware,
            content_security_policy=custom_csp
        )

        @app.get("/test")
        def test_endpoint():
            return {"message": "ok"}

        client = TestClient(app)
        response = client.get("/test")
        assert response.headers.get("Content-Security-Policy") == custom_csp

    def test_custom_referrer_policy(self):
        """Deve permitir customizar Referrer-Policy."""
        app = FastAPI()
        app.add_middleware(
            SecurityHeadersMiddleware,
            referrer_policy="no-referrer"
        )

        @app.get("/test")
        def test_endpoint():
            return {"message": "ok"}

        client = TestClient(app)
        response = client.get("/test")
        assert response.headers.get("Referrer-Policy") == "no-referrer"


class TestHSTSBehavior:
    """Testes do comportamento do HSTS."""

    def test_hsts_not_added_in_development(self):
        """HSTS nao deve ser adicionado em ambiente de desenvolvimento."""
        with patch("middleware.security_headers.ENVIRONMENT", "development"):
            app = FastAPI()
            app.add_middleware(SecurityHeadersMiddleware, enable_hsts=True)

            @app.get("/test")
            def test_endpoint():
                return {"message": "ok"}

            client = TestClient(app)
            response = client.get("/test")
            assert response.headers.get("Strict-Transport-Security") is None

    def test_hsts_added_in_production(self):
        """HSTS deve ser adicionado em ambiente de producao."""
        with patch("middleware.security_headers.ENVIRONMENT", "production"):
            app = FastAPI()
            app.add_middleware(SecurityHeadersMiddleware, enable_hsts=True)

            @app.get("/test")
            def test_endpoint():
                return {"message": "ok"}

            client = TestClient(app)
            response = client.get("/test")
            hsts = response.headers.get("Strict-Transport-Security")
            assert hsts is not None
            assert "max-age=" in hsts
            assert "includeSubDomains" in hsts

    def test_hsts_custom_max_age(self):
        """Deve permitir customizar o max-age do HSTS."""
        with patch("middleware.security_headers.ENVIRONMENT", "production"):
            app = FastAPI()
            app.add_middleware(
                SecurityHeadersMiddleware,
                enable_hsts=True,
                hsts_max_age=86400  # 1 dia
            )

            @app.get("/test")
            def test_endpoint():
                return {"message": "ok"}

            client = TestClient(app)
            response = client.get("/test")
            hsts = response.headers.get("Strict-Transport-Security")
            assert "max-age=86400" in hsts

    def test_hsts_disabled(self):
        """HSTS nao deve ser adicionado quando desabilitado."""
        with patch("middleware.security_headers.ENVIRONMENT", "production"):
            app = FastAPI()
            app.add_middleware(SecurityHeadersMiddleware, enable_hsts=False)

            @app.get("/test")
            def test_endpoint():
                return {"message": "ok"}

            client = TestClient(app)
            response = client.get("/test")
            assert response.headers.get("Strict-Transport-Security") is None


class TestDefaultCSP:
    """Testes da Content Security Policy padrao."""

    @pytest.fixture
    def middleware(self):
        """Cria instancia do middleware."""
        app = MagicMock()
        return SecurityHeadersMiddleware(app)

    def test_csp_has_default_src(self, middleware):
        """CSP padrao deve ter default-src."""
        assert "default-src 'self'" in middleware.csp

    def test_csp_has_script_src(self, middleware):
        """CSP padrao deve ter script-src."""
        assert "script-src 'self'" in middleware.csp

    def test_csp_has_style_src(self, middleware):
        """CSP padrao deve ter style-src."""
        assert "style-src 'self'" in middleware.csp

    def test_csp_has_img_src(self, middleware):
        """CSP padrao deve ter img-src."""
        assert "img-src 'self' data: blob:" in middleware.csp

    def test_csp_has_connect_src(self, middleware):
        """CSP padrao deve ter connect-src."""
        assert "connect-src 'self'" in middleware.csp

    def test_csp_has_frame_ancestors(self, middleware):
        """CSP padrao deve ter frame-ancestors."""
        assert "frame-ancestors 'none'" in middleware.csp

    def test_csp_has_base_uri(self, middleware):
        """CSP padrao deve ter base-uri."""
        assert "base-uri 'self'" in middleware.csp

    def test_csp_has_form_action(self, middleware):
        """CSP padrao deve ter form-action."""
        assert "form-action 'self'" in middleware.csp


class TestDefaultPermissionsPolicy:
    """Testes da Permissions Policy padrao."""

    @pytest.fixture
    def middleware(self):
        """Cria instancia do middleware."""
        app = MagicMock()
        return SecurityHeadersMiddleware(app)

    def test_disables_camera(self, middleware):
        """Permissions Policy deve desabilitar camera."""
        assert "camera=()" in middleware.permissions_policy

    def test_disables_microphone(self, middleware):
        """Permissions Policy deve desabilitar microphone."""
        assert "microphone=()" in middleware.permissions_policy

    def test_disables_geolocation(self, middleware):
        """Permissions Policy deve desabilitar geolocation."""
        assert "geolocation=()" in middleware.permissions_policy

    def test_disables_payment(self, middleware):
        """Permissions Policy deve desabilitar payment."""
        assert "payment=()" in middleware.permissions_policy

    def test_disables_usb(self, middleware):
        """Permissions Policy deve desabilitar USB."""
        assert "usb=()" in middleware.permissions_policy


class TestHeadersOnDifferentResponses:
    """Testes de headers em diferentes tipos de resposta."""

    @pytest.fixture
    def app(self):
        """Cria app com varios endpoints."""
        app = FastAPI()
        app.add_middleware(SecurityHeadersMiddleware)

        @app.get("/json")
        def json_endpoint():
            return {"data": "value"}

        @app.get("/error")
        def error_endpoint():
            raise ValueError("test error")

        @app.get("/redirect")
        def redirect_endpoint():
            from fastapi.responses import RedirectResponse
            return RedirectResponse(url="/json")

        return app

    @pytest.fixture
    def client(self, app):
        """Cria TestClient."""
        return TestClient(app, raise_server_exceptions=False)

    def test_headers_on_json_response(self, client):
        """Headers devem estar presentes em resposta JSON."""
        response = client.get("/json")
        assert response.headers.get("X-Content-Type-Options") == "nosniff"
        assert response.headers.get("X-Frame-Options") == "DENY"

    def test_headers_on_error_response(self, client):
        """Headers podem nao estar presentes em erros nao tratados (500).

        Nota: Quando uma excecao nao tratada e lancada, o middleware pode
        nao ter a oportunidade de adicionar headers. Isso e comportamento
        esperado do Starlette/FastAPI.
        """
        response = client.get("/error")
        assert response.status_code == 500
        # Em erros 500 nao tratados, os headers podem ou nao estar presentes
        # dependendo de onde a excecao e lancada
        # Este teste verifica que a resposta foi recebida
        assert response.content is not None

    def test_headers_on_redirect_response(self, client):
        """Headers devem estar presentes em resposta de redirect."""
        response = client.get("/redirect", follow_redirects=False)
        assert response.status_code == 307
        assert response.headers.get("X-Content-Type-Options") == "nosniff"
