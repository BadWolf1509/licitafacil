"""Tests for documentos router endpoints."""
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from models import DocumentoLicitacao, Licitacao, Usuario
from models.documento import DocumentoStatus, DocumentoTipo
from tests.conftest import create_mock_auth_headers

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_user(db: Session, *, email: str = "rdoc@teste.com") -> Usuario:
    user = Usuario(
        email=email, nome="Router Doc User",
        supabase_id=str(uuid.uuid4()),
        is_active=True, is_approved=True, is_admin=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _make_licitacao(db: Session, user_id: int, *, numero: str = "PE 001/2026") -> Licitacao:
    lic = Licitacao(
        user_id=user_id, numero=numero,
        orgao="Prefeitura Teste", objeto="Pavimentacao asfaltica",
        modalidade="Pregao Eletronico", status="identificada", uf="SP",
    )
    db.add(lic)
    db.commit()
    db.refresh(lic)
    return lic


def _make_documento(
    db: Session, user_id: int, *,
    nome: str = "Certidao Federal",
    tipo_documento: str = DocumentoTipo.CERTIDAO_FEDERAL,
    licitacao_id: int | None = None,
    status: str = DocumentoStatus.VALIDO,
    data_validade: datetime | None = None,
) -> DocumentoLicitacao:
    doc = DocumentoLicitacao(
        user_id=user_id,
        licitacao_id=licitacao_id,
        nome=nome,
        tipo_documento=tipo_documento,
        status=status,
        data_validade=data_validade,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


# ===========================================================================
# Authentication
# ===========================================================================

class TestDocumentosAuth:

    def test_list_without_auth_returns_401(self, client: TestClient):
        response = client.get("/api/v1/documentos/")
        assert response.status_code in (401, 403)

    def test_create_without_auth_returns_401(self, client: TestClient):
        response = client.post("/api/v1/documentos/", json={
            "nome": "Doc", "tipo_documento": "edital"
        })
        assert response.status_code in (401, 403)

    def test_vencendo_without_auth_returns_401(self, client: TestClient):
        response = client.get("/api/v1/documentos/vencendo")
        assert response.status_code in (401, 403)

    def test_resumo_without_auth_returns_401(self, client: TestClient):
        response = client.get("/api/v1/documentos/resumo")
        assert response.status_code in (401, 403)


# ===========================================================================
# CRUD Documentos
# ===========================================================================

class TestDocumentosCRUD:

    def test_create_documento(self, client: TestClient, db_session: Session, mock_supabase_verify: MagicMock):
        user = _make_user(db_session, email="create@rdoc.com")
        headers = create_mock_auth_headers(user, mock_supabase_verify)

        response = client.post("/api/v1/documentos/", json={
            "nome": "Balanco Patrimonial",
            "tipo_documento": "balanco",
            "obrigatorio": True,
        }, headers=headers)

        assert response.status_code == 201
        data = response.json()
        assert data["nome"] == "Balanco Patrimonial"
        assert data["tipo_documento"] == "balanco"
        assert data["user_id"] == user.id
        assert data["obrigatorio"] is True

    def test_create_documento_invalid_tipo(self, client: TestClient, db_session: Session, mock_supabase_verify: MagicMock):
        user = _make_user(db_session, email="invtipo@rdoc.com")
        headers = create_mock_auth_headers(user, mock_supabase_verify)

        response = client.post("/api/v1/documentos/", json={
            "nome": "Doc",
            "tipo_documento": "tipo_invalido",
        }, headers=headers)

        assert response.status_code == 422

    def test_list_documentos(self, client: TestClient, db_session: Session, mock_supabase_verify: MagicMock):
        user = _make_user(db_session, email="list@rdoc.com")
        headers = create_mock_auth_headers(user, mock_supabase_verify)
        _make_documento(db_session, user.id, nome="Doc1")
        _make_documento(db_session, user.id, nome="Doc2")

        response = client.get("/api/v1/documentos/", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2

    def test_list_documentos_with_pagination(self, client: TestClient, db_session: Session, mock_supabase_verify: MagicMock):
        user = _make_user(db_session, email="listpag@rdoc.com")
        headers = create_mock_auth_headers(user, mock_supabase_verify)
        for i in range(5):
            _make_documento(db_session, user.id, nome=f"Doc {i}")

        response = client.get("/api/v1/documentos/?page=1&page_size=2", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 5
        assert len(data["items"]) == 2
        assert data["page_size"] == 2

    def test_list_documentos_with_tipo_filter(self, client: TestClient, db_session: Session, mock_supabase_verify: MagicMock):
        user = _make_user(db_session, email="filtipo@rdoc.com")
        headers = create_mock_auth_headers(user, mock_supabase_verify)
        _make_documento(db_session, user.id, nome="D1", tipo_documento="edital")
        _make_documento(db_session, user.id, nome="D2", tipo_documento="balanco")

        response = client.get("/api/v1/documentos/?tipo_documento=balanco", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["tipo_documento"] == "balanco"

    def test_get_documento_by_id(self, client: TestClient, db_session: Session, mock_supabase_verify: MagicMock):
        user = _make_user(db_session, email="getid@rdoc.com")
        headers = create_mock_auth_headers(user, mock_supabase_verify)
        doc = _make_documento(db_session, user.id, nome="Especifico")

        response = client.get(f"/api/v1/documentos/{doc.id}", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == doc.id
        assert data["nome"] == "Especifico"

    def test_get_documento_not_found(self, client: TestClient, db_session: Session, mock_supabase_verify: MagicMock):
        user = _make_user(db_session, email="nf@rdoc.com")
        headers = create_mock_auth_headers(user, mock_supabase_verify)

        response = client.get("/api/v1/documentos/999999", headers=headers)
        assert response.status_code == 404

    def test_get_documento_other_user_returns_404(self, client: TestClient, db_session: Session, mock_supabase_verify: MagicMock):
        user_a = _make_user(db_session, email="ownera@rdoc.com")
        user_b = _make_user(db_session, email="ownerb@rdoc.com")
        doc = _make_documento(db_session, user_a.id)

        headers_b = create_mock_auth_headers(user_b, mock_supabase_verify)
        response = client.get(f"/api/v1/documentos/{doc.id}", headers=headers_b)
        assert response.status_code == 404

    def test_update_documento(self, client: TestClient, db_session: Session, mock_supabase_verify: MagicMock):
        user = _make_user(db_session, email="upd@rdoc.com")
        headers = create_mock_auth_headers(user, mock_supabase_verify)
        doc = _make_documento(db_session, user.id)

        response = client.put(f"/api/v1/documentos/{doc.id}", json={
            "nome": "Atualizado",
            "observacoes": "Nota via teste",
        }, headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["nome"] == "Atualizado"
        assert data["observacoes"] == "Nota via teste"

    def test_update_documento_not_found(self, client: TestClient, db_session: Session, mock_supabase_verify: MagicMock):
        user = _make_user(db_session, email="updnf@rdoc.com")
        headers = create_mock_auth_headers(user, mock_supabase_verify)

        response = client.put("/api/v1/documentos/999999", json={
            "nome": "X",
        }, headers=headers)
        assert response.status_code == 404

    def test_delete_documento(self, client: TestClient, db_session: Session, mock_supabase_verify: MagicMock):
        user = _make_user(db_session, email="del@rdoc.com")
        headers = create_mock_auth_headers(user, mock_supabase_verify)
        doc = _make_documento(db_session, user.id)

        response = client.delete(f"/api/v1/documentos/{doc.id}", headers=headers)
        assert response.status_code == 200
        assert response.json()["sucesso"] is True

        # Confirm deletion
        response = client.get(f"/api/v1/documentos/{doc.id}", headers=headers)
        assert response.status_code == 404

    def test_delete_documento_not_found(self, client: TestClient, db_session: Session, mock_supabase_verify: MagicMock):
        user = _make_user(db_session, email="delnf@rdoc.com")
        headers = create_mock_auth_headers(user, mock_supabase_verify)

        response = client.delete("/api/v1/documentos/999999", headers=headers)
        assert response.status_code == 404


# ===========================================================================
# Vencendo / Resumo
# ===========================================================================

class TestDocumentosVencendoResumo:

    def test_get_vencendo(self, client: TestClient, db_session: Session, mock_supabase_verify: MagicMock):
        user = _make_user(db_session, email="venc@rdoc.com")
        headers = create_mock_auth_headers(user, mock_supabase_verify)

        # Create doc vencendo
        _make_documento(
            db_session, user.id, nome="Vencendo",
            status=DocumentoStatus.VENCENDO,
            data_validade=datetime.now(timezone.utc) + timedelta(days=10),
        )
        # Create doc valido
        _make_documento(
            db_session, user.id, nome="Valido",
            status=DocumentoStatus.VALIDO,
            data_validade=datetime.now(timezone.utc) + timedelta(days=90),
        )

        response = client.get("/api/v1/documentos/vencendo", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        # At least the "Vencendo" doc should appear
        assert any(d["nome"] == "Vencendo" for d in data)

    def test_get_resumo(self, client: TestClient, db_session: Session, mock_supabase_verify: MagicMock):
        user = _make_user(db_session, email="res@rdoc.com")
        headers = create_mock_auth_headers(user, mock_supabase_verify)
        _make_documento(db_session, user.id, status=DocumentoStatus.VALIDO)
        _make_documento(db_session, user.id, nome="D2", status=DocumentoStatus.VENCENDO)

        response = client.get("/api/v1/documentos/resumo", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "validos" in data
        assert "vencendo" in data
        assert "vencidos" in data
        assert "nao_aplicavel" in data
        assert data["total"] == 2


# ===========================================================================
# Documentos por Licitacao
# ===========================================================================

class TestDocumentosPorLicitacao:

    def test_get_by_licitacao(self, client: TestClient, db_session: Session, mock_supabase_verify: MagicMock):
        user = _make_user(db_session, email="bylic@rdoc.com")
        headers = create_mock_auth_headers(user, mock_supabase_verify)
        lic = _make_licitacao(db_session, user.id)
        _make_documento(db_session, user.id, nome="D1", licitacao_id=lic.id)
        _make_documento(db_session, user.id, nome="D2", licitacao_id=lic.id)

        response = client.get(f"/api/v1/documentos/licitacao/{lic.id}", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

    def test_get_by_licitacao_not_found(self, client: TestClient, db_session: Session, mock_supabase_verify: MagicMock):
        user = _make_user(db_session, email="bylicnf@rdoc.com")
        headers = create_mock_auth_headers(user, mock_supabase_verify)

        response = client.get("/api/v1/documentos/licitacao/999999", headers=headers)
        assert response.status_code == 404


# ===========================================================================
# Checklist
# ===========================================================================

class TestDocumentosChecklist:

    def test_create_checklist_items(self, client: TestClient, db_session: Session, mock_supabase_verify: MagicMock):
        user = _make_user(db_session, email="clcreate@rdoc.com")
        headers = create_mock_auth_headers(user, mock_supabase_verify)
        lic = _make_licitacao(db_session, user.id)

        response = client.post(f"/api/v1/documentos/checklist/{lic.id}", json=[
            {"descricao": "Certidao FGTS", "tipo_documento": "certidao_fgts", "obrigatorio": True},
            {"descricao": "Balanco", "tipo_documento": "balanco"},
        ], headers=headers)

        assert response.status_code == 201
        data = response.json()
        assert len(data) == 2
        assert data[0]["descricao"] == "Certidao FGTS"
        assert data[0]["licitacao_id"] == lic.id
        assert data[0]["user_id"] == user.id

    def test_create_checklist_licitacao_not_found(self, client: TestClient, db_session: Session, mock_supabase_verify: MagicMock):
        user = _make_user(db_session, email="clnf@rdoc.com")
        headers = create_mock_auth_headers(user, mock_supabase_verify)

        response = client.post("/api/v1/documentos/checklist/999999", json=[
            {"descricao": "Item"},
        ], headers=headers)
        assert response.status_code == 404

    def test_get_checklist(self, client: TestClient, db_session: Session, mock_supabase_verify: MagicMock):
        user = _make_user(db_session, email="clget@rdoc.com")
        headers = create_mock_auth_headers(user, mock_supabase_verify)
        lic = _make_licitacao(db_session, user.id)

        # Create items first
        client.post(f"/api/v1/documentos/checklist/{lic.id}", json=[
            {"descricao": "Item 1"},
            {"descricao": "Item 2"},
        ], headers=headers)

        response = client.get(f"/api/v1/documentos/checklist/{lic.id}", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

    def test_get_checklist_resumo(self, client: TestClient, db_session: Session, mock_supabase_verify: MagicMock):
        user = _make_user(db_session, email="clresumo@rdoc.com")
        headers = create_mock_auth_headers(user, mock_supabase_verify)
        lic = _make_licitacao(db_session, user.id)

        client.post(f"/api/v1/documentos/checklist/{lic.id}", json=[
            {"descricao": "Item 1", "obrigatorio": True},
            {"descricao": "Item 2", "obrigatorio": True},
        ], headers=headers)

        response = client.get(f"/api/v1/documentos/checklist/{lic.id}/resumo", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["licitacao_id"] == lic.id
        assert data["total"] == 2
        assert data["cumpridos"] == 0
        assert data["pendentes"] == 2
        assert "percentual" in data

    def test_update_checklist_item(self, client: TestClient, db_session: Session, mock_supabase_verify: MagicMock):
        user = _make_user(db_session, email="clupd@rdoc.com")
        headers = create_mock_auth_headers(user, mock_supabase_verify)
        lic = _make_licitacao(db_session, user.id)

        create_resp = client.post(f"/api/v1/documentos/checklist/{lic.id}", json=[
            {"descricao": "Item Original"},
        ], headers=headers)
        item_id = create_resp.json()[0]["id"]

        response = client.put(f"/api/v1/documentos/checklist/item/{item_id}", json={
            "descricao": "Item Atualizado",
            "obrigatorio": False,
        }, headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["descricao"] == "Item Atualizado"
        assert data["obrigatorio"] is False

    def test_update_checklist_item_not_found(self, client: TestClient, db_session: Session, mock_supabase_verify: MagicMock):
        user = _make_user(db_session, email="clupdnf@rdoc.com")
        headers = create_mock_auth_headers(user, mock_supabase_verify)

        response = client.put("/api/v1/documentos/checklist/item/999999", json={
            "descricao": "X",
        }, headers=headers)
        assert response.status_code == 404

    def test_toggle_checklist_item(self, client: TestClient, db_session: Session, mock_supabase_verify: MagicMock):
        user = _make_user(db_session, email="cltoggle@rdoc.com")
        headers = create_mock_auth_headers(user, mock_supabase_verify)
        lic = _make_licitacao(db_session, user.id)

        create_resp = client.post(f"/api/v1/documentos/checklist/{lic.id}", json=[
            {"descricao": "Item Toggle"},
        ], headers=headers)
        item_id = create_resp.json()[0]["id"]

        # Toggle to cumprido
        response = client.patch(f"/api/v1/documentos/checklist/item/{item_id}/toggle", json={
            "cumprido": True,
        }, headers=headers)
        assert response.status_code == 200
        assert response.json()["cumprido"] is True

        # Toggle back
        response = client.patch(f"/api/v1/documentos/checklist/item/{item_id}/toggle", json={
            "cumprido": False,
        }, headers=headers)
        assert response.status_code == 200
        assert response.json()["cumprido"] is False

    def test_toggle_checklist_item_with_documento_id(self, client: TestClient, db_session: Session, mock_supabase_verify: MagicMock):
        user = _make_user(db_session, email="cltogdoc@rdoc.com")
        headers = create_mock_auth_headers(user, mock_supabase_verify)
        lic = _make_licitacao(db_session, user.id)
        doc = _make_documento(db_session, user.id, licitacao_id=lic.id)

        create_resp = client.post(f"/api/v1/documentos/checklist/{lic.id}", json=[
            {"descricao": "Item Vinculo"},
        ], headers=headers)
        item_id = create_resp.json()[0]["id"]

        response = client.patch(f"/api/v1/documentos/checklist/item/{item_id}/toggle", json={
            "cumprido": True,
            "documento_id": doc.id,
        }, headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["cumprido"] is True
        assert data["documento_id"] == doc.id

    def test_toggle_checklist_item_not_found(self, client: TestClient, db_session: Session, mock_supabase_verify: MagicMock):
        user = _make_user(db_session, email="cltognf@rdoc.com")
        headers = create_mock_auth_headers(user, mock_supabase_verify)

        response = client.patch("/api/v1/documentos/checklist/item/999999/toggle", json={
            "cumprido": True,
        }, headers=headers)
        assert response.status_code == 404

    def test_delete_checklist_item(self, client: TestClient, db_session: Session, mock_supabase_verify: MagicMock):
        user = _make_user(db_session, email="cldel@rdoc.com")
        headers = create_mock_auth_headers(user, mock_supabase_verify)
        lic = _make_licitacao(db_session, user.id)

        create_resp = client.post(f"/api/v1/documentos/checklist/{lic.id}", json=[
            {"descricao": "Item a Excluir"},
        ], headers=headers)
        item_id = create_resp.json()[0]["id"]

        response = client.delete(f"/api/v1/documentos/checklist/item/{item_id}", headers=headers)
        assert response.status_code == 200
        assert response.json()["sucesso"] is True

    def test_delete_checklist_item_not_found(self, client: TestClient, db_session: Session, mock_supabase_verify: MagicMock):
        user = _make_user(db_session, email="cldelnf@rdoc.com")
        headers = create_mock_auth_headers(user, mock_supabase_verify)

        response = client.delete("/api/v1/documentos/checklist/item/999999", headers=headers)
        assert response.status_code == 404
