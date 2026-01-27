"""
Implementação do AIProvider para OpenAI.

Encapsula a lógica de comunicação com a API da OpenAI,
incluindo suporte a GPT-4o Vision para análise de imagens.
"""

import os
import base64
import time
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv

from services.base_ai_provider import (
    BaseAIProvider,
    AIProviderType,
    AIResponse,
    AIProviderException
)
from config import AIModelConfig, PAID_SERVICES_ENABLED

load_dotenv()


class OpenAIProvider(BaseAIProvider):
    """Implementação do AIProvider para OpenAI GPT e GPT-4o Vision."""

    def __init__(self, api_key: Optional[str] = None):
        self._text_model = AIModelConfig.OPENAI_TEXT_MODEL
        self._vision_model = AIModelConfig.OPENAI_VISION_MODEL
        super().__init__(api_key)

    def _initialize(self) -> None:
        """Inicializa o cliente OpenAI."""
        if not PAID_SERVICES_ENABLED:
            self._client = None
            return
        api_key = self._api_key or os.getenv("OPENAI_API_KEY")
        if not api_key or api_key == "sua-chave-openai-aqui":
            self._client = None
        else:
            try:
                from openai import OpenAI
                self._client = OpenAI(api_key=api_key)
            except Exception as e:
                raise AIProviderException(
                    "Falha ao inicializar cliente OpenAI",
                    AIProviderType.OPENAI,
                    str(e)
                )

    @property
    def is_configured(self) -> bool:
        """Verifica se a API está configurada."""
        return self._client is not None

    @property
    def provider_type(self) -> AIProviderType:
        return AIProviderType.OPENAI

    @property
    def model_name(self) -> str:
        return self._text_model

    def generate_text(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> AIResponse:
        """Gera texto usando GPT."""
        if not self.is_configured:
            raise AIProviderException(
                "OpenAI não está configurado",
                AIProviderType.OPENAI
            )

        temp = temperature if temperature is not None else AIModelConfig.OPENAI_TEMPERATURE
        tokens = max_tokens if max_tokens is not None else AIModelConfig.OPENAI_MAX_TOKENS

        try:
            start_time = time.time()
            assert self._client is not None
            response = self._client.chat.completions.create(
                model=self._text_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=temp,
                max_tokens=tokens
            )
            duration = self._measure_duration(start_time)

            return AIResponse(
                content=response.choices[0].message.content,
                model_used=self._text_model,
                provider=AIProviderType.OPENAI,
                tokens_used=response.usage.total_tokens if response.usage else None,
                duration_ms=duration
            )
        except Exception as e:
            raise AIProviderException(
                "Erro na geração de texto OpenAI",
                AIProviderType.OPENAI,
                str(e),
                retryable=True
            )

    def generate_with_vision(
        self,
        system_prompt: str,
        images: List[bytes],
        user_text: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> AIResponse:
        """Gera conteúdo usando GPT-4o Vision."""
        if not self.is_configured:
            raise AIProviderException(
                "OpenAI não está configurado",
                AIProviderType.OPENAI
            )

        temp = temperature if temperature is not None else AIModelConfig.OPENAI_TEMPERATURE
        tokens = max_tokens if max_tokens is not None else AIModelConfig.OPENAI_MAX_TOKENS

        try:
            # Construir conteúdo multimodal
            content: List[Dict[str, Any]] = []

            if user_text:
                content.append({"type": "text", "text": user_text})

            for img_bytes in images:
                base64_image = base64.b64encode(img_bytes).decode('utf-8')
                content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{base64_image}",
                        "detail": "high"
                    }
                })

            start_time = time.time()
            assert self._client is not None
            response = self._client.chat.completions.create(
                model=self._vision_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": content}
                ],
                temperature=temp,
                max_tokens=tokens
            )
            duration = self._measure_duration(start_time)

            return AIResponse(
                content=response.choices[0].message.content,
                model_used=self._vision_model,
                provider=AIProviderType.OPENAI,
                tokens_used=response.usage.total_tokens if response.usage else None,
                duration_ms=duration
            )
        except Exception as e:
            raise AIProviderException(
                "Erro na geração com visão OpenAI",
                AIProviderType.OPENAI,
                str(e),
                retryable=True
            )

    def extract_atestado_from_images(self, images: List[bytes]) -> Dict[str, Any]:
        """Extrai informacoes de atestado usando GPT-4o Vision."""
        from services.ai.extraction_service import AIExtractionService
        service = AIExtractionService()
        return service.extract_atestado_from_images(images, provider=self)

    def extract_atestado_info(self, texto: str) -> Dict[str, Any]:
        """Extrai informacoes de atestado a partir de texto."""
        from services.ai.extraction_service import AIExtractionService
        service = AIExtractionService()
        return service.extract_atestado_info(texto, provider=self)

    def extract_atestado_metadata(self, texto: str) -> Dict[str, Any]:
        """Extrai apenas metadados de atestado a partir de texto."""
        from services.ai.extraction_service import AIExtractionService
        service = AIExtractionService()
        return service.extract_atestado_metadata(texto, provider=self)

    def extract_edital_requirements(self, texto: str) -> List[Dict[str, Any]]:
        """Extrai requisitos de edital."""
        from services.ai.extraction_service import AIExtractionService
        service = AIExtractionService()
        return service.extract_edital_requirements(texto, provider=self)

    def get_model_info(self) -> Dict[str, Any]:
        """Retorna informações sobre os modelos configurados."""
        return {
            "provider": "OpenAI",
            "text_model": self._text_model,
            "vision_model": self._vision_model,
            "configured": self.is_configured,
            "temperature": AIModelConfig.OPENAI_TEMPERATURE,
            "max_tokens": AIModelConfig.OPENAI_MAX_TOKENS
        }
