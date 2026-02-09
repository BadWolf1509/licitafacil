"""
Filtros de validação para serviços extraídos.

Extrai e centraliza lógica de filtragem do DocumentProcessor,
oferecendo filtros para remover itens inválidos ou incompletos.

NOTA: Este módulo é diferente de services/extraction/item_filters.py,
que contém filtros de baixo nível para extração. Este módulo contém
filtros de alto nível para pós-processamento de documentos.
"""

import logging
import re
from typing import Any, Dict, List, Optional, Set

from services.extraction import item_code_in_text, parse_quantity
from services.processing_helpers import normalize_item_code

logger = logging.getLogger(__name__)


class ServiceFilter:
    """
    Filtra serviços inválidos ou incompletos.

    Filtros disponíveis:
    - filter_headers: Remove cabeçalhos de seção
    - filter_no_quantity: Remove itens sem quantidade
    - filter_no_code: Remove itens sem código válido
    - filter_not_in_sources: Remove itens não encontrados em fontes
    """

    def __init__(
        self,
        servicos: List[Dict[str, Any]],
        texto: str = "",
        servicos_table: Optional[List[Dict[str, Any]]] = None
    ):
        """
        Inicializa o filtro com a lista de serviços e contexto.

        Args:
            servicos: Lista de dicionários de serviços
            texto: Texto do documento (para validação)
            servicos_table: Serviços extraídos de tabelas (para validação cruzada)
        """
        self.servicos = servicos if servicos else []
        self.texto = texto or ""
        self.servicos_table = servicos_table or []

    def filter_headers(self) -> List[Dict[str, Any]]:
        """
        Remove cabeçalhos de seção que não são itens reais.

        Cabeçalhos de seção são itens como "1.4.10 COBERTURA" que servem apenas
        para agrupar sub-itens (1.4.10.1, 1.4.10.2, etc.) e não devem ser
        contabilizados como serviços.

        Critérios para identificar cabeçalhos:
        1. Descrição muito curta (menos de 25 caracteres)
        2. Tem pelo menos um item filho (código que começa com o código do pai + ".")

        Returns:
            Lista filtrada sem cabeçalhos de seção
        """
        if not self.servicos:
            return self.servicos

        # Construir set de códigos para busca rápida
        all_codes: Set[str] = set()
        for s in self.servicos:
            code = s.get("item")
            if code:
                # Remover prefixo S1-, S2-, etc.
                clean_code = re.sub(r'^S\d+-', '', str(code))
                all_codes.add(clean_code)

        filtered = []
        removed = 0
        for s in self.servicos:
            code = s.get("item")
            desc = s.get("descricao") or ""

            # Só verificar itens com código e descrição curta
            if code and len(desc.strip()) < 25:
                clean_code = re.sub(r'^S\d+-', '', str(code))
                # Verificar se tem filhos (códigos que começam com este + ".")
                has_children = any(
                    c.startswith(clean_code + ".") for c in all_codes if c != clean_code
                )
                if has_children:
                    removed += 1
                    logger.info(f"[FILTRO] Removido cabeçalho de seção: {code} ({desc[:30]})")
                    continue

            filtered.append(s)

        if removed > 0:
            logger.info(f"[FILTRO] {removed} cabeçalhos de seção removidos")

        return filtered

    def filter_no_quantity(self) -> List[Dict[str, Any]]:
        """
        Remove itens que não têm quantidade definida.

        Filtro estrito: remove itens com quantidade nula ou zero.

        Returns:
            Lista filtrada sem itens sem quantidade
        """
        if not self.servicos:
            return self.servicos

        return [
            s for s in self.servicos
            if parse_quantity(s.get("quantidade")) not in (None, 0)
        ]

    def filter_no_code(self, min_items_with_code: int = 5) -> List[Dict[str, Any]]:
        """
        Remove itens sem código de item quando há itens suficientes com código.

        Itens sem código (item=None) geralmente são descrições gerais do documento
        (ex: "Execução de obra de SISTEMAS DE ILUMINAÇÃO") que foram erroneamente
        extraídos como serviços pela IA.

        Só remove itens sem código quando há pelo menos `min_items_with_code` itens
        com código, para não afetar documentos simples sem numeração.

        Args:
            min_items_with_code: Mínimo de itens com código para ativar o filtro

        Returns:
            Lista filtrada de serviços
        """
        if not self.servicos:
            return self.servicos

        # Contar itens com e sem código
        com_codigo = [s for s in self.servicos if s.get("item")]
        sem_codigo = [s for s in self.servicos if not s.get("item")]

        # Se há poucos itens com código, manter todos (documento pode não ter numeração)
        if len(com_codigo) < min_items_with_code:
            return self.servicos

        # Se há itens suficientes com código, remover os sem código
        if sem_codigo:
            logger.info(
                f"[FILTRO] Removendo {len(sem_codigo)} itens sem código de item "
                f"(há {len(com_codigo)} itens com código)"
            )
            for s in sem_codigo:
                desc = (s.get("descricao") or "")[:50]
                logger.info(f"[FILTRO] Removido item sem código: {desc}...")

        return com_codigo

    def filter_not_in_sources(self) -> List[Dict[str, Any]]:
        """
        Remove itens que não aparecem no texto nem nas tabelas originais.

        Este filtro valida que os itens extraídos existem em pelo menos uma
        das fontes originais (texto OCR ou tabelas extraídas).

        Returns:
            Lista filtrada com apenas itens validados
        """
        if not self.servicos or not self.texto:
            return self.servicos

        # Coletar códigos das tabelas
        table_items: Set[str] = set()
        for s in self.servicos_table:
            code = normalize_item_code(s.get("item"))
            if code:
                table_items.add(code)

        filtered = []
        removed = []
        for s in self.servicos:
            item = s.get("item")
            code = normalize_item_code(item)
            if not code:
                filtered.append(s)
                continue
            if item_code_in_text(code, self.texto):
                filtered.append(s)
                continue
            removed.append((item, s.get("descricao"), code in table_items))

        if removed:
            logger.info(
                f"[FILTRO] Removendo {len(removed)} itens sem código no texto"
            )
            for item, desc, in_table in removed:
                desc_preview = (desc or "")[:60]
                origem = "tabela" if in_table else "ia"
                logger.info(f"[FILTRO] Removido item {item} (origem={origem}): {desc_preview}...")

        return filtered

    def filter_all(self, min_items_with_code: int = 5) -> List[Dict[str, Any]]:
        """
        Aplica todos os filtros em sequência.

        Ordem de execução:
        1. filter_headers - Remove cabeçalhos de seção
        2. filter_no_quantity - Remove itens sem quantidade
        3. filter_no_code - Remove itens sem código

        Args:
            min_items_with_code: Mínimo de itens com código para filtro de código

        Returns:
            Lista com todos os filtros aplicados
        """
        result = self.filter_headers()
        result = ServiceFilter(result).filter_no_quantity()
        result = ServiceFilter(result).filter_no_code(min_items_with_code)
        return result


