"""
Middleware de Rate Limiting para proteção contra abuso.

Limita o número de requisições por IP em uma janela de tempo.
Suporta limites diferentes por rota (ex: login mais restritivo).
"""
import ipaddress
import os
import time
from collections import defaultdict
from typing import Callable, Dict, List, Optional, Tuple, Union
from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from config import (
    RATE_LIMIT_ENABLED,
    RATE_LIMIT_REQUESTS,
    RATE_LIMIT_WINDOW,
    RATE_LIMIT_AUTH_LOGIN,
    RATE_LIMIT_AUTH_REGISTER,
    RATE_LIMIT_AUTH_WINDOW,
    RATE_LIMIT_UPLOAD,
    RATE_LIMIT_UPLOAD_WINDOW,
    Messages,
)
from logging_config import get_logger

logger = get_logger(__name__)

# IPs/redes de proxies confiáveis (ex: load balancer, CDN)
# Configurar via variável de ambiente: TRUSTED_PROXIES=10.0.0.0/8,172.16.0.0/12
TRUSTED_PROXIES_ENV = os.environ.get("TRUSTED_PROXIES", "")
TRUSTED_PROXY_NETWORKS: List[Union[ipaddress.IPv4Network, ipaddress.IPv6Network]] = []

for network_str in TRUSTED_PROXIES_ENV.split(","):
    network_str = network_str.strip()
    if network_str:
        try:
            TRUSTED_PROXY_NETWORKS.append(ipaddress.ip_network(network_str, strict=False))
        except ValueError as e:
            logger.warning(f"Rede de proxy inválida ignorada: {network_str} - {e}")

# Intervalo mínimo entre limpezas (segundos)
CLEANUP_INTERVAL = 60

