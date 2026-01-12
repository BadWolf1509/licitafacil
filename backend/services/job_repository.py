"""
Repositório de Jobs de Processamento.

Encapsula toda a lógica de persistência de jobs em SQLite,
separando as preocupações de armazenamento da lógica de processamento.
"""

import json
import sqlite3
from typing import List, Optional
from datetime import datetime

from .models import JobStatus, ProcessingJob

from logging_config import get_logger
logger = get_logger('services.job_repository')


class JobRepository:
    """
    Repositório para persistência de jobs de processamento.

    Utiliza SQLite com WAL mode para performance e confiabilidade.
    """

    def __init__(self, db_path: str = "licitafacil.db"):
        """
        Inicializa o repositório.

        Args:
            db_path: Caminho para o arquivo SQLite
        """
        self._db_path = db_path
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Cria conexão SQLite com configurações otimizadas."""
        conn = sqlite3.connect(self._db_path, timeout=30.0, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=30000")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    def _init_db(self):
        """Cria tabela de jobs se não existir."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS processing_jobs (
                id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                file_path TEXT NOT NULL,
                original_filename TEXT,
                job_type TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL,
                started_at TEXT,
                completed_at TEXT,
                canceled_at TEXT,
                result TEXT,
                error TEXT,
                attempts INTEGER DEFAULT 0,
                max_attempts INTEGER DEFAULT 3,
                progress_current INTEGER DEFAULT 0,
                progress_total INTEGER DEFAULT 0,
                progress_stage TEXT,
                progress_message TEXT,
                pipeline TEXT
            )
        """)
        self._ensure_columns(cursor)
        conn.commit()
        conn.close()

    def _ensure_columns(self, cursor: sqlite3.Cursor):
        """Garante que colunas novas existem (compatibilidade com DB antigo)."""
        cursor.execute("PRAGMA table_info(processing_jobs)")
        existing = {row[1] for row in cursor.fetchall()}
        columns = {
            "canceled_at": "TEXT",
            "progress_current": "INTEGER DEFAULT 0",
            "progress_total": "INTEGER DEFAULT 0",
            "progress_stage": "TEXT",
            "progress_message": "TEXT",
            "original_filename": "TEXT",
            "pipeline": "TEXT"
        }
        for name, col_type in columns.items():
            if name not in existing:
                cursor.execute(f"ALTER TABLE processing_jobs ADD COLUMN {name} {col_type}")

    def _row_to_job(self, row: tuple) -> ProcessingJob:
        """Converte linha do banco para objeto ProcessingJob."""
        return ProcessingJob(
            id=row[0],
            user_id=row[1],
            file_path=row[2],
            original_filename=row[3],
            job_type=row[4],
            status=JobStatus(row[5]),
            created_at=row[6],
            started_at=row[7],
            completed_at=row[8],
            canceled_at=row[9],
            result=json.loads(row[10]) if row[10] else None,
            error=row[11],
            attempts=row[12],
            max_attempts=row[13],
            progress_current=row[14] or 0,
            progress_total=row[15] or 0,
            progress_stage=row[16],
            progress_message=row[17],
            pipeline=row[18]
        )

    def save(self, job: ProcessingJob):
        """
        Salva ou atualiza um job no banco.

        Args:
            job: Job a ser salvo
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO processing_jobs
            (id, user_id, file_path, original_filename, job_type, status, created_at,
             started_at, completed_at, canceled_at, result, error, attempts, max_attempts,
             progress_current, progress_total, progress_stage, progress_message, pipeline)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            job.id,
            job.user_id,
            job.file_path,
            job.original_filename,
            job.job_type,
            job.status.value if isinstance(job.status, JobStatus) else job.status,
            job.created_at,
            job.started_at,
            job.completed_at,
            job.canceled_at,
            json.dumps(job.result) if job.result else None,
            job.error,
            job.attempts,
            job.max_attempts,
            job.progress_current,
            job.progress_total,
            job.progress_stage,
            job.progress_message,
            job.pipeline
        ))
        conn.commit()
        conn.close()

    def get_by_id(self, job_id: str) -> Optional[ProcessingJob]:
        """
        Busca um job pelo ID.

        Args:
            job_id: ID do job

        Returns:
            ProcessingJob ou None se não encontrado
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, user_id, file_path, original_filename, job_type, status, created_at,
                   started_at, completed_at, canceled_at, result, error,
                   attempts, max_attempts, progress_current, progress_total,
                   progress_stage, progress_message, pipeline
            FROM processing_jobs
            WHERE id = ?
        """, (job_id,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        return self._row_to_job(row)

    def get_pending(self) -> List[ProcessingJob]:
        """
        Busca jobs pendentes ou em processamento.

        Returns:
            Lista de jobs pendentes
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, user_id, file_path, original_filename, job_type, status, created_at,
                   started_at, completed_at, canceled_at, result, error,
                   attempts, max_attempts, progress_current, progress_total,
                   progress_stage, progress_message, pipeline
            FROM processing_jobs
            WHERE status IN ('pending', 'processing')
            ORDER BY created_at ASC
        """)
        rows = cursor.fetchall()
        conn.close()

        return [self._row_to_job(row) for row in rows]

    def get_by_user(self, user_id: int, limit: int = 20) -> List[ProcessingJob]:
        """
        Busca jobs de um usuário.

        Args:
            user_id: ID do usuário
            limit: Limite de resultados

        Returns:
            Lista de jobs do usuário
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, user_id, file_path, original_filename, job_type, status, created_at,
                   started_at, completed_at, canceled_at, result, error,
                   attempts, max_attempts, progress_current, progress_total,
                   progress_stage, progress_message, pipeline
            FROM processing_jobs
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT ?
        """, (user_id, limit))
        rows = cursor.fetchall()
        conn.close()

        return [self._row_to_job(row) for row in rows]

    def delete(self, job_id: str) -> bool:
        """
        Remove um job do banco.

        Args:
            job_id: ID do job

        Returns:
            True se removido, False se não encontrado
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM processing_jobs WHERE id = ?", (job_id,))
        affected = cursor.rowcount
        conn.commit()
        conn.close()
        return affected > 0

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
        now = datetime.now().isoformat()

        conn = self._get_connection()
        cursor = conn.cursor()

        if status == JobStatus.PROCESSING:
            cursor.execute("""
                UPDATE processing_jobs
                SET status = ?, started_at = ?
                WHERE id = ?
            """, (status.value, now, job_id))
        elif status == JobStatus.COMPLETED:
            cursor.execute("""
                UPDATE processing_jobs
                SET status = ?, completed_at = ?, result = ?
                WHERE id = ?
            """, (status.value, now, json.dumps(result) if result else None, job_id))
        elif status == JobStatus.FAILED:
            cursor.execute("""
                UPDATE processing_jobs
                SET status = ?, completed_at = ?, error = ?
                WHERE id = ?
            """, (status.value, now, error, job_id))
        elif status == JobStatus.CANCELLED:
            cursor.execute("""
                UPDATE processing_jobs
                SET status = ?, canceled_at = ?
                WHERE id = ?
            """, (status.value, now, job_id))
        else:
            cursor.execute("""
                UPDATE processing_jobs
                SET status = ?
                WHERE id = ?
            """, (status.value, job_id))

        conn.commit()
        conn.close()

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
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE processing_jobs
            SET progress_current = ?,
                progress_total = ?,
                progress_stage = ?,
                progress_message = ?,
                pipeline = COALESCE(?, pipeline)
            WHERE id = ?
        """, (current, total, stage, message, pipeline, job_id))
        conn.commit()
        conn.close()

    def increment_attempts(self, job_id: str) -> int:
        """
        Incrementa o contador de tentativas.

        Args:
            job_id: ID do job

        Returns:
            Novo número de tentativas
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE processing_jobs
            SET attempts = attempts + 1
            WHERE id = ?
        """, (job_id,))
        conn.commit()

        cursor.execute("SELECT attempts FROM processing_jobs WHERE id = ?", (job_id,))
        row = cursor.fetchone()
        conn.close()

        return row[0] if row else 0

    def get_stats(self) -> dict:
        """
        Retorna estatísticas dos jobs.

        Returns:
            Dicionário com estatísticas
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT status, COUNT(*) as count
            FROM processing_jobs
            GROUP BY status
        """)
        status_counts = {row[0]: row[1] for row in cursor.fetchall()}

        cursor.execute("SELECT COUNT(*) FROM processing_jobs")
        total = cursor.fetchone()[0]

        conn.close()

        return {
            "total": total,
            "pending": status_counts.get("pending", 0),
            "processing": status_counts.get("processing", 0),
            "completed": status_counts.get("completed", 0),
            "failed": status_counts.get("failed", 0),
            "cancelled": status_counts.get("cancelled", 0)
        }
