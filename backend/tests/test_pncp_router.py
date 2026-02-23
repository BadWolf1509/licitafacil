"""Tests for PNCP router endpoints with mocked dependencies."""
from datetime import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from auth import get_current_approved_user
from database import get_db
from models.pncp import PncpResultadoStatus
from routers.pncp import router

# ---------------------------------------------------------------------------
# Test App Setup
# ---------------------------------------------------------------------------

app = FastAPI()
app.include_router(router)

# Mock user
mock_user = MagicMock()
mock_user.id = 1
mock_user.is_admin = False
mock_user.email = "pncp@teste.com"
mock_user.supabase_id = "fake-uuid"


@pytest.fixture
def mock_db():
    db = MagicMock()
    return db


@pytest.fixture
def client(mock_db):
    """TestClient with overridden dependencies."""
    app.dependency_overrides[get_current_approved_user] = lambda: mock_user
    app.dependency_overrides[get_db] = lambda: mock_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Helper: build mock monitoramento
# ---------------------------------------------------------------------------

def _mock_monitoramento(**overrides):
    m = MagicMock()
    defaults = {
        "id": 1,
        "user_id": 1,
        "nome": "Monitor Teste",
        "ativo": True,
        "palavras_chave": ["asfalto"],
        "ufs": ["SP"],
        "modalidades": None,
        "esferas": None,
        "valor_minimo": None,
        "valor_maximo": None,
        "ultimo_check": None,
        "created_at": datetime(2026, 1, 15, 10, 0),
    }
    defaults.update(overrides)
    for k, v in defaults.items():
        setattr(m, k, v)
    return m


def _mock_resultado(**overrides):
    r = MagicMock()
    defaults = {
        "id": 10,
        "monitoramento_id": 1,
        "user_id": 1,
        "numero_controle_pncp": "12345678901234567890",
        "orgao_cnpj": "12345678000100",
        "orgao_razao_social": "Prefeitura Municipal",
        "objeto_compra": "Pavimentacao asfaltica",
        "modalidade_nome": "Pregao Eletronico",
        "uf": "SP",
        "municipio": "Sao Paulo",
        "valor_estimado": Decimal("500000.00"),
        "data_abertura": datetime(2026, 3, 15),
        "data_encerramento": datetime(2026, 4, 15),
        "link_sistema_origem": "https://pncp.gov.br/1234",
        "status": PncpResultadoStatus.NOVO,
        "licitacao_id": None,
        "encontrado_em": datetime(2026, 1, 10),
    }
    defaults.update(overrides)
    for k, v in defaults.items():
        setattr(r, k, v)
    return r


# ===========================================================================
# GET /monitoramentos
# ===========================================================================

class TestListMonitoramentos:

    @patch("routers.pncp.paginate_query")
    @patch("routers.pncp.pncp_monitoramento_repository")
    def test_list_monitoramentos_ok(self, mock_repo, mock_paginate, client):
        mock_paginate.return_value = {
            "items": [], "total": 0, "page": 1, "page_size": 20, "total_pages": 0,
        }
        response = client.get("/pncp/monitoramentos")
        assert response.status_code == 200
        mock_repo.get_filtered.assert_called_once()

    @patch("routers.pncp.paginate_query")
    @patch("routers.pncp.pncp_monitoramento_repository")
    def test_list_monitoramentos_with_filters(self, mock_repo, mock_paginate, client):
        mock_paginate.return_value = {
            "items": [], "total": 0, "page": 1, "page_size": 20, "total_pages": 0,
        }
        response = client.get("/pncp/monitoramentos?ativo=true&busca=asfalto")
        assert response.status_code == 200


# ===========================================================================
# POST /monitoramentos
# ===========================================================================

class TestCreateMonitoramento:

    @patch("routers.pncp.log_action")
    @patch("routers.pncp.pncp_monitoramento_repository")
    def test_create_monitoramento_201(self, mock_repo, mock_log, client):
        mock_monitor = _mock_monitoramento()
        mock_repo.create.return_value = mock_monitor

        response = client.post("/pncp/monitoramentos", json={
            "nome": "Monitor Teste",
            "palavras_chave": ["asfalto"],
            "ufs": ["SP"],
        })
        assert response.status_code == 201
        data = response.json()
        assert data["nome"] == "Monitor Teste"
        mock_repo.create.assert_called_once()

    def test_create_monitoramento_missing_nome(self, client):
        response = client.post("/pncp/monitoramentos", json={})
        assert response.status_code == 422


# ===========================================================================
# GET /monitoramentos/{id}
# ===========================================================================

