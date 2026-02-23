"""Tests for licitacoes router endpoints."""
import uuid
from unittest.mock import MagicMock

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from models import Licitacao, LicitacaoHistorico, LicitacaoTag, Usuario
from tests.conftest import create_mock_auth_headers

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_user(db: Session, *, email: str = "rlic@teste.com") -> Usuario:
    user = Usuario(
        email=email, nome="Router Lic User",
        supabase_id=str(uuid.uuid4()),
        is_active=True, is_approved=True, is_admin=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _make_licitacao(
    db: Session, user_id: int, *,
    numero: str = "PE 001/2026",
    status: str = "identificada",
    uf: str | None = "SP",
    modalidade: str = "Pregao Eletronico",
) -> Licitacao:
    lic = Licitacao(
        user_id=user_id, numero=numero,
        orgao="Prefeitura Teste", objeto="Pavimentacao asfaltica",
        modalidade=modalidade, status=status, uf=uf,
    )
    db.add(lic)
    db.commit()
    db.refresh(lic)
    return lic


def _get_db(client: TestClient):
    """Get a fresh db session from the client's override."""
    from database import get_db
    from main import app
    override = app.dependency_overrides.get(get_db)
    if override:
        gen = override()
        db = next(gen)
        return db, gen
    return None, None


# ===========================================================================
# Authentication
# ===========================================================================

class TestLicitacoesAuth:

    def test_list_without_auth_returns_401(self, client: TestClient):
        response = client.get("/api/v1/licitacoes/")
        assert response.status_code in (401, 403)

    def test_create_without_auth_returns_401(self, client: TestClient):
        response = client.post("/api/v1/licitacoes/", json={
            "numero": "PE 001", "orgao": "Org", "objeto": "Obj", "modalidade": "Mod"
        })
        assert response.status_code in (401, 403)


# ===========================================================================
# CRUD Endpoints
# ===========================================================================

class TestLicitacoesCRUD:

    def test_create_licitacao(self, client: TestClient, db_session: Session, mock_supabase_verify: MagicMock):
        user = _make_user(db_session, email="create@rlic.com")
        headers = create_mock_auth_headers(user, mock_supabase_verify)

        response = client.post("/api/v1/licitacoes/", json={
            "numero": "PE 001/2026",
            "orgao": "Prefeitura de SP",
            "objeto": "Pavimentacao de vias urbanas",
            "modalidade": "Pregao Eletronico",
            "uf": "SP",
        }, headers=headers)

        assert response.status_code == 201
        data = response.json()
        assert data["numero"] == "PE 001/2026"
        assert data["status"] == "identificada"
        assert data["user_id"] == user.id

    def test_list_licitacoes(self, client: TestClient, db_session: Session, mock_supabase_verify: MagicMock):
        user = _make_user(db_session, email="list@rlic.com")
        headers = create_mock_auth_headers(user, mock_supabase_verify)
        _make_licitacao(db_session, user.id, numero="L1")
        _make_licitacao(db_session, user.id, numero="L2")

        response = client.get("/api/v1/licitacoes/", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2

    def test_list_with_status_filter(self, client: TestClient, db_session: Session, mock_supabase_verify: MagicMock):
        user = _make_user(db_session, email="filtst@rlic.com")
        headers = create_mock_auth_headers(user, mock_supabase_verify)
        _make_licitacao(db_session, user.id, numero="L1", status="identificada")
        _make_licitacao(db_session, user.id, numero="L2", status="vencida")

        response = client.get("/api/v1/licitacoes/?status=vencida", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["status"] == "vencida"

    def test_get_licitacao_detail(self, client: TestClient, db_session: Session, mock_supabase_verify: MagicMock):
        user = _make_user(db_session, email="det@rlic.com")
        headers = create_mock_auth_headers(user, mock_supabase_verify)
        lic = _make_licitacao(db_session, user.id)

        response = client.get(f"/api/v1/licitacoes/{lic.id}", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == lic.id
        assert "historico" in data
        assert "tags" in data

    def test_get_licitacao_not_found(self, client: TestClient, db_session: Session, mock_supabase_verify: MagicMock):
        user = _make_user(db_session, email="nf@rlic.com")
        headers = create_mock_auth_headers(user, mock_supabase_verify)

        response = client.get("/api/v1/licitacoes/999999", headers=headers)
        assert response.status_code == 404

    def test_get_licitacao_other_user_returns_404(self, client: TestClient, db_session: Session, mock_supabase_verify: MagicMock):
        user_a = _make_user(db_session, email="ownera@rlic.com")
        user_b = _make_user(db_session, email="ownerb@rlic.com")
        lic = _make_licitacao(db_session, user_a.id)

        headers_b = create_mock_auth_headers(user_b, mock_supabase_verify)
        response = client.get(f"/api/v1/licitacoes/{lic.id}", headers=headers_b)
        assert response.status_code == 404

    def test_update_licitacao(self, client: TestClient, db_session: Session, mock_supabase_verify: MagicMock):
        user = _make_user(db_session, email="upd@rlic.com")
        headers = create_mock_auth_headers(user, mock_supabase_verify)
        lic = _make_licitacao(db_session, user.id)

        response = client.put(f"/api/v1/licitacoes/{lic.id}", json={
            "observacoes": "Atualizado via teste",
        }, headers=headers)
        assert response.status_code == 200
        assert response.json()["observacoes"] == "Atualizado via teste"

    def test_delete_licitacao(self, client: TestClient, db_session: Session, mock_supabase_verify: MagicMock):
        user = _make_user(db_session, email="del@rlic.com")
        headers = create_mock_auth_headers(user, mock_supabase_verify)
        lic = _make_licitacao(db_session, user.id)

        response = client.delete(f"/api/v1/licitacoes/{lic.id}", headers=headers)
        assert response.status_code == 200
        assert response.json()["sucesso"] is True

        # Confirmar exclusao
        response = client.get(f"/api/v1/licitacoes/{lic.id}", headers=headers)
        assert response.status_code == 404


# ===========================================================================
# Status Transitions
# ===========================================================================

class TestLicitacoesStatus:

    def test_valid_status_transition(self, client: TestClient, db_session: Session, mock_supabase_verify: MagicMock):
        user = _make_user(db_session, email="stat@rlic.com")
        headers = create_mock_auth_headers(user, mock_supabase_verify)
        lic = _make_licitacao(db_session, user.id, status="identificada")

        response = client.patch(f"/api/v1/licitacoes/{lic.id}/status", json={
            "status": "em_analise",
            "observacao": "Iniciando analise",
        }, headers=headers)
        assert response.status_code == 200
        assert response.json()["status"] == "em_analise"

    def test_invalid_status_transition(self, client: TestClient, db_session: Session, mock_supabase_verify: MagicMock):
        user = _make_user(db_session, email="inv@rlic.com")
        headers = create_mock_auth_headers(user, mock_supabase_verify)
        lic = _make_licitacao(db_session, user.id, status="identificada")

        response = client.patch(f"/api/v1/licitacoes/{lic.id}/status", json={
            "status": "vencida",
        }, headers=headers)
        assert response.status_code == 400
        assert "Transição de status inválida" in response.json()["detail"]

    def test_final_status_has_no_transitions(self, client: TestClient, db_session: Session, mock_supabase_verify: MagicMock):
        user = _make_user(db_session, email="final@rlic.com")
        headers = create_mock_auth_headers(user, mock_supabase_verify)
        lic = _make_licitacao(db_session, user.id, status="concluida")

        response = client.patch(f"/api/v1/licitacoes/{lic.id}/status", json={
            "status": "identificada",
        }, headers=headers)
        assert response.status_code == 400


# ===========================================================================
# Historico
# ===========================================================================

class TestLicitacoesHistorico:

    def test_get_historico(self, client: TestClient, db_session: Session, mock_supabase_verify: MagicMock):
        user = _make_user(db_session, email="hist@rlic.com")
        headers = create_mock_auth_headers(user, mock_supabase_verify)
        lic = _make_licitacao(db_session, user.id, status="identificada")

        # Create some historico
        db_session.add(LicitacaoHistorico(
            licitacao_id=lic.id, user_id=user.id,
            status_anterior=None, status_novo="identificada",
            observacao="Criada",
        ))
        db_session.commit()

        response = client.get(f"/api/v1/licitacoes/{lic.id}/historico", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["status_novo"] == "identificada"


# ===========================================================================
# Tags
# ===========================================================================

class TestLicitacoesTags:

    def test_add_tag(self, client: TestClient, db_session: Session, mock_supabase_verify: MagicMock):
        user = _make_user(db_session, email="addtag@rlic.com")
        headers = create_mock_auth_headers(user, mock_supabase_verify)
        lic = _make_licitacao(db_session, user.id)

        response = client.post(f"/api/v1/licitacoes/{lic.id}/tags", json={
            "tag": "infraestrutura",
        }, headers=headers)
        assert response.status_code == 201
        assert response.json()["tag"] == "infraestrutura"

    def test_add_duplicate_tag_returns_409(self, client: TestClient, db_session: Session, mock_supabase_verify: MagicMock):
        user = _make_user(db_session, email="duptag@rlic.com")
        headers = create_mock_auth_headers(user, mock_supabase_verify)
        lic = _make_licitacao(db_session, user.id)

        # First tag
        db_session.add(LicitacaoTag(licitacao_id=lic.id, tag="teste"))
        db_session.commit()

        response = client.post(f"/api/v1/licitacoes/{lic.id}/tags", json={
            "tag": "teste",
        }, headers=headers)
        assert response.status_code == 409

    def test_remove_tag(self, client: TestClient, db_session: Session, mock_supabase_verify: MagicMock):
        user = _make_user(db_session, email="rmtag@rlic.com")
        headers = create_mock_auth_headers(user, mock_supabase_verify)
        lic = _make_licitacao(db_session, user.id)

        db_session.add(LicitacaoTag(licitacao_id=lic.id, tag="remover"))
        db_session.commit()

        response = client.delete(f"/api/v1/licitacoes/{lic.id}/tags/remover", headers=headers)
        assert response.status_code == 200

    def test_remove_nonexistent_tag_returns_404(self, client: TestClient, db_session: Session, mock_supabase_verify: MagicMock):
        user = _make_user(db_session, email="notag@rlic.com")
        headers = create_mock_auth_headers(user, mock_supabase_verify)
        lic = _make_licitacao(db_session, user.id)

        response = client.delete(f"/api/v1/licitacoes/{lic.id}/tags/inexistente", headers=headers)
        assert response.status_code == 404


# ===========================================================================
# Estatisticas
# ===========================================================================

class TestLicitacoesEstatisticas:

    def test_get_estatisticas(self, client: TestClient, db_session: Session, mock_supabase_verify: MagicMock):
        user = _make_user(db_session, email="est@rlic.com")
        headers = create_mock_auth_headers(user, mock_supabase_verify)
        _make_licitacao(db_session, user.id, numero="L1", status="identificada", uf="SP")
        _make_licitacao(db_session, user.id, numero="L2", status="vencida", uf="RJ")

        response = client.get("/api/v1/licitacoes/estatisticas", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert "por_status" in data
        assert "por_uf" in data
        assert "por_modalidade" in data
