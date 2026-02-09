"""
Testes para o repositorio de jobs de processamento.

Testa as funcoes em services/job_repository.py.

IMPORTANTE: Os metodos que usam AUTOCOMMIT (delete, delete_by_statuses,
cleanup_orphaned_jobs) sao testados com mocks do engine, pois usam
conexao direta em vez de Session do SQLAlchemy.

Os metodos que usam get_db_session (save, get_by_id, update_status, etc.)
sao testados com mocks do context manager get_db_session.
"""
from contextlib import contextmanager
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from models import ProcessingJobModel
from repositories.job_repository import JobRepository, _now_iso
from services.models import JobStatus, ProcessingJob

# === Helpers ===

def _make_job(
    job_id="test-job-001",
    user_id=1,
    file_path="/tmp/test.pdf",
    status=JobStatus.PENDING,
    attempts=0,
    max_attempts=3,
    job_type="atestado",
    original_filename="documento.pdf",
    pipeline=None
) -> ProcessingJob:
    """Cria um ProcessingJob para testes."""
    return ProcessingJob(
        id=job_id,
        user_id=user_id,
        file_path=file_path,
        original_filename=original_filename,
        job_type=job_type,
        status=status,
        created_at=_now_iso(),
        attempts=attempts,
        max_attempts=max_attempts,
        pipeline=pipeline
    )


def _make_model(
    job_id="test-job-001",
    user_id=1,
    file_path="/tmp/test.pdf",
    status="pending",
    attempts=0,
    max_attempts=3,
    job_type="atestado",
    original_filename="documento.pdf",
    pipeline=None
) -> ProcessingJobModel:
    """Cria um ProcessingJobModel para testes."""
    model = ProcessingJobModel(
        id=job_id,
        user_id=user_id,
        file_path=file_path,
        original_filename=original_filename,
        job_type=job_type,
        status=status,
        created_at=_now_iso(),
        attempts=attempts,
        max_attempts=max_attempts,
        progress_current=0,
        progress_total=0,
        pipeline=pipeline
    )
    return model


@contextmanager
def _mock_db_session(mock_db):
    """Context manager que simula get_db_session retornando mock_db."""
    yield mock_db


# === Fixtures ===

@pytest.fixture
def repo():
    """Cria instancia de JobRepository."""
    return JobRepository()


@pytest.fixture
def mock_db():
    """Mock da sessao de banco de dados."""
    db = MagicMock()
    return db


@pytest.fixture
def mock_engine():
    """Mock do engine para metodos AUTOCOMMIT."""
    engine = MagicMock()
    mock_conn = MagicMock()
    mock_conn.execution_options.return_value = mock_conn
    # Suportar uso como context manager
    mock_conn.__enter__ = MagicMock(return_value=mock_conn)
    mock_conn.__exit__ = MagicMock(return_value=False)
    engine.connect.return_value = mock_conn
    return engine, mock_conn


# === TestJobRepositorySave ===

