"""
Testes para o router de atestados.

Testa endpoints de CRUD, upload e paginação de atestados.
Usa mocking para autenticação Supabase.
"""
import uuid
from datetime import date
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from models import Usuario, Atestado


def unique_email(prefix: str = "test") -> str:
    """Gera email único para evitar conflitos."""
    return f"{prefix}_{uuid.uuid4().hex[:8]}@teste.com"


def generate_supabase_id() -> str:
    """Gera um UUID simulando supabase_id."""
    return str(uuid.uuid4())


class TestAtestadosRequireAuth:
    """Testes de autenticação para endpoints de atestados."""

    def test_list_atestados_requires_auth(self, client: TestClient):
        """Verifica que listar atestados requer autenticação."""
        response = client.get("/api/v1/atestados/")
        assert response.status_code == 401

    def test_get_atestado_requires_auth(self, client: TestClient):
        """Verifica que obter atestado requer autenticação."""
        response = client.get("/api/v1/atestados/1")
        assert response.status_code == 401

    def test_create_atestado_requires_auth(self, client: TestClient):
        """Verifica que criar atestado requer autenticação."""
        response = client.post("/api/v1/atestados/", json={
            "descricao_servico": "Teste"
        })
        assert response.status_code == 401

    def test_upload_atestado_requires_auth(self, client: TestClient):
        """Verifica que upload de atestado requer autenticação."""
        response = client.post("/api/v1/atestados/upload")
        assert response.status_code == 401

    def test_update_atestado_requires_auth(self, client: TestClient):
        """Verifica que atualizar atestado requer autenticação."""
        response = client.put("/api/v1/atestados/1", json={
            "descricao_servico": "Novo"
        })
        assert response.status_code == 401

    def test_delete_atestado_requires_auth(self, client: TestClient):
        """Verifica que excluir atestado requer autenticação."""
        response = client.delete("/api/v1/atestados/1")
        assert response.status_code == 401

    def test_update_servicos_requires_auth(self, client: TestClient):
        """Verifica que atualizar serviços requer autenticação."""
        response = client.patch("/api/v1/atestados/1/servicos", json={
            "servicos_json": []
        })
        assert response.status_code == 401

    def test_reprocess_requires_auth(self, client: TestClient):
        """Verifica que reprocessar atestado requer autenticação."""
        response = client.post("/api/v1/atestados/1/reprocess")
        assert response.status_code == 401


