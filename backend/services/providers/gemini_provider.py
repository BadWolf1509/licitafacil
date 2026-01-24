"""
Implementação do AIProvider para Google Gemini.

Encapsula a lógica de comunicação com a API do Gemini,
suportando tanto a nova SDK quanto a versão legada.
"""

import os
import time
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv

from services.base_ai_provider import (
    BaseAIProvider,
    AIProviderType,
    AIResponse,
    AIProviderException
)
from config import AIModelConfig

load_dotenv()


class GeminiProvider(BaseAIProvider):
    """Implementação do AIProvider para Google Gemini."""

    def __init__(self, api_key: Optional[str] = None):
        self._model_name = AIModelConfig.GEMINI_MODEL
        self._pro_model = AIModelConfig.GEMINI_PRO_MODEL
        self._types: Any = None
        self._use_new_sdk = False
        super().__init__(api_key)

    def _initialize(self) -> None:
        """Inicializa o cliente Gemini."""
        api_key = self._api_key or os.getenv("GOOGLE_API_KEY")
        if not api_key or api_key == "sua-chave-google-aqui":
            self._client = None
            return

        allow_legacy = AIModelConfig.GEMINI_ALLOW_LEGACY

        # Tentar nova SDK primeiro
        try:
            from google import genai
            from google.genai import types
            self._client = genai.Client(api_key=api_key)
            self._types = types
            self._use_new_sdk = True
        except ImportError:
            if not allow_legacy:
                self._client = None
                return
            # Fallback para SDK legada (opcional)
            try:
                import google.generativeai as genai_old
                genai_old.configure(api_key=api_key)
                self._client = genai_old
                self._use_new_sdk = False
            except ImportError:
                self._client = None

    @property
    def is_configured(self) -> bool:
        """Verifica se a API está configurada."""
        return self._client is not None

    @property
    def provider_type(self) -> AIProviderType:
        return AIProviderType.GEMINI

    @property
    def model_name(self) -> str:
        return self._model_name

    def generate_text(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> AIResponse:
        """Gera texto usando Gemini."""
        if not self.is_configured:
            raise AIProviderException(
                "Gemini não está configurado",
                AIProviderType.GEMINI
            )

        temp = temperature if temperature is not None else AIModelConfig.GEMINI_TEMPERATURE
        tokens = max_tokens if max_tokens is not None else AIModelConfig.GEMINI_MAX_TOKENS

        try:
            start_time = time.time()

            if self._use_new_sdk:
                assert self._types is not None
                assert self._client is not None
                config = self._types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    temperature=temp,
                    max_output_tokens=tokens,
                    response_mime_type="application/json"
                )
                response = self._client.models.generate_content(
                    model=self._model_name,
                    contents=user_prompt,
                    config=config
                )
                content = response.text
            else:
                assert self._client is not None
                model = self._client.GenerativeModel(
                    model_name=self._model_name,
                    system_instruction=system_prompt
                )
                response = model.generate_content(
                    user_prompt,
                    generation_config={
                        "temperature": temp,
                        "max_output_tokens": tokens,
                        "response_mime_type": "application/json"
                    }
                )
                content = response.text

            duration = self._measure_duration(start_time)

            return AIResponse(
                content=content,
                model_used=self._model_name,
                provider=AIProviderType.GEMINI,
                duration_ms=duration
            )
        except Exception as e:
            raise AIProviderException(
                "Erro na geração de texto Gemini",
                AIProviderType.GEMINI,
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
        """Gera conteúdo usando Gemini Vision."""
        if not self.is_configured:
            raise AIProviderException(
                "Gemini não está configurado",
                AIProviderType.GEMINI
            )

        temp = temperature if temperature is not None else AIModelConfig.GEMINI_TEMPERATURE
        tokens = max_tokens if max_tokens is not None else AIModelConfig.GEMINI_MAX_TOKENS

        try:
            start_time = time.time()

            if self._use_new_sdk:
                assert self._types is not None
                assert self._client is not None
                parts: List[Any] = []
                if user_text:
                    parts.append(user_text)

                for img_bytes in images:
                    parts.append(self._types.Part.from_bytes(
                        data=img_bytes,
                        mime_type="image/png"
                    ))

                config = self._types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    temperature=temp,
                    max_output_tokens=tokens,
                    response_mime_type="application/json"
                )
                response = self._client.models.generate_content(
                    model=self._model_name,
                    contents=parts,
                    config=config
                )
                content = response.text
            else:
                assert self._client is not None
                from PIL import Image
                import io

                model = self._client.GenerativeModel(
                    model_name=self._model_name,
                    system_instruction=system_prompt
                )

                content_parts: List[Any] = []
                if user_text:
                    content_parts.append(user_text)

                for img_bytes in images:
                    img = Image.open(io.BytesIO(img_bytes))
                    content_parts.append(img)

                response = model.generate_content(
                    content_parts,
                    generation_config={
                        "temperature": temp,
                        "max_output_tokens": tokens,
                        "response_mime_type": "application/json"
                    }
                )
                content = response.text

            duration = self._measure_duration(start_time)

            return AIResponse(
                content=content,
                model_used=self._model_name,
                provider=AIProviderType.GEMINI,
                duration_ms=duration
            )
        except Exception as e:
            raise AIProviderException(
                "Erro na geração com visão Gemini",
                AIProviderType.GEMINI,
                str(e),
                retryable=True
            )

    def extract_atestado_from_images(self, images: List[bytes]) -> Dict[str, Any]:
        """Extrai informacoes de atestado usando Gemini Vision."""
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
            "provider": "Google Gemini",
            "model": self._model_name,
            "pro_model": self._pro_model,
            "configured": self.is_configured,
            "sdk_version": "new" if self._use_new_sdk else "legacy",
            "temperature": AIModelConfig.GEMINI_TEMPERATURE,
            "max_tokens": AIModelConfig.GEMINI_MAX_TOKENS
        }
