"""
Funções auxiliares para HTTP/routers.

Centraliza padrões comuns de resposta HTTP, tratamento de erros
e validação de recursos.
"""
import ipaddress
import os
from typing import List, Optional, Any, Union

from fastapi import HTTPException, Request, status
from sqlalchemy.orm import Session

from config import Messages
from logging_config import get_logger

logger = get_logger(__name__)

# Redes de proxies confiáveis (ex: load balancer, CDN)
# Configurar via: TRUSTED_PROXIES=10.0.0.0/8,172.16.0.0/12
_TRUSTED_PROXIES_ENV = os.environ.get("TRUSTED_PROXIES", "")
_TRUSTED_PROXY_NETWORKS: List[Union[ipaddress.IPv4Network, ipaddress.IPv6Network]] = []

for _network_str in _TRUSTED_PROXIES_ENV.split(","):
    _network_str = _network_str.strip()
    if _network_str:
        try:
            _TRUSTED_PROXY_NETWORKS.append(
                ipaddress.ip_network(_network_str, strict=False)
            )
        except ValueError as e:
            logger.warning(f"Rede de proxy inválida ignorada: {_network_str} - {e}")


def _is_trusted_proxy(ip: str) -> bool:
    """Verifica se o IP é de um proxy confiável."""
    if not _TRUSTED_PROXY_NETWORKS:
        return False
    try:
        ip_addr = ipaddress.ip_address(ip)
        return any(ip_addr in network for network in _TRUSTED_PROXY_NETWORKS)
    except ValueError:
        return False


def get_client_ip_safe(request: Request) -> str:
    """
    Obtém o IP do cliente de forma segura.

    Só confia em headers de proxy (X-Forwarded-For, X-Real-IP) se a
    requisição vier de um proxy confiável configurado em TRUSTED_PROXIES.
    Isso previne IP spoofing via headers forjados.

    Args:
        request: Objeto Request do FastAPI

    Returns:
        IP do cliente validado
    """
    # IP direto da conexão
    direct_ip = request.client.host if request.client else "unknown"

    # Só considerar headers de proxy se vier de proxy confiável
    if not _is_trusted_proxy(direct_ip):
        return direct_ip

    # Proxy confiável - usar X-Forwarded-For
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        client_ip = forwarded.split(",")[0].strip()
        try:
            ipaddress.ip_address(client_ip)
            return client_ip
        except ValueError:
            logger.warning(f"X-Forwarded-For inválido: {client_ip}")
            return direct_ip

    # Fallback para X-Real-IP
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        try:
            ipaddress.ip_address(real_ip)
            return real_ip
        except ValueError:
            logger.warning(f"X-Real-IP inválido: {real_ip}")
            return direct_ip

    return direct_ip


def get_resource_or_404(
    db: Session,
    model: Any,
    resource_id: int,
    user_id: Optional[int] = None,
    error_message: str = Messages.NOT_FOUND
) -> Any:
    """
    Busca um recurso por ID ou levanta HTTPException 404.

    Args:
        db: Sessão do banco de dados
        model: Classe do modelo SQLAlchemy
        resource_id: ID do recurso a buscar
        user_id: Se informado, filtra também por user_id
        error_message: Mensagem de erro personalizada

    Returns:
        O recurso encontrado

    Raises:
        HTTPException: 404 se o recurso não for encontrado
    """
    query = db.query(model).filter(model.id == resource_id)

    if user_id is not None:
        query = query.filter(model.user_id == user_id)

    resource = query.first()

    if not resource:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=error_message
        )

    return resource


def get_user_resource_or_404(
    db: Session,
    model: Any,
    resource_id: int,
    user_id: int,
    error_message: str = Messages.NOT_FOUND
) -> Any:
    """
    Busca recurso pertencente ao usuário ou levanta 404.

    Wrapper conveniente para get_resource_or_404 com user_id obrigatório.

    Args:
        db: Sessão do banco de dados
        model: Classe do modelo SQLAlchemy
        resource_id: ID do recurso
        user_id: ID do usuário proprietário
        error_message: Mensagem de erro personalizada

    Returns:
        O recurso encontrado

    Raises:
        HTTPException: 404 se o recurso não for encontrado
    """
    return get_resource_or_404(db, model, resource_id, user_id, error_message)
