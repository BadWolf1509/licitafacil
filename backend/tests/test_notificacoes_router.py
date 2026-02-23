"""Tests for notificacoes router endpoints."""
import uuid
from unittest.mock import MagicMock

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from models import Notificacao, Usuario
from tests.conftest import create_mock_auth_headers

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_user(db: Session, *, email: str = "rnot@teste.com") -> Usuario:
    user = Usuario(
        email=email, nome="Router Not User",
        supabase_id=str(uuid.uuid4()),
        is_active=True, is_approved=True, is_admin=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _make_notificacao(
    db: Session, user_id: int, *,
    titulo: str = "Notif Teste",
    lida: bool = False,
) -> Notificacao:
    notif = Notificacao(
        user_id=user_id,
        titulo=titulo,
        mensagem="Mensagem de teste",
        tipo="lembrete",
        lida=lida,
    )
    db.add(notif)
    db.commit()
    db.refresh(notif)
    return notif


# ===========================================================================
# Authentication
# ===========================================================================

class TestNotificacoesAuth:

    def test_list_without_auth_returns_401(self, client: TestClient):
        response = client.get("/api/v1/notificacoes/")
        assert response.status_code in (401, 403)

    def test_count_without_auth_returns_401(self, client: TestClient):
        response = client.get("/api/v1/notificacoes/nao-lidas/count")
        assert response.status_code in (401, 403)


# ===========================================================================
# CRUD
# ===========================================================================

class TestNotificacoesCRUD:

    def test_list_notificacoes(self, client: TestClient, db_session: Session, mock_supabase_verify: MagicMock):
        user = _make_user(db_session, email="list@rnot.com")
        headers = create_mock_auth_headers(user, mock_supabase_verify)
        _make_notificacao(db_session, user.id, titulo="N1")
        _make_notificacao(db_session, user.id, titulo="N2")

        response = client.get("/api/v1/notificacoes/", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2

    def test_count_nao_lidas(self, client: TestClient, db_session: Session, mock_supabase_verify: MagicMock):
        user = _make_user(db_session, email="count@rnot.com")
        headers = create_mock_auth_headers(user, mock_supabase_verify)
        _make_notificacao(db_session, user.id, titulo="N1", lida=False)
        _make_notificacao(db_session, user.id, titulo="N2", lida=False)
        _make_notificacao(db_session, user.id, titulo="N3", lida=True)

        response = client.get("/api/v1/notificacoes/nao-lidas/count", headers=headers)
        assert response.status_code == 200
        assert response.json()["count"] == 2

    def test_marcar_lida(self, client: TestClient, db_session: Session, mock_supabase_verify: MagicMock):
        user = _make_user(db_session, email="lida@rnot.com")
        headers = create_mock_auth_headers(user, mock_supabase_verify)
        notif = _make_notificacao(db_session, user.id, lida=False)

        response = client.patch(f"/api/v1/notificacoes/{notif.id}/lida", headers=headers)
        assert response.status_code == 200
        assert response.json()["lida"] is True
        assert response.json()["lida_em"] is not None

    def test_marcar_todas_lidas(self, client: TestClient, db_session: Session, mock_supabase_verify: MagicMock):
        user = _make_user(db_session, email="todas@rnot.com")
        headers = create_mock_auth_headers(user, mock_supabase_verify)
        _make_notificacao(db_session, user.id, titulo="N1", lida=False)
        _make_notificacao(db_session, user.id, titulo="N2", lida=False)

        response = client.post("/api/v1/notificacoes/marcar-todas-lidas", headers=headers)
        assert response.status_code == 200
        assert "2" in response.json()["mensagem"]

    def test_delete_notificacao(self, client: TestClient, db_session: Session, mock_supabase_verify: MagicMock):
        user = _make_user(db_session, email="del@rnot.com")
        headers = create_mock_auth_headers(user, mock_supabase_verify)
        notif = _make_notificacao(db_session, user.id)

        response = client.delete(f"/api/v1/notificacoes/{notif.id}", headers=headers)
        assert response.status_code == 200
        assert response.json()["sucesso"] is True

    def test_delete_not_found(self, client: TestClient, db_session: Session, mock_supabase_verify: MagicMock):
        user = _make_user(db_session, email="nf@rnot.com")
        headers = create_mock_auth_headers(user, mock_supabase_verify)

        response = client.delete("/api/v1/notificacoes/999999", headers=headers)
        assert response.status_code == 404

    def test_other_user_returns_404(self, client: TestClient, db_session: Session, mock_supabase_verify: MagicMock):
        user_a = _make_user(db_session, email="ownera@rnot.com")
        user_b = _make_user(db_session, email="ownerb@rnot.com")
        notif = _make_notificacao(db_session, user_a.id)

        headers_b = create_mock_auth_headers(user_b, mock_supabase_verify)
        response = client.patch(f"/api/v1/notificacoes/{notif.id}/lida", headers=headers_b)
        assert response.status_code == 404


# ===========================================================================
# Preferencias
# ===========================================================================

class TestNotificacoesPreferencias:

    def test_get_preferencias_creates_default(self, client: TestClient, db_session: Session, mock_supabase_verify: MagicMock):
        user = _make_user(db_session, email="pref@rnot.com")
        headers = create_mock_auth_headers(user, mock_supabase_verify)

        response = client.get("/api/v1/notificacoes/preferencias", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["email_habilitado"] is True
        assert data["app_habilitado"] is True
        assert data["antecedencia_horas"] == 24

    def test_update_preferencias(self, client: TestClient, db_session: Session, mock_supabase_verify: MagicMock):
        user = _make_user(db_session, email="updpref@rnot.com")
        headers = create_mock_auth_headers(user, mock_supabase_verify)

        # First call creates default
        client.get("/api/v1/notificacoes/preferencias", headers=headers)

        # Update
        response = client.put("/api/v1/notificacoes/preferencias", json={
            "email_habilitado": False,
            "antecedencia_horas": 48,
        }, headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["email_habilitado"] is False
        assert data["antecedencia_horas"] == 48
        # app_habilitado should remain True (not updated)
        assert data["app_habilitado"] is True

    def test_list_with_lida_filter(self, client: TestClient, db_session: Session, mock_supabase_verify: MagicMock):
        user = _make_user(db_session, email="filtlida@rnot.com")
        headers = create_mock_auth_headers(user, mock_supabase_verify)
        _make_notificacao(db_session, user.id, titulo="N1", lida=False)
        _make_notificacao(db_session, user.id, titulo="N2", lida=True)

        response = client.get("/api/v1/notificacoes/?lida=false", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["lida"] is False
