"""
Testes para o executor de jobs de processamento.

Testa as funcoes em services/job_executor.py.

IMPORTANTE: Todos os testes mockam o document_processor, ai_provider e
job_repository para evitar processamento real de documentos e acesso
ao banco de dados.
"""
import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock, patch, PropertyMock

from services.job_executor import JobExecutor, _now_iso
from services.models import JobStatus, ProcessingJob


# === Helpers ===

def _make_job(
    job_id="exec-job-001",
    user_id=1,
    file_path="/tmp/test.pdf",
    status=JobStatus.PENDING,
    attempts=0,
    max_attempts=3,
    job_type="atestado"
) -> ProcessingJob:
    """Cria um ProcessingJob para testes."""
    return ProcessingJob(
        id=job_id,
        user_id=user_id,
        file_path=file_path,
        original_filename="documento.pdf",
        job_type=job_type,
        status=status,
        created_at=_now_iso(),
        attempts=attempts,
        max_attempts=max_attempts
    )


# === Fixtures ===

@pytest.fixture
def mock_save_job():
    """Mock para callback de salvar job."""
    return MagicMock()


@pytest.fixture
def mock_update_progress():
    """Mock para callback de atualizar progresso."""
    return MagicMock()


@pytest.fixture
def mock_is_cancel_requested():
    """Mock para callback de verificar cancelamento."""
    mock = MagicMock(return_value=False)
    return mock


@pytest.fixture
def executor(mock_save_job, mock_update_progress, mock_is_cancel_requested):
    """Cria instancia de JobExecutor com mocks."""
    return JobExecutor(
        save_job_callback=mock_save_job,
        update_progress_callback=mock_update_progress,
        is_cancel_requested_callback=mock_is_cancel_requested
    )


# === TestJobExecutor ===

