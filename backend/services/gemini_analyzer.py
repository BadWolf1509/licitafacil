"""
Serviço de análise com IA usando Google Gemini.
Alternativa mais econômica para escala.
Suporta Gemini Vision para análise direta de imagens.
"""

import os
import json
import base64
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv

load_dotenv()


class GeminiAnalyzer:
    """Analisador de documentos usando Google Gemini."""

    def __init__(self):
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key or api_key == "sua-chave-google-aqui":
            self._client = None
            self._model = None
        else:
            try:
                import google.generativeai as genai
                genai.configure(api_key=api_key)
                self._client = genai
                self._model = "gemini-2.0-flash"  # Modelo mais rápido e econômico
                self._pro_model = "gemini-2.0-flash"  # Usar Flash para tudo (mais barato)
            except ImportError:
                self._client = None
                self._model = None

    @property
    def is_configured(self) -> bool:
        """Verifica se a API está configurada."""
        return self._client is not None

    def _call_gemini(self, system_prompt: str, user_prompt: str) -> str:
        """
        Faz uma chamada à API do Gemini para texto.

        Args:
            system_prompt: Instrução do sistema
            user_prompt: Prompt do usuário

        Returns:
            Resposta do modelo
        """
        if not self.is_configured:
            raise Exception("API Google não configurada. Defina GOOGLE_API_KEY no arquivo .env")

        try:
            model = self._client.GenerativeModel(
                model_name=self._model,
                system_instruction=system_prompt
            )

            response = model.generate_content(
                user_prompt,
                generation_config={
                    "temperature": 0,
                    "max_output_tokens": 16000,
                    "response_mime_type": "application/json"
                }
            )
            return response.text
        except Exception as e:
            raise Exception(f"Erro na API Google Gemini: {str(e)}")

    def _call_gemini_vision(self, system_prompt: str, images: List[bytes], user_text: str = "") -> str:
        """
        Faz uma chamada à API do Gemini com imagens.

        Args:
            system_prompt: Instrução do sistema
            images: Lista de imagens em bytes (PNG/JPEG)
            user_text: Texto adicional do usuário (opcional)

        Returns:
            Resposta do modelo
        """
        if not self.is_configured:
            raise Exception("API Google não configurada. Defina GOOGLE_API_KEY no arquivo .env")

        try:
            from PIL import Image
            import io

            model = self._client.GenerativeModel(
                model_name=self._model,
                system_instruction=system_prompt
            )

            # Preparar conteúdo multimodal
            content_parts = []

            if user_text:
                content_parts.append(user_text)

            # Adicionar imagens
            for img_bytes in images:
                img = Image.open(io.BytesIO(img_bytes))
                content_parts.append(img)

            response = model.generate_content(
                content_parts,
                generation_config={
                    "temperature": 0,
                    "max_output_tokens": 16000,
                    "response_mime_type": "application/json"
                }
            )
            return response.text
        except Exception as e:
            raise Exception(f"Erro na API Google Gemini Vision: {str(e)}")

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
            response = response.strip()
            if response.startswith("```json"):
                response = response[7:]
            if response.startswith("```"):
                response = response[3:]
            if response.endswith("```"):
                response = response[:-3]

            return json.loads(response.strip())
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
            response = response.strip()
            if response.startswith("```json"):
                response = response[7:]
            if response.startswith("```"):
                response = response[3:]
            if response.endswith("```"):
                response = response[:-3]

            return json.loads(response.strip())
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
        except:
            return []


# Instância singleton para uso global
gemini_analyzer = GeminiAnalyzer()
