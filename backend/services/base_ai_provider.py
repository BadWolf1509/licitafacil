"""
Interface base para provedores de IA.

Define o contrato que todos os provedores devem implementar,
permitindo fácil extensão e substituição.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import List, Dict, Any, Optional
import time


class AIProviderType(str, Enum):
    """Tipos de provedores de IA suportados."""
    OPENAI = "openai"
    GEMINI = "gemini"
    CLAUDE = "claude"
    AUTO = "auto"


@dataclass
class AIModelConfig:
    """Configuração de um modelo de IA."""
    provider: AIProviderType
    model_name: str
    temperature: float = 0.0
    max_tokens: int = 16000
    timeout: int = 60


@dataclass
class AIResponse:
    """Resposta padronizada de um provedor de IA."""
    content: str
    model_used: str
    provider: AIProviderType
    tokens_used: Optional[int] = None
    duration_ms: Optional[float] = None
    error: Optional[str] = None

    @property
    def is_success(self) -> bool:
        """Verifica se a resposta foi bem-sucedida."""
        return self.error is None and self.content is not None


class AIProviderException(Exception):
    """Exceção base para erros de provedores de IA."""

    def __init__(
        self,
        message: str,
        provider: AIProviderType,
        details: Optional[str] = None,
        retryable: bool = False
    ):
        self.message = message
        self.provider = provider
        self.details = details
        self.retryable = retryable
        super().__init__(self.message)


class BaseAIProvider(ABC):
    """
    Interface abstrata para provedores de IA.

    Define o contrato que todos os provedores devem implementar.
    Permite fácil extensão com novos provedores sem alterar código existente.
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        Inicializa o provedor.

        Args:
            api_key: Chave de API do provedor (opcional, pode vir do ambiente)
        """
        self._api_key = api_key
        self._client = None
        self._initialize()

    @abstractmethod
    def _initialize(self) -> None:
        """Inicializa o cliente específico do provedor."""
        pass

    @property
    @abstractmethod
    def is_configured(self) -> bool:
        """Verifica se o provedor está corretamente configurado."""
        pass

    @property
    @abstractmethod
    def provider_type(self) -> AIProviderType:
        """Retorna o tipo de provedor."""
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Retorna o nome do modelo em uso."""
        pass

    # === MÉTODOS DE GERAÇÃO DE CONTEÚDO ===

    @abstractmethod
    def generate_text(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> AIResponse:
        """
        Gera texto baseado em prompts.

        Args:
            system_prompt: Instrução do sistema
            user_prompt: Prompt do usuário
            temperature: Temperatura (sobrescreve configuração padrão)
            max_tokens: Máximo de tokens (sobrescreve configuração padrão)

        Returns:
            AIResponse com conteúdo gerado

        Raises:
            AIProviderException: Se houver erro na API
        """
        pass

    @abstractmethod
    def generate_with_vision(
        self,
        system_prompt: str,
        images: List[bytes],
        user_text: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> AIResponse:
        """
        Gera conteúdo usando imagens (multi-modal).

        Args:
            system_prompt: Instrução do sistema
            images: Lista de imagens em bytes
            user_text: Texto adicional do usuário
            temperature: Temperatura (sobrescreve configuração)
            max_tokens: Máximo de tokens (sobrescreve configuração)

        Returns:
            AIResponse com conteúdo gerado

        Raises:
            AIProviderException: Se houver erro na API
        """
        pass

    # === MÉTODOS ESPECÍFICOS DO DOMÍNIO ===

    @abstractmethod
    def extract_atestado_from_images(self, images: List[bytes]) -> Dict[str, Any]:
        """
        Extrai informações de atestado diretamente das imagens.

        Args:
            images: Imagens do documento (PNG bytes)

        Returns:
            Dicionário com informações extraídas
        """
        pass

    @abstractmethod
    def extract_atestado_info(self, texto: str) -> Dict[str, Any]:
        """
        Extrai informações de atestado a partir de texto OCR.

        Args:
            texto: Texto extraído do documento

        Returns:
            Dicionário com informações extraídas
        """
        pass

    @abstractmethod
    def extract_edital_requirements(self, texto: str) -> List[Dict[str, Any]]:
        """
        Extrai requisitos de capacidade técnica de editais.

        Args:
            texto: Texto do edital

        Returns:
            Lista de requisitos com descrição, quantidade, unidade
        """
        pass

    # === MÉTODOS AUXILIARES ===

    def get_model_info(self) -> Dict[str, Any]:
        """Retorna informações sobre o modelo configurado."""
        return {
            "provider": self.provider_type.value,
            "model": self.model_name,
            "configured": self.is_configured
        }

    def _measure_duration(self, start_time: float) -> float:
        """Calcula duração em milissegundos."""
        return (time.time() - start_time) * 1000
