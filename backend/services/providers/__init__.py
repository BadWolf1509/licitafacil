"""
Provedores de IA para o LicitaFácil.

Este módulo contém implementações concretas da interface BaseAIProvider
para diferentes provedores de IA (OpenAI, Gemini, etc.).
"""

from .openai_provider import OpenAIProvider
from .gemini_provider import GeminiProvider

__all__ = ["OpenAIProvider", "GeminiProvider"]