def filter_servicos(
    servicos: List[Dict[str, Any]],
    texto: str = "",
    min_items_with_code: int = 5
) -> List[Dict[str, Any]]:
    """
    Função de conveniência para aplicar todos os filtros.

    Args:
        servicos: Lista de serviços
        texto: Texto do documento
        min_items_with_code: Mínimo de itens com código para filtro

    Returns:
        Lista filtrada
    """
    return ServiceFilter(servicos, texto).filter_all(min_items_with_code)


def filter_headers(servicos: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Função de conveniência para filtrar cabeçalhos.

    Args:
        servicos: Lista de serviços

    Returns:
        Lista sem cabeçalhos de seção
    """
    return ServiceFilter(servicos).filter_headers()


def filter_no_quantity(servicos: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Função de conveniência para filtrar itens sem quantidade.

    Args:
        servicos: Lista de serviços

    Returns:
        Lista sem itens sem quantidade
    """
    return ServiceFilter(servicos).filter_no_quantity()


def filter_no_code(
    servicos: List[Dict[str, Any]],
    min_items_with_code: int = 5
) -> List[Dict[str, Any]]:
    """
    Função de conveniência para filtrar itens sem código.

    Args:
        servicos: Lista de serviços
        min_items_with_code: Mínimo de itens com código

    Returns:
        Lista filtrada
    """
    return ServiceFilter(servicos).filter_no_code(min_items_with_code)
