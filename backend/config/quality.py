"""
Configuracoes de qualidade e deduplicacao do LicitaFacil.
"""
from .base import env_int, env_float


class DeduplicationConfig:
    """Configuracoes para deteccao de duplicatas."""
    SIMILARITY_THRESHOLD = env_float("DEDUP_SIMILARITY_THRESHOLD", 0.5)
    MAX_DESC_CHARS = env_int("DEDUP_MAX_DESC_CHARS", 50)
    ITEM_LENGTH_RATIO = env_float("ATTESTADO_ITEM_LEN_RATIO", 0.6)
    ITEM_LENGTH_KEEP_MIN_DESC = env_int("ATTESTADO_ITEM_LEN_KEEP_MIN_DESC", 20)
    ITEM_PREFIX_RATIO = env_float("ATTESTADO_ITEM_PREFIX_RATIO", 0.7)
    ITEM_PREFIX_KEEP_MIN_DESC = env_int("ATTESTADO_ITEM_PREFIX_KEEP_MIN_DESC", 15)
    ITEM_COL_MIN_SCORE = env_float("ATTESTADO_ITEM_COL_MIN_SCORE", 0.5)


class QualityScoreConfig:
    """Configuracoes para calculo de score de qualidade."""
    MIN_UNIT_RATIO = env_float("QUALITY_SCORE_MIN_UNIT_RATIO", 0.8)
    MIN_QTY_RATIO = env_float("QUALITY_SCORE_MIN_QTY_RATIO", 0.8)
    MIN_ITEM_RATIO = env_float("QUALITY_SCORE_MIN_ITEM_RATIO", 0.4)
    MAX_DUPLICATE_RATIO = env_float("QUALITY_SCORE_MAX_DUPLICATE_RATIO", 0.35)
    PENALTY_UNIT = env_float("QUALITY_SCORE_PENALTY_UNIT", 0.2)
    PENALTY_QTY = env_float("QUALITY_SCORE_PENALTY_QTY", 0.2)
    PENALTY_ITEM = env_float("QUALITY_SCORE_PENALTY_ITEM", 0.2)
    PENALTY_DUPLICATE = env_float("QUALITY_SCORE_PENALTY_DUPLICATE", 0.1)
    PENALTY_FEW_ITEMS = env_float("QUALITY_SCORE_PENALTY_FEW_ITEMS", 0.2)
