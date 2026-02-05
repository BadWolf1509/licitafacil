"""
Executor de Jobs de Processamento.

Encapsula a lógica de execução de jobs de processamento de documentos,
separando as responsabilidades de execução da fila de processamento.
"""

import asyncio
import os
import traceback
from datetime import datetime
from typing import Optional, Callable, Dict, Any

from .models import JobStatus, ProcessingJob
from logging_config import get_logger

logger = get_logger('services.job_executor')


def _now_iso() -> str:
    """Retorna timestamp ISO com timezone local para parsing correto no frontend."""
    return datetime.now().astimezone().isoformat()


class JobExecutor:
    """
    Executor de jobs de processamento de documentos.

    Responsável por:
    - Executar processamento de atestados e editais
    - Gerenciar callbacks de progresso
    - Tratar erros e retries
    """

    def __init__(
        self,
        save_job_callback: Callable[[ProcessingJob], None],
        update_progress_callback: Callable[[str, int, int, Optional[str], Optional[str]], None],
        is_cancel_requested_callback: Callable[[str], bool]
    ):
        """
        Inicializa o executor.

        Args:
            save_job_callback: Função para salvar job no repositório
            update_progress_callback: Função para atualizar progresso (job_id, current, total, stage, message)
            is_cancel_requested_callback: Função para verificar se cancelamento foi solicitado
        """
        self._save_job = save_job_callback
        self._update_progress = update_progress_callback
        self._is_cancel_requested = is_cancel_requested_callback

    def _get_document_processor(self):
        """Obtém DocumentProcessor (lazy import)."""
        from .document_processor import DocumentProcessor
        return DocumentProcessor()

    def _get_processing_cancelled_exception(self):
        """Obtém exceção ProcessingCancelled (lazy import)."""
        from .document_processor import ProcessingCancelled
        return ProcessingCancelled

    def _get_ai_provider(self):
        """Obtém ai_provider (lazy import)."""
        from .ai_provider import ai_provider
        return ai_provider

    async def execute(self, job: ProcessingJob) -> ProcessingJob:
        """
        Executa um job de processamento.

        Args:
            job: Job a ser executado

        Returns:
            Job atualizado com resultado ou erro
        """
        # Verificar cancelamento antes de iniciar
        if self._is_cancel_requested(job.id):
            return self._mark_cancelled(job)

        # Verificar se o arquivo existe antes de processar
        if not job.file_path or not os.path.exists(job.file_path):
            logger.warning(f"Arquivo não encontrado para job {job.id}: {job.file_path}")
            job.status = JobStatus.FAILED
            job.completed_at = _now_iso()
            job.error = f"Arquivo não encontrado: {job.file_path}"
            self._save_job(job)
            return job

        # Marcar como em processamento
        job.status = JobStatus.PROCESSING
        job.started_at = _now_iso()
        job.attempts += 1
        job.progress_current = 0
        job.progress_total = 0
        job.progress_stage = "processing"
        job.progress_message = "Iniciando processamento"
        self._save_job(job)

        try:
            result = await self._run_processing(job)

            # Notificar que está salvando resultado
            self._update_progress(job.id, 0, 0, "save", "Salvando resultado")

            job.status = JobStatus.COMPLETED
            job.completed_at = _now_iso()
            job.result = result

        except Exception as e:
            ProcessingCancelled = self._get_processing_cancelled_exception()
            if isinstance(e, ProcessingCancelled):
                return self._mark_cancelled(job)

            error_msg = f"{str(e)}\n{traceback.format_exc()}"
            logger.error(f"Erro no job {job.id}: {error_msg}")

            # FileNotFoundError não é retryável - falhar imediatamente
            is_retryable = not isinstance(e, (FileNotFoundError, PermissionError))

            if is_retryable and job.attempts < job.max_attempts:
                # Retry - manter como pending
                job.status = JobStatus.PENDING
                job.error = f"Tentativa {job.attempts}/{job.max_attempts}: {error_msg}"
            else:
                # Falha definitiva
                job.status = JobStatus.FAILED
                job.completed_at = _now_iso()
                if not is_retryable:
                    job.error = f"Erro não recuperável: {error_msg}"
                else:
                    job.error = f"Falhou após {job.attempts} tentativas: {error_msg}"

        self._save_job(job)
        return job

    async def _run_processing(self, job: ProcessingJob) -> Dict[str, Any]:
        """
        Executa o processamento específico do job.

        Args:
            job: Job a processar

        Returns:
            Resultado do processamento
        """
        processor = self._get_document_processor()
        ai_provider = self._get_ai_provider()

        def progress_callback(current, total, stage=None, message=None):
            self._update_progress(job.id, current, total, stage, message)

        def cancel_check():
            return self._is_cancel_requested(job.id)

        # Executar em thread separada para não bloquear o event loop
        loop = asyncio.get_event_loop()

        if job.job_type == "atestado":
            return await self._process_atestado(
                loop, processor, job, ai_provider, progress_callback, cancel_check
            )
        else:
            return await self._process_edital(
                loop, processor, job, progress_callback, cancel_check
            )

    async def _process_atestado(
        self,
        loop: asyncio.AbstractEventLoop,
        processor,
        job: ProcessingJob,
        ai_provider,
        progress_callback: Callable,
        cancel_check: Callable
    ) -> Dict[str, Any]:
        """
        Processa um atestado.

        Args:
            loop: Event loop
            processor: DocumentProcessor
            job: Job a processar
            ai_provider: Provedor de IA
            progress_callback: Callback de progresso
            cancel_check: Função de verificação de cancelamento

        Returns:
            Resultado do processamento
        """
        use_vision = ai_provider.is_configured

        return await loop.run_in_executor(
            None,
            lambda: processor.process_atestado(
                job.file_path,
                use_vision=use_vision,
                progress_callback=progress_callback,
                cancel_check=cancel_check
            )
        )

    async def _process_edital(
        self,
        loop: asyncio.AbstractEventLoop,
        processor,
        job: ProcessingJob,
        progress_callback: Callable,
        cancel_check: Callable
    ) -> Dict[str, Any]:
        """
        Processa um edital.

        Args:
            loop: Event loop
            processor: DocumentProcessor
            job: Job a processar
            progress_callback: Callback de progresso
            cancel_check: Função de verificação de cancelamento

        Returns:
            Resultado do processamento
        """
        return await loop.run_in_executor(
            None,
            lambda: processor.process_edital(
                job.file_path,
                progress_callback=progress_callback,
                cancel_check=cancel_check
            )
        )

    def _mark_cancelled(self, job: ProcessingJob) -> ProcessingJob:
        """
        Marca um job como cancelado.

        Args:
            job: Job a cancelar

        Returns:
            Job atualizado
        """
        now = _now_iso()
        job.status = JobStatus.CANCELLED
        job.completed_at = now
        job.canceled_at = now
        job.error = "Cancelado pelo usuário"
        self._save_job(job)
        return job
