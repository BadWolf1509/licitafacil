"""
Repositório de Jobs de Processamento.

Encapsula toda a lógica de persistência de jobs,
separando as preocupações de armazenamento da lógica de processamento.

Usa SQLAlchemy com PostgreSQL (Supabase).
"""

import os
from datetime import datetime
from typing import List, Optional

from sqlalchemy import text

from database import engine, get_db_session
from logging_config import get_logger
from models import ProcessingJobModel
from services.models import JobStatus, ProcessingJob

logger = get_logger('services.job_repository')


def _now_iso() -> str:
    """Retorna timestamp ISO com timezone local para parsing correto no frontend."""
    return datetime.now().astimezone().isoformat()


class JobRepository:
    """
    Repositório para persistência de jobs de processamento.

    Usa SQLAlchemy com PostgreSQL (Supabase).
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

    def get_pending(self, include_processing: bool = False) -> List[ProcessingJob]:
        """
        Busca jobs pendentes para processamento.

        Em cenários multi-instância, incluir jobs em processamento pode causar
        duplicidade; por isso o padrão é retornar apenas `pending`.

        Returns:
            Lista de jobs pendentes
        """
        statuses = ['pending']
        if include_processing:
            statuses.append('processing')

        with get_db_session() as db:
            models = db.query(ProcessingJobModel).filter(
                ProcessingJobModel.status.in_(statuses)
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
        Remove um job do banco usando conexão direta com AUTOCOMMIT.

        Usa engine.connect() com AUTOCOMMIT para garantir que o DELETE
        persista no Supabase (bypass do Session e transaction pooling).

        Args:
            job_id: ID do job

        Returns:
            True se removido, False se não encontrado
        """
        logger.info(f"Tentando excluir job {job_id} do banco...")

        with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            result = conn.execute(
                text("DELETE FROM processing_jobs WHERE id = :job_id"),
                {"job_id": job_id}
            )
            deleted_count = result.rowcount
            logger.info(f"DELETE executado para job {job_id}: rowcount={deleted_count}")

            # Verificação pós-delete
            verify = conn.execute(
                text("SELECT COUNT(*) FROM processing_jobs WHERE id = :job_id"),
                {"job_id": job_id}
            )
            still_exists = verify.scalar() or 0

            if still_exists > 0:
                logger.error(
                    f"FALHA: Job {job_id} ainda existe após DELETE! "
                    f"rowcount foi {deleted_count} mas registro persiste."
                )
                return False

            if deleted_count > 0:
                logger.info(f"Job {job_id} excluído e verificado com sucesso")
                return True
            else:
                logger.warning(f"Job {job_id} não encontrado para exclusão (rowcount=0)")
                return False

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
                logger.warning(f"update_status: Job {job_id} nao encontrado, ignorando update para {status.value}")
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
                logger.warning(f"update_progress: Job {job_id} nao encontrado, ignorando update de progresso")
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
                logger.warning(f"increment_attempts: Job {job_id} nao encontrado")
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

    def cleanup_orphaned_jobs(self) -> dict:
        """
        Identifica e marca como FAILED jobs cujos arquivos não existem mais.

        Também marca como FAILED jobs stuck em 'processing' (sem worker ativo).

        Returns:
            Dicionário com contagem de jobs limpos por categoria.
        """
        now = _now_iso()
        result = {"orphaned_files": 0, "stuck_processing": 0, "total_cleaned": 0}

        batch_size = 100

        with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            # 1. Jobs pendentes/processando com arquivos ausentes (em lotes)
            offset = 0
            while True:
                active_rows = conn.execute(
                    text(
                        "SELECT id, file_path FROM processing_jobs "
                        "WHERE status IN ('pending', 'processing') "
                        "LIMIT :limit OFFSET :offset"
                    ),
                    {"limit": batch_size, "offset": offset}
                ).fetchall()

                if not active_rows:
                    break

                for row in active_rows:
                    job_id, file_path = row[0], row[1]
                    if not file_path or not os.path.exists(file_path):
                        conn.execute(
                            text(
                                "UPDATE processing_jobs SET status = 'failed', "
                                "completed_at = :now, "
                                "error = :error "
                                "WHERE id = :job_id"
                            ),
                            {
                                "now": now,
                                "error": f"Arquivo não encontrado (cleanup): {file_path}",
                                "job_id": job_id
                            }
                        )
                        result["orphaned_files"] += 1
                        logger.info(f"Job órfão limpo: {job_id}")

                if len(active_rows) < batch_size:
                    break
                offset += batch_size

            # 2. Jobs stuck em 'processing' (sem worker ativo)
            stuck_result = conn.execute(
                text(
                    "UPDATE processing_jobs SET status = 'failed', "
                    "completed_at = :now, "
                    "error = 'Job stuck em processamento (cleanup automático)' "
                    "WHERE status = 'processing'"
                ),
                {"now": now}
            )
            result["stuck_processing"] = stuck_result.rowcount

        result["total_cleaned"] = result["orphaned_files"] + result["stuck_processing"]
        return result

    def delete_by_statuses(self, statuses: List[str]) -> int:
        """
        Remove jobs em determinados status usando conexão direta com AUTOCOMMIT.

        Args:
            statuses: Lista de status para deletar (ex: ['failed', 'cancelled'])

        Returns:
            Número de jobs removidos.
        """
        with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            # Construir placeholders para IN clause
            placeholders = ", ".join(f":s{i}" for i in range(len(statuses)))
            params = {f"s{i}": s for i, s in enumerate(statuses)}

            result = conn.execute(
                text(f"DELETE FROM processing_jobs WHERE status IN ({placeholders})"),
                params
            )
            count = result.rowcount

            logger.info(f"Bulk delete: {count} jobs removidos (statuses={statuses})")
            return count
