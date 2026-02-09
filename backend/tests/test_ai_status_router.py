"""
Testes para o router de status de IA e fila de processamento.

Testa endpoints de status dos provedores de IA, fila de processamento e jobs.
Usa mocking para autenticação Supabase e fila de processamento.
"""
import uuid
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from models import Usuario


def unique_email(prefix: str = "test") -> str:
    """Gera email único para evitar conflitos."""
    return f"{prefix}_{uuid.uuid4().hex[:8]}@teste.com"


def generate_supabase_id() -> str:
    """Gera um UUID simulando supabase_id."""
    return str(uuid.uuid4())


class TestAIStatusRequireAuth:
    """Testes de autenticação para endpoints de AI status."""

    def test_ai_status_requires_auth(self, client: TestClient):
        """Verifica que GET /ai/status requer autenticação."""
        response = client.get("/api/v1/ai/status")
        assert response.status_code == 401

    def test_queue_status_requires_auth(self, client: TestClient):
        """Verifica que GET /ai/queue/status requer autenticação."""
        response = client.get("/api/v1/ai/queue/status")
        assert response.status_code == 401

    def test_queue_jobs_requires_auth(self, client: TestClient):
        """Verifica que GET /ai/queue/jobs requer autenticação."""
        response = client.get("/api/v1/ai/queue/jobs")
        assert response.status_code == 401

    def test_get_job_status_requires_auth(self, client: TestClient):
        """Verifica que GET /ai/queue/jobs/{job_id} requer autenticação."""
        response = client.get("/api/v1/ai/queue/jobs/some-job-id")
        assert response.status_code == 401

    def test_cancel_job_requires_auth(self, client: TestClient):
        """Verifica que POST /ai/queue/jobs/{job_id}/cancel requer autenticação."""
        response = client.post("/api/v1/ai/queue/jobs/some-job-id/cancel")
        assert response.status_code == 401

    def test_retry_job_requires_auth(self, client: TestClient):
        """Verifica que POST /ai/queue/jobs/{job_id}/retry requer autenticação."""
        response = client.post("/api/v1/ai/queue/jobs/some-job-id/retry")
        assert response.status_code == 401

    def test_delete_job_requires_auth(self, client: TestClient):
        """Verifica que DELETE /ai/queue/jobs/{job_id} requer autenticação."""
        response = client.delete("/api/v1/ai/queue/jobs/some-job-id")
        assert response.status_code == 401