class TestGetMonitoramento:

    @patch("routers.pncp.pncp_monitoramento_repository")
    def test_get_monitoramento_ok(self, mock_repo, client):
        mock_repo.get_by_id_for_user.return_value = _mock_monitoramento(id=5)
        response = client.get("/pncp/monitoramentos/5")
        assert response.status_code == 200
        assert response.json()["id"] == 5

    @patch("routers.pncp.pncp_monitoramento_repository")
    def test_get_monitoramento_not_found(self, mock_repo, client):
        mock_repo.get_by_id_for_user.return_value = None
        response = client.get("/pncp/monitoramentos/999")
        assert response.status_code == 404


# ===========================================================================
# PUT /monitoramentos/{id}
# ===========================================================================

class TestUpdateMonitoramento:

    @patch("routers.pncp.log_action")
    @patch("routers.pncp.pncp_monitoramento_repository")
    def test_update_monitoramento_ok(self, mock_repo, mock_log, client, mock_db):
        mock_monitor = _mock_monitoramento(id=3)
        mock_repo.get_by_id_for_user.return_value = mock_monitor

        response = client.put("/pncp/monitoramentos/3", json={
            "nome": "Nome Atualizado",
        })
        assert response.status_code == 200
        assert mock_monitor.nome == "Nome Atualizado"
        mock_db.commit.assert_called()
        mock_db.refresh.assert_called()

    @patch("routers.pncp.pncp_monitoramento_repository")
    def test_update_monitoramento_not_found(self, mock_repo, client):
        mock_repo.get_by_id_for_user.return_value = None
        response = client.put("/pncp/monitoramentos/999", json={"nome": "X"})
        assert response.status_code == 404


# ===========================================================================
# DELETE /monitoramentos/{id}
# ===========================================================================

class TestDeleteMonitoramento:

    @patch("routers.pncp.log_action")
    @patch("routers.pncp.pncp_monitoramento_repository")
    def test_delete_monitoramento_ok(self, mock_repo, mock_log, client):
        mock_repo.get_by_id_for_user.return_value = _mock_monitoramento(id=7)
        response = client.delete("/pncp/monitoramentos/7")
        assert response.status_code == 200
        data = response.json()
        assert data["sucesso"] is True
        mock_repo.delete.assert_called_once()

    @patch("routers.pncp.pncp_monitoramento_repository")
    def test_delete_monitoramento_not_found(self, mock_repo, client):
        mock_repo.get_by_id_for_user.return_value = None
        response = client.delete("/pncp/monitoramentos/999")
        assert response.status_code == 404


# ===========================================================================
# PATCH /monitoramentos/{id}/toggle
# ===========================================================================

class TestToggleMonitoramento:

    @patch("routers.pncp.pncp_monitoramento_repository")
    def test_toggle_monitoramento_activate(self, mock_repo, client, mock_db):
        mock_monitor = _mock_monitoramento(id=2, ativo=False)
        mock_repo.get_by_id_for_user.return_value = mock_monitor

        response = client.patch("/pncp/monitoramentos/2/toggle")
        assert response.status_code == 200
        assert mock_monitor.ativo is True
        mock_db.commit.assert_called()

    @patch("routers.pncp.pncp_monitoramento_repository")
    def test_toggle_monitoramento_deactivate(self, mock_repo, client, mock_db):
        mock_monitor = _mock_monitoramento(id=2, ativo=True)
        mock_repo.get_by_id_for_user.return_value = mock_monitor

        response = client.patch("/pncp/monitoramentos/2/toggle")
        assert response.status_code == 200
        assert mock_monitor.ativo is False

    @patch("routers.pncp.pncp_monitoramento_repository")
    def test_toggle_monitoramento_not_found(self, mock_repo, client):
        mock_repo.get_by_id_for_user.return_value = None
        response = client.patch("/pncp/monitoramentos/999/toggle")
        assert response.status_code == 404


# ===========================================================================
# GET /resultados
# ===========================================================================

class TestListResultados:

    @patch("routers.pncp.paginate_query")
    @patch("routers.pncp.pncp_resultado_repository")
    def test_list_resultados_ok(self, mock_repo, mock_paginate, client):
        mock_paginate.return_value = {
            "items": [], "total": 0, "page": 1, "page_size": 20, "total_pages": 0,
        }
        response = client.get("/pncp/resultados")
        assert response.status_code == 200
        mock_repo.get_filtered.assert_called_once()

    @patch("routers.pncp.paginate_query")
    @patch("routers.pncp.pncp_resultado_repository")
    def test_list_resultados_with_filters(self, mock_repo, mock_paginate, client):
        mock_paginate.return_value = {
            "items": [], "total": 0, "page": 1, "page_size": 20, "total_pages": 0,
        }
        response = client.get(
            "/pncp/resultados?monitoramento_id=1&status=novo&uf=SP&busca=asfalto"
        )
        assert response.status_code == 200


