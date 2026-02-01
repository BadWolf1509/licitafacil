"""
Gerenciador de Provedores de IA.

NOTA: APIs pagas (OpenAI, Gemini) foram DESABILITADAS permanentemente.
O sistema usa apenas processamento local (OCR, pdfplumber, PyMuPDF).
"""

from typing import List, Dict, Any, Optional
from enum import Enum
from exceptions import AINotConfiguredError

from logging_config import get_logger
logger = get_logger('services.ai_provider')

# APIs PAGAS PERMANENTEMENTE DESABILITADAS
PAID_SERVICES_ENABLED = False


class AIProviderEnum(str, Enum):
    """Provedores de IA disponíveis."""
    OPENAI = "openai"
    GEMINI = "gemini"
    AUTO = "auto"


# Alias para compatibilidade com código existente
AIProvider = AIProviderEnum


def get_provider(provider_type: str):
    """
    APIs pagas desabilitadas permanentemente.

    Raises:
        ValueError: Sempre - serviços pagos desabilitados
    """
    raise ValueError("APIs pagas (OpenAI/Gemini) foram desabilitadas. Use apenas processamento local.")


class AIProviderManager:
    """
    Gerenciador de provedores de IA.

    NOTA: APIs pagas foram DESABILITADAS permanentemente.
    Todos os métodos retornam que não há provedores configurados.
    """

    def __init__(self):
        self._provider = "disabled"
        self._stats = {
            "openai": {"calls": 0, "errors": 0, "tokens_used": 0},
            "gemini": {"calls": 0, "errors": 0, "tokens_used": 0}
        }

    @property
    def current_provider(self) -> str:
        """Retorna o provedor atual - sempre 'disabled'."""
        return "disabled"

    @property
    def available_providers(self) -> List[str]:
        """Retorna lista vazia - nenhum provedor pago disponível."""
        return []

    @property
    def is_configured(self) -> bool:
        """Sempre retorna False - APIs pagas desabilitadas."""
        return False

    def extract_atestado_from_images(
        self,
        images: List[bytes],
        provider: Optional[str] = None
    ) -> Dict[str, Any]:
        """APIs pagas desabilitadas."""
        raise AINotConfiguredError("APIs pagas desabilitadas permanentemente")

    def extract_atestado_info(
        self,
        texto: str,
        provider: Optional[str] = None
    ) -> Dict[str, Any]:
        """APIs pagas desabilitadas."""
        raise AINotConfiguredError("APIs pagas desabilitadas permanentemente")

    def extract_atestado_metadata(
        self,
        texto: str,
        provider: Optional[str] = None
    ) -> Dict[str, Any]:
        """APIs pagas desabilitadas."""
        raise AINotConfiguredError("APIs pagas desabilitadas permanentemente")

    def match_atestados(
        self,
        exigencias: List[Dict],
        atestados: List[Dict],
        provider: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Matching local - não usa IA paga."""
        from .matching_service import matching_service
        return matching_service.match_exigencias(exigencias, atestados)

    def get_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas de uso dos provedores."""
        return {
            "provider_atual": "disabled",
            "providers_disponiveis": [],
            "estatisticas": self._stats,
            "nota": "APIs pagas desabilitadas permanentemente"
        }

    def get_status(self) -> Dict[str, Any]:
        """Retorna status detalhado dos provedores."""
        return {
            "provider_configurado": "disabled",
            "paid_services_enabled": False,
            "openai": {"configurado": False},
            "gemini": {"configurado": False},
            "recomendacao": "Sistema usa apenas processamento local (OCR, pdfplumber, PyMuPDF)"
        }


# Instância singleton para uso global
ai_provider = AIProviderManager()
