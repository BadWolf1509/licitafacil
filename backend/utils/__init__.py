# Backend utilities package

from .text_utils import sanitize_description
from .retry import retry

# Exceções importadas do módulo centralizado
from exceptions import (
    LicitaFacilError,
    ProcessingError,
    ValidationError,
    DatabaseError,
    ExternalServiceError,
    ResourceNotFoundError,
    PermissionDeniedError,
)

# Funções utilitárias de tratamento de erros
from .error_handlers import (
    handle_exception,
    log_exception,
    log_and_raise_http_error,
    safe_operation,
)

__all__ = [
    # text_utils
    "sanitize_description",
    # retry
    "retry",
    # exceções (de exceptions.py)
    "LicitaFacilError",
    "ProcessingError",
    "ValidationError",
    "DatabaseError",
    "ExternalServiceError",
    "ResourceNotFoundError",
    "PermissionDeniedError",
    # funções de error_handlers
    "handle_exception",
    "log_exception",
    "log_and_raise_http_error",
    "safe_operation",
]
