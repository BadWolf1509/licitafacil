"""
Configuracoes do LicitaFacil.

Este modulo re-exporta todas as configuracoes para manter
compatibilidade com imports existentes.

Exemplo:
    from config import Messages, AtestadoProcessingConfig
"""

# Base - helpers e constantes fundamentais
# IA
from .ai import AIModelConfig

# API
from .api import (
    API_PREFIX,
    API_VERSION,
)

# Atestados
from .atestado import AtestadoProcessingConfig
from .base import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    ALLOWED_DOCUMENT_EXTENSIONS,
    ALLOWED_IMAGE_EXTENSIONS,
    ALLOWED_MIME_TYPES,
    ALLOWED_PDF_EXTENSIONS,
    AUTO_CREATE_TABLES,
    BASE_DIR,
    CORS_ALLOW_CREDENTIALS,
    CORS_ORIGINS,
    CSRF_PROTECTION_ENABLED,
    DEFAULT_PAGE_SIZE,
    ENVIRONMENT,
    MAX_PAGE_SIZE,
    MAX_UPLOAD_SIZE_BYTES,
    MAX_UPLOAD_SIZE_MB,
    METRICS_PUBLIC,
    OCR_MAX_WORKERS,
    OCR_PARALLEL_ENABLED,
    OCR_PREFER_TESSERACT,
    OCR_PREPROCESS_ENABLED,
    OCR_TESSERACT_FALLBACK,
    PAID_SERVICES_ENABLED,
    QUEUE_MAX_CONCURRENT,
    QUEUE_POLL_INTERVAL,
    RATE_LIMIT_AUTH_LOGIN,
    RATE_LIMIT_AUTH_REGISTER,
    RATE_LIMIT_AUTH_WINDOW,
    RATE_LIMIT_ENABLED,
    RATE_LIMIT_REQUESTS,
    RATE_LIMIT_UPLOAD,
    RATE_LIMIT_UPLOAD_WINDOW,
    RATE_LIMIT_WINDOW,
    SUPABASE_ANON_KEY,
    SUPABASE_SERVICE_KEY,
    SUPABASE_URL,
    UPLOAD_DIR,
    env_bool,
    env_float,
    env_int,
    get_cors_origins,
    get_file_extension,
    is_allowed_extension,
)

# Defaults
from .defaults import (
    DEFAULT_ADMIN_EMAIL,
    DEFAULT_ADMIN_NAME,
    DEFAULT_OCR_TIMEOUT_SECONDS,
    DEFAULT_PAGE,
    DEFAULT_PROCESSING_TIMEOUT_SECONDS,
    MAX_TEMP_FILE_AGE_HOURS,
    MIN_PASSWORD_LENGTH,
    TEMP_CLEANUP_INTERVAL_HOURS,
)

# Matching
from .matching import MatchingConfig

# Mensagens
from .messages import Messages

# OCR
from .ocr import (
    OCRConfig,
    OCRNoiseConfig,
    PipelineConfig,
)

# Qualidade e Deduplicacao
from .quality import (
    DeduplicationConfig,
    QualityScoreConfig,
)

# Seguranca
from .security import (
    FRAME_OPTIONS,
    HSTS_MAX_AGE,
    JWT_ALGORITHM,
    JWT_EXPIRATION_HOURS,
    PASSWORD_MIN_LENGTH,
    PASSWORD_REQUIRE_DIGIT,
    PASSWORD_REQUIRE_LOWERCASE,
    PASSWORD_REQUIRE_SPECIAL,
    PASSWORD_REQUIRE_UPPERCASE,
    REFERRER_POLICY,
    SECRET_KEY,
    SECURITY_HEADERS_ENABLED,
)

# Tabelas
from .table import TableExtractionConfig

# Validacao
from .validation import (
    detect_mime_type,
    validate_file_size,
    validate_mime_type,
    validate_upload_complete,
    validate_upload_file,
)

# Exportar tudo
__all__ = [
    # Base
    "env_bool",
    "env_int",
    "env_float",
    "BASE_DIR",
    "UPLOAD_DIR",
    "ALLOWED_PDF_EXTENSIONS",
    "ALLOWED_IMAGE_EXTENSIONS",
    "ALLOWED_DOCUMENT_EXTENSIONS",
    "ALLOWED_MIME_TYPES",
    "MAX_UPLOAD_SIZE_MB",
    "MAX_UPLOAD_SIZE_BYTES",
    "get_cors_origins",
    "CORS_ORIGINS",
    "CORS_ALLOW_CREDENTIALS",
    "RATE_LIMIT_ENABLED",
    "RATE_LIMIT_REQUESTS",
    "RATE_LIMIT_WINDOW",
    "RATE_LIMIT_AUTH_LOGIN",
    "RATE_LIMIT_AUTH_REGISTER",
    "RATE_LIMIT_AUTH_WINDOW",
    "RATE_LIMIT_UPLOAD",
    "RATE_LIMIT_UPLOAD_WINDOW",
    "ENVIRONMENT",
    "AUTO_CREATE_TABLES",
    "METRICS_PUBLIC",
    "CSRF_PROTECTION_ENABLED",
    "OCR_PARALLEL_ENABLED",
    "OCR_MAX_WORKERS",
    "OCR_PREPROCESS_ENABLED",
    "OCR_TESSERACT_FALLBACK",
    "OCR_PREFER_TESSERACT",
    "PAID_SERVICES_ENABLED",
    "QUEUE_MAX_CONCURRENT",
    "QUEUE_POLL_INTERVAL",
    "ACCESS_TOKEN_EXPIRE_MINUTES",
    "DEFAULT_PAGE_SIZE",
    "MAX_PAGE_SIZE",
    "is_allowed_extension",
    "get_file_extension",
    "SUPABASE_URL",
    "SUPABASE_ANON_KEY",
    "SUPABASE_SERVICE_KEY",
    # Seguranca
    "SECRET_KEY",
    "JWT_ALGORITHM",
    "JWT_EXPIRATION_HOURS",
    "SECURITY_HEADERS_ENABLED",
    "HSTS_MAX_AGE",
    "FRAME_OPTIONS",
    "REFERRER_POLICY",
    "PASSWORD_MIN_LENGTH",
    "PASSWORD_REQUIRE_UPPERCASE",
    "PASSWORD_REQUIRE_LOWERCASE",
    "PASSWORD_REQUIRE_DIGIT",
    "PASSWORD_REQUIRE_SPECIAL",
    # Mensagens
    "Messages",
    # OCR
    "OCRConfig",
    "PipelineConfig",
    "OCRNoiseConfig",
    # IA
    "AIModelConfig",
    # Matching
    "MatchingConfig",
    # Tabelas
    "TableExtractionConfig",
    # Qualidade
    "DeduplicationConfig",
    "QualityScoreConfig",
    # Atestados
    "AtestadoProcessingConfig",
    # API
    "API_VERSION",
    "API_PREFIX",
    # Validacao
    "validate_upload_file",
    "validate_file_size",
    "validate_mime_type",
    "validate_upload_complete",
    "detect_mime_type",
    # Defaults
    "DEFAULT_ADMIN_EMAIL",
    "DEFAULT_ADMIN_NAME",
    "MIN_PASSWORD_LENGTH",
    "DEFAULT_PAGE",
    "DEFAULT_PROCESSING_TIMEOUT_SECONDS",
    "DEFAULT_OCR_TIMEOUT_SECONDS",
    "MAX_TEMP_FILE_AGE_HOURS",
    "TEMP_CLEANUP_INTERVAL_HOURS",
]
