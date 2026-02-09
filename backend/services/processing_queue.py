"""
Fila de Processamento Assíncrono para Atestados.

Permite processar documentos em background com suporte a batch.
Utiliza JobRepository para persistência, JobExecutor para execução
e models compartilhados.
"""

import asyncio
import os
import threading
from collections import deque
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from config import QUEUE_MAX_CONCURRENT, QUEUE_POLL_INTERVAL
from logging_config import get_logger

from .job_executor import JobExecutor
from .job_repository import JobRepository
from .metrics import record_job_cancelled, record_job_completed, record_job_failed, update_queue_metrics
from .models import JobStatus, ProcessingJob

logger = get_logger('services.processing_queue')


def _now_iso() -> str:
    """Retorna timestamp ISO com timezone local para parsing correto no frontend."""
    return datetime.now().astimezone().isoformat()


class ProcessingQueue:
    """
    Fila de processamento assíncrono para documentos.

    Características:
    - Processamento em background
    - Retry automático em caso de falha
    - Callback após conclusão
    - Persistência de jobs (sobrevive a restart)
    """

    def __init__(self):
        self._queue: deque = deque()
        self._queued_jobs: Dict[str, ProcessingJob] = {}  # Índice para O(1) lookup
        self._processing: Dict[str, ProcessingJob] = {}
        self._lock = threading.Lock()
        self._is_running = False
        self._worker_task = None
        self._callbacks: Dict[str, Callable] = {}
        self._callbacks_by_type: Dict[str, Callable] = {}
        self._cancel_requested: set = set()

        # Configurações (importadas de config.py)
        self._max_concurrent = QUEUE_MAX_CONCURRENT
        self._poll_interval = QUEUE_POLL_INTERVAL

        # Repositório para persistência (usa SQLAlchemy)
        self._repository = JobRepository()

        # Executor para processamento de jobs
        self._executor = JobExecutor(
            save_job_callback=self._save_job,
            update_progress_callback=self.update_job_progress,
            is_cancel_requested_callback=self.is_cancel_requested
        )

    def _save_job(self, job: ProcessingJob):
        """Salva job no banco de dados via repositório."""
        self._repository.save(job)

    def _load_pending_jobs(self) -> List[ProcessingJob]:
        """Carrega jobs pendentes do banco via repositório."""
        return self._repository.get_pending()

    def get_job(self, job_id: str) -> Optional[ProcessingJob]:
        """Busca um job pelo ID (memória primeiro, depois repositório)."""
        with self._lock:
            job = self._queued_jobs.get(job_id) or self._processing.get(job_id)
        if job:
            return job
        return self._repository.get_by_id(job_id)

    def get_user_jobs(self, user_id: int, limit: int = 20) -> List[ProcessingJob]:
        """Busca jobs de um usuário via repositório."""
        return self._repository.get_by_user(user_id, limit)

    def register_callback(self, job_type: str, callback: Callable):
        """Registra callback padrÆo por tipo de job."""
        self._callbacks_by_type[job_type] = callback

    def add_job(
        self,
        job_id: str,
        user_id: int,
        file_path: str,
        job_type: str = "atestado",
        original_filename: Optional[str] = None,
        callback: Optional[Callable] = None
    ) -> ProcessingJob:
        """
        Adiciona um job à fila de processamento.

        Args:
            job_id: ID único do job
            user_id: ID do usuário
            file_path: Caminho do arquivo a processar
            job_type: Tipo de job (atestado ou edital)
            original_filename: Nome original do arquivo enviado pelo usuário
            callback: Função a chamar após conclusão

        Returns:
            Job criado
        """
        job = ProcessingJob(
            id=job_id,
            user_id=user_id,
            file_path=file_path,
            original_filename=original_filename,
            job_type=job_type,
            progress_stage="queued",
            progress_message="Aguardando na fila"
        )

        if callback is None:
            callback = self._callbacks_by_type.get(job_type)

        with self._lock:
            self._queue.append(job)
            self._queued_jobs[job_id] = job  # Adicionar ao índice para O(1) lookup
            if callback:
                self._callbacks[job_id] = callback

        self._save_job(job)
        return job

    # Mapeamento de stage para pipeline
    STAGE_TO_PIPELINE = {
        'texto': 'NATIVE_TEXT',
        'ocr': 'LOCAL_OCR',
        'vision': 'VISION_AI',
    }

    def update_job_progress(
        self,
        job_id: str,
        current: int,
        total: int,
        stage: Optional[str] = None,
        message: Optional[str] = None
    ):
        """Atualiza progresso do job em memória e no banco."""
        if self.is_cancel_requested(job_id):
            return

        # Detecta pipeline baseado no stage
        new_pipeline = self.STAGE_TO_PIPELINE.get(stage) if stage else None

        with self._lock:
            # O(1) lookup em vez de O(n) linear search
            job = self._processing.get(job_id) or self._queued_jobs.get(job_id)
            if job:
                job.progress_current = current
                job.progress_total = total
                job.progress_stage = stage
                job.progress_message = message
                # Atualiza pipeline apenas se detectado um novo (não sobrescreve com None)
                if new_pipeline:
                    job.pipeline = new_pipeline

        # Atualiza no banco via repositório
        self._repository.update_progress(
            job_id, current, total, stage, message, new_pipeline
        )

    def is_cancel_requested(self, job_id: str) -> bool:
        """Verifica se o cancelamento foi solicitado."""
        return job_id in self._cancel_requested

    def cancel_job(self, job_id: str) -> Optional[ProcessingJob]:
        """Solicita cancelamento de um job."""
        job = self.get_job(job_id)
        if not job:
            return None

        if job.status in {JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED}:
            return job

        now = _now_iso()
        job.status = JobStatus.CANCELLED
        job.completed_at = now
        job.canceled_at = now
        job.error = "Cancelado pelo usuario"

        with self._lock:
            self._queue = deque([j for j in self._queue if j.id != job_id])
            self._queued_jobs.pop(job_id, None)  # Remover do índice
            if job_id in self._processing:
                self._cancel_requested.add(job_id)
                self._processing[job_id].status = JobStatus.CANCELLED
            else:
                self._cancel_requested.discard(job_id)

        self._save_job(job)
        return job

    def delete_job(self, job_id: str) -> bool:
        """Remove um job do banco e da fila/memória."""
        with self._lock:
            self._queue = deque([j for j in self._queue if j.id != job_id])
            self._queued_jobs.pop(job_id, None)  # Remover do índice
            self._processing.pop(job_id, None)
            self._cancel_requested.discard(job_id)
            self._callbacks.pop(job_id, None)

        return self._repository.delete(job_id)

    async def _process_job(self, job: ProcessingJob) -> ProcessingJob:
        """
        Processa um job individual delegando ao JobExecutor.

        Args:
            job: Job a processar

        Returns:
            Job atualizado com resultado ou erro
        """
        return await self._executor.execute(job)

    async def _worker(self):
        """Worker que processa jobs da fila."""
        while self._is_running:
            jobs_to_process = []

            with self._lock:
                while len(jobs_to_process) < self._max_concurrent and self._queue:
                    job = self._queue.popleft()
                    self._queued_jobs.pop(job.id, None)  # Remover do índice de fila
                    jobs_to_process.append(job)
                    self._processing[job.id] = job

            if jobs_to_process:
                # Processar jobs em paralelo
                tasks = [self._process_job(job) for job in jobs_to_process]
                completed_jobs = await asyncio.gather(*tasks, return_exceptions=True)

                # Coletar callbacks para executar fora do lock
                callbacks_to_run = []

                for job in completed_jobs:
                    if isinstance(job, ProcessingJob):
                        with self._lock:
                            if job.id in self._processing:
                                del self._processing[job.id]

                            if job.status in {JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED}:
                                self._cancel_requested.discard(job.id)

                            # Registrar metricas por status
                            if job.status == JobStatus.COMPLETED:
                                duration = 0.0
                                if job.started_at and job.completed_at:
                                    try:
                                        from datetime import datetime
                                        start = datetime.fromisoformat(job.started_at)
                                        end = datetime.fromisoformat(job.completed_at)
                                        duration = (end - start).total_seconds()
                                    except Exception:
                                        pass
                                record_job_completed(job.job_type, job.pipeline or 'unknown', duration)
                            elif job.status == JobStatus.FAILED:
                                record_job_failed(job.job_type)
                            elif job.status == JobStatus.CANCELLED:
                                record_job_cancelled(job.job_type)

                            # Re-adicionar à fila se precisa retry
                            if job.status == JobStatus.PENDING:
                                self._queue.append(job)
                                self._queued_jobs[job.id] = job

                            # Coletar callback para executar fora do lock
                            callback = self._callbacks.pop(job.id, None)
                            if callback and job.status == JobStatus.COMPLETED:
                                callbacks_to_run.append((callback, job))

                # Executar callbacks fora do lock, em threads separadas
                for callback, job in callbacks_to_run:
                    try:
                        loop = asyncio.get_event_loop()
                        await loop.run_in_executor(None, callback, job)
                    except Exception as e:
                        logger.error(f"Erro no callback do job {job.id}: {e}")

            await asyncio.sleep(self._poll_interval)

    async def start(self):
        """Inicia o worker de processamento."""
        if self._is_running:
            return

        self._is_running = True

        # Recarregar jobs pendentes do banco
        pending = self._load_pending_jobs()
        valid_count = 0
        orphaned_count = 0

        with self._lock:
            for job in pending:
                # Verificar se o arquivo do job ainda existe
                if not job.file_path or not os.path.exists(job.file_path):
                    # Marcar como falho - arquivo órfão
                    job.status = JobStatus.FAILED
                    job.completed_at = _now_iso()
                    job.error = f"Arquivo não encontrado ao reiniciar: {job.file_path}"
                    self._save_job(job)
                    orphaned_count += 1
                    logger.warning(f"Job órfão marcado como FAILED: {job.id} (arquivo: {job.file_path})")
                    continue

                self._queue.append(job)
                self._queued_jobs[job.id] = job
                valid_count += 1

        self._worker_task = asyncio.create_task(self._worker())
        logger.info(
            f"ProcessingQueue iniciada: {valid_count} jobs válidos, "
            f"{orphaned_count} jobs órfãos marcados como FAILED"
        )

    async def stop(self):
        """Para o worker de processamento."""
        self._is_running = False
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        logger.info("ProcessingQueue parada")

    def get_status(self) -> Dict[str, Any]:
        """Retorna status da fila."""
        with self._lock:
            queue_len = len(self._queue)
            processing_len = len(self._processing)

            # Atualizar metricas Prometheus
            update_queue_metrics(queue_len, processing_len)

            return {
                "is_running": self._is_running,
                "queue_size": queue_len,
                "processing_count": processing_len,
                "max_concurrent": self._max_concurrent,
                "poll_interval": self._poll_interval
            }


# Instância singleton
processing_queue = ProcessingQueue()
