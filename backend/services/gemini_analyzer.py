"""
Serviço de análise com IA usando Google Gemini.
Alternativa mais econômica para escala.
Suporta Gemini Vision para análise direta de imagens.
"""

import os
import json
from typing import List, Dict, Any
from dotenv import load_dotenv
from utils.json_helpers import clean_json_response
from exceptions import AINotConfiguredError, GeminiError
from config import AIModelConfig

load_dotenv()


class GeminiAnalyzer:
    """Analisador de documentos usando Google Gemini."""

    def __init__(self):
        api_key = os.getenv("GOOGLE_API_KEY")
        self._types = None
        self._use_new = False
        if not api_key or api_key == "sua-chave-google-aqui":
            self._client = None
            self._model = None
        else:
            try:
                from google import genai
                from google.genai import types
                self._client = genai.Client(api_key=api_key)
                self._types = types
                self._use_new = True
                self._model = AIModelConfig.GEMINI_MODEL
                self._pro_model = AIModelConfig.GEMINI_PRO_MODEL
            except ImportError:
                try:
                    import google.generativeai as genai_old
                    genai_old.configure(api_key=api_key)
                    self._client = genai_old
                    self._model = AIModelConfig.GEMINI_MODEL
                    self._pro_model = AIModelConfig.GEMINI_PRO_MODEL
                except ImportError:
                    self._client = None
                    self._model = None

    @property
    def is_configured(self) -> bool:
        """Verifica se a API está configurada."""
        return self._client is not None

    def _call_gemini(self, system_prompt: str, user_prompt: str) -> str:
        """
        Faz uma chamada a API do Gemini para texto.

        Args:
            system_prompt: Instrucao do sistema
            user_prompt: Prompt do usuario

        Returns:
            Resposta do modelo
        """
        if not self.is_configured:
            raise AINotConfiguredError("Google Gemini")

        try:
            if self._use_new:
                config = self._types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    temperature=AIModelConfig.GEMINI_TEMPERATURE,
                    max_output_tokens=AIModelConfig.GEMINI_MAX_TOKENS,
                    response_mime_type="application/json"
                )
                response = self._client.models.generate_content(
                    model=self._model,
                    contents=user_prompt,
                    config=config
                )
                return response.text

            model = self._client.GenerativeModel(
                model_name=self._model,
                system_instruction=system_prompt
            )

            response = model.generate_content(
                user_prompt,
                generation_config={
                    "temperature": AIModelConfig.GEMINI_TEMPERATURE,
                    "max_output_tokens": AIModelConfig.GEMINI_MAX_TOKENS,
                    "response_mime_type": "application/json"
                }
            )
            return response.text
        except Exception as e:
            raise GeminiError(str(e))

    def _call_gemini_vision(self, system_prompt: str, images: List[bytes], user_text: str = "") -> str:
        """
        Faz uma chamada a API do Gemini com imagens.

        Args:
            system_prompt: Instrucao do sistema
            images: Lista de imagens em bytes (PNG/JPEG)
            user_text: Texto adicional do usuario (opcional)

        Returns:
            Resposta do modelo
        """
        if not self.is_configured:
            raise AINotConfiguredError("Google Gemini")

        try:
            from PIL import Image
            import io

            if self._use_new:
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
                    temperature=AIModelConfig.GEMINI_TEMPERATURE,
                    max_output_tokens=AIModelConfig.GEMINI_MAX_TOKENS,
                    response_mime_type="application/json"
                )
                response = self._client.models.generate_content(
                    model=self._model,
                    contents=parts,
                    config=config
                )
                return response.text

            model = self._client.GenerativeModel(
                model_name=self._model,
                system_instruction=system_prompt
            )

            # Preparar conteudo multimodal
            content_parts: List[Any] = []

            if user_text:
                content_parts.append(user_text)

            for img_bytes in images:
                img = Image.open(io.BytesIO(img_bytes))
                content_parts.append(img)

            response = model.generate_content(
                content_parts,
                generation_config={
                    "temperature": AIModelConfig.GEMINI_TEMPERATURE,
                    "max_output_tokens": AIModelConfig.GEMINI_MAX_TOKENS,
                    "response_mime_type": "application/json"
                }
            )
            return response.text
        except Exception as e:
            raise GeminiError(str(e))

    def extract_atestado_from_images(self, images: List[bytes]) -> Dict[str, Any]:
        """
        Extrai informações de um atestado diretamente das imagens usando Gemini Vision.

        Args:
            images: Lista de imagens das páginas do documento (PNG bytes)

        Returns:
            Dicionário com as informações extraídas
        """
        system_prompt = """Você é um especialista em análise de atestados de capacidade técnica para licitações públicas no Brasil.

Analise CUIDADOSAMENTE as imagens do documento e extraia as seguintes informações:

1. descricao_servico: Descrição RESUMIDA do serviço/obra principal executado (1-2 linhas)
2. contratante: Nome da empresa/órgão contratante
3. servicos: Lista COMPLETA de TODOS os serviços executados com quantidades

IMPORTANTE PARA TABELAS DE SERVIÇOS:
- Identifique a coluna "Quantidade Executada" ou "Qtd" (NÃO confunda com "Custo Unitário")
- Regra: Valor Total ≈ Custo Unitário × Quantidade
- Inclua o código do item na descrição quando disponível (ex: "001.03.01 MOBILIZAÇÃO")
- Itens similares em séries diferentes (001.03.xx vs 001.04.xx) são itens DISTINTOS

FORMATO DE NÚMEROS BRASILEIRO:
- "1.843,84" = 1843.84 (ponto separa milhar, vírgula separa decimal)
- Sempre converta para formato numérico padrão (ponto decimal) no JSON

Retorne APENAS um JSON válido:
{
    "descricao_servico": "Descrição resumida da obra",
    "quantidade": 474487.96,
    "unidade": "R$",
    "contratante": "Nome do contratante",
    "data_emissao": "2022-04-11",
    "servicos": [
        {"descricao": "001.01.01 MOBILIZAÇÃO DE EQUIPAMENTOS", "quantidade": 1.00, "unidade": "UN"},
        {"descricao": "001.03.01 EXECUÇÃO DE ESTRUTURAS", "quantidade": 6.85, "unidade": "M3"}
    ]
}"""

        user_text = """Analise as imagens do documento e extraia TODOS os serviços executados.

INSTRUÇÕES:
1. Use a coluna "Quantidade Executada" (não "Custo Unitário")
2. Inclua o código do item na descrição quando visível
3. Extraia TODOS os itens de TODAS as séries/etapas
4. Converta números brasileiros (1.234,56) para formato padrão (1234.56)"""

        try:
            response = self._call_gemini_vision(system_prompt, images, user_text)
            # Limpar resposta e extrair JSON
            response = clean_json_response(response)
            return json.loads(response)
        except json.JSONDecodeError:
            return {
                "descricao_servico": None,
                "quantidade": None,
                "unidade": None,
                "contratante": None,
                "data_emissao": None,
                "servicos": []
            }

    def extract_atestado_info(self, texto: str) -> Dict[str, Any]:
        """
        Extrai informações de um atestado de capacidade técnica a partir de texto.

        Args:
            texto: Texto extraído do atestado

        Returns:
            Dicionário com as informações extraídas
        """
        system_prompt = """Você é um especialista em análise de atestados de capacidade técnica para licitações públicas no Brasil.

Analise o texto do documento e extraia:

1. descricao_servico: Descrição resumida do serviço principal
2. contratante: Nome do contratante
3. servicos: Lista de serviços com quantidades

FORMATO DE SAÍDA (JSON):
{
    "descricao_servico": "...",
    "quantidade": 0.0,
    "unidade": "R$",
    "contratante": "...",
    "data_emissao": "YYYY-MM-DD",
    "servicos": [
        {"descricao": "...", "quantidade": 0.0, "unidade": "UN"}
    ]
}

REGRAS:
- Use a coluna "Quantidade Executada" para quantidades
- Inclua códigos de item quando disponíveis
- Converta números BR (1.234,56) para padrão (1234.56)"""

        try:
            response = self._call_gemini(system_prompt, f"Analise este atestado:\n\n{texto}")
            response = clean_json_response(response)
            return json.loads(response)
        except json.JSONDecodeError:
            return {
                "descricao_servico": None,
                "quantidade": None,
                "unidade": None,
                "contratante": None,
                "data_emissao": None,
                "servicos": []
            }

    def extract_edital_requirements(self, texto: str) -> List[Dict[str, Any]]:
        """
        Extrai exigências de qualificação técnica de um edital.

        Args:
            texto: Texto extraído do edital

        Returns:
            Lista de exigências extraídas
        """
        system_prompt = """Você é um especialista em licitações públicas no Brasil.

Analise o texto e extraia as exigências de qualificação técnica.

FORMATO DE SAÍDA (JSON):
{
    "exigencias": [
        {
            "descricao": "Descrição do serviço exigido",
            "quantidade_minima": 100.0,
            "unidade": "M2",
            "percentual_minimo": 50.0
        }
    ]
}

REGRAS:
- Identifique quantitativos mínimos exigidos
- Use o percentual mencionado (geralmente 50%)
- Converta números BR para padrão"""

        try:
            response = self._call_gemini(system_prompt, f"Analise este edital:\n\n{texto}")
            response = response.strip()
            if response.startswith("```"):
                response = response.split("```")[1]
                if response.startswith("json"):
                    response = response[4:]

            data = json.loads(response.strip())
            return data.get("exigencias", [])
        except Exception:
            return []


# Instância singleton para uso global
gemini_analyzer = GeminiAnalyzer()
