"""
Middleware de proteção contra CSRF.

Implementa proteção baseada em header customizado (X-Requested-With).
Browsers não enviam headers customizados em requisições cross-origin
sem passar pelo preflight CORS, então se o CORS não permitir a origem,
a requisição será bloqueada.

Para APIs que usam autenticação via Bearer token (não cookies),
CSRF é menos crítico, mas esta proteção adiciona uma camada extra.
"""
from typing import Callable, List, Optional

from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from logging_config import get_logger

logger = get_logger(__name__)


class CSRFProtectionMiddleware(BaseHTTPMiddleware):
    """
    Middleware que requer header X-Requested-With para requisições mutáveis.

    Requisições GET, HEAD, OPTIONS são sempre permitidas.
    Requisições POST, PUT, DELETE, PATCH precisam do header.
    """

    def __init__(
        self,
        app,
        exempt_paths: Optional[List[str]] = None,
        enabled: bool = True
    ):
        super().__init__(app)
        self.enabled = enabled
        # Paths isentos de verificação CSRF
        self.exempt_paths = exempt_paths or [
            "/docs",
            "/redoc",
            "/openapi.json",
            "/health",
            # Webhooks externos podem precisar de isenção
        ]

    def _is_exempt(self, path: str) -> bool:
        """Verifica se o path está isento de verificação CSRF."""
        return any(path.startswith(exempt) for exempt in self.exempt_paths)

    def _requires_csrf_check(self, method: str) -> bool:
        """Verifica se o método HTTP requer verificação CSRF."""
        # Métodos seguros (idempotentes) não precisam de verificação
        safe_methods = {"GET", "HEAD", "OPTIONS"}
        return method.upper() not in safe_methods

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Processa a requisição verificando proteção CSRF."""
        if not self.enabled:
            return await call_next(request)

        path = request.url.path
        method = request.method

        # Pular verificação para paths isentos ou métodos seguros
        if self._is_exempt(path) or not self._requires_csrf_check(method):
            return await call_next(request)

        # Verificar presença do header X-Requested-With
        # Valor comum é "XMLHttpRequest" mas aceitamos qualquer valor
        requested_with = request.headers.get("X-Requested-With")

        if not requested_with:
            logger.warning(
                f"CSRF check failed: missing X-Requested-With header "
                f"for {method} {path}"
            )
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={
                    "detail": "Requisição inválida: header X-Requested-With ausente"
                }
            )

        return await call_next(request)