class TestJobRepositorySave:
    """Testes para salvar e recuperar jobs no repositorio."""

    @patch('repositories.job_repository.get_db_session')
    def test_save_calls_merge_and_commit(self, mock_get_db, repo):
        """Salvar job chama merge e commit na sessao."""
        mock_db = MagicMock()
        mock_get_db.return_value = _mock_db_session(mock_db)

        job = _make_job()
        repo.save(job)

        mock_db.merge.assert_called_once()
        mock_db.commit.assert_called_once()

    @patch('repositories.job_repository.get_db_session')
    def test_save_converts_job_to_model(self, mock_get_db, repo):
        """Salvar job converte ProcessingJob para ProcessingJobModel."""
        mock_db = MagicMock()
        mock_get_db.return_value = _mock_db_session(mock_db)

        job = _make_job(job_id="save-test-001", user_id=42)
        repo.save(job)

        # Verificar que merge foi chamado com um ProcessingJobModel
        call_args = mock_db.merge.call_args
        saved_model = call_args[0][0]
        assert isinstance(saved_model, ProcessingJobModel)
        assert saved_model.id == "save-test-001"
        assert saved_model.user_id == 42
        assert saved_model.status == "pending"

    @patch('repositories.job_repository.get_db_session')
    def test_save_preserves_all_fields(self, mock_get_db, repo):
        """Salvar preserva todos os campos do job."""
        mock_db = MagicMock()
        mock_get_db.return_value = _mock_db_session(mock_db)

        job = _make_job(
            job_id="full-001",
            user_id=10,
            file_path="/tmp/full.pdf",
            status=JobStatus.PROCESSING,
            attempts=2,
            max_attempts=5,
            job_type="edital",
            original_filename="edital.pdf",
            pipeline="NATIVE_TEXT"
        )
        repo.save(job)

        saved_model = mock_db.merge.call_args[0][0]
        assert saved_model.id == "full-001"
        assert saved_model.user_id == 10
        assert saved_model.file_path == "/tmp/full.pdf"
        assert saved_model.status == "processing"
        assert saved_model.attempts == 2
        assert saved_model.max_attempts == 5
        assert saved_model.job_type == "edital"
        assert saved_model.original_filename == "edital.pdf"
        assert saved_model.pipeline == "NATIVE_TEXT"

    @patch('repositories.job_repository.get_db_session')
    def test_get_by_id_returns_job(self, mock_get_db, repo):
        """get_by_id retorna ProcessingJob quando encontrado."""
        mock_db = MagicMock()
        mock_get_db.return_value = _mock_db_session(mock_db)

        mock_model = _make_model(job_id="found-001", user_id=5)
        mock_db.query.return_value.filter.return_value.first.return_value = mock_model

        result = repo.get_by_id("found-001")

        assert result is not None
        assert isinstance(result, ProcessingJob)
        assert result.id == "found-001"
        assert result.user_id == 5
        assert result.status == JobStatus.PENDING

    @patch('repositories.job_repository.get_db_session')
    def test_get_by_id_returns_none_when_not_found(self, mock_get_db, repo):
        """get_by_id retorna None quando job nao existe."""
        mock_db = MagicMock()
        mock_get_db.return_value = _mock_db_session(mock_db)

        mock_db.query.return_value.filter.return_value.first.return_value = None

        result = repo.get_by_id("inexistente")

        assert result is None


# === TestJobRepositoryUpdate ===