class TestAtestadosCRUD:
    """Testes de operações CRUD de atestados."""

    def test_list_atestados_empty(self, client: TestClient, db_session: Session):
        """Verifica que listar atestados retorna lista vazia quando não há dados."""
        email = unique_email("list_empty")
        supabase_id = generate_supabase_id()
        user = Usuario(
            email=email,
            nome="Teste Lista Vazia",
            supabase_id=supabase_id,
            is_active=True,
            is_approved=True,
            is_admin=False
        )
        db_session.add(user)
        db_session.commit()

        try:
            with patch('services.supabase_auth.verify_supabase_token') as mock_verify:
                mock_verify.return_value = {"id": supabase_id, "email": email}
                headers = {"Authorization": "Bearer mock_token"}

                response = client.get("/api/v1/atestados/", headers=headers)
                assert response.status_code in [200, 429]

                if response.status_code == 200:
                    data = response.json()
                    assert "items" in data
                    assert "total" in data
                    assert data["items"] == []
                    assert data["total"] == 0
        finally:
            db_session.delete(user)
            db_session.commit()

    def test_list_atestados_with_data(self, client: TestClient, db_session: Session):
        """Verifica que listar atestados retorna dados existentes."""
        email = unique_email("list_data")
        supabase_id = generate_supabase_id()
        user = Usuario(
            email=email,
            nome="Teste Lista Dados",
            supabase_id=supabase_id,
            is_active=True,
            is_approved=True,
            is_admin=False
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        atestado = Atestado(
            user_id=user.id,
            descricao_servico="Pavimentação asfáltica",
            quantidade=1000.0,
            unidade="m2",
            contratante="Prefeitura Teste"
        )
        db_session.add(atestado)
        db_session.commit()

        try:
            with patch('services.supabase_auth.verify_supabase_token') as mock_verify:
                mock_verify.return_value = {"id": supabase_id, "email": email}
                headers = {"Authorization": "Bearer mock_token"}

                response = client.get("/api/v1/atestados/", headers=headers)
                assert response.status_code in [200, 429]

                if response.status_code == 200:
                    data = response.json()
                    assert data["total"] >= 1
                    assert len(data["items"]) >= 1
                    assert data["items"][0]["descricao_servico"] == "Pavimentação asfáltica"
        finally:
            db_session.delete(atestado)
            db_session.delete(user)
            db_session.commit()

    def test_list_atestados_pagination(self, client: TestClient, db_session: Session):
        """Verifica que paginação funciona corretamente."""
        email = unique_email("list_pag")
        supabase_id = generate_supabase_id()
        user = Usuario(
            email=email,
            nome="Teste Paginação",
            supabase_id=supabase_id,
            is_active=True,
            is_approved=True,
            is_admin=False
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        atestados = []
        for i in range(5):
            a = Atestado(
                user_id=user.id,
                descricao_servico=f"Serviço {i+1}",
                quantidade=100.0 * (i + 1),
                unidade="m2",
                contratante=f"Contratante {i+1}"
            )
            db_session.add(a)
            atestados.append(a)
        db_session.commit()

        try:
            with patch('services.supabase_auth.verify_supabase_token') as mock_verify:
                mock_verify.return_value = {"id": supabase_id, "email": email}
                headers = {"Authorization": "Bearer mock_token"}

                # Primeira página com 2 itens
                response = client.get(
                    "/api/v1/atestados/?page=1&page_size=2",
                    headers=headers
                )
                assert response.status_code in [200, 429]

                if response.status_code == 200:
                    data = response.json()
                    assert data["total"] == 5
                    assert len(data["items"]) == 2
                    assert data["page"] == 1
                    assert data["page_size"] == 2
        finally:
            for a in atestados:
                db_session.delete(a)
            db_session.delete(user)
            db_session.commit()

    def test_get_atestado_by_id(self, client: TestClient, db_session: Session):
        """Verifica que é possível obter um atestado específico pelo ID."""
        email = unique_email("get_by_id")
        supabase_id = generate_supabase_id()
        user = Usuario(
            email=email,
            nome="Teste Get ID",
            supabase_id=supabase_id,
            is_active=True,
            is_approved=True,
            is_admin=False
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        atestado = Atestado(
            user_id=user.id,
            descricao_servico="Serviço Específico",
            quantidade=500.0,
            unidade="ml",
            contratante="Contratante Específico",
            data_emissao=date(2023, 6, 15)
        )
        db_session.add(atestado)
        db_session.commit()
        db_session.refresh(atestado)

        try:
            with patch('services.supabase_auth.verify_supabase_token') as mock_verify:
                mock_verify.return_value = {"id": supabase_id, "email": email}
                headers = {"Authorization": "Bearer mock_token"}

                response = client.get(
                    f"/api/v1/atestados/{atestado.id}",
                    headers=headers
                )
                assert response.status_code in [200, 429]

                if response.status_code == 200:
                    data = response.json()
                    assert data["id"] == atestado.id
                    assert data["descricao_servico"] == "Serviço Específico"
                    assert data["contratante"] == "Contratante Específico"
        finally:
            db_session.delete(atestado)
            db_session.delete(user)
            db_session.commit()

    def test_get_atestado_not_found(self, client: TestClient, db_session: Session):
        """Verifica que retorna 404 para atestado inexistente."""
        email = unique_email("get_404")
        supabase_id = generate_supabase_id()
        user = Usuario(
            email=email,
            nome="Teste 404",
            supabase_id=supabase_id,
            is_active=True,
            is_approved=True,
            is_admin=False
        )
        db_session.add(user)
        db_session.commit()

        try:
            with patch('services.supabase_auth.verify_supabase_token') as mock_verify:
                mock_verify.return_value = {"id": supabase_id, "email": email}
                headers = {"Authorization": "Bearer mock_token"}

                response = client.get(
                    "/api/v1/atestados/99999",
                    headers=headers
                )
                assert response.status_code in [404, 429]
        finally:
            db_session.delete(user)
            db_session.commit()

    def test_create_atestado_manual(self, client: TestClient, db_session: Session):
        """Verifica que é possível criar um atestado manualmente."""
        email = unique_email("create")
        supabase_id = generate_supabase_id()
        user = Usuario(
            email=email,
            nome="Teste Create",
            supabase_id=supabase_id,
            is_active=True,
            is_approved=True,
            is_admin=False
        )
        db_session.add(user)
        db_session.commit()

        try:
            with patch('services.supabase_auth.verify_supabase_token') as mock_verify:
                mock_verify.return_value = {"id": supabase_id, "email": email}
                headers = {"Authorization": "Bearer mock_token"}

                response = client.post(
                    "/api/v1/atestados/",
                    headers=headers,
                    json={
                        "descricao_servico": "Construção de ponte",
                        "quantidade": 150.0,
                        "unidade": "m",
                        "contratante": "DNIT"
                    }
                )
                assert response.status_code in [200, 429]

                if response.status_code == 200:
                    data = response.json()
                    assert data["descricao_servico"] == "Construção de ponte"
                    assert data["contratante"] == "DNIT"
                    assert data["unidade"] == "m"
                    assert "id" in data

                    # Cleanup: remover atestado criado
                    created_atestado = db_session.query(Atestado).get(data["id"])
                    if created_atestado:
                        db_session.delete(created_atestado)
                        db_session.commit()
        finally:
            db_session.delete(user)
            db_session.commit()

    def test_update_atestado(self, client: TestClient, db_session: Session):
        """Verifica que é possível atualizar um atestado existente."""
        email = unique_email("update")
        supabase_id = generate_supabase_id()
        user = Usuario(
            email=email,
            nome="Teste Update",
            supabase_id=supabase_id,
            is_active=True,
            is_approved=True,
            is_admin=False
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        atestado = Atestado(
            user_id=user.id,
            descricao_servico="Serviço Original",
            quantidade=100.0,
            unidade="m2",
            contratante="Contratante Original"
        )
        db_session.add(atestado)
        db_session.commit()
        db_session.refresh(atestado)

        try:
            with patch('services.supabase_auth.verify_supabase_token') as mock_verify:
                mock_verify.return_value = {"id": supabase_id, "email": email}
                headers = {"Authorization": "Bearer mock_token"}

                response = client.put(
                    f"/api/v1/atestados/{atestado.id}",
                    headers=headers,
                    json={
                        "descricao_servico": "Serviço Atualizado",
                        "quantidade": 200.0,
                        "contratante": "Contratante Atualizado"
                    }
                )
                assert response.status_code in [200, 429]

                if response.status_code == 200:
                    data = response.json()
                    assert data["descricao_servico"] == "Serviço Atualizado"
                    assert data["contratante"] == "Contratante Atualizado"
        finally:
            db_session.delete(atestado)
            db_session.delete(user)
            db_session.commit()

    def test_delete_atestado(self, client: TestClient, db_session: Session):
        """Verifica que é possível excluir um atestado."""
        email = unique_email("delete")
        supabase_id = generate_supabase_id()
        user = Usuario(
            email=email,
            nome="Teste Delete",
            supabase_id=supabase_id,
            is_active=True,
            is_approved=True,
            is_admin=False
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        atestado = Atestado(
            user_id=user.id,
            descricao_servico="Serviço para Excluir",
            quantidade=300.0,
            unidade="m2",
            contratante="Contratante Delete"
        )
        db_session.add(atestado)
        db_session.commit()
        db_session.refresh(atestado)
        atestado_id = atestado.id

        try:
            with patch('services.supabase_auth.verify_supabase_token') as mock_verify:
                mock_verify.return_value = {"id": supabase_id, "email": email}
                headers = {"Authorization": "Bearer mock_token"}

                response = client.delete(
                    f"/api/v1/atestados/{atestado_id}",
                    headers=headers
                )
                assert response.status_code in [200, 429]

                if response.status_code == 200:
                    data = response.json()
                    assert data["sucesso"] is True

                    # Expirar cache da sessao para ver estado atual do banco
                    db_session.expire_all()
                    check = db_session.query(Atestado).get(atestado_id)
                    assert check is None
        finally:
            # Cleanup: caso o delete não tenha funcionado
            db_session.expire_all()
            remaining = db_session.query(Atestado).get(atestado_id)
            if remaining:
                db_session.delete(remaining)
            db_session.delete(user)
            db_session.commit()

    def test_get_atestado_other_user_returns_404(self, client: TestClient, db_session: Session):
        """Verifica que usuário não pode acessar atestado de outro usuário."""
        # Criar dono do atestado
        owner_email = unique_email("owner")
        owner_supabase_id = generate_supabase_id()
        owner = Usuario(
            email=owner_email,
            nome="Dono",
            supabase_id=owner_supabase_id,
            is_active=True,
            is_approved=True,
            is_admin=False
        )
        db_session.add(owner)
        db_session.commit()
        db_session.refresh(owner)

        atestado = Atestado(
            user_id=owner.id,
            descricao_servico="Atestado do Dono",
            quantidade=100.0,
            unidade="m2"
        )
        db_session.add(atestado)
        db_session.commit()
        db_session.refresh(atestado)

        # Criar outro usuário que tentará acessar
        other_email = unique_email("other")
        other_supabase_id = generate_supabase_id()
        other_user = Usuario(
            email=other_email,
            nome="Outro",
            supabase_id=other_supabase_id,
            is_active=True,
            is_approved=True,
            is_admin=False
        )
        db_session.add(other_user)
        db_session.commit()

        try:
            with patch('services.supabase_auth.verify_supabase_token') as mock_verify:
                mock_verify.return_value = {"id": other_supabase_id, "email": other_email}
                headers = {"Authorization": "Bearer mock_token"}

                response = client.get(
                    f"/api/v1/atestados/{atestado.id}",
                    headers=headers
                )
                # Should be 404 (not 403) to avoid revealing resource existence
                assert response.status_code in [404, 429]
        finally:
            db_session.delete(atestado)
            db_session.delete(other_user)
            db_session.delete(owner)
            db_session.commit()


class TestAtestadosUpload:
    """Testes para upload de atestados."""

    def test_upload_invalid_extension_rejected(self, client: TestClient, db_session: Session):
        """Verifica que upload com extensão inválida é rejeitado."""
        email = unique_email("upload_ext")
        supabase_id = generate_supabase_id()
        user = Usuario(
            email=email,
            nome="Teste Upload Ext",
            supabase_id=supabase_id,
            is_active=True,
            is_approved=True,
            is_admin=False
        )
        db_session.add(user)
        db_session.commit()

        try:
            with patch('services.supabase_auth.verify_supabase_token') as mock_verify:
                mock_verify.return_value = {"id": supabase_id, "email": email}
                headers = {"Authorization": "Bearer mock_token"}

                # Tentar upload com arquivo .txt (extensão inválida)
                response = client.post(
                    "/api/v1/atestados/upload",
                    headers=headers,
                    files={"file": ("documento.txt", b"conteudo do arquivo", "text/plain")}
                )
                assert response.status_code in [400, 422, 429]
        finally:
            db_session.delete(user)
            db_session.commit()

    def test_upload_no_file_rejected(self, client: TestClient, db_session: Session):
        """Verifica que upload sem arquivo é rejeitado."""
        email = unique_email("upload_no_file")
        supabase_id = generate_supabase_id()
        user = Usuario(
            email=email,
            nome="Teste Upload No File",
            supabase_id=supabase_id,
            is_active=True,
            is_approved=True,
            is_admin=False
        )
        db_session.add(user)
        db_session.commit()

        try:
            with patch('services.supabase_auth.verify_supabase_token') as mock_verify:
                mock_verify.return_value = {"id": supabase_id, "email": email}
                headers = {"Authorization": "Bearer mock_token"}

                response = client.post(
                    "/api/v1/atestados/upload",
                    headers=headers
                )
                assert response.status_code in [422, 429]
        finally:
            db_session.delete(user)
            db_session.commit()
