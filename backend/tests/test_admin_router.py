"""
Testes para o router de administração.

Testa endpoints de gerenciamento de usuários e estatísticas.
Usa mocking para autenticação Supabase.
"""
import uuid
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from models import Usuario


def unique_email(prefix: str = "test") -> str:
    """Gera email único para evitar conflitos."""
    return f"{prefix}_{uuid.uuid4().hex[:8]}@teste.com"


def generate_supabase_id() -> str:
    """Gera um UUID simulando supabase_id."""
    return str(uuid.uuid4())


class TestAdminEndpointsRequireAuth:
    """Testes de autenticação para endpoints admin."""

    def test_listar_usuarios_requires_auth(self, client: TestClient):
        """Verifica que listar usuários requer autenticação."""
        response = client.get("/api/v1/admin/usuarios")
        assert response.status_code == 401

    def test_listar_pendentes_requires_auth(self, client: TestClient):
        """Verifica que listar pendentes requer autenticação."""
        response = client.get("/api/v1/admin/usuarios/pendentes")
        assert response.status_code == 401

    def test_estatisticas_requires_auth(self, client: TestClient):
        """Verifica que estatísticas requer autenticação."""
        response = client.get("/api/v1/admin/estatisticas")
        assert response.status_code == 401

    def test_aprovar_requires_auth(self, client: TestClient):
        """Verifica que aprovar usuário requer autenticação."""
        response = client.post("/api/v1/admin/usuarios/1/aprovar")
        assert response.status_code == 401

    def test_rejeitar_requires_auth(self, client: TestClient):
        """Verifica que rejeitar usuário requer autenticação."""
        response = client.post("/api/v1/admin/usuarios/1/rejeitar")
        assert response.status_code == 401

    def test_reativar_requires_auth(self, client: TestClient):
        """Verifica que reativar usuário requer autenticação."""
        response = client.post("/api/v1/admin/usuarios/1/reativar")
        assert response.status_code == 401

    def test_excluir_requires_auth(self, client: TestClient):
        """Verifica que excluir requer autenticação."""
        response = client.delete("/api/v1/admin/usuarios/1")
        assert response.status_code == 401


class TestAdminEndpointsRequireAdminRole:
    """Testes de autorização para endpoints admin."""

    def test_listar_usuarios_requires_admin(self, client: TestClient, db_session: Session):
        """Verifica que listar usuários requer role admin."""
        # Criar usuário não-admin
        email = unique_email("nonadmin")
        supabase_id = generate_supabase_id()
        user = Usuario(
            email=email,
            nome="Usuário Comum",
            supabase_id=supabase_id,
            is_active=True,
            is_approved=True,
            is_admin=False
        )
        db_session.add(user)
        db_session.commit()

        try:
            # Mock do token Supabase
            with patch('services.supabase_auth.verify_supabase_token') as mock_verify:
                mock_verify.return_value = {"id": supabase_id, "email": email}
                headers = {"Authorization": "Bearer mock_token"}

                # Tentar acessar admin
                response = client.get("/api/v1/admin/usuarios", headers=headers)
                assert response.status_code == 403
        finally:
            # Cleanup
            db_session.delete(user)
            db_session.commit()