# ===========================================================================
# PATCH /resultados/{id}/status
# ===========================================================================

class TestUpdateResultadoStatus:

    @patch("routers.pncp.pncp_resultado_repository")
    def test_update_status_ok(self, mock_repo, client, mock_db):
        mock_result = _mock_resultado(id=10, status="novo")
        mock_repo.get_by_id_for_user.return_value = mock_result

        response = client.patch("/pncp/resultados/10/status", json={
            "status": "interessante",
        })
        assert response.status_code == 200
        assert mock_result.status == "interessante"
        mock_db.commit.assert_called()

    @patch("routers.pncp.pncp_resultado_repository")
    def test_update_status_not_found(self, mock_repo, client):
        mock_repo.get_by_id_for_user.return_value = None
        response = client.patch("/pncp/resultados/999/status", json={
            "status": "interessante",
        })
        assert response.status_code == 404

    def test_update_status_invalid(self, client):
        """Invalid status should return 422 (Pydantic validation)."""
        response = client.patch("/pncp/resultados/10/status", json={
            "status": "invalido",
        })
        assert response.status_code == 422


# ===========================================================================
# POST /resultados/{id}/importar
# ===========================================================================

class TestImportarResultado:

    @patch("routers.pncp.log_action")
    @patch("routers.pncp.pncp_mapper")
    @patch("routers.pncp.pncp_resultado_repository")
    def test_importar_ok(self, mock_repo, mock_mapper, mock_log, client, mock_db):
        mock_result = _mock_resultado(id=10, status="novo")
        mock_repo.get_by_id_for_user.return_value = mock_result
        mock_mapper.resultado_para_licitacao.return_value = {
            "numero": "PNCP-1234567890",
            "objeto": "Pavimentacao asfaltica",
            "orgao": "Prefeitura Municipal",
            "modalidade": "Pregao Eletronico",
            "fonte": "pncp",
            "status": "identificada",
            "numero_controle_pncp": "12345678901234567890",
            "valor_estimado": Decimal("500000.00"),
            "data_abertura": None,
            "data_encerramento": None,
            "uf": "SP",
            "municipio": "Sao Paulo",
            "link_sistema_origem": None,
            "observacoes": "Importado do PNCP. Controle: 12345678901234567890",
        }

        response = client.post("/pncp/resultados/10/importar", json={})
        assert response.status_code == 200
        assert mock_result.status == PncpResultadoStatus.IMPORTADO
        mock_db.add.assert_called_once()  # licitacao added
        mock_mapper.resultado_para_licitacao.assert_called_once_with(mock_result)

    @patch("routers.pncp.pncp_resultado_repository")
    def test_importar_not_found(self, mock_repo, client):
        mock_repo.get_by_id_for_user.return_value = None
        response = client.post("/pncp/resultados/999/importar", json={})
        assert response.status_code == 404

    @patch("routers.pncp.pncp_resultado_repository")
    def test_importar_already_imported(self, mock_repo, client):
        mock_result = _mock_resultado(id=10, status=PncpResultadoStatus.IMPORTADO)
        mock_repo.get_by_id_for_user.return_value = mock_result

        response = client.post("/pncp/resultados/10/importar", json={})
        assert response.status_code == 400

    @patch("routers.pncp.log_action")
    @patch("routers.pncp.pncp_mapper")
    @patch("routers.pncp.pncp_resultado_repository")
    def test_importar_with_observacoes(self, mock_repo, mock_mapper, mock_log, client, mock_db):
        mock_result = _mock_resultado(id=10, status="novo")
        mock_repo.get_by_id_for_user.return_value = mock_result
        mock_mapper.resultado_para_licitacao.return_value = {
            "numero": "PNCP-1234567890",
            "objeto": "Pavimentacao",
            "orgao": "Prefeitura",
            "modalidade": "Pregao",
            "fonte": "pncp",
            "status": "identificada",
            "numero_controle_pncp": "12345678901234567890",
            "valor_estimado": None,
            "data_abertura": None,
            "data_encerramento": None,
            "uf": "SP",
            "municipio": None,
            "link_sistema_origem": None,
            "observacoes": "Importado do PNCP. Controle: 12345678901234567890",
        }

        response = client.post("/pncp/resultados/10/importar", json={
            "observacoes": "Prioridade alta",
        })
        assert response.status_code == 200


# ===========================================================================
# GET /busca
# ===========================================================================

