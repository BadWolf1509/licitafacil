"""
Utilitários padronizados para tratamento de erros.

Centraliza padrões de logging e tratamento de exceções
para garantir consistência em todo o projeto.
"""
from functools import wraps
from typing import Callable, TypeVar, Any, Optional
from logging import Logger

from fastapi import HTTPException, status

from .router_helpers import safe_delete_file

# Importar exceções do módulo centralizado
from exceptions import (
    ProcessingError,
    ValidationError,
    DatabaseError,
    ExternalServiceError,
    ResourceNotFoundError,
    PermissionDeniedError,
)

T = TypeVar("T")


# ==============================================================================
# Mapeamento de Exceções para HTTP
# ==============================================================================

EXCEPTION_STATUS_MAP = {
    ProcessingError: (status.HTTP_422_UNPROCESSABLE_ENTITY, "Erro no processamento do documento"),
    ValidationError: (status.HTTP_400_BAD_REQUEST, "Dados inválidos"),
    DatabaseError: (status.HTTP_503_SERVICE_UNAVAILABLE, "Erro de banco de dados"),
    ExternalServiceError: (status.HTTP_502_BAD_GATEWAY, "Erro em serviço externo"),
    ResourceNotFoundError: (status.HTTP_404_NOT_FOUND, "Recurso não encontrado"),
    PermissionDeniedError: (status.HTTP_403_FORBIDDEN, "Acesso negado"),
}


def handle_exception(exc: Exception, logger: Logger, context: str = "") -> HTTPException:
    """
    Converte exceção em HTTPException apropriada.

    Args:
        exc: Exceção original
        logger: Logger para registrar o erro
        context: Contexto adicional para o log

    Returns:
        HTTPException com status code apropriado
    """
    ctx = f" ({context})" if context else ""

    # Verificar se é uma exceção conhecida
    for exc_type, (status_code, default_detail) in EXCEPTION_STATUS_MAP.items():
        if isinstance(exc, exc_type):
            detail = str(exc) if str(exc) else default_detail
            logger.warning(f"{exc_type.__name__}{ctx}: {detail}")
            return HTTPException(status_code=status_code, detail=detail)

    # Exceção desconhecida - erro interno
    logger.exception(f"Erro inesperado{ctx}: {exc}")
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Erro interno do servidor"
    )


def log_exception(
    logger: Logger,
    context: str,
    exc: Exception,
    include_traceback: bool = True
) -> None:
    """
    Loga exceção com formato padronizado.

    Args:
        logger: Instância do logger
        context: Contexto da operação (ex: "processando atestado")
        exc: Exceção a ser logada
        include_traceback: Se True, inclui traceback completo
    """
    if include_traceback:
        logger.error(f"Erro em {context}: {exc}", exc_info=True)
    else:
        logger.error(f"Erro em {context}: {exc}")


def log_and_raise_http_error(
    logger: Logger,
    message: str,
    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
    detail: str = "Erro interno do servidor",
    cleanup_path: Optional[str] = None
) -> None:
    """
    Loga erro, limpa arquivo se necessário e levanta HTTPException.

    Args:
        logger: Instância do logger
        message: Mensagem para o log
        status_code: Código HTTP de resposta
        detail: Detalhe para a resposta HTTP
        cleanup_path: Caminho do arquivo para limpar (opcional)

    Raises:
        HTTPException: Sempre levanta com o status_code e detail informados
    """
    logger.error(message, exc_info=True)

    if cleanup_path:
        safe_delete_file(cleanup_path)

    raise HTTPException(status_code=status_code, detail=detail)


def safe_operation(
    context: str,
    default: Any = None,
    reraise: bool = False,
    logger: Optional[Logger] = None
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Decorator para operações seguras com logging.

    Args:
        context: Contexto da operação para logging
        default: Valor padrão a retornar em caso de erro
        reraise: Se True, re-levanta a exceção após logar
        logger: Logger a usar (se None, usa logging padrão)

    Returns:
        Decorator que envolve a função com tratamento de erros
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            nonlocal logger
            if logger is None:
                from logging_config import get_logger
                logger = get_logger(func.__module__)

            try:
                return func(*args, **kwargs)
            except Exception as e:
                log_exception(logger, context, e)
                if reraise:
                    raise
                return default

        return wrapper
    return decorator
