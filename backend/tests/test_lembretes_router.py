"""Tests for lembretes router endpoints."""
import uuid
from datetime import datetime, timedelta
from unittest.mock import MagicMock

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from models import Lembrete, Usuario
from tests.conftest import create_mock_auth_headers

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_user(db: Session, *, email: str = "rlem@teste.com") -> Usuario:
    user = Usuario(
        email=email, nome="Router Lem User",
        supabase_id=str(uuid.uuid4()),
        is_active=True, is_approved=True, is_admin=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _make_lembrete(
    db: Session, user_id: int, *,
    titulo: str = "Lembrete Router",
    data_lembrete: datetime | None = None,
    status: str = "pendente",
) -> Lembrete:
    if data_lembrete is None:
        data_lembrete = datetime.now() + timedelta(hours=1)
    lem = Lembrete(
        user_id=user_id,
        titulo=titulo,
        data_lembrete=data_lembrete,
        status=status,
        tipo="manual",
    )
    db.add(lem)
    db.commit()
    db.refresh(lem)
    return lem


def _get_db(client: TestClient):
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

class TestLembretesAuth:

    def test_list_without_auth_returns_401(self, client: TestClient):
        response = client.get("/api/v1/lembretes/")
        assert response.status_code in (401, 403)

    def test_create_without_auth_returns_401(self, client: TestClient):
        response = client.post("/api/v1/lembretes/", json={
            "titulo": "Teste", "data_lembrete": "2026-03-15T10:00:00"
        })
        assert response.status_code in (401, 403)


# ===========================================================================
# CRUD
# ===========================================================================

class TestLembretesCRUD:

    def test_create_lembrete(self, client: TestClient, db_session: Session, mock_supabase_verify: MagicMock):
        user = _make_user(db_session, email="create@rlem.com")
        headers = create_mock_auth_headers(user, mock_supabase_verify)

        response = client.post("/api/v1/lembretes/", json={
            "titulo": "Prazo de entrega",
            "descricao": "Entregar proposta",
            "data_lembrete": "2026-03-15T10:00:00",
            "tipo": "manual",
        }, headers=headers)

        assert response.status_code == 201
        data = response.json()
        assert data["titulo"] == "Prazo de entrega"
        assert data["status"] == "pendente"
        assert data["user_id"] == user.id

    def test_list_lembretes(self, client: TestClient, db_session: Session, mock_supabase_verify: MagicMock):
        user = _make_user(db_session, email="list@rlem.com")
        headers = create_mock_auth_headers(user, mock_supabase_verify)
        _make_lembrete(db_session, user.id, titulo="L1")
        _make_lembrete(db_session, user.id, titulo="L2")

        response = client.get("/api/v1/lembretes/", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2

    def test_list_with_status_filter(self, client: TestClient, db_session: Session, mock_supabase_verify: MagicMock):
        user = _make_user(db_session, email="filtst@rlem.com")
        headers = create_mock_auth_headers(user, mock_supabase_verify)
        _make_lembrete(db_session, user.id, titulo="L1", status="pendente")
        _make_lembrete(db_session, user.id, titulo="L2", status="enviado")

        response = client.get("/api/v1/lembretes/?status=enviado", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["status"] == "enviado"

    def test_update_lembrete(self, client: TestClient, db_session: Session, mock_supabase_verify: MagicMock):
        user = _make_user(db_session, email="upd@rlem.com")
        headers = create_mock_auth_headers(user, mock_supabase_verify)
        lem = _make_lembrete(db_session, user.id)

        response = client.put(f"/api/v1/lembretes/{lem.id}", json={
            "titulo": "Atualizado",
        }, headers=headers)
        assert response.status_code == 200
        assert response.json()["titulo"] == "Atualizado"

    def test_delete_lembrete(self, client: TestClient, db_session: Session, mock_supabase_verify: MagicMock):
        user = _make_user(db_session, email="del@rlem.com")
        headers = create_mock_auth_headers(user, mock_supabase_verify)
        lem = _make_lembrete(db_session, user.id)

        response = client.delete(f"/api/v1/lembretes/{lem.id}", headers=headers)
        assert response.status_code == 200
        assert response.json()["sucesso"] is True

    def test_get_not_found(self, client: TestClient, db_session: Session, mock_supabase_verify: MagicMock):
        user = _make_user(db_session, email="nf@rlem.com")
        headers = create_mock_auth_headers(user, mock_supabase_verify)

        response = client.put("/api/v1/lembretes/999999", json={
            "titulo": "X",
        }, headers=headers)
        assert response.status_code == 404

    def test_other_user_returns_404(self, client: TestClient, db_session: Session, mock_supabase_verify: MagicMock):
        user_a = _make_user(db_session, email="ownera@rlem.com")
        user_b = _make_user(db_session, email="ownerb@rlem.com")
        lem = _make_lembrete(db_session, user_a.id)

        headers_b = create_mock_auth_headers(user_b, mock_supabase_verify)
        response = client.delete(f"/api/v1/lembretes/{lem.id}", headers=headers_b)
        assert response.status_code == 404


# ===========================================================================
# Status
# ===========================================================================

class TestLembretesStatus:

    def test_change_status(self, client: TestClient, db_session: Session, mock_supabase_verify: MagicMock):
        user = _make_user(db_session, email="stat@rlem.com")
        headers = create_mock_auth_headers(user, mock_supabase_verify)
        lem = _make_lembrete(db_session, user.id, status="pendente")

        response = client.patch(f"/api/v1/lembretes/{lem.id}/status", json={
            "status": "cancelado",
        }, headers=headers)
        assert response.status_code == 200
        assert response.json()["status"] == "cancelado"


# ===========================================================================
# Calendario
# ===========================================================================

class TestLembretesCalendario:

    def test_get_calendario(self, client: TestClient, db_session: Session, mock_supabase_verify: MagicMock):
        user = _make_user(db_session, email="cal@rlem.com")
        headers = create_mock_auth_headers(user, mock_supabase_verify)
        now = datetime.now()
        _make_lembrete(db_session, user.id, titulo="Cal1",
                       data_lembrete=now + timedelta(hours=1))

        inicio = (now - timedelta(days=1)).isoformat()
        fim = (now + timedelta(days=2)).isoformat()
        response = client.get(
            f"/api/v1/lembretes/calendario?data_inicio={inicio}&data_fim={fim}",
            headers=headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        assert data[0]["titulo"] == "Cal1"
