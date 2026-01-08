"""
Middleware de Rate Limiting para proteção contra abuso.

Limita o número de requisições por IP em uma janela de tempo.
"""
import time
from collections import defaultdict
from typing import Callable, Dict, Optional, Tuple
from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from config import RATE_LIMIT_ENABLED, RATE_LIMIT_REQUESTS, RATE_LIMIT_WINDOW, Messages
from logging_config import get_logger

logger = get_logger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Middleware que implementa rate limiting por IP.

    Usa um algoritmo de janela deslizante simples.
    """

    def __init__(self, app, requests_limit: Optional[int] = None, window_seconds: Optional[int] = None):
        super().__init__(app)
        self.requests_limit = requests_limit or RATE_LIMIT_REQUESTS
        self.window_seconds = window_seconds or RATE_LIMIT_WINDOW
        self.requests: Dict[str, list] = defaultdict(list)
        self._cleanup_counter = 0

    def _get_client_ip(self, request: Request) -> str:
        """Obtém o IP do cliente, considerando proxies."""
        # Verificar headers de proxy
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()

        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip

        # Fallback para IP direto
        return request.client.host if request.client else "unknown"

    def _cleanup_old_requests(self, current_time: float):
        """Remove requisições antigas para liberar memória."""
        cutoff = current_time - self.window_seconds
        keys_to_delete = []

        for ip, timestamps in self.requests.items():
            # Filtrar timestamps antigos
            self.requests[ip] = [ts for ts in timestamps if ts > cutoff]
            if not self.requests[ip]:
                keys_to_delete.append(ip)

        for key in keys_to_delete:
            del self.requests[key]

    def _is_rate_limited(self, client_ip: str) -> Tuple[bool, int]:
        """
        Verifica se o IP está limitado.

        Returns:
            Tupla (is_limited, remaining_requests)
        """
        current_time = time.time()
        cutoff = current_time - self.window_seconds

        # Filtrar requisições antigas
        self.requests[client_ip] = [
            ts for ts in self.requests[client_ip] if ts > cutoff
        ]

        # Verificar limite
        request_count = len(self.requests[client_ip])
        remaining = max(0, self.requests_limit - request_count)

        if request_count >= self.requests_limit:
            return True, remaining

        # Registrar nova requisição
        self.requests[client_ip].append(current_time)
        return False, remaining - 1

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Processa a requisição aplicando rate limiting."""
        # Pular rate limiting se desabilitado
        if not RATE_LIMIT_ENABLED:
            return await call_next(request)

        # Pular rate limiting para rotas de saúde e estáticas
        path = request.url.path
        skip_paths = ["/health", "/docs", "/redoc", "/openapi.json", "/css/", "/js/"]
        if any(path.startswith(p) for p in skip_paths):
            return await call_next(request)

        client_ip = self._get_client_ip(request)
        is_limited, remaining = self._is_rate_limited(client_ip)

        # Cleanup periódico (a cada 100 requisições)
        self._cleanup_counter += 1
        if self._cleanup_counter >= 100:
            self._cleanup_old_requests(time.time())
            self._cleanup_counter = 0

        if is_limited:
            logger.warning(f"Rate limit exceeded for IP: {client_ip}")
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={"detail": Messages.RATE_LIMIT_EXCEEDED},
                headers={
                    "X-RateLimit-Limit": str(self.requests_limit),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(int(time.time()) + self.window_seconds),
                    "Retry-After": str(self.window_seconds),
                }
            )

        # Processar requisição
        response = await call_next(request)

        # Adicionar headers de rate limit
        response.headers["X-RateLimit-Limit"] = str(self.requests_limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)

        return response
