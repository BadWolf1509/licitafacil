"""
Fila de Processamento Assíncrono para Atestados.
Permite processar documentos em background com suporte a batch.
"""

import asyncio
import json
import os
import sqlite3
from datetime import datetime
from typing import Dict, Any, Optional, List, Callable
from enum import Enum
from dataclasses import dataclass, asdict
from collections import deque
import threading
import traceback


class JobStatus(str, Enum):
    """Status de um job de processamento."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class ProcessingJob:
    """Representa um job de processamento."""
    id: str
    user_id: int
    file_path: str
    job_type: str  # "atestado" ou "edital"
    status: JobStatus = JobStatus.PENDING
    created_at: str = ""
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    attempts: int = 0
    max_attempts: int = 3

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        """Converte para dicionário."""
        return asdict(self)


class ProcessingQueue:
    """
    Fila de processamento assíncrono para documentos.

    Características:
    - Processamento em background
    - Retry automático em caso de falha
    - Callback após conclusão
    - Persistência de jobs (sobrevive a restart)
    """

    def __init__(self, db_path: str = "licitafacil.db"):
        self._queue: deque = deque()
        self._processing: Dict[str, ProcessingJob] = {}
        self._lock = threading.Lock()
        self._db_path = db_path
        self._is_running = False
        self._worker_task = None
        self._callbacks: Dict[str, Callable] = {}

        # Configurações
        self._max_concurrent = int(os.getenv("QUEUE_MAX_CONCURRENT", "3"))
        self._poll_interval = float(os.getenv("QUEUE_POLL_INTERVAL", "1.0"))

        # Inicializar tabela de jobs
        self._init_db()

    def _init_db(self):
        """Cria tabela de jobs se não existir."""
        conn = sqlite3.connect(self._db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS processing_jobs (
                id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                file_path TEXT NOT NULL,
                job_type TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL,
                started_at TEXT,
                completed_at TEXT,
                result TEXT,
                error TEXT,
                attempts INTEGER DEFAULT 0,
                max_attempts INTEGER DEFAULT 3
            )
        """)
        conn.commit()
        conn.close()

    def _save_job(self, job: ProcessingJob):
        """Salva job no banco de dados."""
        conn = sqlite3.connect(self._db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO processing_jobs
            (id, user_id, file_path, job_type, status, created_at, started_at,
             completed_at, result, error, attempts, max_attempts)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            job.id,
            job.user_id,
            job.file_path,
            job.job_type,
            job.status.value if isinstance(job.status, JobStatus) else job.status,
            job.created_at,
            job.started_at,
            job.completed_at,
            json.dumps(job.result) if job.result else None,
            job.error,
            job.attempts,
            job.max_attempts
        ))
        conn.commit()
        conn.close()

    def _load_pending_jobs(self) -> List[ProcessingJob]:
        """Carrega jobs pendentes do banco."""
        conn = sqlite3.connect(self._db_path)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, user_id, file_path, job_type, status, created_at,
                   started_at, completed_at, result, error, attempts, max_attempts
            FROM processing_jobs
            WHERE status IN ('pending', 'processing')
            ORDER BY created_at ASC
        """)
        rows = cursor.fetchall()
        conn.close()

        jobs = []
        for row in rows:
            job = ProcessingJob(
                id=row[0],
                user_id=row[1],
                file_path=row[2],
                job_type=row[3],
                status=JobStatus(row[4]),
                created_at=row[5],
                started_at=row[6],
                completed_at=row[7],
                result=json.loads(row[8]) if row[8] else None,
                error=row[9],
                attempts=row[10],
                max_attempts=row[11]
            )
            jobs.append(job)
        return jobs

    def get_job(self, job_id: str) -> Optional[ProcessingJob]:
        """Busca um job pelo ID."""
        conn = sqlite3.connect(self._db_path)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, user_id, file_path, job_type, status, created_at,
                   started_at, completed_at, result, error, attempts, max_attempts
            FROM processing_jobs
            WHERE id = ?
        """, (job_id,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        return ProcessingJob(
            id=row[0],
            user_id=row[1],
            file_path=row[2],
            job_type=row[3],
            status=JobStatus(row[4]),
            created_at=row[5],
            started_at=row[6],
            completed_at=row[7],
            result=json.loads(row[8]) if row[8] else None,
            error=row[9],
            attempts=row[10],
            max_attempts=row[11]
        )

    def get_user_jobs(self, user_id: int, limit: int = 20) -> List[ProcessingJob]:
        """Busca jobs de um usuário."""
        conn = sqlite3.connect(self._db_path)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, user_id, file_path, job_type, status, created_at,
                   started_at, completed_at, result, error, attempts, max_attempts
            FROM processing_jobs
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT ?
        """, (user_id, limit))
        rows = cursor.fetchall()
        conn.close()

        return [
            ProcessingJob(
                id=row[0],
                user_id=row[1],
                file_path=row[2],
                job_type=row[3],
                status=JobStatus(row[4]),
                created_at=row[5],
                started_at=row[6],
                completed_at=row[7],
                result=json.loads(row[8]) if row[8] else None,
                error=row[9],
                attempts=row[10],
                max_attempts=row[11]
            )
            for row in rows
        ]

    def add_job(
        self,
        job_id: str,
        user_id: int,
        file_path: str,
        job_type: str = "atestado",
        callback: Optional[Callable] = None
    ) -> ProcessingJob:
        """
        Adiciona um job à fila de processamento.

        Args:
            job_id: ID único do job
            user_id: ID do usuário
            file_path: Caminho do arquivo a processar
            job_type: Tipo de job (atestado ou edital)
            callback: Função a chamar após conclusão

        Returns:
            Job criado
        """
        job = ProcessingJob(
            id=job_id,
            user_id=user_id,
            file_path=file_path,
            job_type=job_type
        )

        with self._lock:
            self._queue.append(job)
            if callback:
                self._callbacks[job_id] = callback

        self._save_job(job)
        return job

    async def _process_job(self, job: ProcessingJob) -> ProcessingJob:
        """
        Processa um job individual.

        Args:
            job: Job a processar

        Returns:
            Job atualizado com resultado ou erro
        """
        from .document_processor import DocumentProcessor
        from .ai_provider import ai_provider

        job.status = JobStatus.PROCESSING
        job.started_at = datetime.now().isoformat()
        job.attempts += 1
        self._save_job(job)

        try:
            processor = DocumentProcessor()

            if job.job_type == "atestado":
                # Processar atestado com Vision se disponível
                use_vision = ai_provider.is_configured
                result = processor.process_atestado(job.file_path, use_vision=use_vision)
            else:
                # Processar edital
                result = processor.process_edital(job.file_path)

            job.status = JobStatus.COMPLETED
            job.completed_at = datetime.now().isoformat()
            job.result = result

        except Exception as e:
            error_msg = f"{str(e)}\n{traceback.format_exc()}"

            if job.attempts < job.max_attempts:
                # Retry
                job.status = JobStatus.PENDING
                job.error = f"Tentativa {job.attempts}/{job.max_attempts}: {error_msg}"
            else:
                # Falha definitiva
                job.status = JobStatus.FAILED
                job.completed_at = datetime.now().isoformat()
                job.error = f"Falhou após {job.attempts} tentativas: {error_msg}"

        self._save_job(job)
        return job

    async def _worker(self):
        """Worker que processa jobs da fila."""
        while self._is_running:
            jobs_to_process = []

            with self._lock:
                while len(jobs_to_process) < self._max_concurrent and self._queue:
                    job = self._queue.popleft()
                    jobs_to_process.append(job)
                    self._processing[job.id] = job

            if jobs_to_process:
                # Processar jobs em paralelo
                tasks = [self._process_job(job) for job in jobs_to_process]
                completed_jobs = await asyncio.gather(*tasks, return_exceptions=True)

                for job in completed_jobs:
                    if isinstance(job, ProcessingJob):
                        with self._lock:
                            if job.id in self._processing:
                                del self._processing[job.id]

                            # Re-adicionar à fila se precisa retry
                            if job.status == JobStatus.PENDING:
                                self._queue.append(job)

                            # Executar callback se houver
                            callback = self._callbacks.pop(job.id, None)
                            if callback:
                                try:
                                    callback(job)
                                except Exception as e:
                                    print(f"Erro no callback do job {job.id}: {e}")

            await asyncio.sleep(self._poll_interval)

    async def start(self):
        """Inicia o worker de processamento."""
        if self._is_running:
            return

        self._is_running = True

        # Recarregar jobs pendentes do banco
        pending = self._load_pending_jobs()
        with self._lock:
            for job in pending:
                if job.status == JobStatus.PROCESSING:
                    job.status = JobStatus.PENDING
                self._queue.append(job)

        self._worker_task = asyncio.create_task(self._worker())
        print(f"ProcessingQueue iniciada com {len(pending)} jobs pendentes")

    async def stop(self):
        """Para o worker de processamento."""
        self._is_running = False
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        print("ProcessingQueue parada")

    def get_status(self) -> Dict[str, Any]:
        """Retorna status da fila."""
        with self._lock:
            return {
                "is_running": self._is_running,
                "queue_size": len(self._queue),
                "processing_count": len(self._processing),
                "max_concurrent": self._max_concurrent,
                "poll_interval": self._poll_interval
            }


# Instância singleton
processing_queue = ProcessingQueue()
