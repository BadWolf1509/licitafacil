"""Tests for PncpClient with mocked httpx."""
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from services.pncp.client import PncpClient


@pytest.fixture
def pncp_client():
    """Create a PncpClient instance with zero rate limit delay for speed."""
    client = PncpClient()
    client._rate_limit_delay = 0  # Skip delay in tests
    return client


# ===========================================================================
# buscar_contratacoes
# ===========================================================================


class TestBuscarContratacoes:

    @pytest.mark.asyncio
    @patch("services.pncp.client.httpx.AsyncClient")
    async def test_buscar_contratacoes_valid_response(self, MockAsyncClient, pncp_client):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": [{"id": 1, "objetoCompra": "Pavimentacao"}],
            "totalRegistros": 1,
            "totalPaginas": 1,
            "numeroPagina": 1,
            "paginasRestantes": 0,
        }
        mock_response.raise_for_status = MagicMock()

        mock_client_instance = AsyncMock()
        mock_client_instance.get.return_value = mock_response
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=False)
        MockAsyncClient.return_value = mock_client_instance

        result = await pncp_client.buscar_contratacoes(
            data_inicial="20260101",
            data_final="20260115",
        )

        assert result["totalRegistros"] == 1
        assert len(result["data"]) == 1
        mock_client_instance.get.assert_called_once()

    @pytest.mark.asyncio
    @patch("services.pncp.client.httpx.AsyncClient")
    async def test_buscar_contratacoes_http_error(self, MockAsyncClient, pncp_client):
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Server Error", request=MagicMock(), response=MagicMock(status_code=500),
        )

        mock_client_instance = AsyncMock()
        mock_client_instance.get.return_value = mock_response
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=False)
        MockAsyncClient.return_value = mock_client_instance

        with pytest.raises(httpx.HTTPStatusError):
            await pncp_client.buscar_contratacoes(
                data_inicial="20260101",
                data_final="20260115",
            )

    @pytest.mark.asyncio
    @patch("services.pncp.client.httpx.AsyncClient")
    async def test_buscar_contratacoes_timeout(self, MockAsyncClient, pncp_client):
        mock_client_instance = AsyncMock()
        mock_client_instance.get.side_effect = httpx.TimeoutException("Timeout")
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=False)
        MockAsyncClient.return_value = mock_client_instance

        with pytest.raises(httpx.TimeoutException):
            await pncp_client.buscar_contratacoes(
                data_inicial="20260101",
                data_final="20260115",
            )

    @pytest.mark.asyncio
    @patch("services.pncp.client.httpx.AsyncClient")
    async def test_buscar_contratacoes_params_passed(self, MockAsyncClient, pncp_client):
        mock_response = MagicMock()
        mock_response.json.return_value = {"data": [], "totalRegistros": 0}
        mock_response.raise_for_status = MagicMock()

        mock_client_instance = AsyncMock()
        mock_client_instance.get.return_value = mock_response
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=False)
        MockAsyncClient.return_value = mock_client_instance

        await pncp_client.buscar_contratacoes(
            data_inicial="20260101",
            data_final="20260115",
            pagina=2,
            tamanho_pagina=100,
            uf="SP",
            codigo_modalidade="6",
            cnpj="12345678000100",
        )

        call_args = mock_client_instance.get.call_args
        params = call_args[1]["params"]
        assert params["dataInicial"] == "20260101"
        assert params["dataFinal"] == "20260115"
        assert params["pagina"] == 2
        assert params["tamanhoPagina"] == 100
        assert params["uf"] == "SP"
        assert params["codigoModalidadeContratacao"] == "6"
        assert params["cnpjOrgao"] == "12345678000100"


# ===========================================================================
# buscar_todas_paginas
# ===========================================================================


class TestBuscarTodasPaginas:

    @pytest.mark.asyncio
    async def test_buscar_todas_paginas_multiple(self, pncp_client):
        """Fetches multiple pages until paginasRestantes == 0."""
        call_count = 0

        async def mock_buscar(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return {
                    "data": [{"id": 1}, {"id": 2}],
                    "paginasRestantes": 1,
                }
            return {
                "data": [{"id": 3}],
                "paginasRestantes": 0,
            }

        pncp_client.buscar_contratacoes = mock_buscar

        result = await pncp_client.buscar_todas_paginas(
            data_inicial="20260101",
            data_final="20260115",
        )

        assert len(result) == 3
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_buscar_todas_paginas_stops_when_no_remaining(self, pncp_client):
        """Stops when paginasRestantes is 0."""
        async def mock_buscar(**kwargs):
            return {
                "data": [{"id": 1}],
                "paginasRestantes": 0,
            }

        pncp_client.buscar_contratacoes = mock_buscar

        result = await pncp_client.buscar_todas_paginas(
            data_inicial="20260101",
            data_final="20260115",
        )

        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_buscar_todas_paginas_stops_on_error(self, pncp_client):
        """Stops gracefully on HTTP error without raising."""
        call_count = 0

        async def mock_buscar(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return {"data": [{"id": 1}], "paginasRestantes": 2}
            raise httpx.HTTPError("Server error")

        pncp_client.buscar_contratacoes = mock_buscar

        result = await pncp_client.buscar_todas_paginas(
            data_inicial="20260101",
            data_final="20260115",
        )

        assert len(result) == 1  # Only first page
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_buscar_todas_paginas_max_paginas_limit(self, pncp_client):
        """Respects max_paginas limit."""
        call_count = 0

        async def mock_buscar(**kwargs):
            nonlocal call_count
            call_count += 1
            return {
                "data": [{"id": call_count}],
                "paginasRestantes": 10,  # Always more pages
            }

        pncp_client.buscar_contratacoes = mock_buscar

        result = await pncp_client.buscar_todas_paginas(
            data_inicial="20260101",
            data_final="20260115",
            max_paginas=3,
        )

        assert len(result) == 3
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_buscar_todas_paginas_stops_on_empty_data(self, pncp_client):
        """Stops when data list is empty even if paginasRestantes > 0."""
        call_count = 0

        async def mock_buscar(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return {"data": [{"id": 1}], "paginasRestantes": 5}
            return {"data": [], "paginasRestantes": 4}

        pncp_client.buscar_contratacoes = mock_buscar

        result = await pncp_client.buscar_todas_paginas(
            data_inicial="20260101",
            data_final="20260115",
        )

        assert len(result) == 1
        assert call_count == 2