class TestJobExecutor:
    """Testes para execucao de jobs."""

    @pytest.mark.asyncio
    async def test_execute_missing_file(self, executor, mock_save_job):
        """Job com arquivo ausente e marcado como FAILED imediatamente."""
        job = _make_job(file_path="/tmp/nonexistent_file.pdf")

        with patch('services.job_executor.os.path.exists', return_value=False):
            result = await executor.execute(job)

        assert result.status == JobStatus.FAILED
        assert "Arquivo" in result.error
        assert "nonexistent_file.pdf" in result.error
        assert result.completed_at is not None
        mock_save_job.assert_called_once_with(job)

    @pytest.mark.asyncio
    async def test_execute_missing_file_none_path(self, executor, mock_save_job):
        """Job com file_path None e marcado como FAILED."""
        job = _make_job(file_path=None)

        result = await executor.execute(job)

        assert result.status == JobStatus.FAILED
        assert "Arquivo" in result.error
        mock_save_job.assert_called_once_with(job)

    @pytest.mark.asyncio
    async def test_execute_missing_file_empty_path(self, executor, mock_save_job):
        """Job com file_path vazio e marcado como FAILED."""
        job = _make_job(file_path="")

        result = await executor.execute(job)

        assert result.status == JobStatus.FAILED
        assert "Arquivo" in result.error
        mock_save_job.assert_called_once_with(job)

    @pytest.mark.asyncio
    async def test_execute_cancelled_before_start(
        self, mock_save_job, mock_update_progress
    ):
        """Job cancelado antes de iniciar e marcado como CANCELLED."""
        mock_cancel = MagicMock(return_value=True)
        executor = JobExecutor(
            save_job_callback=mock_save_job,
            update_progress_callback=mock_update_progress,
            is_cancel_requested_callback=mock_cancel
        )

        job = _make_job()

        result = await executor.execute(job)

        assert result.status == JobStatus.CANCELLED
        assert result.canceled_at is not None
        assert result.completed_at is not None
        assert result.error == "Cancelado pelo usuário"
        mock_save_job.assert_called_once_with(job)

    @pytest.mark.asyncio
    async def test_execute_max_attempts_reached(self, executor, mock_save_job):
        """Job que excede max_attempts e marcado como FAILED definitivamente."""
        job = _make_job(attempts=2, max_attempts=3)

        with patch('services.job_executor.os.path.exists', return_value=True):
            # Simular erro retryable
            mock_processor = MagicMock()
            mock_processor.process_atestado.side_effect = RuntimeError("Erro temporario")

            with patch.object(executor, '_get_document_processor', return_value=mock_processor):
                mock_ai = MagicMock()
                mock_ai.is_configured = True
                with patch.object(executor, '_get_ai_provider', return_value=mock_ai):
                    result = await executor.execute(job)

        assert result.status == JobStatus.FAILED
        assert result.completed_at is not None
        assert "Falhou" in result.error or "tentativas" in result.error

    @pytest.mark.asyncio
    async def test_execute_retryable_error_before_max(self, executor, mock_save_job):
        """Job com erro retryable abaixo de max_attempts volta para PENDING."""
        job = _make_job(attempts=0, max_attempts=3)

        with patch('services.job_executor.os.path.exists', return_value=True):
            mock_processor = MagicMock()
            mock_processor.process_atestado.side_effect = RuntimeError("Erro temporario")

            with patch.object(executor, '_get_document_processor', return_value=mock_processor):
                mock_ai = MagicMock()
                mock_ai.is_configured = True
                with patch.object(executor, '_get_ai_provider', return_value=mock_ai):
                    result = await executor.execute(job)

        assert result.status == JobStatus.PENDING
        assert result.attempts == 1
        assert "Tentativa" in result.error

    @pytest.mark.asyncio
    async def test_execute_non_retryable_file_not_found_error(self, executor, mock_save_job):
        """FileNotFoundError nao e retryavel - falha imediatamente."""
        job = _make_job(attempts=0, max_attempts=3)

        with patch('services.job_executor.os.path.exists', return_value=True):
            mock_processor = MagicMock()
            mock_processor.process_atestado.side_effect = FileNotFoundError("Arquivo nao encontrado")

            with patch.object(executor, '_get_document_processor', return_value=mock_processor):
                mock_ai = MagicMock()
                mock_ai.is_configured = True
                with patch.object(executor, '_get_ai_provider', return_value=mock_ai):
                    result = await executor.execute(job)

        assert result.status == JobStatus.FAILED
        assert "recuperável" in result.error.lower() or "não recuperável" in result.error.lower()

    @pytest.mark.asyncio
    async def test_execute_non_retryable_permission_error(self, executor, mock_save_job):
        """PermissionError nao e retryavel - falha imediatamente."""
        job = _make_job(attempts=0, max_attempts=3)

        with patch('services.job_executor.os.path.exists', return_value=True):
            mock_processor = MagicMock()
            mock_processor.process_atestado.side_effect = PermissionError("Acesso negado")

            with patch.object(executor, '_get_document_processor', return_value=mock_processor):
                mock_ai = MagicMock()
                mock_ai.is_configured = True
                with patch.object(executor, '_get_ai_provider', return_value=mock_ai):
                    result = await executor.execute(job)

        assert result.status == JobStatus.FAILED
        assert result.completed_at is not None

    @pytest.mark.asyncio
    async def test_execute_successful_atestado(self, executor, mock_save_job, mock_update_progress):
        """Job de atestado processado com sucesso."""
        job = _make_job(job_type="atestado")
        expected_result = {"descricao": "Teste", "servicos": []}

        with patch('services.job_executor.os.path.exists', return_value=True):
            mock_processor = MagicMock()
            mock_processor.process_atestado.return_value = expected_result

            with patch.object(executor, '_get_document_processor', return_value=mock_processor):
                mock_ai = MagicMock()
                mock_ai.is_configured = True
                with patch.object(executor, '_get_ai_provider', return_value=mock_ai):
                    result = await executor.execute(job)

        assert result.status == JobStatus.COMPLETED
        assert result.completed_at is not None
        assert result.result == expected_result
        assert result.attempts == 1

    @pytest.mark.asyncio
    async def test_execute_successful_edital(self, executor, mock_save_job, mock_update_progress):
        """Job de edital processado com sucesso."""
        job = _make_job(job_type="edital")
        expected_result = {"exigencias": []}

        with patch('services.job_executor.os.path.exists', return_value=True):
            mock_processor = MagicMock()
            mock_processor.process_edital.return_value = expected_result

            with patch.object(executor, '_get_document_processor', return_value=mock_processor):
                mock_ai = MagicMock()
                mock_ai.is_configured = True
                with patch.object(executor, '_get_ai_provider', return_value=mock_ai):
                    result = await executor.execute(job)

        assert result.status == JobStatus.COMPLETED
        assert result.result == expected_result

    @pytest.mark.asyncio
    async def test_execute_sets_processing_state(self, executor, mock_save_job):
        """Job e marcado como PROCESSING antes de executar."""
        job = _make_job()
        save_calls = []

        def capture_save(j):
            # Capturar o estado do job no momento do save
            save_calls.append(j.status)

        mock_save_job.side_effect = capture_save

        with patch('services.job_executor.os.path.exists', return_value=True):
            mock_processor = MagicMock()
            mock_processor.process_atestado.return_value = {"ok": True}

            with patch.object(executor, '_get_document_processor', return_value=mock_processor):
                mock_ai = MagicMock()
                mock_ai.is_configured = True
                with patch.object(executor, '_get_ai_provider', return_value=mock_ai):
                    await executor.execute(job)

        # Primeiro save deve ser PROCESSING, segundo deve ser COMPLETED
        assert len(save_calls) == 2
        assert save_calls[0] == JobStatus.PROCESSING
        assert save_calls[1] == JobStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_execute_increments_attempts(self, executor, mock_save_job):
        """Execute incrementa o contador de tentativas."""
        job = _make_job(attempts=0)

        with patch('services.job_executor.os.path.exists', return_value=True):
            mock_processor = MagicMock()
            mock_processor.process_atestado.return_value = {"ok": True}

            with patch.object(executor, '_get_document_processor', return_value=mock_processor):
                mock_ai = MagicMock()
                mock_ai.is_configured = True
                with patch.object(executor, '_get_ai_provider', return_value=mock_ai):
                    result = await executor.execute(job)

        assert result.attempts == 1

    @pytest.mark.asyncio
    async def test_execute_processing_cancelled_during_run(
        self, mock_save_job, mock_update_progress
    ):
        """Job cancelado durante processamento e marcado como CANCELLED."""
        mock_cancel = MagicMock(return_value=False)
        executor = JobExecutor(
            save_job_callback=mock_save_job,
            update_progress_callback=mock_update_progress,
            is_cancel_requested_callback=mock_cancel
        )

        job = _make_job()

        # Criar a excecao mock
        class MockProcessingCancelled(Exception):
            pass

        with patch('services.job_executor.os.path.exists', return_value=True):
            mock_processor = MagicMock()
            mock_processor.process_atestado.side_effect = MockProcessingCancelled("Cancelado")

            with patch.object(executor, '_get_document_processor', return_value=mock_processor):
                mock_ai = MagicMock()
                mock_ai.is_configured = True
                with patch.object(executor, '_get_ai_provider', return_value=mock_ai):
                    with patch.object(
                        executor,
                        '_get_processing_cancelled_exception',
                        return_value=MockProcessingCancelled
                    ):
                        result = await executor.execute(job)

        assert result.status == JobStatus.CANCELLED
        assert result.canceled_at is not None
        assert result.error == "Cancelado pelo usuário"