class TestBuscaPncp:

    def test_busca_missing_params(self, client):
        """data_inicial, data_final and codigo_modalidade are required."""
        response = client.get("/pncp/busca")
        assert response.status_code == 422

    def test_busca_missing_modalidade(self, client):
        """codigo_modalidade is required by PNCP API."""
        response = client.get(
            "/pncp/busca?data_inicial=20260101&data_final=20260115"
        )
        assert response.status_code == 422

    def test_busca_filters_by_abertura_date(self, client):
        """Results are filtered by dataAberturaProposta within requested range."""
        items = [
            {"dataAberturaProposta": "2026-01-05T09:00:00", "objetoCompra": "Fora do range"},
            {"dataAberturaProposta": "2026-01-10T09:00:00", "objetoCompra": "Dentro do range"},
            {"dataAberturaProposta": "2026-01-14T09:00:00", "objetoCompra": "Dentro do range 2"},
            {"dataAberturaProposta": "2026-01-20T09:00:00", "objetoCompra": "Fora do range"},
            {"objetoCompra": "Sem data abertura"},
        ]
        with patch(
            "services.pncp.client.pncp_client.buscar_todas_paginas",
            new_callable=AsyncMock,
            return_value=items,
        ):
            response = client.get(
                "/pncp/busca?data_inicial=20260108&data_final=20260115&codigo_modalidade=6"
            )
        assert response.status_code == 200
        data = response.json()
        assert data["total_registros"] == 2
        assert len(data["data"]) == 2
        assert data["data"][0]["objetoCompra"] == "Dentro do range"
        assert data["data"][1]["objetoCompra"] == "Dentro do range 2"

    def test_busca_empty_results(self, client):
        """Empty results from PNCP returns empty list."""
        with patch(
            "services.pncp.client.pncp_client.buscar_todas_paginas",
            new_callable=AsyncMock,
            return_value=[],
        ):
            response = client.get(
                "/pncp/busca?data_inicial=20260301&data_final=20260315&codigo_modalidade=6"
            )
        assert response.status_code == 200
        data = response.json()
        assert data["total_registros"] == 0
        assert data["data"] == []

    def test_busca_error_returns_502(self, client):
        with patch(
            "services.pncp.client.pncp_client.buscar_todas_paginas",
            new_callable=AsyncMock,
            side_effect=Exception("Connection error"),
        ):
            response = client.get(
                "/pncp/busca?data_inicial=20260101&data_final=20260115&codigo_modalidade=6"
            )
        assert response.status_code == 502


# ===========================================================================
# POST /busca/importar
# ===========================================================================

class TestBuscaImportar:

    @staticmethod
    def _make_item(suffix=None):
        import uuid
        suffix = suffix or uuid.uuid4().hex[:8]
        return {
            "numeroControlePNCP": f"99988877000100-1-{suffix}/2026",
            "objetoCompra": "Obra de pavimentação",
            "orgaoEntidade": {"cnpj": "99988877000100", "razaoSocial": "MUNICIPIO TESTE"},
            "unidadeOrgao": {"ufSigla": "PB", "municipioNome": "Cidade Teste"},
            "modalidadeNome": "Concorrência - Eletrônica",
            "valorTotalEstimado": 500000.00,
            "dataAberturaProposta": "2026-03-01T09:00:00",
            "dataEncerramentoProposta": "2026-03-15T09:00:00",
            "linkSistemaOrigem": "https://example.com/licitacao",
        }

    @patch("routers.pncp.log_action")
    def test_importar_busca_ok(self, mock_log, client, mock_db):
        mock_db.query.return_value.filter.return_value.first.return_value = None
        mock_db.refresh = MagicMock(side_effect=lambda obj: setattr(obj, "id", 42))
        item = self._make_item()
        response = client.post("/pncp/busca/importar", json=item)
        assert response.status_code == 200
        data = response.json()
        assert "licitacao_id" in data
        assert data["message"] == "Licitação importada com sucesso!"

    def test_importar_busca_duplicata(self, client, mock_db):
        mock_db.query.return_value.filter.return_value.first.return_value = MagicMock(id=1)
        item = self._make_item()
        response = client.post("/pncp/busca/importar", json=item)
        assert response.status_code == 409

    def test_importar_busca_sem_numero_controle(self, client):
        response = client.post("/pncp/busca/importar", json={"objetoCompra": "test"})
        assert response.status_code == 400


# ===========================================================================
# POST /sincronizar
# ===========================================================================

class TestSincronizar:

    @patch("routers.pncp.log_action")
    @patch("routers.pncp.asyncio.create_task")
    @patch(
        "services.pncp.sync_service.pncp_sync_service._sync_all",
        new_callable=AsyncMock,
    )
    def test_sincronizar_ok(self, mock_sync_all, mock_create_task, mock_log, client):
        response = client.post("/pncp/sincronizar")
        assert response.status_code == 200
        data = response.json()
        assert data["sucesso"] is True