class TestJobRepositoryUpdate:
    """Testes para atualizacao de status e progresso de jobs."""

    @patch('repositories.job_repository.get_db_session')
    def test_update_status_to_processing(self, mock_get_db, repo):
        """Atualizar status para PROCESSING define started_at."""
        mock_db = MagicMock()
        mock_get_db.return_value = _mock_db_session(mock_db)

        mock_model = _make_model(job_id="proc-001")
        mock_db.query.return_value.filter.return_value.first.return_value = mock_model

        repo.update_status("proc-001", JobStatus.PROCESSING)

        assert mock_model.status == "processing"
        assert mock_model.started_at is not None
        mock_db.commit.assert_called_once()

    @patch('repositories.job_repository.get_db_session')
    def test_update_status_to_completed(self, mock_get_db, repo):
        """Atualizar status para COMPLETED define completed_at e result."""
        mock_db = MagicMock()
        mock_get_db.return_value = _mock_db_session(mock_db)

        mock_model = _make_model(job_id="comp-001")
        mock_db.query.return_value.filter.return_value.first.return_value = mock_model

        result_data = {"atestados": [{"descricao": "teste"}]}
        repo.update_status("comp-001", JobStatus.COMPLETED, result=result_data)

        assert mock_model.status == "completed"
        assert mock_model.completed_at is not None
        assert mock_model.result == result_data
        mock_db.commit.assert_called_once()

    @patch('repositories.job_repository.get_db_session')
    def test_update_status_to_failed(self, mock_get_db, repo):
        """Atualizar status para FAILED define completed_at e error."""
        mock_db = MagicMock()
        mock_get_db.return_value = _mock_db_session(mock_db)

        mock_model = _make_model(job_id="fail-001")
        mock_db.query.return_value.filter.return_value.first.return_value = mock_model

        repo.update_status("fail-001", JobStatus.FAILED, error="Arquivo corrompido")

        assert mock_model.status == "failed"
        assert mock_model.completed_at is not None
        assert mock_model.error == "Arquivo corrompido"
        mock_db.commit.assert_called_once()

    @patch('repositories.job_repository.get_db_session')
    def test_update_status_to_cancelled(self, mock_get_db, repo):
        """Atualizar status para CANCELLED define canceled_at."""
        mock_db = MagicMock()
        mock_get_db.return_value = _mock_db_session(mock_db)

        mock_model = _make_model(job_id="cancel-001")
        mock_db.query.return_value.filter.return_value.first.return_value = mock_model

        repo.update_status("cancel-001", JobStatus.CANCELLED)

        assert mock_model.status == "cancelled"
        assert mock_model.canceled_at is not None
        mock_db.commit.assert_called_once()

    @patch('repositories.job_repository.get_db_session')
    def test_update_status_not_found_does_nothing(self, mock_get_db, repo):
        """Atualizar status de job inexistente nao faz nada."""
        mock_db = MagicMock()
        mock_get_db.return_value = _mock_db_session(mock_db)

        mock_db.query.return_value.filter.return_value.first.return_value = None

        repo.update_status("inexistente", JobStatus.PROCESSING)

        mock_db.commit.assert_not_called()

    @patch('repositories.job_repository.get_db_session')
    def test_update_progress(self, mock_get_db, repo):
        """Atualizar progresso define campos corretamente."""
        mock_db = MagicMock()
        mock_get_db.return_value = _mock_db_session(mock_db)

        mock_model = _make_model(job_id="progress-001")
        mock_db.query.return_value.filter.return_value.first.return_value = mock_model

        repo.update_progress(
            "progress-001",
            current=5,
            total=10,
            stage="ocr",
            message="Processando pagina 5 de 10"
        )

        assert mock_model.progress_current == 5
        assert mock_model.progress_total == 10
        assert mock_model.progress_stage == "ocr"
        assert mock_model.progress_message == "Processando pagina 5 de 10"
        mock_db.commit.assert_called_once()

    @patch('repositories.job_repository.get_db_session')
    def test_update_progress_with_pipeline(self, mock_get_db, repo):
        """Atualizar progresso pode definir pipeline."""
        mock_db = MagicMock()
        mock_get_db.return_value = _mock_db_session(mock_db)

        mock_model = _make_model(job_id="pipeline-001")
        mock_db.query.return_value.filter.return_value.first.return_value = mock_model

        repo.update_progress(
            "pipeline-001",
            current=1,
            total=5,
            pipeline="OCR_LOCAL"
        )

        assert mock_model.pipeline == "OCR_LOCAL"
        mock_db.commit.assert_called_once()

    @patch('repositories.job_repository.get_db_session')
    def test_update_progress_not_found_does_nothing(self, mock_get_db, repo):
        """Atualizar progresso de job inexistente nao faz nada."""
        mock_db = MagicMock()
        mock_get_db.return_value = _mock_db_session(mock_db)

        mock_db.query.return_value.filter.return_value.first.return_value = None

        repo.update_progress("inexistente", current=1, total=5)

        mock_db.commit.assert_not_called()

    @patch('repositories.job_repository.get_db_session')
    def test_increment_attempts(self, mock_get_db, repo):
        """Incrementar tentativas incrementa corretamente."""
        mock_db = MagicMock()
        mock_get_db.return_value = _mock_db_session(mock_db)

        mock_model = _make_model(job_id="attempts-001", attempts=1)
        mock_db.query.return_value.filter.return_value.first.return_value = mock_model

        result = repo.increment_attempts("attempts-001")

        assert result == 2
        assert mock_model.attempts == 2
        mock_db.commit.assert_called_once()

    @patch('repositories.job_repository.get_db_session')
    def test_increment_attempts_from_zero(self, mock_get_db, repo):
        """Incrementar tentativas de zero para um."""
        mock_db = MagicMock()
        mock_get_db.return_value = _mock_db_session(mock_db)

        mock_model = _make_model(job_id="attempts-zero", attempts=0)
        mock_db.query.return_value.filter.return_value.first.return_value = mock_model

        result = repo.increment_attempts("attempts-zero")

        assert result == 1
        assert mock_model.attempts == 1

    @patch('repositories.job_repository.get_db_session')
    def test_increment_attempts_from_none(self, mock_get_db, repo):
        """Incrementar tentativas quando attempts e None."""
        mock_db = MagicMock()
        mock_get_db.return_value = _mock_db_session(mock_db)

        mock_model = _make_model(job_id="attempts-none")
        mock_model.attempts = None
        mock_db.query.return_value.filter.return_value.first.return_value = mock_model

        result = repo.increment_attempts("attempts-none")

        assert result == 1
        assert mock_model.attempts == 1

    @patch('repositories.job_repository.get_db_session')
    def test_increment_attempts_not_found(self, mock_get_db, repo):
        """Incrementar tentativas de job inexistente retorna 0."""
        mock_db = MagicMock()
        mock_get_db.return_value = _mock_db_session(mock_db)

        mock_db.query.return_value.filter.return_value.first.return_value = None

        result = repo.increment_attempts("inexistente")

        assert result == 0


