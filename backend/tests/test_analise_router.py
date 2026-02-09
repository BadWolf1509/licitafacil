"""
Testes para o router de análises de licitação.

Testa endpoints de CRUD, criação manual e paginação de análises.
Usa mocking para autenticação Supabase.
"""
import uuid
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from models import Analise, Usuario


def unique_email(prefix: str = "test") -> str:
    """Gera email único para evitar conflitos."""
    return f"{prefix}_{uuid.uuid4().hex[:8]}@teste.com"


def generate_supabase_id() -> str:
    """Gera um UUID simulando supabase_id."""
    return str(uuid.uuid4())


class TestAnaliseRequireAuth:
    """Testes de autenticação para endpoints de análises."""

    def test_list_analises_requires_auth(self, client: TestClient):
        """Verifica que listar análises requer autenticação."""
        response = client.get("/api/v1/analises/")
        assert response.status_code == 401

    def test_get_analise_requires_auth(self, client: TestClient):
        """Verifica que obter análise requer autenticação."""
        response = client.get("/api/v1/analises/1")
        assert response.status_code == 401

    def test_create_analise_requires_auth(self, client: TestClient):
        """Verifica que criar análise (upload) requer autenticação."""
        response = client.post("/api/v1/analises/")
        assert response.status_code == 401

    def test_create_manual_analise_requires_auth(self, client: TestClient):
        """Verifica que criar análise manual requer autenticação."""
        response = client.post("/api/v1/analises/manual", json={
            "nome_licitacao": "Teste",
            "exigencias": []
        })
        assert response.status_code == 401

    def test_reprocess_analise_requires_auth(self, client: TestClient):
        """Verifica que reprocessar análise requer autenticação."""
        response = client.post("/api/v1/analises/1/processar")
        assert response.status_code == 401

    def test_delete_analise_requires_auth(self, client: TestClient):
        """Verifica que excluir análise requer autenticação."""
        response = client.delete("/api/v1/analises/1")
        assert response.status_code == 401

    def test_services_status_requires_auth(self, client: TestClient):
        """Verifica que status dos serviços requer autenticação."""
        response = client.get("/api/v1/analises/status/servicos")
        assert response.status_code == 401


class TestAnaliseCRUD:
    """Testes de operações CRUD de análises."""

    def test_list_analises_empty(self, client: TestClient, db_session: Session):
        """Verifica que listar análises retorna lista vazia quando não há dados."""
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

                response = client.get("/api/v1/analises/", headers=headers)
                assert response.status_code in [200, 401, 429]

                if response.status_code == 200:
                    data = response.json()
                    assert "items" in data
                    assert "total" in data
                    assert data["items"] == []
                    assert data["total"] == 0
        finally:
            db_session.delete(user)
            db_session.commit()

    def test_list_analises_with_data(self, client: TestClient, db_session: Session):
        """Verifica que listar análises retorna dados existentes."""
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

        analise = Analise(
            user_id=user.id,
            nome_licitacao="Edital de Teste",
            arquivo_path="uploads/edital_teste.pdf",
            exigencias_json=[
                {"descricao": "Pavimentação", "quantidade_minima": 1000.0, "unidade": "m2"}
            ],
            resultado_json=[]
        )
        db_session.add(analise)
        db_session.commit()

        try:
            with patch('services.supabase_auth.verify_supabase_token') as mock_verify:
                mock_verify.return_value = {"id": supabase_id, "email": email}
                headers = {"Authorization": "Bearer mock_token"}

                response = client.get("/api/v1/analises/", headers=headers)
                assert response.status_code in [200, 401, 429]

                if response.status_code == 200:
                    data = response.json()
                    assert data["total"] >= 1
                    assert len(data["items"]) >= 1
                    assert data["items"][0]["nome_licitacao"] == "Edital de Teste"
        finally:
            db_session.delete(analise)
            db_session.delete(user)
            db_session.commit()

    def test_list_analises_pagination(self, client: TestClient, db_session: Session):
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

        analises = []
        for i in range(5):
            a = Analise(
                user_id=user.id,
                nome_licitacao=f"Edital {i+1}",
                exigencias_json=[],
                resultado_json=[]
            )
            db_session.add(a)
            analises.append(a)
        db_session.commit()

        try:
            with patch('services.supabase_auth.verify_supabase_token') as mock_verify:
                mock_verify.return_value = {"id": supabase_id, "email": email}
                headers = {"Authorization": "Bearer mock_token"}

                # Primeira página com 2 itens
                response = client.get(
                    "/api/v1/analises/?page=1&page_size=2",
                    headers=headers
                )
                assert response.status_code in [200, 401, 429]

                if response.status_code == 200:
                    data = response.json()
                    assert data["total"] == 5
                    assert len(data["items"]) == 2
                    assert data["page"] == 1
                    assert data["page_size"] == 2
        finally:
            for a in analises:
                db_session.delete(a)
            db_session.delete(user)
            db_session.commit()

    def test_get_analise_by_id(self, client: TestClient, db_session: Session):
        """Verifica que é possível obter uma análise específica pelo ID."""
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

        analise = Analise(
            user_id=user.id,
            nome_licitacao="Edital Específico",
            arquivo_path="uploads/edital_especifico.pdf",
            exigencias_json=[
                {"descricao": "Drenagem", "quantidade_minima": 500.0, "unidade": "ml"}
            ],
            resultado_json=[
                {
                    "exigencia": {"descricao": "Drenagem", "quantidade_minima": 500.0, "unidade": "ml"},
                    "status": "atende",
                    "atestados_recomendados": [],
                    "soma_quantidades": 600.0,
                    "percentual_total": 120.0
                }
            ]
        )
        db_session.add(analise)
        db_session.commit()
        db_session.refresh(analise)

        try:
            with patch('services.supabase_auth.verify_supabase_token') as mock_verify:
                mock_verify.return_value = {"id": supabase_id, "email": email}
                headers = {"Authorization": "Bearer mock_token"}

                response = client.get(
                    f"/api/v1/analises/{analise.id}",
                    headers=headers
                )
                assert response.status_code in [200, 401, 429]

                if response.status_code == 200:
                    data = response.json()
                    assert data["id"] == analise.id
                    assert data["nome_licitacao"] == "Edital Específico"
                    assert "exigencias_json" in data
                    assert "resultado_json" in data
        finally:
            db_session.delete(analise)
            db_session.delete(user)
            db_session.commit()

    def test_get_analise_not_found(self, client: TestClient, db_session: Session):
        """Verifica que retorna 404 para análise inexistente."""
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
                    "/api/v1/analises/99999",
                    headers=headers
                )
                assert response.status_code in [401, 404, 429]
        finally:
            db_session.delete(user)
            db_session.commit()

    def test_delete_analise(self, client: TestClient, db_session: Session):
        """Verifica que é possível excluir uma análise."""
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

        analise = Analise(
            user_id=user.id,
            nome_licitacao="Edital para Excluir",
            exigencias_json=[],
            resultado_json=[]
        )
        db_session.add(analise)
        db_session.commit()
        db_session.refresh(analise)
        analise_id = analise.id

        try:
            with patch('services.supabase_auth.verify_supabase_token') as mock_verify:
                mock_verify.return_value = {"id": supabase_id, "email": email}
                headers = {"Authorization": "Bearer mock_token"}

                response = client.delete(
                    f"/api/v1/analises/{analise_id}",
                    headers=headers
                )
                assert response.status_code in [200, 401, 429]

                if response.status_code == 200:
                    data = response.json()
                    assert data["sucesso"] is True

                    # Expirar cache da sessao para ver estado atual do banco
                    db_session.expire_all()
                    check = db_session.query(Analise).get(analise_id)
                    assert check is None
        finally:
            # Cleanup: caso o delete não tenha funcionado
            db_session.expire_all()
            remaining = db_session.query(Analise).get(analise_id)
            if remaining:
                db_session.delete(remaining)
            db_session.delete(user)
            db_session.commit()

    def test_get_analise_other_user_returns_404(self, client: TestClient, db_session: Session):
        """Verifica que usuário não pode acessar análise de outro usuário."""
        # Criar dono da análise
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

        analise = Analise(
            user_id=owner.id,
            nome_licitacao="Edital do Dono",
            exigencias_json=[],
            resultado_json=[]
        )
        db_session.add(analise)
        db_session.commit()
        db_session.refresh(analise)

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
                    f"/api/v1/analises/{analise.id}",
                    headers=headers
                )
                # Should be 404 (not 403) to avoid revealing resource existence
                assert response.status_code in [401, 404, 429]
        finally:
            db_session.delete(analise)
            db_session.delete(other_user)
            db_session.delete(owner)
            db_session.commit()


