"""
Gerenciador de Provedores de IA.

Abstrai a escolha entre OpenAI e Google Gemini.
Permite trocar de provedor via configuração.
Suporta novos providers (OpenAIProvider, GeminiProvider) e analyzers legados.
"""

import os
from typing import List, Dict, Any, Optional
from enum import Enum
from dotenv import load_dotenv
from exceptions import AINotConfiguredError
from config import PAID_SERVICES_ENABLED
from .base_ai_provider import BaseAIProvider

from logging_config import get_logger
logger = get_logger('services.ai_provider')

load_dotenv()


class AIProviderEnum(str, Enum):
    """Provedores de IA disponíveis."""
    OPENAI = "openai"
    GEMINI = "gemini"
    AUTO = "auto"  # Escolhe automaticamente baseado em disponibilidade


# Alias para compatibilidade com código existente
AIProvider = AIProviderEnum


def get_provider(provider_type: str) -> BaseAIProvider:
    """
    Factory para obter instância de um provider específico.

    Args:
        provider_type: 'openai' ou 'gemini'

    Returns:
        Instância do provider solicitado

    Raises:
        ValueError: Se provider_type inválido
    """
    if not PAID_SERVICES_ENABLED:
        raise ValueError("Serviços pagos desativados (PAID_SERVICES_ENABLED=false)")
    if provider_type == "openai":
        from .providers.openai_provider import OpenAIProvider
        return OpenAIProvider()
    elif provider_type == "gemini":
        from .providers.gemini_provider import GeminiProvider
        return GeminiProvider()
    else:
        raise ValueError(f"Provider inválido: {provider_type}. Use 'openai' ou 'gemini'")