# === TestJobRepositoryDelete ===

class TestJobRepositoryDelete:
    """Testes para exclusao de jobs usando AUTOCOMMIT."""

    @patch('repositories.job_repository.engine')
    def test_delete_existing_job(self, mock_engine, repo):
        """Deletar job existente retorna True."""
        mock_conn = MagicMock()
        mock_conn.execution_options.return_value = mock_conn
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_engine.connect.return_value = mock_conn

        # DELETE retorna rowcount=1
        delete_result = MagicMock()
        delete_result.rowcount = 1

        # SELECT COUNT retorna 0 (nao existe mais)
        verify_result = MagicMock()
        verify_result.scalar.return_value = 0

        mock_conn.execute.side_effect = [delete_result, verify_result]

        result = repo.delete("job-to-delete")

        assert result is True
        assert mock_conn.execute.call_count == 2

    @patch('repositories.job_repository.engine')
    def test_delete_nonexistent_job(self, mock_engine, repo):
        """Deletar job inexistente retorna False."""
        mock_conn = MagicMock()
        mock_conn.execution_options.return_value = mock_conn
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_engine.connect.return_value = mock_conn

        # DELETE retorna rowcount=0
        delete_result = MagicMock()
        delete_result.rowcount = 0

        # SELECT COUNT retorna 0
        verify_result = MagicMock()
        verify_result.scalar.return_value = 0

        mock_conn.execute.side_effect = [delete_result, verify_result]

        result = repo.delete("inexistente")

        assert result is False

    @patch('repositories.job_repository.engine')
    def test_delete_fails_if_still_exists(self, mock_engine, repo):
        """Delete retorna False se job ainda existe apos DELETE."""
        mock_conn = MagicMock()
        mock_conn.execution_options.return_value = mock_conn
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_engine.connect.return_value = mock_conn

        # DELETE retorna rowcount=1, mas...
        delete_result = MagicMock()
        delete_result.rowcount = 1

        # ...verificacao mostra que o registro persiste (Supabase Pooler bug)
        verify_result = MagicMock()
        verify_result.scalar.return_value = 1

        mock_conn.execute.side_effect = [delete_result, verify_result]

        result = repo.delete("stubborn-job")

        assert result is False

    @patch('repositories.job_repository.engine')
    def test_delete_uses_autocommit(self, mock_engine, repo):
        """Delete usa execution_options com AUTOCOMMIT."""
        mock_conn = MagicMock()
        mock_conn.execution_options.return_value = mock_conn
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_engine.connect.return_value = mock_conn

        delete_result = MagicMock()
        delete_result.rowcount = 1
        verify_result = MagicMock()
        verify_result.scalar.return_value = 0
        mock_conn.execute.side_effect = [delete_result, verify_result]

        repo.delete("auto-commit-test")

        mock_conn.execution_options.assert_called_once_with(isolation_level="AUTOCOMMIT")

    @patch('repositories.job_repository.engine')
    def test_delete_by_statuses(self, mock_engine, repo):
        """delete_by_statuses remove jobs pelos status informados."""
        mock_conn = MagicMock()
        mock_conn.execution_options.return_value = mock_conn
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_engine.connect.return_value = mock_conn

        delete_result = MagicMock()
        delete_result.rowcount = 5
        mock_conn.execute.return_value = delete_result

        result = repo.delete_by_statuses(["failed", "cancelled"])

        assert result == 5
        mock_conn.execute.assert_called_once()

    @patch('repositories.job_repository.engine')
    def test_delete_by_statuses_single_status(self, mock_engine, repo):
        """delete_by_statuses funciona com status unico."""
        mock_conn = MagicMock()
        mock_conn.execution_options.return_value = mock_conn
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_engine.connect.return_value = mock_conn

        delete_result = MagicMock()
        delete_result.rowcount = 3
        mock_conn.execute.return_value = delete_result

        result = repo.delete_by_statuses(["failed"])

        assert result == 3

    @patch('repositories.job_repository.engine')
    def test_delete_by_statuses_none_found(self, mock_engine, repo):
        """delete_by_statuses retorna 0 quando nenhum job encontrado."""
        mock_conn = MagicMock()
        mock_conn.execution_options.return_value = mock_conn
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_engine.connect.return_value = mock_conn

        delete_result = MagicMock()
        delete_result.rowcount = 0
        mock_conn.execute.return_value = delete_result

        result = repo.delete_by_statuses(["failed", "cancelled"])

        assert result == 0

    @patch('repositories.job_repository.engine')
    def test_delete_by_statuses_uses_autocommit(self, mock_engine, repo):
        """delete_by_statuses usa AUTOCOMMIT."""
        mock_conn = MagicMock()
        mock_conn.execution_options.return_value = mock_conn
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_engine.connect.return_value = mock_conn

        delete_result = MagicMock()
        delete_result.rowcount = 0
        mock_conn.execute.return_value = delete_result

        repo.delete_by_statuses(["failed"])

        mock_conn.execution_options.assert_called_once_with(isolation_level="AUTOCOMMIT")