# Limites específicos por rota (path_contains, requests, window_seconds)
PATH_SPECIFIC_LIMITS: List[Tuple[str, int, int]] = [
    # Endpoints de login - mais restritivos para evitar brute force
    ("/auth/login", RATE_LIMIT_AUTH_LOGIN, RATE_LIMIT_AUTH_WINDOW),
    # Endpoint de registro - ainda mais restritivo
    ("/auth/registrar", RATE_LIMIT_AUTH_REGISTER, RATE_LIMIT_AUTH_WINDOW),
    # Upload de atestados - limitar processamento pesado
    ("/atestados/upload", RATE_LIMIT_UPLOAD, RATE_LIMIT_UPLOAD_WINDOW),
]


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Middleware que implementa rate limiting por IP.

    Usa um algoritmo de janela deslizante simples.
    Suporta limites diferentes por rota para endpoints sensíveis.
    """

    def __init__(self, app, requests_limit: Optional[int] = None, window_seconds: Optional[int] = None):
        super().__init__(app)
        self.requests_limit = requests_limit or RATE_LIMIT_REQUESTS
        self.window_seconds = window_seconds or RATE_LIMIT_WINDOW
        # Separar contadores por rota para limites específicos
        self.requests: Dict[str, list] = defaultdict(list)
        self.path_requests: Dict[str, Dict[str, list]] = defaultdict(lambda: defaultdict(list))
        self._last_cleanup = time.time()

    def _is_trusted_proxy(self, ip: str) -> bool:
        """Verifica se o IP é de um proxy confiável."""
        if not TRUSTED_PROXY_NETWORKS:
            return False
        try:
            ip_addr = ipaddress.ip_address(ip)
            return any(ip_addr in network for network in TRUSTED_PROXY_NETWORKS)
        except ValueError:
            return False

    def _get_client_ip(self, request: Request) -> str:
        """
        Obtém o IP do cliente de forma segura.

        Só confia em headers de proxy se a requisição vier de um proxy confiável.
        Isso previne IP spoofing via X-Forwarded-For.
        """
        # IP direto da conexão
        direct_ip = request.client.host if request.client else "unknown"

        # Só considerar headers de proxy se vier de proxy confiável
        if not self._is_trusted_proxy(direct_ip):
            return direct_ip

        # Proxy confiável - usar X-Forwarded-For
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            # Pegar o primeiro IP (cliente original)
            client_ip = forwarded.split(",")[0].strip()
            # Validar que é um IP válido
            try:
                ipaddress.ip_address(client_ip)
                return client_ip
            except ValueError:
                logger.warning(f"X-Forwarded-For inválido: {client_ip}")
                return direct_ip

        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            try:
                ipaddress.ip_address(real_ip)
                return real_ip
            except ValueError:
                logger.warning(f"X-Real-IP inválido: {real_ip}")
                return direct_ip

        return direct_ip

    def _cleanup_old_requests(self, current_time: float):
        """Remove requisições antigas para liberar memória."""
        # Limpar requisições globais
        cutoff = current_time - self.window_seconds
        keys_to_delete = []

        for ip, timestamps in self.requests.items():
            # Filtrar timestamps antigos
            self.requests[ip] = [ts for ts in timestamps if ts > cutoff]
            if not self.requests[ip]:
                keys_to_delete.append(ip)

        for key in keys_to_delete:
            del self.requests[key]

        # Limpar requisições por path
        for path_key, ip_requests in list(self.path_requests.items()):
            # Usar janela específica do path ou global
            path_window = self.window_seconds
            for pattern, _, window in PATH_SPECIFIC_LIMITS:
                if pattern == path_key:
                    path_window = window
                    break

            path_cutoff = current_time - path_window
            ips_to_delete = []

            for ip, timestamps in ip_requests.items():
                self.path_requests[path_key][ip] = [
                    ts for ts in timestamps if ts > path_cutoff
                ]
                if not self.path_requests[path_key][ip]:
                    ips_to_delete.append(ip)

            for ip in ips_to_delete:
                del self.path_requests[path_key][ip]

            if not self.path_requests[path_key]:
                del self.path_requests[path_key]

    def _get_path_limit(self, path: str) -> Optional[Tuple[str, int, int]]:
        """
        Retorna limite específico para o path, se existir.

        Returns:
            Tupla (path_key, requests_limit, window_seconds) ou None
        """
        for path_pattern, limit, window in PATH_SPECIFIC_LIMITS:
            if path_pattern in path:
                return (path_pattern, limit, window)
        return None

    def _is_rate_limited(self, client_ip: str) -> Tuple[bool, int]:
        """
        Verifica se o IP está limitado (limite global).

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

    def _is_path_rate_limited(
        self, client_ip: str, path_key: str, limit: int, window: int
    ) -> Tuple[bool, int]:
        """
        Verifica se o IP está limitado para um path específico.

        Returns:
            Tupla (is_limited, remaining_requests)
        """
        current_time = time.time()
        cutoff = current_time - window

        # Filtrar requisições antigas para este path
        self.path_requests[path_key][client_ip] = [
            ts for ts in self.path_requests[path_key][client_ip] if ts > cutoff
        ]

        # Verificar limite
        request_count = len(self.path_requests[path_key][client_ip])
        remaining = max(0, limit - request_count)

        if request_count >= limit:
            return True, remaining

        # Registrar nova requisição
        self.path_requests[path_key][client_ip].append(current_time)
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

        # Verificar se há limite específico para este path
        path_limit = self._get_path_limit(path)
        if path_limit:
            path_key, limit, window = path_limit
            is_limited, remaining = self._is_path_rate_limited(
                client_ip, path_key, limit, window
            )
            rate_limit_value = limit
            rate_window = window
        else:
            is_limited, remaining = self._is_rate_limited(client_ip)
            rate_limit_value = self.requests_limit
            rate_window = self.window_seconds

        # Cleanup periódico baseado em tempo (mais previsível, evita memory leak)
        current_time = time.time()
        if current_time - self._last_cleanup >= CLEANUP_INTERVAL:
            self._cleanup_old_requests(current_time)
            self._last_cleanup = current_time

        if is_limited:
            if path_limit:
                logger.warning(
                    f"Rate limit exceeded for IP {client_ip} on path {path_limit[0]} "
                    f"(limit: {path_limit[1]}/{path_limit[2]}s)"
                )
            else:
                logger.warning(f"Rate limit exceeded for IP: {client_ip}")
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={"detail": Messages.RATE_LIMIT_EXCEEDED},
                headers={
                    "X-RateLimit-Limit": str(rate_limit_value),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(int(time.time()) + rate_window),
                    "Retry-After": str(rate_window),
                }
            )

        # Processar requisição
        response = await call_next(request)

        # Adicionar headers de rate limit
        response.headers["X-RateLimit-Limit"] = str(rate_limit_value)
        response.headers["X-RateLimit-Remaining"] = str(remaining)

        return response
