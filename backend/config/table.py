"""
Configuracoes de extracao de tabelas do LicitaFacil.
"""
from .base import env_int, env_float


class TableExtractionConfig:
    """Configuracoes para extracao e parsing de tabelas."""
    HEADER_ROWS_LIMIT = env_int("TABLE_HEADER_ROWS_LIMIT", 5)
    HEADER_MIN_KEYWORD_MATCHES = env_int("TABLE_HEADER_MIN_KEYWORDS", 2)
    MIN_DESCRIPTION_LENGTH = env_int("TABLE_MIN_DESC_LENGTH", 5)
    # Validacao de colunas
    MIN_UNIT_RATIO = env_float("TABLE_MIN_UNIT_RATIO", 0.2)
    MIN_QTY_RATIO = env_float("TABLE_MIN_QTY_RATIO", 0.35)
    MIN_DESC_LEN = env_float("TABLE_MIN_DESC_LEN", 10.0)
    MAX_DESC_NUMERIC = env_float("TABLE_MAX_DESC_NUMERIC", 0.6)
    # Pesos de scoring para deteccao de coluna de item
    ITEM_SCORE_PATTERN_WEIGHT = env_float("ITEM_SCORE_PATTERN_WEIGHT", 0.45)
    ITEM_SCORE_SEQ_WEIGHT = env_float("ITEM_SCORE_SEQ_WEIGHT", 0.2)
    ITEM_SCORE_UNIQUE_WEIGHT = env_float("ITEM_SCORE_UNIQUE_WEIGHT", 0.2)
    ITEM_SCORE_LEFT_BIAS_WEIGHT = env_float("ITEM_SCORE_LEFT_BIAS_WEIGHT", 0.1)
    ITEM_SCORE_LENGTH_BONUS_WEIGHT = env_float("ITEM_SCORE_LENGTH_BONUS_WEIGHT", 0.05)