# === TestJobRepositoryQuery ===

class TestJobRepositoryQuery:
    """Testes para consultas de jobs."""

    @patch('repositories.job_repository.get_db_session')
    def test_get_by_user(self, mock_get_db, repo):
        """get_by_user retorna lista de jobs do usuario."""
        mock_db = MagicMock()
        mock_get_db.return_value = _mock_db_session(mock_db)

        models = [
            _make_model(job_id="user-job-1", user_id=42),
            _make_model(job_id="user-job-2", user_id=42),
        ]
        mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = models

        results = repo.get_by_user(42)

        assert len(results) == 2
        assert all(isinstance(j, ProcessingJob) for j in results)
        assert results[0].id == "user-job-1"
        assert results[1].id == "user-job-2"

    @patch('repositories.job_repository.get_db_session')
    def test_get_by_user_empty(self, mock_get_db, repo):
        """get_by_user retorna lista vazia quando usuario nao tem jobs."""
        mock_db = MagicMock()
        mock_get_db.return_value = _mock_db_session(mock_db)

        mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []

        results = repo.get_by_user(999)

        assert results == []

    @patch('repositories.job_repository.get_db_session')
    def test_get_by_user_with_custom_limit(self, mock_get_db, repo):
        """get_by_user aceita limite personalizado."""
        mock_db = MagicMock()
        mock_get_db.return_value = _mock_db_session(mock_db)

        mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []

        repo.get_by_user(1, limit=5)

        # Verificar que limit foi chamado (a chain de calls)
        mock_db.query.return_value.filter.return_value.order_by.return_value.limit.assert_called_once_with(5)

    @patch('repositories.job_repository.get_db_session')
    def test_get_pending(self, mock_get_db, repo):
        """get_pending retorna jobs pendentes por padrão."""
        mock_db = MagicMock()
        mock_get_db.return_value = _mock_db_session(mock_db)

        models = [
            _make_model(job_id="pending-1", status="pending"),
        ]
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = models

        results = repo.get_pending()

        assert len(results) == 1
        assert results[0].status == JobStatus.PENDING

    @patch('repositories.job_repository.get_db_session')
    def test_get_pending_can_include_processing(self, mock_get_db, repo):
        """get_pending pode incluir jobs em processamento quando solicitado."""
        mock_db = MagicMock()
        mock_get_db.return_value = _mock_db_session(mock_db)

        models = [
            _make_model(job_id="pending-1", status="pending"),
            _make_model(job_id="processing-1", status="processing"),
        ]
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = models

        results = repo.get_pending(include_processing=True)

        assert len(results) == 2
        assert results[0].status == JobStatus.PENDING
        assert results[1].status == JobStatus.PROCESSING

    @patch('repositories.job_repository.get_db_session')
    def test_get_pending_empty(self, mock_get_db, repo):
        """get_pending retorna lista vazia quando nao ha jobs pendentes."""
        mock_db = MagicMock()
        mock_get_db.return_value = _mock_db_session(mock_db)

        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []

        results = repo.get_pending()

        assert results == []

    @patch('repositories.job_repository.get_db_session')
    def test_get_stats(self, mock_get_db, repo):
        """get_stats retorna estatisticas corretas."""
        mock_db = MagicMock()
        mock_get_db.return_value = _mock_db_session(mock_db)

        # Mock total count
        mock_db.query.return_value.scalar.return_value = 10

        # Mock group by results
        mock_db.query.return_value.group_by.return_value.all.return_value = [
            ("pending", 3),
            ("processing", 2),
            ("completed", 4),
            ("failed", 1),
        ]

        stats = repo.get_stats()

        assert stats["total"] == 10
        assert stats["pending"] == 3
        assert stats["processing"] == 2
        assert stats["completed"] == 4
        assert stats["failed"] == 1
        assert stats["cancelled"] == 0  # Nao presente nos dados, default 0

    @patch('repositories.job_repository.get_db_session')
    def test_get_stats_empty_database(self, mock_get_db, repo):
        """get_stats retorna zeros quando banco esta vazio."""
        mock_db = MagicMock()
        mock_get_db.return_value = _mock_db_session(mock_db)

        mock_db.query.return_value.scalar.return_value = 0
        mock_db.query.return_value.group_by.return_value.all.return_value = []

        stats = repo.get_stats()

        assert stats["total"] == 0
        assert stats["pending"] == 0
        assert stats["processing"] == 0
        assert stats["completed"] == 0
        assert stats["failed"] == 0
        assert stats["cancelled"] == 0


