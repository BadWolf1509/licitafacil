"""
Configuracoes de matching do LicitaFacil.
"""
from .base import env_float, env_int


class MatchingConfig:
    """Configuracoes do matching deterministico."""
    SIMILARITY_THRESHOLD = env_float("MATCH_SIMILARITY_THRESHOLD", 0.50)
    MIN_COMMON_WORDS = env_int("MATCH_MIN_COMMON_WORDS", 2)
    MIN_COMMON_WORDS_SHORT = env_int("MATCH_MIN_COMMON_WORDS_SHORT", 1)