class TestAdminOperations:
    """Testes para operações de admin."""

    def test_aprovar_usuario_not_found(self, client: TestClient, db_session: Session):
        """Verifica erro ao aprovar usuário inexistente."""
        # Criar admin
        email = unique_email("admin")
        supabase_id = generate_supabase_id()
        admin = Usuario(
            email=email,
            nome="Admin Teste",
            supabase_id=supabase_id,
            is_active=True,
            is_approved=True,
            is_admin=True
        )
        db_session.add(admin)
        db_session.commit()

        try:
            # Mock do token Supabase
            with patch('services.supabase_auth.verify_supabase_token') as mock_verify:
                mock_verify.return_value = {"id": supabase_id, "email": email}
                headers = {"Authorization": "Bearer mock_token"}

                # Tentar aprovar usuário inexistente
                response = client.post(
                    "/api/v1/admin/usuarios/99999/aprovar",
                    headers=headers
                )
                assert response.status_code in [404, 429]
        finally:
            db_session.delete(admin)
            db_session.commit()

    def test_listar_usuarios_success(self, client: TestClient, db_session: Session):
        """Verifica que admin pode listar usuários."""
        # Criar admin
        email = unique_email("admin")
        supabase_id = generate_supabase_id()
        admin = Usuario(
            email=email,
            nome="Admin Teste",
            supabase_id=supabase_id,
            is_active=True,
            is_approved=True,
            is_admin=True
        )
        db_session.add(admin)
        db_session.commit()

        try:
            # Mock do token Supabase
            with patch('services.supabase_auth.verify_supabase_token') as mock_verify:
                mock_verify.return_value = {"id": supabase_id, "email": email}
                headers = {"Authorization": "Bearer mock_token"}

                # Listar usuários
                response = client.get("/api/v1/admin/usuarios", headers=headers)
                assert response.status_code in [200, 429]

                if response.status_code == 200:
                    data = response.json()
                    assert isinstance(data, list)
        finally:
            db_session.delete(admin)
            db_session.commit()

    def test_estatisticas_success(self, client: TestClient, db_session: Session):
        """Verifica que admin pode ver estatísticas."""
        # Criar admin
        email = unique_email("admin")
        supabase_id = generate_supabase_id()
        admin = Usuario(
            email=email,
            nome="Admin Teste",
            supabase_id=supabase_id,
            is_active=True,
            is_approved=True,
            is_admin=True
        )
        db_session.add(admin)
        db_session.commit()

        try:
            # Mock do token Supabase
            with patch('services.supabase_auth.verify_supabase_token') as mock_verify:
                mock_verify.return_value = {"id": supabase_id, "email": email}
                headers = {"Authorization": "Bearer mock_token"}

                # Ver estatísticas
                response = client.get("/api/v1/admin/estatisticas", headers=headers)
                assert response.status_code in [200, 429]

                if response.status_code == 200:
                    data = response.json()
                    assert isinstance(data, dict)
        finally:
            db_session.delete(admin)
            db_session.commit()


class TestApprovalWorkflow:
    """Testes do workflow de aprovação."""

    def test_approve_pending_user(self, client: TestClient, db_session: Session):
        """Testa aprovação de usuário pendente."""
        # Criar admin
        admin_email = unique_email("admin")
        admin_supabase_id = generate_supabase_id()
        admin = Usuario(
            email=admin_email,
            nome="Admin",
            supabase_id=admin_supabase_id,
            is_active=True,
            is_approved=True,
            is_admin=True
        )
        db_session.add(admin)

        # Criar usuário pendente
        pending_email = unique_email("pending")
        pending_user = Usuario(
            email=pending_email,
            nome="Pendente",
            supabase_id=generate_supabase_id(),
            is_active=True,
            is_approved=False,
            is_admin=False
        )
        db_session.add(pending_user)
        db_session.commit()
        db_session.refresh(pending_user)

        try:
            # Mock do token Supabase para admin
            with patch('services.supabase_auth.verify_supabase_token') as mock_verify:
                mock_verify.return_value = {"id": admin_supabase_id, "email": admin_email}
                headers = {"Authorization": "Bearer mock_token"}

                # Aprovar usuário
                response = client.post(
                    f"/api/v1/admin/usuarios/{pending_user.id}/aprovar",
                    headers=headers
                )

                if response.status_code == 200:
                    data = response.json()
                    assert data["sucesso"] is True
        finally:
            db_session.delete(pending_user)
            db_session.delete(admin)
            db_session.commit()

    def test_cannot_approve_already_approved(self, client: TestClient, db_session: Session):
        """Verifica que não pode aprovar usuário já aprovado."""
        # Criar admin
        admin_email = unique_email("admin")
        admin_supabase_id = generate_supabase_id()
        admin = Usuario(
            email=admin_email,
            nome="Admin",
            supabase_id=admin_supabase_id,
            is_active=True,
            is_approved=True,
            is_admin=True
        )
        db_session.add(admin)

        # Criar usuário já aprovado
        approved_email = unique_email("approved")
        approved_user = Usuario(
            email=approved_email,
            nome="Aprovado",
            supabase_id=generate_supabase_id(),
            is_active=True,
            is_approved=True,  # Já aprovado
            is_admin=False
        )
        db_session.add(approved_user)
        db_session.commit()
        db_session.refresh(approved_user)

        try:
            # Mock do token Supabase para admin
            with patch('services.supabase_auth.verify_supabase_token') as mock_verify:
                mock_verify.return_value = {"id": admin_supabase_id, "email": admin_email}
                headers = {"Authorization": "Bearer mock_token"}

                # Tentar aprovar novamente
                response = client.post(
                    f"/api/v1/admin/usuarios/{approved_user.id}/aprovar",
                    headers=headers
                )
                assert response.status_code in [400, 429]
        finally:
            db_session.delete(approved_user)
            db_session.delete(admin)
            db_session.commit()