# === TestJobRepositoryCleanup ===

class TestJobRepositoryCleanup:
    """Testes para limpeza de jobs orfaos."""

    @patch('repositories.job_repository.os.path.exists')
    @patch('repositories.job_repository.engine')
    def test_cleanup_orphaned_files(self, mock_engine, mock_exists, repo):
        """cleanup_orphaned_jobs marca jobs sem arquivo como FAILED."""
        mock_conn = MagicMock()
        mock_conn.execution_options.return_value = mock_conn
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_engine.connect.return_value = mock_conn

        # Jobs ativos com arquivos ausentes
        active_rows = [
            ("orphan-001", "/tmp/missing1.pdf"),
            ("orphan-002", "/tmp/missing2.pdf"),
        ]
        # Nenhum job stuck em processing apos update dos orfaos
        stuck_result = MagicMock()
        stuck_result.rowcount = 0

        mock_conn.execute.side_effect = [
            MagicMock(fetchall=MagicMock(return_value=active_rows)),  # SELECT active jobs
            MagicMock(),  # UPDATE orphan-001
            MagicMock(),  # UPDATE orphan-002
            stuck_result,  # UPDATE stuck processing
        ]

        # Nenhum arquivo existe
        mock_exists.return_value = False

        result = repo.cleanup_orphaned_jobs()

        assert result["orphaned_files"] == 2
        assert result["stuck_processing"] == 0
        assert result["total_cleaned"] == 2

    @patch('repositories.job_repository.os.path.exists')
    @patch('repositories.job_repository.engine')
    def test_cleanup_stuck_processing(self, mock_engine, mock_exists, repo):
        """cleanup_orphaned_jobs marca jobs stuck em processing como FAILED."""
        mock_conn = MagicMock()
        mock_conn.execution_options.return_value = mock_conn
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_engine.connect.return_value = mock_conn

        # Nenhum job com arquivo ausente
        stuck_result = MagicMock()
        stuck_result.rowcount = 3

        mock_conn.execute.side_effect = [
            MagicMock(fetchall=MagicMock(return_value=[])),  # SELECT active jobs (nenhum)
            stuck_result,  # UPDATE stuck processing
        ]

        result = repo.cleanup_orphaned_jobs()

        assert result["orphaned_files"] == 0
        assert result["stuck_processing"] == 3
        assert result["total_cleaned"] == 3

    @patch('repositories.job_repository.os.path.exists')
    @patch('repositories.job_repository.engine')
    def test_cleanup_mixed(self, mock_engine, mock_exists, repo):
        """cleanup_orphaned_jobs limpa orfaos e stuck simultaneamente."""
        mock_conn = MagicMock()
        mock_conn.execution_options.return_value = mock_conn
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_engine.connect.return_value = mock_conn

        # Um job orfao
        active_rows = [
            ("orphan-001", "/tmp/missing.pdf"),
            ("valid-001", "/tmp/exists.pdf"),
        ]
        stuck_result = MagicMock()
        stuck_result.rowcount = 2

        mock_conn.execute.side_effect = [
            MagicMock(fetchall=MagicMock(return_value=active_rows)),  # SELECT
            MagicMock(),  # UPDATE orphan-001 (arquivo nao existe)
            stuck_result,  # UPDATE stuck processing
        ]

        # Simular: primeiro arquivo nao existe, segundo existe
        mock_exists.side_effect = [False, True]

        result = repo.cleanup_orphaned_jobs()

        assert result["orphaned_files"] == 1
        assert result["stuck_processing"] == 2
        assert result["total_cleaned"] == 3

    @patch('repositories.job_repository.os.path.exists')
    @patch('repositories.job_repository.engine')
    def test_cleanup_nothing_to_clean(self, mock_engine, mock_exists, repo):
        """cleanup_orphaned_jobs retorna zeros quando nao ha nada para limpar."""
        mock_conn = MagicMock()
        mock_conn.execution_options.return_value = mock_conn
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_engine.connect.return_value = mock_conn

        stuck_result = MagicMock()
        stuck_result.rowcount = 0

        mock_conn.execute.side_effect = [
            MagicMock(fetchall=MagicMock(return_value=[])),  # Nenhum job ativo
            stuck_result,  # Nenhum stuck
        ]

        result = repo.cleanup_orphaned_jobs()

        assert result["orphaned_files"] == 0
        assert result["stuck_processing"] == 0
        assert result["total_cleaned"] == 0

    @patch('repositories.job_repository.os.path.exists')
    @patch('repositories.job_repository.engine')
    def test_cleanup_null_file_path(self, mock_engine, mock_exists, repo):
        """cleanup_orphaned_jobs trata file_path None como orfao."""
        mock_conn = MagicMock()
        mock_conn.execution_options.return_value = mock_conn
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_engine.connect.return_value = mock_conn

        # Job com file_path None
        active_rows = [
            ("null-path-001", None),
        ]
        stuck_result = MagicMock()
        stuck_result.rowcount = 0

        mock_conn.execute.side_effect = [
            MagicMock(fetchall=MagicMock(return_value=active_rows)),  # SELECT
            MagicMock(),  # UPDATE null-path-001
            stuck_result,  # UPDATE stuck
        ]

        result = repo.cleanup_orphaned_jobs()

        assert result["orphaned_files"] == 1

    @patch('repositories.job_repository.engine')
    def test_cleanup_uses_autocommit(self, mock_engine, repo):
        """cleanup_orphaned_jobs usa AUTOCOMMIT."""
        mock_conn = MagicMock()
        mock_conn.execution_options.return_value = mock_conn
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_engine.connect.return_value = mock_conn

        stuck_result = MagicMock()
        stuck_result.rowcount = 0

        mock_conn.execute.side_effect = [
            MagicMock(fetchall=MagicMock(return_value=[])),
            stuck_result,
        ]

        repo.cleanup_orphaned_jobs()

        mock_conn.execution_options.assert_called_once_with(isolation_level="AUTOCOMMIT")


