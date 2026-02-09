"""
Configuracoes de modelos de IA do LicitaFacil.
"""
import os

from .base import env_bool, env_float, env_int


class AIModelConfig:
    """Configuracoes dos modelos de IA."""
    # OpenAI
    OPENAI_TEXT_MODEL = os.getenv("OPENAI_TEXT_MODEL", "gpt-4o-mini")
    OPENAI_VISION_MODEL = os.getenv("OPENAI_VISION_MODEL", "gpt-4o")
    OPENAI_MAX_TOKENS = env_int("OPENAI_MAX_TOKENS", 16000)
    OPENAI_TEMPERATURE = env_float("OPENAI_TEMPERATURE", 0)
    # Gemini
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
    GEMINI_PRO_MODEL = os.getenv("GEMINI_PRO_MODEL", "gemini-2.0-flash")
    GEMINI_MAX_TOKENS = env_int("GEMINI_MAX_TOKENS", 16000)
    GEMINI_TEMPERATURE = env_float("GEMINI_TEMPERATURE", 0)
    GEMINI_ALLOW_LEGACY = env_bool("GEMINI_ALLOW_LEGACY", False)