class AIProviderManager:
    """
    Gerenciador central de provedores de IA.

    Permite:
    - Escolher provedor via configuração
    - Fallback automático se um provedor falhar
    - Estatísticas de uso por provedor
    """

    def __init__(self):
        self._provider = os.getenv("AI_PROVIDER", "auto").lower()
        self._openai_provider = None
        self._gemini_provider = None
        self._stats = {
            "openai": {"calls": 0, "errors": 0, "tokens_used": 0},
            "gemini": {"calls": 0, "errors": 0, "tokens_used": 0}
        }

    def _get_openai(self):
        """Retorna provider OpenAI."""
        return self.get_openai_provider()

    def _get_gemini(self):
        """Retorna provider Gemini."""
        return self.get_gemini_provider()

    def get_openai_provider(self):
        """
        Obtém instância do novo OpenAIProvider.

        Returns:
            OpenAIProvider configurado
        """
        if self._openai_provider is None:
            from .providers.openai_provider import OpenAIProvider
            self._openai_provider = OpenAIProvider()
        return self._openai_provider

    def get_gemini_provider(self):
        """
        Obtém instância do novo GeminiProvider.

        Returns:
            GeminiProvider configurado
        """
        if self._gemini_provider is None:
            from .providers.gemini_provider import GeminiProvider
            self._gemini_provider = GeminiProvider()
        return self._gemini_provider

    def get_provider_instance(self, provider_type: Optional[str] = None):
        """
        Obtém instância do provider baseado na interface BaseAIProvider.

        Args:
            provider_type: 'openai', 'gemini' ou None para auto

        Returns:
            Instância de BaseAIProvider (OpenAIProvider ou GeminiProvider)
        """
        selected = self._select_provider(provider_type)
        if selected == "openai":
            return self.get_openai_provider()
        return self.get_gemini_provider()

    @property
    def current_provider(self) -> str:
        """Retorna o provedor atual configurado."""
        return self._provider

    @property
    def available_providers(self) -> List[str]:
        """Retorna lista de provedores disponíveis (com API key configurada)."""
        if not PAID_SERVICES_ENABLED:
            return []
        available = []

        openai = self._get_openai()
        if openai.is_configured:
            available.append("openai")

        gemini = self._get_gemini()
        if gemini.is_configured:
            available.append("gemini")

        return available

    @property
    def is_configured(self) -> bool:
        """Verifica se pelo menos um provedor está configurado."""
        return len(self.available_providers) > 0

    def _select_provider(self, preferred: Optional[str] = None) -> str:
        """
        Seleciona o provedor a usar.

        Args:
            preferred: Provedor preferido (opcional)

        Returns:
            Nome do provedor selecionado
        """
        available = self.available_providers

        if not available:
            raise AINotConfiguredError()

        # Se especificado um preferido e está disponível
        if preferred and preferred in available:
            return preferred

        # Se configurado um provedor específico
        if self._provider != "auto" and self._provider in available:
            return self._provider

        # Auto: priorizar Gemini (mais barato) se disponível
        if "gemini" in available:
            return "gemini"

        return available[0]

    def _get_analyzer(self, provider_name: str):
        """Retorna o provider para o provedor especificado."""
        if provider_name == "gemini":
            return self.get_gemini_provider()
        return self.get_openai_provider()

    def _execute_with_fallback(
        self,
        method_name: str,
        args: tuple,
        provider: Optional[str] = None
    ) -> Any:
        """
        Executa método no provedor selecionado com fallback automático.

        Args:
            method_name: Nome do método a chamar no analisador
            args: Argumentos para passar ao método
            provider: Provedor específico a usar (opcional)

        Returns:
            Resultado do método chamado

        Raises:
            Exception: Se todos os provedores falharem
        """
        selected = self._select_provider(provider)

        try:
            analyzer = self._get_analyzer(selected)
            method = getattr(analyzer, method_name)
            result = method(*args)

            self._stats[selected]["calls"] += 1
            return result

        except Exception as e:
            self._stats[selected]["errors"] += 1

            # Tentar fallback se houver outro provedor
            available = self.available_providers
            fallback = [p for p in available if p != selected]

            if fallback:
                fallback_provider = fallback[0]
                logger.warning(
                    f"Erro com {selected}, tentando fallback para {fallback_provider}: {e}"
                )

                fallback_analyzer = self._get_analyzer(fallback_provider)
                fallback_method = getattr(fallback_analyzer, method_name)
                return fallback_method(*args)

            raise

    def extract_atestado_from_images(
        self,
        images: List[bytes],
        provider: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Extrai informações de atestado a partir de imagens.

        Args:
            images: Lista de imagens em bytes
            provider: Provedor específico a usar (opcional)

        Returns:
            Dicionário com dados extraídos
        """
        return self._execute_with_fallback(
            "extract_atestado_from_images",
            (images,),
            provider
        )

    def extract_atestado_info(
        self,
        texto: str,
        provider: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Extrai informações de atestado a partir de texto.

        Args:
            texto: Texto extraído do documento
            provider: Provedor específico a usar (opcional)

        Returns:
            Dicionário com dados extraídos
        """
        return self._execute_with_fallback(
            "extract_atestado_info",
            (texto,),
            provider
        )

    def extract_atestado_metadata(
        self,
        texto: str,
        provider: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Extrai apenas metadados do atestado a partir de texto.

        Args:
            texto: Texto extraído do documento
            provider: Provedor específico a usar (opcional)

        Returns:
            Dicionário com metadados extraídos
        """
        return self._execute_with_fallback(
            "extract_atestado_metadata",
            (texto,),
            provider
        )

    def match_atestados(
        self,
        exigencias: List[Dict],
        atestados: List[Dict],
        provider: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Faz matching entre exigencias e atestados.

        Args:
            exigencias: Lista de exigencias do edital
            atestados: Lista de atestados disponiveis
            provider: Provedor especifico a usar (opcional) - nao usado

        Returns:
            Lista de resultados do matching
        """
        from .matching_service import matching_service
        return matching_service.match_exigencias(exigencias, atestados)

    def get_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas de uso dos provedores."""
        return {
            "provider_atual": self._provider,
            "providers_disponiveis": self.available_providers,
            "estatisticas": self._stats
        }

    def get_status(self) -> Dict[str, Any]:
        """Retorna status detalhado dos provedores."""
        openai = self.get_openai_provider()
        gemini = self.get_gemini_provider()

        return {
            "provider_configurado": self._provider,
            "paid_services_enabled": PAID_SERVICES_ENABLED,
            "openai": {
                "configurado": openai.is_configured,
                "modelo_texto": getattr(openai, '_text_model', 'N/A'),
                "modelo_vision": getattr(openai, '_vision_model', 'N/A')
            },
            "gemini": {
                "configurado": gemini.is_configured,
                "modelo": getattr(gemini, '_model_name', 'N/A')
            },
            "recomendacao": self._get_recommendation()
        }

    def _get_recommendation(self) -> str:
        """Retorna recomendação de provedor baseado na configuração."""
        if not PAID_SERVICES_ENABLED:
            return "Serviços pagos desativados. Ative PAID_SERVICES_ENABLED=true para usar IA."
        available = self.available_providers

        if not available:
            return "Configure OPENAI_API_KEY ou GOOGLE_API_KEY para usar IA"

        if "gemini" in available and "openai" in available:
            return "Ambos configurados. Gemini será usado por padrão (mais econômico). Use AI_PROVIDER=openai para forçar OpenAI."

        if "gemini" in available:
            return "Apenas Gemini configurado. Recomendado para escala."

        return "Apenas OpenAI configurado. Configure GOOGLE_API_KEY para economia em escala."


# Instância singleton para uso global
ai_provider = AIProviderManager()
