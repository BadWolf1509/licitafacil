"""
Configuracoes de OCR do LicitaFacil.
"""
from .base import env_int, env_float


class OCRConfig:
    """Configuracoes para processamento OCR."""
    DPI = env_int("OCR_DPI", 300)
    MIN_TEXT_PER_PAGE = env_int("OCR_MIN_TEXT_PER_PAGE", 200)
    MIN_TEXT_LENGTH = env_int("OCR_MIN_TEXT_LENGTH", 100)
    MIN_CONFIDENT_CHARS = env_int("OCR_MIN_CONFIDENT_CHARS", 20)


class PipelineConfig:
    """Configuracoes de confianca do pipeline de extracao."""
    MIN_CONFIDENCE_LOCAL_OCR = env_float("MIN_CONFIDENCE_LOCAL_OCR", 0.70)
    MIN_CONFIDENCE_CLOUD_OCR = env_float("MIN_CONFIDENCE_CLOUD_OCR", 0.85)


class OCRNoiseConfig:
    """Configuracoes para deteccao de ruido em extracao OCR."""
    MIN_UNIT_RATIO = env_float("ATTESTADO_OCR_NOISE_MIN_UNIT_RATIO", 0.5)
    MIN_QTY_RATIO = env_float("ATTESTADO_OCR_NOISE_MIN_QTY_RATIO", 0.35)
    MIN_AVG_DESC_LEN = env_float("ATTESTADO_OCR_NOISE_MIN_AVG_DESC_LEN", 14.0)
    MAX_SHORT_DESC_RATIO = env_float("ATTESTADO_OCR_NOISE_MAX_SHORT_DESC_RATIO", 0.45)
    MIN_ALPHA_RATIO = env_float("ATTESTADO_OCR_NOISE_MIN_ALPHA_RATIO", 0.45)
    MIN_FAILURES = env_int("ATTESTADO_OCR_NOISE_MIN_FAILS", 2)
    SHORT_DESC_LEN = env_int("ATTESTADO_OCR_NOISE_SHORT_DESC_LEN", 12)


class OCRTimeoutConfig:
    """Configuracoes de timeout para operacoes OCR."""
    # Timeout por pagina em segundos
    PAGE_TIMEOUT = env_int("OCR_PAGE_TIMEOUT", 60)
    # Timeout total do documento em segundos
    DOCUMENT_TIMEOUT = env_int("OCR_DOCUMENT_TIMEOUT", 600)
    # Timeout para retry (mais curto)
    RETRY_TIMEOUT = env_int("OCR_RETRY_TIMEOUT", 30)
    # Timeout para extracao de tabela
    TABLE_EXTRACTION_TIMEOUT = env_int("OCR_TABLE_EXTRACTION_TIMEOUT", 120)
