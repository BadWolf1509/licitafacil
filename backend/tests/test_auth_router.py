"""
Testes para o router de autenticação.

Testa endpoints de configuração, status, perfil e requisitos de senha.
Usa mocking para autenticação Supabase.
"""
import uuid
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from models import Usuario


def unique_email(prefix: str = "test") -> str:
    """Gera email único para evitar conflitos."""
    return f"{prefix}_{uuid.uuid4().hex[:8]}@teste.com"


def generate_supabase_id() -> str:
    """Gera um UUID simulando supabase_id."""
    return str(uuid.uuid4())


class TestAuthEndpointsRequireAuth:
    """Testes de autenticação para endpoints protegidos do auth router."""

    def test_me_requires_auth(self, client: TestClient):
        """Verifica que GET /auth/me requer autenticação."""
        response = client.get("/api/v1/auth/me")
        assert response.status_code == 401

    def test_status_requires_auth(self, client: TestClient):
        """Verifica que GET /auth/status requer autenticação."""
        response = client.get("/api/v1/auth/status")
        assert response.status_code == 401

    def test_update_profile_requires_auth(self, client: TestClient):
        """Verifica que PUT /auth/me requer autenticação."""
        response = client.put("/api/v1/auth/me", json={"nome": "Novo Nome"})
        assert response.status_code == 401


class TestAuthConfig:
    """Testes para o endpoint de configuração de autenticação."""

    def test_get_auth_config_returns_200(self, client: TestClient):
        """Verifica que GET /auth/config retorna 200 sem autenticação."""
        response = client.get("/api/v1/auth/config")
        assert response.status_code == 200

    def test_get_auth_config_has_expected_fields(self, client: TestClient):
        """Verifica que a configuração contém os campos esperados."""
        response = client.get("/api/v1/auth/config")
        assert response.status_code == 200
        data = response.json()
        assert "mode" in data
        assert "supabase_enabled" in data
        assert isinstance(data["mode"], str)
        assert isinstance(data["supabase_enabled"], bool)

    def test_get_auth_config_mode_is_valid(self, client: TestClient):
        """Verifica que o modo de autenticação é um valor válido."""
        response = client.get("/api/v1/auth/config")
        assert response.status_code == 200
        data = response.json()
        assert data["mode"] in ["supabase", "local"]


class TestPasswordRequirements:
    """Testes para o endpoint de requisitos de senha."""

    def test_get_password_requirements_returns_200(self, client: TestClient):
        """Verifica que GET /auth/password-requirements retorna 200 sem autenticação."""
        response = client.get("/api/v1/auth/password-requirements")
        assert response.status_code == 200

    def test_get_password_requirements_has_list(self, client: TestClient):
        """Verifica que a resposta contém uma lista de requisitos."""
        response = client.get("/api/v1/auth/password-requirements")
        assert response.status_code == 200
        data = response.json()
        assert "requisitos" in data
        assert isinstance(data["requisitos"], list)
        assert len(data["requisitos"]) > 0

    def test_get_password_requirements_items_are_strings(self, client: TestClient):
        """Verifica que cada requisito é uma string."""
        response = client.get("/api/v1/auth/password-requirements")
        assert response.status_code == 200
        data = response.json()
        for req in data["requisitos"]:
            assert isinstance(req, str)
            assert len(req) > 0


