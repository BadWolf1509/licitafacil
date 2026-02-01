# Backend utilities package

from .text_utils import sanitize_description
from .retry import retry
from .error_handlers import (
    # Exceções
    LicitaFacilError,
    ProcessingError,
    ValidationError,
    DatabaseError,
    ExternalServiceError,
    ResourceNotFoundError,
    PermissionDeniedError,
    # Funções
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
    # error_handlers - exceções
    "LicitaFacilError",
    "ProcessingError",
    "ValidationError",
    "DatabaseError",
    "ExternalServiceError",
    "ResourceNotFoundError",
    "PermissionDeniedError",
    # error_handlers - funções
    "handle_exception",
    "log_exception",
    "log_and_raise_http_error",
    "safe_operation",
]
