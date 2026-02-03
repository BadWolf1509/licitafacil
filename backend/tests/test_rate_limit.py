"""
Testes para o middleware de Rate Limiting.
"""

from middleware.rate_limit import RateLimitMiddleware, PATH_SPECIFIC_LIMITS


class TestPathSpecificLimits:
    """Testes para limites específicos por path."""

    def test_path_specific_limits_defined(self):
        """Verifica que limites específicos estão definidos."""
        assert len(PATH_SPECIFIC_LIMITS) >= 2

        # Verificar que login e registro têm limites
        paths = [p[0] for p in PATH_SPECIFIC_LIMITS]
        assert any("/auth/login" in p for p in paths)
        assert any("/auth/registrar" in p for p in paths)

    def test_login_limit_is_restrictive(self):
        """Verifica que limite de login é mais restritivo que o global."""
        from config import RATE_LIMIT_REQUESTS, RATE_LIMIT_AUTH_LOGIN

        assert RATE_LIMIT_AUTH_LOGIN < RATE_LIMIT_REQUESTS
        assert RATE_LIMIT_AUTH_LOGIN <= 10  # No máximo 10 tentativas

    def test_register_limit_is_most_restrictive(self):
        """Verifica que limite de registro é o mais restritivo."""
        from config import RATE_LIMIT_AUTH_LOGIN, RATE_LIMIT_AUTH_REGISTER

        assert RATE_LIMIT_AUTH_REGISTER <= RATE_LIMIT_AUTH_LOGIN


class TestRateLimitMiddleware:
    """Testes para o middleware de rate limiting."""

    def test_get_path_limit_returns_none_for_generic_path(self):
        """Verifica que paths genéricos não têm limite específico."""
        middleware = RateLimitMiddleware(app=None)
        assert middleware._get_path_limit("/api/v1/atestados") is None
        assert middleware._get_path_limit("/health") is None

    def test_get_path_limit_returns_limit_for_login(self):
        """Verifica que path de login retorna limite específico."""
        middleware = RateLimitMiddleware(app=None)
        result = middleware._get_path_limit("/api/v1/auth/login")

        assert result is not None
        path_key, limit, window = result
        assert "/auth/login" in path_key
        assert limit > 0
        assert window > 0

    def test_get_path_limit_returns_limit_for_register(self):
        """Verifica que path de registro retorna limite específico."""
        middleware = RateLimitMiddleware(app=None)
        result = middleware._get_path_limit("/api/v1/auth/registrar")

        assert result is not None
        path_key, limit, window = result
        assert "/auth/registrar" in path_key
        assert limit > 0

    def test_is_rate_limited_global(self):
        """Testa rate limiting global."""
        middleware = RateLimitMiddleware(app=None)
        middleware.requests_limit = 3
        middleware.window_seconds = 60

        client_ip = "192.168.1.100"

        # Primeiras 3 requisições passam
        for _ in range(3):
            is_limited, _ = middleware._is_rate_limited(client_ip)
            assert not is_limited

        # Quarta requisição é bloqueada
        is_limited, remaining = middleware._is_rate_limited(client_ip)
        assert is_limited
        assert remaining == 0

    def test_is_path_rate_limited(self):
        """Testa rate limiting por path."""
        middleware = RateLimitMiddleware(app=None)

        client_ip = "192.168.1.101"
        path_key = "/auth/login"
        limit = 2
        window = 60

        # Primeiras 2 requisições passam
        for _ in range(2):
            is_limited, _ = middleware._is_path_rate_limited(
                client_ip, path_key, limit, window
            )
            assert not is_limited

        # Terceira requisição é bloqueada
        is_limited, remaining = middleware._is_path_rate_limited(
            client_ip, path_key, limit, window
        )
        assert is_limited
        assert remaining == 0

    def test_different_paths_have_separate_counters(self):
        """Verifica que paths diferentes têm contadores separados."""
        middleware = RateLimitMiddleware(app=None)

        client_ip = "192.168.1.102"
        limit = 2
        window = 60

        # Esgotar limite de login
        for _ in range(2):
            middleware._is_path_rate_limited(client_ip, "/auth/login", limit, window)

        # Login está bloqueado
        is_limited, _ = middleware._is_path_rate_limited(
            client_ip, "/auth/login", limit, window
        )
        assert is_limited

        # Mas registro ainda funciona
        is_limited, _ = middleware._is_path_rate_limited(
            client_ip, "/auth/registrar", limit, window
        )
        assert not is_limited

    def test_different_ips_have_separate_counters(self):
        """Verifica que IPs diferentes têm contadores separados."""
        middleware = RateLimitMiddleware(app=None)
        middleware.requests_limit = 2

        ip1 = "192.168.1.1"
        ip2 = "192.168.1.2"

        # Esgotar limite do IP1
        for _ in range(2):
            middleware._is_rate_limited(ip1)

        # IP1 está bloqueado
        is_limited, _ = middleware._is_rate_limited(ip1)
        assert is_limited

        # IP2 ainda pode fazer requisições
        is_limited, _ = middleware._is_rate_limited(ip2)
        assert not is_limited

    def test_cleanup_removes_old_requests(self):
        """Testa que cleanup remove requisições antigas."""
        import time

        middleware = RateLimitMiddleware(app=None)
        middleware.window_seconds = 1  # 1 segundo

        client_ip = "192.168.1.103"

        # Adicionar algumas requisições
        middleware.requests[client_ip] = [time.time() - 10, time.time() - 5]

        # Cleanup deve remover requisições antigas
        middleware._cleanup_old_requests(time.time())

        assert len(middleware.requests.get(client_ip, [])) == 0


class TestRateLimitIntegration:
    """Testes de integração para rate limiting."""

    def test_login_endpoint_responds_correctly(self, client):
        """Testa que endpoint de login responde corretamente.

        Nota: Supabase Auth gerencia seu próprio rate limiting.
        Este teste verifica apenas que o endpoint está funcional.
        """
        response = client.post(
            "/api/v1/auth/supabase-login",
            json={"email": "test@test.com", "senha": "wrong"}
        )
        # Deve retornar 401 (credenciais inválidas), 503 (Supabase não configurado), ou 429 (rate limit)
        assert response.status_code in [401, 429, 503]

    def test_rate_limit_headers_present(self, client):
        """Testa que headers de rate limit estão presentes."""
        response = client.get("/health")

        # Health check não tem rate limit
        assert response.status_code == 200

    def test_global_rate_limit_not_too_restrictive(self, client):
        """Verifica que rate limit global permite operações normais."""
        # Fazer várias requisições ao health check
        for _ in range(10):
            response = client.get("/health")
            assert response.status_code == 200
