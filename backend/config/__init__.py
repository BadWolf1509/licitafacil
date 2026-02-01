"""
Configuracoes do LicitaFacil.

Este modulo re-exporta todas as configuracoes para manter
compatibilidade com imports existentes.

Exemplo:
    from config import Messages, AtestadoProcessingConfig
"""

# Base - helpers e constantes fundamentais
from .base import (
    env_bool,
    env_int,
    env_float,
    BASE_DIR,
    UPLOAD_DIR,
    ALLOWED_PDF_EXTENSIONS,
    ALLOWED_IMAGE_EXTENSIONS,
    ALLOWED_DOCUMENT_EXTENSIONS,
    get_cors_origins,
    CORS_ORIGINS,
    CORS_ALLOW_CREDENTIALS,
    RATE_LIMIT_ENABLED,
    RATE_LIMIT_REQUESTS,
    RATE_LIMIT_WINDOW,
    ENVIRONMENT,
    OCR_PARALLEL_ENABLED,
    OCR_MAX_WORKERS,
    OCR_PREPROCESS_ENABLED,
    OCR_TESSERACT_FALLBACK,
    OCR_PREFER_TESSERACT,
    PAID_SERVICES_ENABLED,
    QUEUE_MAX_CONCURRENT,
    QUEUE_POLL_INTERVAL,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
    is_allowed_extension,
    get_file_extension,
    SUPABASE_URL,
    SUPABASE_ANON_KEY,
    SUPABASE_SERVICE_KEY,
)

# Seguranca
from .security import (
    SECRET_KEY,
    JWT_ALGORITHM,
    JWT_EXPIRATION_HOURS,
)

# Mensagens
from .messages import Messages

# OCR
from .ocr import (
    OCRConfig,
    PipelineConfig,
    OCRNoiseConfig,
)

# IA
from .ai import AIModelConfig

# Matching
from .matching import MatchingConfig

# Tabelas
from .table import TableExtractionConfig

# Qualidade e Deduplicacao
from .quality import (
    DeduplicationConfig,
    QualityScoreConfig,
)

# Atestados
from .atestado import AtestadoProcessingConfig

# API
from .api import (
    API_VERSION,
    API_PREFIX,
)

# Validacao
from .validation import validate_upload_file

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
    "get_cors_origins",
    "CORS_ORIGINS",
    "CORS_ALLOW_CREDENTIALS",
    "RATE_LIMIT_ENABLED",
    "RATE_LIMIT_REQUESTS",
    "RATE_LIMIT_WINDOW",
    "ENVIRONMENT",
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
]