# === TestModelConversion ===

class TestModelConversion:
    """Testes para conversao entre ProcessingJob e ProcessingJobModel."""

    def test_model_to_job_conversion(self, repo):
        """Converte ProcessingJobModel para ProcessingJob corretamente."""
        model = _make_model(
            job_id="conv-001",
            user_id=7,
            file_path="/tmp/conv.pdf",
            status="completed",
            attempts=2,
            max_attempts=3,
            job_type="edital",
            original_filename="edital_orig.pdf",
            pipeline="VISION_AI"
        )

        job = repo._model_to_job(model)

        assert isinstance(job, ProcessingJob)
        assert job.id == "conv-001"
        assert job.user_id == 7
        assert job.file_path == "/tmp/conv.pdf"
        assert job.status == JobStatus.COMPLETED
        assert job.attempts == 2
        assert job.max_attempts == 3
        assert job.job_type == "edital"
        assert job.original_filename == "edital_orig.pdf"
        assert job.pipeline == "VISION_AI"

    def test_job_to_model_conversion(self, repo):
        """Converte ProcessingJob para ProcessingJobModel corretamente."""
        job = _make_job(
            job_id="conv-002",
            user_id=8,
            file_path="/tmp/conv2.pdf",
            status=JobStatus.FAILED,
            attempts=3,
            max_attempts=3,
            job_type="atestado",
            original_filename="atestado_orig.pdf",
            pipeline="OCR_LOCAL"
        )

        model = repo._job_to_model(job)

        assert isinstance(model, ProcessingJobModel)
        assert model.id == "conv-002"
        assert model.user_id == 8
        assert model.file_path == "/tmp/conv2.pdf"
        assert model.status == "failed"
        assert model.attempts == 3
        assert model.max_attempts == 3
        assert model.job_type == "atestado"
        assert model.original_filename == "atestado_orig.pdf"
        assert model.pipeline == "OCR_LOCAL"

    def test_model_to_job_handles_none_attempts(self, repo):
        """Conversao trata attempts None como 0."""
        model = _make_model(job_id="none-attempts")
        model.attempts = None
        model.max_attempts = None

        job = repo._model_to_job(model)

        assert job.attempts == 0
        assert job.max_attempts == 3  # default

    def test_model_to_job_handles_none_progress(self, repo):
        """Conversao trata progress None como 0."""
        model = _make_model(job_id="none-progress")
        model.progress_current = None
        model.progress_total = None

        job = repo._model_to_job(model)

        assert job.progress_current == 0
        assert job.progress_total == 0


# === TestNowIso ===

class TestNowIso:
    """Testes para funcao _now_iso."""

    def test_now_iso_returns_string(self):
        """_now_iso retorna string."""
        result = _now_iso()
        assert isinstance(result, str)

    def test_now_iso_is_parseable(self):
        """_now_iso retorna timestamp ISO parseavel."""
        result = _now_iso()
        # Deve ser parseavel pelo datetime
        parsed = datetime.fromisoformat(result)
        assert parsed is not None

    def test_now_iso_has_timezone(self):
        """_now_iso inclui informacao de timezone."""
        result = _now_iso()
        # ISO format com timezone tem + ou - no final
        assert "+" in result or "-" in result[10:]  # Apos a data
