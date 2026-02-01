"""
Repositório de Jobs de Processamento.

Encapsula toda a lógica de persistência de jobs,
separando as preocupações de armazenamento da lógica de processamento.

Usa SQLAlchemy para compatibilidade com SQLite e PostgreSQL.
"""

from datetime import datetime
from typing import List, Optional


from database import get_db_session
from models import ProcessingJobModel
from .models import JobStatus, ProcessingJob
from logging_config import get_logger

logger = get_logger('services.job_repository')


def _now_iso() -> str:
    """Retorna timestamp ISO com timezone local para parsing correto no frontend."""
    return datetime.now().astimezone().isoformat()


class JobRepository:
    """
    Repositório para persistência de jobs de processamento.

    Usa SQLAlchemy ORM para compatibilidade com SQLite e PostgreSQL.
    """

    def _model_to_job(self, model: ProcessingJobModel) -> ProcessingJob:
        """Converte modelo SQLAlchemy para dataclass ProcessingJob."""
        return ProcessingJob(
            id=model.id,
            user_id=model.user_id,
            file_path=model.file_path,
            original_filename=model.original_filename,
            job_type=model.job_type,
            status=JobStatus(model.status),
            created_at=model.created_at,
            started_at=model.started_at,
            completed_at=model.completed_at,
            canceled_at=model.canceled_at,
            result=model.result,
            error=model.error,
            attempts=model.attempts or 0,
            max_attempts=model.max_attempts or 3,
            progress_current=model.progress_current or 0,
            progress_total=model.progress_total or 0,
            progress_stage=model.progress_stage,
            progress_message=model.progress_message,
            pipeline=model.pipeline
        )

    def _job_to_model(self, job: ProcessingJob) -> ProcessingJobModel:
        """Converte dataclass ProcessingJob para modelo SQLAlchemy."""
        status_value = job.status.value if isinstance(job.status, JobStatus) else job.status
        return ProcessingJobModel(
            id=job.id,
            user_id=job.user_id,
            file_path=job.file_path,
            original_filename=job.original_filename,
            job_type=job.job_type,
            status=status_value,
            created_at=job.created_at,
            started_at=job.started_at,
            completed_at=job.completed_at,
            canceled_at=job.canceled_at,
            result=job.result,
            error=job.error,
            attempts=job.attempts,
            max_attempts=job.max_attempts,
            progress_current=job.progress_current,
            progress_total=job.progress_total,
            progress_stage=job.progress_stage,
            progress_message=job.progress_message,
            pipeline=job.pipeline
        )

    def save(self, job: ProcessingJob):
        """
        Salva ou atualiza um job no banco.

        Args:
            job: Job a ser salvo
        """
        with get_db_session() as db:
            db_model = self._job_to_model(job)
            db.merge(db_model)
            db.commit()

    def get_by_id(self, job_id: str) -> Optional[ProcessingJob]:
        """
        Busca um job pelo ID.

        Args:
            job_id: ID do job

        Returns:
            ProcessingJob ou None se não encontrado
        """
        with get_db_session() as db:
            model = db.query(ProcessingJobModel).filter(
                ProcessingJobModel.id == job_id
            ).first()
            if not model:
                return None
            return self._model_to_job(model)

    def get_pending(self) -> List[ProcessingJob]:
        """
        Busca jobs pendentes ou em processamento.

        Returns:
            Lista de jobs pendentes
        """
        with get_db_session() as db:
            models = db.query(ProcessingJobModel).filter(
                ProcessingJobModel.status.in_(['pending', 'processing'])
            ).order_by(ProcessingJobModel.created_at.asc()).all()
            return [self._model_to_job(m) for m in models]

    def get_by_user(self, user_id: int, limit: int = 20) -> List[ProcessingJob]:
        """
        Busca jobs de um usuário.

        Args:
            user_id: ID do usuário
            limit: Limite de resultados

        Returns:
            Lista de jobs do usuário
        """
        with get_db_session() as db:
            models = db.query(ProcessingJobModel).filter(
                ProcessingJobModel.user_id == user_id
            ).order_by(
                ProcessingJobModel.created_at.desc()
            ).limit(limit).all()
            return [self._model_to_job(m) for m in models]

    def delete(self, job_id: str) -> bool:
        """
        Remove um job do banco.

        Args:
            job_id: ID do job

        Returns:
            True se removido, False se não encontrado
        """
        with get_db_session() as db:
            result = db.query(ProcessingJobModel).filter(
                ProcessingJobModel.id == job_id
            ).delete()
            db.commit()
            return result > 0

    def update_status(
        self,
        job_id: str,
        status: JobStatus,
        error: Optional[str] = None,
        result: Optional[dict] = None
    ):
        """
        Atualiza o status de um job.

        Args:
            job_id: ID do job
            status: Novo status
            error: Mensagem de erro (opcional)
            result: Resultado (opcional)
        """
        now = _now_iso()

        with get_db_session() as db:
            model = db.query(ProcessingJobModel).filter(
                ProcessingJobModel.id == job_id
            ).first()

            if not model:
                return

            model.status = status.value

            if status == JobStatus.PROCESSING:
                model.started_at = now
            elif status == JobStatus.COMPLETED:
                model.completed_at = now
                model.result = result
            elif status == JobStatus.FAILED:
                model.completed_at = now
                model.error = error
            elif status == JobStatus.CANCELLED:
                model.canceled_at = now

            db.commit()

    def update_progress(
        self,
        job_id: str,
        current: int,
        total: int,
        stage: Optional[str] = None,
        message: Optional[str] = None,
        pipeline: Optional[str] = None
    ):
        """
        Atualiza o progresso de um job.

        Args:
            job_id: ID do job
            current: Progresso atual
            total: Total de passos
            stage: Estágio atual
            message: Mensagem de progresso
            pipeline: Pipeline sendo usado
        """
        with get_db_session() as db:
            model = db.query(ProcessingJobModel).filter(
                ProcessingJobModel.id == job_id
            ).first()

            if not model:
                return

            model.progress_current = current
            model.progress_total = total
            model.progress_stage = stage
            model.progress_message = message
            if pipeline:
                model.pipeline = pipeline

            db.commit()

    def increment_attempts(self, job_id: str) -> int:
        """
        Incrementa o contador de tentativas.

        Args:
            job_id: ID do job

        Returns:
            Novo número de tentativas
        """
        with get_db_session() as db:
            model = db.query(ProcessingJobModel).filter(
                ProcessingJobModel.id == job_id
            ).first()

            if not model:
                return 0

            model.attempts = (model.attempts or 0) + 1
            db.commit()
            return model.attempts

    def get_stats(self) -> dict:
        """
        Retorna estatísticas dos jobs.

        Returns:
            Dicionário com estatísticas
        """
        with get_db_session() as db:
            from sqlalchemy import func

            total = db.query(func.count(ProcessingJobModel.id)).scalar() or 0

            status_counts = db.query(
                ProcessingJobModel.status,
                func.count(ProcessingJobModel.id)
            ).group_by(ProcessingJobModel.status).all()

            counts = {status: count for status, count in status_counts}

            return {
                "total": total,
                "pending": counts.get("pending", 0),
                "processing": counts.get("processing", 0),
                "completed": counts.get("completed", 0),
                "failed": counts.get("failed", 0),
                "cancelled": counts.get("cancelled", 0)
            }
