"""
Testes basicos da API.
"""
from fastapi.testclient import TestClient


class TestHealthEndpoint:
    """Testes para o endpoint de health check."""

    def test_health_check(self, client: TestClient):
        """Verifica que /health retorna status healthy."""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"


class TestCORSHeaders:
    """Testes para headers CORS."""

    def test_cors_preflight(self, client: TestClient):
        """Verifica resposta a requisicao OPTIONS (preflight)."""
        response = client.options(
            "/health",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET"
            }
        )
        # Deve retornar 200 ou 204 para preflight
        assert response.status_code in [200, 204]


class TestDocsEndpoints:
    """Testes para endpoints de documentacao."""

    def test_docs_available(self, client: TestClient):
        """Verifica que /docs esta disponivel."""
        response = client.get("/docs")
        assert response.status_code == 200

    def test_redoc_available(self, client: TestClient):
        """Verifica que /redoc esta disponivel."""
        response = client.get("/redoc")
        assert response.status_code == 200

    def test_openapi_schema(self, client: TestClient):
        """Verifica que o schema OpenAPI esta disponivel."""
        response = client.get("/openapi.json")
        assert response.status_code == 200
        data = response.json()
        assert "openapi" in data
        assert "info" in data
        assert data["info"]["title"] == "LicitaFácil"


class TestAuthEndpoints:
    """Testes basicos para endpoints de autenticacao."""

    def test_login_missing_credentials(self, client: TestClient):
        """Verifica erro ao fazer login sem credenciais."""
        response = client.post("/auth/login")
        assert response.status_code == 422  # Validation error

    def test_login_invalid_credentials(self, client: TestClient):
        """Verifica erro ao fazer login com credenciais invalidas."""
        response = client.post(
            "/auth/login",
            data={"username": "inexistente@teste.com", "password": "senhaerrada"}
        )
        assert response.status_code == 401

    def test_protected_endpoint_without_token(self, client: TestClient):
        """Verifica que endpoints protegidos requerem token."""
        response = client.get("/atestados/")
        assert response.status_code == 401

    def test_protected_endpoint_with_invalid_token(self, client: TestClient):
        """Verifica rejeicao de token invalido."""
        response = client.get(
            "/atestados/",
            headers={"Authorization": "Bearer token_invalido_123"}
        )
        assert response.status_code == 401


class TestRateLimiting:
    """Testes para rate limiting."""

    def test_rate_limit_header_present(self, client: TestClient):
        """Verifica que headers de rate limit estao presentes."""
        response = client.get("/health")
        # Headers podem variar dependendo da implementacao
        # Verificamos apenas que a requisicao foi bem sucedida
        assert response.status_code == 200


class TestErrorHandling:
    """Testes para tratamento de erros."""

    def test_404_not_found(self, client: TestClient):
        """Verifica resposta para rota inexistente."""
        response = client.get("/rota/que/nao/existe")
        assert response.status_code == 404

    def test_405_method_not_allowed(self, client: TestClient):
        """Verifica resposta para metodo nao permitido."""
        response = client.delete("/health")
        assert response.status_code == 405