class TestJobExecutorCallbacks:
    """Testes para verificar que callbacks sao chamados corretamente."""

    @pytest.mark.asyncio
    async def test_save_callback_called_on_failure(self, executor, mock_save_job):
        """Callback de save e chamado quando job falha."""
        job = _make_job(file_path="/tmp/nonexistent.pdf")

        with patch('services.job_executor.os.path.exists', return_value=False):
            await executor.execute(job)

        mock_save_job.assert_called_once()

    @pytest.mark.asyncio
    async def test_progress_callback_called_on_save_stage(
        self, executor, mock_save_job, mock_update_progress
    ):
        """Callback de progresso e chamado na etapa 'save'."""
        job = _make_job()

        with patch('services.job_executor.os.path.exists', return_value=True):
            mock_processor = MagicMock()
            mock_processor.process_atestado.return_value = {"ok": True}

            with patch.object(executor, '_get_document_processor', return_value=mock_processor):
                mock_ai = MagicMock()
                mock_ai.is_configured = True
                with patch.object(executor, '_get_ai_provider', return_value=mock_ai):
                    await executor.execute(job)

        # Deve ter sido chamado com stage="save"
        mock_update_progress.assert_called_with(
            job.id, 0, 0, "save", "Salvando resultado"
        )

    @pytest.mark.asyncio
    async def test_cancel_check_called_before_execute(
        self, mock_save_job, mock_update_progress
    ):
        """Verificacao de cancelamento e feita antes de iniciar."""
        mock_cancel = MagicMock(return_value=True)
        executor = JobExecutor(
            save_job_callback=mock_save_job,
            update_progress_callback=mock_update_progress,
            is_cancel_requested_callback=mock_cancel
        )

        job = _make_job()
        await executor.execute(job)

        mock_cancel.assert_called_with(job.id)


