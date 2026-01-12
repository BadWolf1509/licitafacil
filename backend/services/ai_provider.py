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
        self._openai_analyzer = None
        self._gemini_analyzer = None
        self._openai_provider = None
        self._gemini_provider = None
        self._stats = {
            "openai": {"calls": 0, "errors": 0, "tokens_used": 0},
            "gemini": {"calls": 0, "errors": 0, "tokens_used": 0}
        }

    def _get_openai(self):
        """Lazy load do analisador OpenAI (legado)."""
        if self._openai_analyzer is None:
            from .ai_analyzer import ai_analyzer
            self._openai_analyzer = ai_analyzer
        return self._openai_analyzer

    def _get_gemini(self):
        """Lazy load do analisador Gemini (legado)."""
        if self._gemini_analyzer is None:
            from .gemini_analyzer import gemini_analyzer
            self._gemini_analyzer = gemini_analyzer
        return self._gemini_analyzer

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
        selected = self._select_provider(provider)

        try:
            if selected == "gemini":
                result = self._get_gemini().extract_atestado_from_images(images)
            else:
                result = self._get_openai().extract_atestado_from_images(images)

            self._stats[selected]["calls"] += 1
            return result

        except Exception as e:
            self._stats[selected]["errors"] += 1

            # Tentar fallback se houver outro provedor
            available = self.available_providers
            fallback = [p for p in available if p != selected]

            if fallback:
                fallback_provider = fallback[0]
                logger.warning(f"Erro com {selected}, tentando fallback para {fallback_provider}: {e}")

                if fallback_provider == "gemini":
                    return self._get_gemini().extract_atestado_from_images(images)
                else:
                    return self._get_openai().extract_atestado_from_images(images)

            raise

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
        selected = self._select_provider(provider)

        try:
            if selected == "gemini":
                result = self._get_gemini().extract_atestado_info(texto)
            else:
                result = self._get_openai().extract_atestado_info(texto)

            self._stats[selected]["calls"] += 1
            return result

        except Exception as e:
            self._stats[selected]["errors"] += 1

            # Tentar fallback
            available = self.available_providers
            fallback = [p for p in available if p != selected]

            if fallback:
                fallback_provider = fallback[0]
                logger.warning(f"Erro com {selected}, tentando fallback para {fallback_provider}: {e}")

                if fallback_provider == "gemini":
                    return self._get_gemini().extract_atestado_info(texto)
                else:
                    return self._get_openai().extract_atestado_info(texto)

            raise

    def match_atestados(
        self,
        exigencias: List[Dict],
        atestados: List[Dict],
        provider: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Faz matching entre exigências e atestados.

        Args:
            exigencias: Lista de exigências do edital
            atestados: Lista de atestados disponíveis
            provider: Provedor específico a usar (opcional)

        Returns:
            Lista de resultados do matching
        """
        selected = self._select_provider(provider)

        # OpenAI tem método específico, Gemini usa o genérico
        if selected == "openai":
            return self._get_openai().match_atestados(exigencias, atestados)
        else:
            # Para Gemini, usar o método do OpenAI (mais maduro)
            # ou implementar matching local
            openai = self._get_openai()
            if openai.is_configured:
                return openai.match_atestados(exigencias, atestados)
            else:
                # Matching local simplificado
                return self._local_match(exigencias, atestados)

    def _local_match(
        self,
        exigencias: List[Dict],
        atestados: List[Dict]
    ) -> List[Dict[str, Any]]:
        """
        Matching local sem IA (fallback).
        Usa similaridade de texto simples.
        """
        import unicodedata

        def normalize(text: str) -> str:
            """Normaliza texto para comparação."""
            text = unicodedata.normalize('NFKD', text)
            text = text.encode('ASCII', 'ignore').decode('ASCII')
            return text.upper()

        results = []

        for exig in exigencias:
            exig_desc = normalize(exig.get("descricao", ""))
            exig_qtd = float(exig.get("quantidade_minima", 0))
            exig_un = exig.get("unidade", "").upper()

            matches = []
            total_qtd = 0.0

            for atestado in atestados:
                servicos = atestado.get("servicos_json", [])

                for s in servicos:
                    s_desc = normalize(s.get("descricao", ""))
                    s_un = s.get("unidade", "").upper()

                    # Verificar se unidade é compatível
                    if s_un != exig_un:
                        continue

                    # Verificar palavras em comum
                    exig_words = set(exig_desc.split())
                    s_words = set(s_desc.split())
                    common = exig_words & s_words

                    # Se tiver pelo menos 2 palavras em comum
                    if len(common) >= 2:
                        s_qtd = float(s.get("quantidade", 0))
                        total_qtd += s_qtd
                        matches.append({
                            "atestado_id": atestado.get("id"),
                            "servico": s.get("descricao"),
                            "quantidade": s_qtd,
                            "unidade": s_un
                        })

            percentual = (total_qtd / exig_qtd * 100) if exig_qtd > 0 else 0

            results.append({
                "exigencia": exig.get("descricao"),
                "quantidade_exigida": exig_qtd,
                "quantidade_comprovada": total_qtd,
                "unidade": exig_un,
                "atende": percentual >= 100,
                "percentual_atendido": round(percentual, 2),
                "atestados_utilizados": matches
            })

        return results

    def get_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas de uso dos provedores."""
        return {
            "provider_atual": self._provider,
            "providers_disponiveis": self.available_providers,
            "estatisticas": self._stats
        }

    def get_status(self) -> Dict[str, Any]:
        """Retorna status detalhado dos provedores."""
        openai = self._get_openai()
        gemini = self._get_gemini()

        return {
            "provider_configurado": self._provider,
            "openai": {
                "configurado": openai.is_configured,
                "modelo_texto": getattr(openai, '_model', 'N/A'),
                "modelo_vision": getattr(openai, '_vision_model', 'N/A')
            },
            "gemini": {
                "configurado": gemini.is_configured,
                "modelo": getattr(gemini, '_model', 'N/A')
            },
            "recomendacao": self._get_recommendation()
        }

    def _get_recommendation(self) -> str:
        """Retorna recomendação de provedor baseado na configuração."""
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