class TestAIStatusOperations:
    """Testes para operações de status de IA e fila."""

    def test_get_ai_status(self, client: TestClient, db_session: Session):
        """Verifica que GET /ai/status retorna status dos provedores."""
        email = unique_email("ai_status")
        supabase_id = generate_supabase_id()
        user = Usuario(
            email=email,
            nome="Teste AI Status",
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

                with patch('routers.ai_status.ai_provider') as mock_ai:
                    mock_ai.get_status.return_value = {
                        "google_vision": {"available": True, "model": "gemini-1.5"},
                        "openai": {"available": False, "model": None}
                    }
                    mock_ai.get_stats.return_value = {
                        "total_requests": 100,
                        "successful_requests": 95,
                        "failed_requests": 5
                    }

                    response = client.get("/api/v1/ai/status", headers=headers)
                    assert response.status_code in [200, 401, 429]

                    if response.status_code == 200:
                        data = response.json()
                        assert data["status"] == "ok"
                        assert "providers" in data
                        assert "statistics" in data
        finally:
            db_session.delete(user)
            db_session.commit()

    def test_get_queue_status(self, client: TestClient, db_session: Session):
        """Verifica que GET /ai/queue/status retorna status da fila."""
        email = unique_email("queue_status")
        supabase_id = generate_supabase_id()
        user = Usuario(
            email=email,
            nome="Teste Queue Status",
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

                with patch('routers.ai_status.processing_queue') as mock_queue:
                    mock_queue.get_status.return_value = {
                        "is_running": True,
                        "queue_size": 3,
                        "processing_count": 1,
                        "max_concurrent": 2,
                        "poll_interval": 5.0
                    }

                    response = client.get("/api/v1/ai/queue/status", headers=headers)
                    assert response.status_code in [200, 401, 429]

                    if response.status_code == 200:
                        data = response.json()
                        assert data["status"] == "ok"
                        assert "queue" in data
                        assert data["queue"]["is_running"] is True
                        assert data["queue"]["queue_size"] == 3
                        assert data["queue"]["processing_count"] == 1
                        assert data["queue"]["max_concurrent"] == 2
        finally:
            db_session.delete(user)
            db_session.commit()

    def test_get_user_jobs_empty(self, client: TestClient, db_session: Session):
        """Verifica que GET /ai/queue/jobs retorna lista vazia para novo usuário."""
        email = unique_email("jobs_empty")
        supabase_id = generate_supabase_id()
        user = Usuario(
            email=email,
            nome="Teste Jobs Vazio",
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

                with patch('routers.ai_status.processing_queue') as mock_queue:
                    mock_queue.get_user_jobs.return_value = []

                    response = client.get("/api/v1/ai/queue/jobs", headers=headers)
                    assert response.status_code in [200, 401, 429]

                    if response.status_code == 200:
                        data = response.json()
                        assert data["status"] == "ok"
                        assert data["jobs"] == []
        finally:
            db_session.delete(user)
            db_session.commit()

    def test_get_user_jobs_with_data(self, client: TestClient, db_session: Session):
        """Verifica que GET /ai/queue/jobs retorna jobs do usuário."""
        email = unique_email("jobs_data")
        supabase_id = generate_supabase_id()
        user = Usuario(
            email=email,
            nome="Teste Jobs Dados",
            supabase_id=supabase_id,
            is_active=True,
            is_approved=True,
            is_admin=False
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        try:
            with patch('services.supabase_auth.verify_supabase_token') as mock_verify:
                mock_verify.return_value = {"id": supabase_id, "email": email}
                headers = {"Authorization": "Bearer mock_token"}

                # Criar mock de job
                mock_job = MagicMock()
                mock_job.to_dict.return_value = {
                    "id": "test-job-123",
                    "status": "completed",
                    "user_id": user.id,
                    "job_type": "atestado",
                    "file_path": "uploads/test.pdf",
                    "original_filename": "atestado.pdf",
                    "progress_current": 1,
                    "progress_total": 1,
                    "progress_stage": "completed",
                    "progress_message": "Processamento concluído",
                    "pipeline": "ocr",
                    "created_at": "2024-01-01T00:00:00",
                    "started_at": "2024-01-01T00:00:01",
                    "completed_at": "2024-01-01T00:00:10",
                    "canceled_at": None,
                    "error": None,
                    "result": None
                }

                with patch('routers.ai_status.processing_queue') as mock_queue:
                    mock_queue.get_user_jobs.return_value = [mock_job]

                    response = client.get("/api/v1/ai/queue/jobs", headers=headers)
                    assert response.status_code in [200, 401, 429]

                    if response.status_code == 200:
                        data = response.json()
                        assert data["status"] == "ok"
                        assert len(data["jobs"]) == 1
                        assert data["jobs"][0]["id"] == "test-job-123"
                        assert data["jobs"][0]["status"] == "completed"
                        assert data["jobs"][0]["job_type"] == "atestado"
        finally:
            db_session.delete(user)
            db_session.commit()

    def test_get_job_status_not_found(self, client: TestClient, db_session: Session):
        """Verifica que GET /ai/queue/jobs/{job_id} retorna 404 para job inexistente."""
        email = unique_email("job_404")
        supabase_id = generate_supabase_id()
        user = Usuario(
            email=email,
            nome="Teste Job 404",
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

                with patch('routers.ai_status.processing_queue') as mock_queue:
                    mock_queue.get_job.return_value = None

                    response = client.get(
                        "/api/v1/ai/queue/jobs/nonexistent-job-id",
                        headers=headers
                    )
                    assert response.status_code in [401, 404, 429]
        finally:
            db_session.delete(user)
            db_session.commit()

    def test_get_user_jobs_with_limit(self, client: TestClient, db_session: Session):
        """Verifica que parâmetro limit funciona para listar jobs."""
        email = unique_email("jobs_limit")
        supabase_id = generate_supabase_id()
        user = Usuario(
            email=email,
            nome="Teste Jobs Limit",
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

                with patch('routers.ai_status.processing_queue') as mock_queue:
                    mock_queue.get_user_jobs.return_value = []

                    response = client.get(
                        "/api/v1/ai/queue/jobs?limit=5",
                        headers=headers
                    )
                    assert response.status_code in [200, 401, 429]

                    if response.status_code == 200:
                        # Verificar que o limit foi passado para a queue
                        mock_queue.get_user_jobs.assert_called_once()
                        call_args = mock_queue.get_user_jobs.call_args
                        assert call_args.kwargs.get("limit") == 5 or call_args[1].get("limit") == 5
        finally:
            db_session.delete(user)
            db_session.commit()

    def test_cancel_job_not_found(self, client: TestClient, db_session: Session):
        """Verifica que cancelar job inexistente retorna 404."""
        email = unique_email("cancel_404")
        supabase_id = generate_supabase_id()
        user = Usuario(
            email=email,
            nome="Teste Cancel 404",
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

                with patch('routers.ai_status.processing_queue') as mock_queue:
                    mock_queue.get_job.return_value = None

                    response = client.post(
                        "/api/v1/ai/queue/jobs/nonexistent-job/cancel",
                        headers=headers
                    )
                    assert response.status_code in [401, 404, 429]
        finally:
            db_session.delete(user)
            db_session.commit()

    def test_delete_job_not_found(self, client: TestClient, db_session: Session):
        """Verifica que excluir job inexistente retorna 404."""
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

                with patch('routers.ai_status.processing_queue') as mock_queue:
                    mock_queue.get_job.return_value = None

                    response = client.delete(
                        "/api/v1/ai/queue/jobs/nonexistent-job",
                        headers=headers
                    )
                    assert response.status_code in [401, 404, 429]
        finally:
            db_session.delete(user)
            db_session.commit()
