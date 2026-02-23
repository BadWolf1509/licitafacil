"""Cliente HTTP para a API pública do PNCP."""
import asyncio
from typing import Any, Dict, List, Optional

import httpx

from config.base import PNCP_API_BASE_URL, PNCP_TIMEOUT_SECONDS
from logging_config import get_logger

logger = get_logger("services.pncp.client")


class PncpClient:
    """Cliente para consultar a API do Portal Nacional de Contratações Públicas."""

    _rate_limit_delay = 0.6  # ~1.67 req/s para não sobrecarregar

    async def _rate_limit(self) -> None:
        """Aplica delay entre requests para respeitar rate limit."""
        await asyncio.sleep(self._rate_limit_delay)

    async def buscar_contratacoes(
        self,
        data_inicial: str,
        data_final: str,
        pagina: int = 1,
        tamanho_pagina: int = 50,
        codigo_modalidade: Optional[str] = None,
        uf: Optional[str] = None,
        cnpj: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Busca contratações publicadas no PNCP.

        Args:
            data_inicial: Data inicial no formato YYYYMMDD
            data_final: Data final no formato YYYYMMDD
            pagina: Número da página (default 1)
            tamanho_pagina: Itens por página (max 50, PNCP rejeita >50)
            codigo_modalidade: Código da modalidade de contratação
            uf: Sigla da UF
            cnpj: CNPJ do órgão

        Returns:
            Dict com data, totalRegistros, totalPaginas, etc.
        """
        await self._rate_limit()

        params: Dict[str, Any] = {
            "dataInicial": data_inicial,
            "dataFinal": data_final,
            "pagina": pagina,
            "tamanhoPagina": tamanho_pagina,
        }
        if codigo_modalidade:
            params["codigoModalidadeContratacao"] = codigo_modalidade
        if uf:
            params["uf"] = uf
        if cnpj:
            params["cnpjOrgao"] = cnpj

        url = f"{PNCP_API_BASE_URL}/contratacoes/publicacao"

        async with httpx.AsyncClient(timeout=PNCP_TIMEOUT_SECONDS) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            if response.status_code == 204:
                return {"data": [], "totalRegistros": 0, "totalPaginas": 0, "paginasRestantes": 0, "empty": True}
            return response.json()

    async def buscar_todas_paginas(
        self,
        data_inicial: str,
        data_final: str,
        max_paginas: int = 5,
        **kwargs: Any,
    ) -> List[Dict[str, Any]]:
        """
        Busca todas as páginas de resultados (até max_paginas).

        Returns:
            Lista flat de todos os itens encontrados.
        """
        todos_items: List[Dict[str, Any]] = []
        pagina = 1

        while pagina <= max_paginas:
            try:
                resultado = await self.buscar_contratacoes(
                    data_inicial=data_inicial,
                    data_final=data_final,
                    pagina=pagina,
                    **kwargs,
                )
            except (httpx.HTTPError, httpx.TimeoutException) as e:
                logger.warning(f"Erro ao buscar página {pagina}: {e}")
                break

            data = resultado.get("data", [])
            todos_items.extend(data)

            paginas_restantes = resultado.get("paginasRestantes", 0)
            if paginas_restantes <= 0 or not data:
                break

            pagina += 1

        return todos_items


pncp_client = PncpClient()