class TestAuthStatus:
    """Testes para o endpoint de status do usuário."""

    def test_status_returns_user_data(self, client: TestClient, db_session: Session):
        """Verifica que GET /auth/status com usuário válido retorna dados."""
        email = unique_email("status")
        supabase_id = generate_supabase_id()
        user = Usuario(
            email=email,
            nome="Usuário Status",
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

                response = client.get("/api/v1/auth/status", headers=headers)
                assert response.status_code in [200, 429]

                if response.status_code == 200:
                    data = response.json()
                    assert "aprovado" in data
                    assert "admin" in data
                    assert "nome" in data
                    assert "auth_mode" in data
                    assert data["aprovado"] is True
                    assert data["admin"] is False
                    assert data["nome"] == "Usuário Status"
        finally:
            db_session.delete(user)
            db_session.commit()

    def test_status_returns_admin_flag(self, client: TestClient, db_session: Session):
        """Verifica que status retorna flag admin correta para admin."""
        email = unique_email("admin_status")
        supabase_id = generate_supabase_id()
        user = Usuario(
            email=email,
            nome="Admin Status",
            supabase_id=supabase_id,
            is_active=True,
            is_approved=True,
            is_admin=True
        )
        db_session.add(user)
        db_session.commit()

        try:
            with patch('services.supabase_auth.verify_supabase_token') as mock_verify:
                mock_verify.return_value = {"id": supabase_id, "email": email}
                headers = {"Authorization": "Bearer mock_token"}

                response = client.get("/api/v1/auth/status", headers=headers)
                assert response.status_code in [200, 429]

                if response.status_code == 200:
                    data = response.json()
                    assert data["admin"] is True
        finally:
            db_session.delete(user)
            db_session.commit()

    def test_status_unapproved_user(self, client: TestClient, db_session: Session):
        """Verifica que status retorna aprovado=False para usuário não aprovado."""
        email = unique_email("unapproved")
        supabase_id = generate_supabase_id()
        user = Usuario(
            email=email,
            nome="Não Aprovado",
            supabase_id=supabase_id,
            is_active=True,
            is_approved=False,
            is_admin=False
        )
        db_session.add(user)
        db_session.commit()

        try:
            with patch('services.supabase_auth.verify_supabase_token') as mock_verify:
                mock_verify.return_value = {"id": supabase_id, "email": email}
                headers = {"Authorization": "Bearer mock_token"}

                response = client.get("/api/v1/auth/status", headers=headers)
                assert response.status_code in [200, 429]

                if response.status_code == 200:
                    data = response.json()
                    assert data["aprovado"] is False
        finally:
            db_session.delete(user)
            db_session.commit()


class TestUserProfile:
    """Testes para endpoints de perfil do usuário."""

    def test_get_me_returns_user_profile(self, client: TestClient, db_session: Session):
        """Verifica que GET /auth/me retorna perfil do usuário."""
        email = unique_email("profile")
        supabase_id = generate_supabase_id()
        user = Usuario(
            email=email,
            nome="Perfil Teste",
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

                response = client.get("/api/v1/auth/me", headers=headers)
                assert response.status_code in [200, 429]

                if response.status_code == 200:
                    data = response.json()
                    assert data["email"] == email
                    assert data["nome"] == "Perfil Teste"
                    assert "id" in data
                    assert "is_admin" in data
                    assert "is_approved" in data
                    assert "is_active" in data
                    assert "tema_preferido" in data
                    assert "created_at" in data
        finally:
            db_session.delete(user)
            db_session.commit()

    def test_update_profile_name(self, client: TestClient, db_session: Session):
        """Verifica que PUT /auth/me atualiza o nome do usuário."""
        email = unique_email("update_name")
        supabase_id = generate_supabase_id()
        user = Usuario(
            email=email,
            nome="Nome Original",
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

                with patch('services.supabase_auth.update_supabase_user_metadata'):
                    response = client.put(
                        "/api/v1/auth/me",
                        headers=headers,
                        json={"nome": "Nome Atualizado"}
                    )
                    assert response.status_code in [200, 429]

                    if response.status_code == 200:
                        data = response.json()
                        assert data["nome"] == "Nome Atualizado"
        finally:
            db_session.delete(user)
            db_session.commit()

    def test_update_profile_theme(self, client: TestClient, db_session: Session):
        """Verifica que PUT /auth/me atualiza o tema preferido."""
        email = unique_email("update_theme")
        supabase_id = generate_supabase_id()
        user = Usuario(
            email=email,
            nome="Tema Teste",
            supabase_id=supabase_id,
            is_active=True,
            is_approved=True,
            is_admin=False,
            tema_preferido="light"
        )
        db_session.add(user)
        db_session.commit()

        try:
            with patch('services.supabase_auth.verify_supabase_token') as mock_verify:
                mock_verify.return_value = {"id": supabase_id, "email": email}
                headers = {"Authorization": "Bearer mock_token"}

                response = client.put(
                    "/api/v1/auth/me",
                    headers=headers,
                    json={"tema_preferido": "dark"}
                )
                assert response.status_code in [200, 429]

                if response.status_code == 200:
                    data = response.json()
                    assert data["tema_preferido"] == "dark"
        finally:
            db_session.delete(user)
            db_session.commit()

    def test_update_profile_invalid_theme(self, client: TestClient, db_session: Session):
        """Verifica que PUT /auth/me rejeita tema inválido."""
        email = unique_email("invalid_theme")
        supabase_id = generate_supabase_id()
        user = Usuario(
            email=email,
            nome="Tema Inválido",
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

                response = client.put(
                    "/api/v1/auth/me",
                    headers=headers,
                    json={"tema_preferido": "invalid_theme"}
                )
                assert response.status_code in [400, 429]
        finally:
            db_session.delete(user)
            db_session.commit()

    def test_update_profile_unapproved_user_rejected(self, client: TestClient, db_session: Session):
        """Verifica que PUT /auth/me rejeita usuário não aprovado."""
        email = unique_email("unapproved_update")
        supabase_id = generate_supabase_id()
        user = Usuario(
            email=email,
            nome="Não Aprovado",
            supabase_id=supabase_id,
            is_active=True,
            is_approved=False,
            is_admin=False
        )
        db_session.add(user)
        db_session.commit()

        try:
            with patch('services.supabase_auth.verify_supabase_token') as mock_verify:
                mock_verify.return_value = {"id": supabase_id, "email": email}
                headers = {"Authorization": "Bearer mock_token"}

                response = client.put(
                    "/api/v1/auth/me",
                    headers=headers,
                    json={"nome": "Tentativa"}
                )
                # Unapproved user should get 403
                assert response.status_code in [403, 429]
        finally:
            db_session.delete(user)
            db_session.commit()
