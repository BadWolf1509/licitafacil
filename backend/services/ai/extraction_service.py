"""
Servico unificado de extracao via IA.

Centraliza toda a logica de extracao de documentos usando IA,
independente do provedor especifico (OpenAI, Gemini, etc.).
"""

import json
from typing import Any, Dict, List, Optional

from prompts import (
    get_atestado_vision_prompts,
    get_atestado_text_prompt,
    get_edital_prompt,
)
from utils.json_helpers import clean_json_response
from services.extraction import filter_classification_paths
from services.base_ai_provider import BaseAIProvider


class AIExtractionService:
    """
    Servico de extracao de documentos usando IA.

    Fornece metodos de alto nivel para extracao de informacoes
    de atestados e editais, trabalhando com qualquer provedor
    que implemente BaseAIProvider.
    """

    BATCH_SIZE = 2  # Paginas por batch para documentos longos

    def __init__(self, provider: Optional[BaseAIProvider] = None):
        """
        Inicializa o servico de extracao.

        Args:
            provider: Provedor de IA a ser usado. Se None, usa o padrao.
        """
        self._provider = provider

    def set_provider(self, provider: BaseAIProvider) -> None:
        """Define o provedor de IA a ser usado."""
        self._provider = provider

    @property
    def provider(self) -> BaseAIProvider:
        """Retorna o provedor configurado."""
        if self._provider is None:
            raise ValueError("Nenhum provedor de IA configurado")
        return self._provider

    # =========================================================================
    # Extracao de Atestado via Imagens (Vision)
    # =========================================================================

    def extract_atestado_from_images(
        self,
        images: List[bytes],
        provider: Optional[BaseAIProvider] = None
    ) -> Dict[str, Any]:
        """
        Extrai informacoes de atestado diretamente das imagens.

        Usa modelo de visao (GPT-4o, Gemini Vision) para interpretar
        as imagens sem depender de OCR.

        Args:
            images: Lista de imagens das paginas (PNG bytes)
            provider: Provedor a usar (opcional, usa padrao se None)

        Returns:
            Dicionario com informacoes extraidas
        """
        ai = provider or self.provider
        prompts = get_atestado_vision_prompts()

        try:
            if len(images) > self.BATCH_SIZE:
                result = self._process_multi_page_document(
                    ai, images, prompts["system"], prompts["user"]
                )
            else:
                result = self._process_vision_batch(
                    ai, images, prompts["system"], prompts["user"], 0, len(images)
                )

            # Filtrar classificacoes invalidas
            if result and "servicos" in result and result["servicos"]:
                result["servicos"] = filter_classification_paths(result["servicos"])

            return result or self._empty_atestado_result()

        except json.JSONDecodeError:
            return self._empty_atestado_result()

    def _process_multi_page_document(
        self,
        ai: BaseAIProvider,
        images: List[bytes],
        system_prompt: str,
        user_text: str
    ) -> Dict[str, Any]:
        """
        Processa documento com multiplas paginas em batches.

        Args:
            ai: Provedor de IA
            images: Lista de imagens
            system_prompt: Prompt de sistema
            user_text: Texto do usuario

        Returns:
            Resultado consolidado
        """
        all_servicos: List[Dict[str, Any]] = []
        result: Dict[str, Any] = {}

        for batch_index, i in enumerate(range(0, len(images), self.BATCH_SIZE)):
            batch = images[i:i + self.BATCH_SIZE]
            batch_result = self._process_vision_batch(
                ai, batch, system_prompt, user_text, batch_index, len(images)
            )

            if not result:
                result = batch_result

            if "servicos" in batch_result and batch_result["servicos"]:
                all_servicos.extend(batch_result["servicos"])

        result["servicos"] = self._deduplicate_servicos_by_item(all_servicos)
        return result

    def _process_vision_batch(
        self,
        ai: BaseAIProvider,
        batch: List[bytes],
        system_prompt: str,
        user_text: str,
        batch_index: int,
        total_images: int
    ) -> Dict[str, Any]:
        """
        Processa um batch de imagens.

        Args:
            ai: Provedor de IA
            batch: Imagens do batch
            system_prompt: Prompt de sistema
            user_text: Texto base
            batch_index: Indice do batch
            total_images: Total de imagens

        Returns:
            Resultado parseado
        """
        batch_user_text = user_text
        if batch_index > 0:
            start_page = batch_index * self.BATCH_SIZE + 1
            end_page = min(start_page + self.BATCH_SIZE - 1, total_images)
            batch_user_text += f"\n\nEsta e a continuacao do documento (paginas {start_page}-{end_page})."

        response = ai.generate_with_vision(system_prompt, batch, batch_user_text)
        cleaned = clean_json_response(response.content)
        return json.loads(cleaned)

    def _deduplicate_servicos_by_item(
        self,
        servicos: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Remove servicos duplicados baseado no codigo do item.

        Args:
            servicos: Lista de servicos (pode ter duplicatas)

        Returns:
            Lista de servicos unicos
        """
        seen_items: set = set()
        unique_servicos: List[Dict[str, Any]] = []

        for s in servicos:
            item = s.get("item", "")
            if item and item not in seen_items:
                seen_items.add(item)
                unique_servicos.append(s)
            elif not item:
                unique_servicos.append(s)

        return unique_servicos

    # =========================================================================
    # Extracao de Atestado via Texto (OCR)
    # =========================================================================

    def extract_atestado_info(
        self,
        texto: str,
        provider: Optional[BaseAIProvider] = None
    ) -> Dict[str, Any]:
        """
        Extrai informacoes de atestado a partir de texto OCR.

        Args:
            texto: Texto extraido do documento
            provider: Provedor a usar (opcional)

        Returns:
            Dicionario com informacoes extraidas
        """
        ai = provider or self.provider
        system_prompt = get_atestado_text_prompt()
        user_prompt = (
            "Analise o seguinte atestado de capacidade tecnica. "
            "Extraia APENAS os itens da 'Planilha de Quantitativos Executados' "
            "ou 'Relatorio de Servicos Executados'. "
            "NAO extraia classificacoes ou caminhos com '>':\n\n"
            f"{texto}"
        )

        try:
            response = ai.generate_text(system_prompt, user_prompt)
            cleaned = clean_json_response(response.content)
            result = json.loads(cleaned)

            if "servicos" in result and result["servicos"]:
                result["servicos"] = filter_classification_paths(result["servicos"])

            return result

        except json.JSONDecodeError:
            return {
                "descricao_servico": texto[:500] if texto else None,
                "quantidade": None,
                "unidade": None,
                "contratante": None,
                "data_emissao": None,
                "servicos": []
            }

    def extract_atestado_metadata(
        self,
        texto: str,
        provider: Optional[BaseAIProvider] = None
    ) -> Dict[str, Any]:
        """
        Extrai apenas metadados do atestado (sem lista de servicos).

        Args:
            texto: Texto extraido do documento
            provider: Provedor a usar (opcional)

        Returns:
            Dicionario com metadados
        """
        ai = provider or self.provider
        system_prompt = """Voce e um especialista em analise de atestados de capacidade tecnica para licitacoes publicas no Brasil.

Extraia APENAS os metadados do documento, sem listar servicos:
1. descricao_servico: descricao resumida da obra/servico principal (1-2 linhas)
2. contratante: nome do contratante
3. quantidade: valor do contrato em R$ (opcional)
4. unidade: "R$" quando houver valor do contrato (opcional)
5. data_emissao: data de emissao (YYYY-MM-DD, opcional)

Retorne APENAS um JSON valido. Se algum campo nao estiver disponivel, use null.

Formato:
{
  "descricao_servico": "...",
  "quantidade": 0.0,
  "unidade": "R$",
  "contratante": "...",
  "data_emissao": "YYYY-MM-DD"
}"""

        user_prompt = f"Analise o seguinte atestado e extraia apenas os metadados:\n\n{texto}"

        try:
            response = ai.generate_text(system_prompt, user_prompt)
            cleaned = clean_json_response(response.content)
            result = json.loads(cleaned)
            return {
                "descricao_servico": result.get("descricao_servico"),
                "quantidade": result.get("quantidade"),
                "unidade": result.get("unidade"),
                "contratante": result.get("contratante"),
                "data_emissao": result.get("data_emissao")
            }
        except json.JSONDecodeError:
            return {
                "descricao_servico": None,
                "quantidade": None,
                "unidade": None,
                "contratante": None,
                "data_emissao": None
            }

    # =========================================================================
    # Extracao de Edital
    # =========================================================================

    def extract_edital_requirements(
        self,
        texto: str,
        provider: Optional[BaseAIProvider] = None
    ) -> List[Dict[str, Any]]:
        """
        Extrai exigencias de capacidade tecnica de um edital.

        Args:
            texto: Texto do edital
            provider: Provedor a usar (opcional)

        Returns:
            Lista de exigencias
        """
        ai = provider or self.provider
        system_prompt = get_edital_prompt()
        user_prompt = (
            "Extraia as exigencias de capacidade tecnica do seguinte trecho de edital:\n\n"
            f"{texto}"
        )

        try:
            response = ai.generate_text(system_prompt, user_prompt)
            cleaned = clean_json_response(response.content)
            return json.loads(cleaned)
        except json.JSONDecodeError:
            return []

    # =========================================================================
    # Utilitarios
    # =========================================================================

    def _empty_atestado_result(self) -> Dict[str, Any]:
        """Retorna resultado vazio padrao para atestado."""
        return {
            "descricao_servico": None,
            "quantidade": None,
            "unidade": None,
            "contratante": None,
            "data_emissao": None,
            "servicos": []
        }


# Instancia singleton para uso conveniente
extraction_service = AIExtractionService()
