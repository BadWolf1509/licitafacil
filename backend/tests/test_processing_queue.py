"""
Testes para fila de processamento assincrono.

Testa as funcoes em services/processing_queue.py.

IMPORTANTE: Todos os testes mockam o repositorio para evitar
persistir jobs de teste no banco de dados Supabase.
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from services.processing_queue import ProcessingQueue
from services.models import JobStatus


@pytest.fixture
def mock_repository():
    """Mock do JobRepository para evitar acesso ao banco real."""
    repo = MagicMock()
    repo.save = MagicMock()
    repo.get_by_id = MagicMock(return_value=None)
    repo.get_by_user = MagicMock(return_value=[])
    repo.get_pending = MagicMock(return_value=[])
    repo.delete = MagicMock(return_value=True)
    return repo


@pytest.fixture
def queue(mock_repository):
    """Cria fila com repositorio mockado."""
    q = ProcessingQueue()
    q._repository = mock_repository
    return q


class TestProcessingQueueInit:
    """Testes para inicializacao da fila."""

    def test_queue_starts_empty(self, queue):
        """Fila comeca vazia."""
        assert len(queue._queue) == 0
        assert len(queue._processing) == 0
        assert len(queue._queued_jobs) == 0

    def test_queue_is_not_running_initially(self, queue):
        """Fila nao esta rodando inicialmente."""
        assert queue._is_running is False


class TestAddJob:
    """Testes para adicao de jobs."""

    def test_add_job_creates_pending_job(self, queue):
        """Adicionar job cria com status correto."""
        job = queue.add_job(
            job_id="test-123",
            user_id=1,
            file_path="/tmp/test.pdf",
            job_type="atestado"
        )

        assert job.id == "test-123"
        assert job.user_id == 1
        assert job.file_path == "/tmp/test.pdf"
        assert job.job_type == "atestado"
        assert job.status == JobStatus.PENDING

    def test_add_job_increments_queue_size(self, queue):
        """Adicionar job incrementa tamanho da fila."""
        assert len(queue._queue) == 0

        queue.add_job("job-1", 1, "/tmp/1.pdf")
        assert len(queue._queue) == 1
        assert len(queue._queued_jobs) == 1

        queue.add_job("job-2", 1, "/tmp/2.pdf")
        assert len(queue._queue) == 2
        assert len(queue._queued_jobs) == 2

    def test_add_job_stores_in_index(self, queue):
        """Job adicionado e indexado por ID."""
        queue.add_job("job-xyz", 1, "/tmp/xyz.pdf")

        assert "job-xyz" in queue._queued_jobs
        assert queue._queued_jobs["job-xyz"].id == "job-xyz"

    def test_add_job_with_callback(self, queue):
        """Callback e armazenado."""
        callback = MagicMock()
        queue.add_job("job-cb", 1, "/tmp/cb.pdf", callback=callback)

        assert "job-cb" in queue._callbacks

    def test_add_job_with_original_filename(self, queue):
        """Nome original e armazenado."""
        job = queue.add_job(
            "job-name",
            1,
            "/tmp/processed.pdf",
            original_filename="documento_original.pdf"
        )

        assert job.original_filename == "documento_original.pdf"

    def test_add_job_saves_to_repository(self, queue, mock_repository):
        """Job e salvo no repositorio."""
        queue.add_job("job-save", 1, "/tmp/s.pdf")
        mock_repository.save.assert_called_once()


class TestCancelJob:
    """Testes para cancelamento de jobs."""

    def test_cancel_pending_job(self, queue):
        """Cancelar job pendente funciona."""
        queue.add_job("cancel-me", 1, "/tmp/cancel.pdf")

        job = queue.cancel_job("cancel-me")

        assert job is not None
        assert job.status == JobStatus.CANCELLED
        assert job.canceled_at is not None

    def test_cancel_nonexistent_job(self, queue):
        """Cancelar job inexistente retorna None."""
        result = queue.cancel_job("nao-existe")
        assert result is None

    def test_cancel_already_completed_job(self, queue):
        """Cancelar job ja completo retorna o job sem alterar."""
        queue.add_job("completed-job", 1, "/tmp/c.pdf")
        # Simular que foi completado
        queue._queued_jobs["completed-job"].status = JobStatus.COMPLETED
        queue._save_job(queue._queued_jobs["completed-job"])

        job = queue.cancel_job("completed-job")

        # Job ja completo nao deve mudar status
        assert job is not None
        assert job.status == JobStatus.COMPLETED

    def test_cancel_removes_from_queue(self, queue):
        """Cancelar remove da fila."""
        queue.add_job("to-cancel", 1, "/tmp/tc.pdf")
        assert len(queue._queue) == 1

        queue.cancel_job("to-cancel")

        # Job deve ser removido da fila
        assert "to-cancel" not in queue._queued_jobs


class TestDeleteJob:
    """Testes para exclusao de jobs."""

    def test_delete_job_removes_from_queue(self, queue):
        """Delete remove job da fila."""
        queue.add_job("delete-me", 1, "/tmp/d.pdf")

        queue.delete_job("delete-me")

        assert "delete-me" not in queue._queued_jobs

    def test_delete_removes_callback(self, queue):
        """Delete remove callback associado."""
        callback = MagicMock()
        queue.add_job("job-with-cb", 1, "/tmp/cb.pdf", callback=callback)

        queue.delete_job("job-with-cb")

        assert "job-with-cb" not in queue._callbacks

    def test_delete_calls_repository(self, queue, mock_repository):
        """Delete chama repositorio para remover do banco."""
        queue.add_job("job-del", 1, "/tmp/del.pdf")

        queue.delete_job("job-del")

        mock_repository.delete.assert_called_once_with("job-del")


class TestUpdateJobProgress:
    """Testes para atualizacao de progresso."""

    def test_update_progress_in_queue(self, queue):
        """Atualiza progresso de job na fila."""
        queue.add_job("progress-test", 1, "/tmp/p.pdf")

        queue.update_job_progress("progress-test", current=5, total=10, stage="ocr")

        job = queue._queued_jobs["progress-test"]
        assert job.progress_current == 5
        assert job.progress_total == 10
        assert job.progress_stage == "ocr"

    def test_update_progress_sets_pipeline(self, queue):
        """Atualiza pipeline baseado no stage."""
        queue.add_job("pipeline-test", 1, "/tmp/pl.pdf")

        queue.update_job_progress("pipeline-test", current=1, total=5, stage="texto")

        job = queue._queued_jobs["pipeline-test"]
        assert job.pipeline == "NATIVE_TEXT"

    def test_update_progress_ignored_if_cancelled(self, queue):
        """Progresso ignorado se cancelamento solicitado."""
        queue.add_job("cancel-progress", 1, "/tmp/cp.pdf")
        queue._cancel_requested.add("cancel-progress")

        queue.update_job_progress("cancel-progress", current=5, total=10)

        # Progresso nao deve ser atualizado
        job = queue._queued_jobs["cancel-progress"]
        assert job.progress_current == 0


class TestIsCancelRequested:
    """Testes para verificacao de cancelamento."""

    def test_returns_false_for_normal_job(self, queue):
        """Retorna False para job normal."""
        queue.add_job("normal", 1, "/tmp/n.pdf")

        assert queue.is_cancel_requested("normal") is False

    def test_returns_true_for_cancelled_job(self, queue):
        """Retorna True para job com cancelamento solicitado."""
        queue.add_job("cancelled", 1, "/tmp/c.pdf")
        queue._cancel_requested.add("cancelled")

        assert queue.is_cancel_requested("cancelled") is True


class TestGetStatus:
    """Testes para status da fila."""

    def test_get_status_returns_info(self, queue):
        """Get status retorna informacoes da fila."""
        queue.add_job("job-1", 1, "/tmp/1.pdf")
        queue.add_job("job-2", 1, "/tmp/2.pdf")

        status = queue.get_status()

        assert status["queue_size"] == 2
        assert status["processing_count"] == 0
        assert status["is_running"] is False

    def test_get_status_shows_processing(self, queue):
        """Get status mostra jobs em processamento."""
        job = queue.add_job("processing-job", 1, "/tmp/p.pdf")
        # Simular que esta processando
        queue._queue.popleft()
        queue._queued_jobs.pop(job.id)
        queue._processing[job.id] = job

        status = queue.get_status()

        assert status["queue_size"] == 0
        assert status["processing_count"] == 1


class TestRegisterCallback:
    """Testes para registro de callbacks."""

    def test_register_callback_by_type(self, queue):
        """Registra callback por tipo de job."""
        callback = MagicMock()

        queue.register_callback("atestado", callback)

        assert "atestado" in queue._callbacks_by_type

    def test_callback_used_when_no_explicit_callback(self, queue):
        """Callback registrado e usado quando nenhum explicito."""
        callback = MagicMock()
        queue.register_callback("edital", callback)

        queue.add_job("edital-job", 1, "/tmp/e.pdf", job_type="edital")

        assert "edital-job" in queue._callbacks


class TestStartStop:
    """Testes para iniciar e parar a fila."""

    @pytest.mark.asyncio
    async def test_start_sets_running(self, queue):
        """Iniciar marca fila como rodando."""
        with patch.object(queue, '_worker', new=AsyncMock()):
            await queue.start()

            assert queue._is_running is True

    @pytest.mark.asyncio
    async def test_start_twice_does_nothing(self, queue):
        """Iniciar duas vezes nao cria worker duplicado."""
        with patch.object(queue, '_worker', new=AsyncMock()):
            await queue.start()
            first_task = queue._worker_task

            await queue.start()
            second_task = queue._worker_task

            assert first_task is second_task

    @pytest.mark.asyncio
    async def test_stop_cancels_worker(self, queue):
        """Parar cancela o worker."""
        with patch.object(queue, '_worker', new=AsyncMock()):
            await queue.start()
            await queue.stop()

            assert queue._is_running is False


class TestO1Lookup:
    """Testes para verificar O(1) lookup."""

    def test_queued_jobs_index_provides_o1_lookup(self, queue):
        """Indice _queued_jobs permite O(1) lookup."""
        for i in range(10):
            queue.add_job(f"job-{i}", 1, f"/tmp/{i}.pdf")

        # Lookup direto no indice deve ser O(1)
        assert "job-5" in queue._queued_jobs
        assert queue._queued_jobs["job-5"].id == "job-5"

    def test_update_progress_uses_index(self, queue):
        """Update progress usa indice em vez de linear search."""
        for i in range(5):
            queue.add_job(f"job-{i}", 1, f"/tmp/{i}.pdf")

        # Atualizar progresso do ultimo job deve ser rapido
        queue.update_job_progress("job-4", current=5, total=10)

        job = queue._queued_jobs["job-4"]
        assert job.progress_current == 5


class TestGetJob:
    """Testes para busca de job por ID."""

    def test_get_job_returns_none_for_nonexistent(self, queue):
        """Retorna None para job inexistente."""
        result = queue.get_job("nao-existe")
        assert result is None


class TestGetUserJobs:
    """Testes para busca de jobs por usuario."""

    def test_get_user_jobs_returns_list(self, queue):
        """Retorna lista de jobs do usuario."""
        result = queue.get_user_jobs(user_id=1, limit=10)
        assert isinstance(result, list)
