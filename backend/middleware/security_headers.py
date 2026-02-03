"""
Middleware para adicionar headers de seguranca a todas as respostas HTTP.

Headers implementados:
- X-Content-Type-Options: Previne MIME type sniffing
- X-Frame-Options: Previne clickjacking
- X-XSS-Protection: Proteção contra XSS (navegadores antigos)
- Referrer-Policy: Controla informações de referrer
- Content-Security-Policy: Controla recursos que podem ser carregados
- Strict-Transport-Security: Força HTTPS (apenas em producao)
- Permissions-Policy: Controla APIs do navegador
"""
from typing import Callable, Optional
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from config import ENVIRONMENT
from logging_config import get_logger

logger = get_logger(__name__)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware que adiciona headers de seguranca a todas as respostas HTTP.

    Configuravel para diferentes ambientes (desenvolvimento vs producao).
    """

    def __init__(
        self,
        app,
        enable_hsts: bool = True,
        hsts_max_age: int = 31536000,  # 1 ano
        frame_options: str = "DENY",
        content_security_policy: Optional[str] = None,
        referrer_policy: str = "strict-origin-when-cross-origin",
        permissions_policy: Optional[str] = None
    ):
        """
        Inicializa o middleware de security headers.

        Args:
            app: Aplicacao FastAPI/Starlette
            enable_hsts: Habilitar HSTS em producao
            hsts_max_age: Tempo de cache do HSTS em segundos
            frame_options: Valor do X-Frame-Options (DENY, SAMEORIGIN)
            content_security_policy: CSP customizada ou None para padrao
            referrer_policy: Politica de referrer
            permissions_policy: Politica de permissoes do navegador
        """
        super().__init__(app)
        self.enable_hsts = enable_hsts
        self.hsts_max_age = hsts_max_age
        self.frame_options = frame_options
        self.csp = content_security_policy or self._default_csp()
        self.referrer_policy = referrer_policy
        self.permissions_policy = permissions_policy or self._default_permissions_policy()

        logger.info(
            f"SecurityHeadersMiddleware inicializado "
            f"(HSTS: {enable_hsts}, Frame-Options: {frame_options})"
        )

    def _default_csp(self) -> str:
        """
        Retorna Content Security Policy padrao.

        Configurada para permitir:
        - Scripts inline (necessario para o frontend atual)
        - Scripts do Supabase via CDN (jsdelivr)
        - Estilos inline e Google Fonts
        - Fontes do Google Fonts
        - Imagens de data: e blob:
        - Conexoes para propria origem e Supabase (API + Realtime WebSocket)
        """
        return (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "img-src 'self' data: blob:; "
            "font-src 'self' https://fonts.gstatic.com; "
            "connect-src 'self' https://*.supabase.co wss://*.supabase.co https://cdn.jsdelivr.net;"
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self'"
        )

    def _default_permissions_policy(self) -> str:
        """
        Retorna Permissions Policy padrao.

        Desabilita APIs de navegador que nao sao usadas pela aplicacao.
        """
        return (
            "accelerometer=(), "
            "camera=(), "
            "geolocation=(), "
            "gyroscope=(), "
            "magnetometer=(), "
            "microphone=(), "
            "payment=(), "
            "usb=()"
        )

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Processa a requisicao e adiciona headers de seguranca a resposta.

        Args:
            request: Requisicao HTTP
            call_next: Proximo handler na cadeia

        Returns:
            Resposta HTTP com headers de seguranca
        """
        response = await call_next(request)

        # Headers sempre adicionados
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = self.frame_options
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = self.referrer_policy
        response.headers["Content-Security-Policy"] = self.csp
        response.headers["Permissions-Policy"] = self.permissions_policy

        # HSTS apenas em producao e para conexoes HTTPS
        if self.enable_hsts and ENVIRONMENT == "production":
            # Em producao, sempre adicionar HSTS
            # O reverse proxy (nginx, cloudflare) deve garantir HTTPS
            response.headers["Strict-Transport-Security"] = (
                f"max-age={self.hsts_max_age}; includeSubDomains"
            )

        return response
