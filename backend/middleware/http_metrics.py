"""
Middleware para coletar métricas HTTP com Prometheus.

Registra automaticamente todas as requisições HTTP com:
- Método (GET, POST, etc.)
- Endpoint (normalizado para evitar alta cardinalidade)
- Status code
- Duração da requisição
"""
import time
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from services.metrics import record_http_request


class HTTPMetricsMiddleware(BaseHTTPMiddleware):
    """Middleware para coletar métricas HTTP automaticamente."""

    # Paths a ignorar para não poluir métricas
    IGNORED_PATHS = {
        "/metrics",
        "/health",
        "/favicon.ico",
    }

    async def dispatch(self, request: Request, call_next) -> Response:
        # Ignorar paths que não devem ser rastreados
        if request.url.path in self.IGNORED_PATHS:
            return await call_next(request)

        start_time = time.perf_counter()

        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception:
            # Em caso de exceção não tratada, registrar como 500
            status_code = 500
            raise
        finally:
            duration = time.perf_counter() - start_time
            record_http_request(
                method=request.method,
                endpoint=request.url.path,
                status_code=status_code,
                duration_seconds=duration
            )

        return response
