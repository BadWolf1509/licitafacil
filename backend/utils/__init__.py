# Backend utilities package

# Exceções importadas do módulo centralizado
from exceptions import (
    DatabaseError,
    ExternalServiceError,
    LicitaFacilError,
    PermissionDeniedError,
    ProcessingError,
    ResourceNotFoundError,
    ValidationError,
)

# Funções utilitárias de tratamento de erros
from .error_handlers import (
    handle_exception,
    log_and_raise_http_error,
    log_exception,
    safe_operation,
)
from .retry import retry
from .text_utils import sanitize_description

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