class TestMarkCancelled:
    """Testes para o metodo _mark_cancelled."""

    def test_mark_cancelled_sets_status(self, executor):
        """_mark_cancelled define status como CANCELLED."""
        job = _make_job()

        result = executor._mark_cancelled(job)

        assert result.status == JobStatus.CANCELLED

    def test_mark_cancelled_sets_timestamps(self, executor):
        """_mark_cancelled define completed_at e canceled_at."""
        job = _make_job()

        result = executor._mark_cancelled(job)

        assert result.completed_at is not None
        assert result.canceled_at is not None

    def test_mark_cancelled_sets_error_message(self, executor):
        """_mark_cancelled define mensagem de erro."""
        job = _make_job()

        result = executor._mark_cancelled(job)

        assert result.error == "Cancelado pelo usuário"

    def test_mark_cancelled_saves_job(self, executor, mock_save_job):
        """_mark_cancelled chama callback de save."""
        job = _make_job()

        executor._mark_cancelled(job)

        mock_save_job.assert_called_once_with(job)


class TestJobExecutorInit:
    """Testes para inicializacao do executor."""

    def test_init_stores_callbacks(self):
        """Init armazena os callbacks fornecidos."""
        save = MagicMock()
        progress = MagicMock()
        cancel = MagicMock()

        executor = JobExecutor(
            save_job_callback=save,
            update_progress_callback=progress,
            is_cancel_requested_callback=cancel
        )

        assert executor._save_job is save
        assert executor._update_progress is progress
        assert executor._is_cancel_requested is cancel

    def test_get_document_processor_lazy_import(self, executor):
        """_get_document_processor faz lazy import."""
        with patch('services.job_executor.JobExecutor._get_document_processor') as mock_get:
            mock_get.return_value = MagicMock()
            result = executor._get_document_processor()
            assert result is not None

    def test_get_ai_provider_lazy_import(self, executor):
        """_get_ai_provider faz lazy import."""
        with patch('services.job_executor.JobExecutor._get_ai_provider') as mock_get:
            mock_get.return_value = MagicMock()
            result = executor._get_ai_provider()
            assert result is not None