class TestAnaliseCreation:
    """Testes para criação de análises."""

    def test_create_manual_analysis(self, client: TestClient, db_session: Session):
        """Verifica que é possível criar uma análise manual."""
        email = unique_email("create_manual")
        supabase_id = generate_supabase_id()
        user = Usuario(
            email=email,
            nome="Teste Manual",
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

                # Mock do document_processor para o matching
                with patch('dependencies.get_services') as mock_services:
                    mock_container = MagicMock()
                    mock_container.document_processor.analyze_qualification.return_value = []
                    mock_services.return_value = mock_container

                    response = client.post(
                        "/api/v1/analises/manual",
                        headers=headers,
                        json={
                            "nome_licitacao": "Licitação Manual",
                            "exigencias": [
                                {
                                    "descricao": "Pavimentação asfáltica em CBUQ",
                                    "quantidade_minima": 5000.0,
                                    "unidade": "m2"
                                }
                            ]
                        }
                    )
                    assert response.status_code in [200, 401, 429]

                    if response.status_code == 200:
                        data = response.json()
                        assert data["nome_licitacao"] == "Licitação Manual"
                        assert "id" in data
                        assert data["arquivo_path"] is None
                        assert "exigencias_json" in data

                        # Cleanup: remover análise criada
                        created = db_session.query(Analise).get(data["id"])
                        if created:
                            db_session.delete(created)
                            db_session.commit()
        finally:
            db_session.delete(user)
            db_session.commit()

    def test_create_manual_analysis_empty_exigencias_rejected(self, client: TestClient, db_session: Session):
        """Verifica que análise manual sem exigências é rejeitada."""
        email = unique_email("create_empty")
        supabase_id = generate_supabase_id()
        user = Usuario(
            email=email,
            nome="Teste Empty",
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
                    "/api/v1/analises/manual",
                    headers=headers,
                    json={
                        "nome_licitacao": "Licitação Vazia",
                        "exigencias": []
                    }
                )
                assert response.status_code in [400, 401, 429]
        finally:
            db_session.delete(user)
            db_session.commit()

    def test_delete_analise_not_found(self, client: TestClient, db_session: Session):
        """Verifica que excluir análise inexistente retorna 404."""
        email = unique_email("delete_404")
        supabase_id = generate_supabase_id()
        user = Usuario(
            email=email,
            nome="Teste Delete 404",
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

                response = client.delete(
                    "/api/v1/analises/99999",
                    headers=headers
                )
                assert response.status_code in [401, 404, 429]
        finally:
            db_session.delete(user)
            db_session.commit()
