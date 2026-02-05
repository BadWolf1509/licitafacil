"""
Rotas para gerenciamento e status dos provedores de IA.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import Optional
import os
import uuid

from auth import get_current_active_user
from models import Usuario
from services.ai_provider import ai_provider
from services.processing_queue import processing_queue, JobStatus, ProcessingJob
from config import Messages
from logging_config import get_logger, log_action
from schemas import (
    AIStatusResponse,
    QueueStatusResponse,
    QueueInfoResponse,
    UserJobsResponse,
    JobStatusResponse,
    JobCancelResponse,
    JobDeleteResponse,
    ProcessingJobDetail,
)

logger = get_logger('routers.ai_status')

router = APIRouter(prefix="/ai", tags=["ai"])


def _get_job_with_permission(
    job_id: str,
    user: Usuario,
    allowed_statuses: Optional[set] = None,
    disallowed_statuses: Optional[set] = None
) -> ProcessingJob:
    """
    Busca um job e verifica permissão de acesso.

    Args:
        job_id: ID do job
        user: Usuário atual
        allowed_statuses: Se fornecido, job deve estar em um desses status
        disallowed_statuses: Se fornecido, job NÃO pode estar nesses status

    Returns:
        ProcessingJob se encontrado e permitido

    Raises:
        HTTPException: Se job não encontrado ou acesso negado
    """
    job = processing_queue.get_job(job_id)

    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=Messages.JOB_NOT_FOUND)

    if job.user_id != user.id and not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=Messages.ACCESS_DENIED)

    if allowed_statuses and job.status not in allowed_statuses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Job não pode ser processado no status atual: {job.status.value}"
        )

    if disallowed_statuses and job.status in disallowed_statuses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Operação não permitida para jobs com status: {job.status.value}"
        )

    return job


def _job_to_detail(job: ProcessingJob) -> ProcessingJobDetail:
    """Converte ProcessingJob para ProcessingJobDetail."""
    job_dict = job.to_dict()
    return ProcessingJobDetail(**job_dict)


@router.get(
    "/status",
    response_model=AIStatusResponse,
    summary="Status dos provedores de IA",
    responses={
        200: {"description": "Status retornado com sucesso"},
        401: {"description": "Não autenticado"},
    }
)
async def get_ai_status(
    current_user: Usuario = Depends(get_current_active_user)
) -> AIStatusResponse:
    """
    Retorna o status dos provedores de IA configurados.

    **Inclui:**
    - Status de cada provedor (Google Vision, OpenAI, etc.)
    - Estatísticas de uso (requisições, erros, latência média)
    - Disponibilidade dos serviços de OCR e visão
    """
    return AIStatusResponse(
        status="ok",
        providers=ai_provider.get_status(),
        statistics=ai_provider.get_stats()
    )


@router.get(
    "/queue/status",
    response_model=QueueStatusResponse,
    summary="Status da fila de processamento",
    responses={
        200: {"description": "Status da fila retornado"},
        401: {"description": "Não autenticado"},
    }
)
async def get_queue_status(
    current_user: Usuario = Depends(get_current_active_user)
) -> QueueStatusResponse:
    """
    Retorna o status da fila de processamento de documentos.

    **Informações retornadas:**
    - `queue_size`: Número de jobs aguardando processamento
    - `processing_count`: Número de jobs sendo processados
    - `is_running`: Se o worker está ativo
    - `max_concurrent`: Limite de processamento paralelo
    """
    queue_info = processing_queue.get_status()
    return QueueStatusResponse(
        status="ok",
        queue=QueueInfoResponse(**queue_info)
    )


@router.get(
    "/queue/jobs",
    response_model=UserJobsResponse,
    summary="Listar jobs do usuário",
    responses={
        200: {"description": "Lista de jobs retornada"},
        401: {"description": "Não autenticado"},
    }
)
async def get_user_jobs(
    limit: int = 20,
    current_user: Usuario = Depends(get_current_active_user)
) -> UserJobsResponse:
    """
    Retorna os jobs de processamento do usuário atual.

    Ordenados do mais recente para o mais antigo.
    Use para acompanhar o histórico de processamentos.

    **Parâmetros:**
    - `limit`: Número máximo de jobs a retornar (padrão: 20)
    """
    jobs = processing_queue.get_user_jobs(current_user.id, limit=limit)
    return UserJobsResponse(
        status="ok",
        jobs=[_job_to_detail(job) for job in jobs]
    )


@router.get(
    "/queue/jobs/{job_id}",
    response_model=JobStatusResponse,
    summary="Obter status de um job",
    responses={
        200: {"description": "Status do job retornado"},
        401: {"description": "Não autenticado"},
        403: {"description": "Acesso negado ao job"},
        404: {"description": "Job não encontrado"},
    }
)
async def get_job_status(
    job_id: str,
    current_user: Usuario = Depends(get_current_active_user)
) -> JobStatusResponse:
    """
    Retorna o status detalhado de um job específico.

    **Informações retornadas:**
    - Status atual (pending, processing, completed, failed, cancelled)
    - Progresso (current/total páginas, etapa atual)
    - Timestamps (criação, início, conclusão)
    - Erro (se falhou)
    """
    job = _get_job_with_permission(job_id, current_user)
    return JobStatusResponse(
        status="ok",
        job=_job_to_detail(job)
    )


@router.post(
    "/queue/jobs/{job_id}/cancel",
    response_model=JobCancelResponse,
    summary="Cancelar um job",
    responses={
        200: {"description": "Job cancelado com sucesso"},
        400: {"description": "Job já finalizado (não pode ser cancelado)"},
        401: {"description": "Não autenticado"},
        403: {"description": "Acesso negado ao job"},
        404: {"description": "Job não encontrado"},
    }
)
async def cancel_job(
    job_id: str,
    current_user: Usuario = Depends(get_current_active_user)
) -> JobCancelResponse:
    """
    Cancela um job pendente ou em processamento.

    Jobs já finalizados (completed, failed, cancelled) não podem ser cancelados.
    O cancelamento de jobs em processamento pode não ser imediato.
    """
    _get_job_with_permission(
        job_id,
        current_user,
        disallowed_statuses={JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED}
    )
    updated = processing_queue.cancel_job(job_id)

    log_action(
        logger, "job_cancelled",
        user_id=current_user.id,
        resource_type="job",
        job_id=job_id,
    )

    return JobCancelResponse(
        status="ok",
        message="Job cancelado com sucesso",
        job=_job_to_detail(updated) if updated else None
    )


@router.post(
    "/queue/jobs/{job_id}/retry",
    response_model=JobStatusResponse,
    summary="Reprocessar um job",
    responses={
        200: {"description": "Job reenviado para processamento"},
        400: {"description": "Job em status inválido ou arquivo não encontrado"},
        401: {"description": "Não autenticado"},
        403: {"description": "Acesso negado ao job"},
        404: {"description": "Job não encontrado"},
    }
)
async def retry_job(
    job_id: str,
    current_user: Usuario = Depends(get_current_active_user)
) -> JobStatusResponse:
    """
    Reenvia um job falhado ou cancelado para processamento.

    Cria um novo job com os mesmos dados do original.
    Apenas jobs com status FAILED ou CANCELLED podem ser reprocessados.
    O arquivo original deve ainda existir no storage.
    """
    job = _get_job_with_permission(
        job_id,
        current_user,
        allowed_statuses={JobStatus.FAILED, JobStatus.CANCELLED}
    )

    if not job.file_path or not os.path.exists(job.file_path):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=Messages.FILE_NOT_FOUND)

    new_job_id = str(uuid.uuid4())
    new_job = processing_queue.add_job(
        job_id=new_job_id,
        user_id=job.user_id,
        file_path=job.file_path,
        job_type=job.job_type,
        original_filename=job.original_filename
    )

    log_action(
        logger, "job_retried",
        user_id=current_user.id,
        resource_type="job",
        job_id=new_job_id,
        original_job_id=job_id,
    )

    return JobStatusResponse(
        status="ok",
        job=_job_to_detail(new_job)
    )


@router.delete(
    "/queue/jobs/{job_id}",
    response_model=JobDeleteResponse,
    summary="Remover um job",
    responses={
        200: {"description": "Job removido com sucesso"},
        400: {"description": "Job em status inválido para exclusão"},
        401: {"description": "Não autenticado"},
        403: {"description": "Acesso negado ao job"},
        404: {"description": "Job não encontrado"},
    }
)
async def delete_job(
    job_id: str,
    current_user: Usuario = Depends(get_current_active_user)
) -> JobDeleteResponse:
    """
    Remove um job da fila e do banco de dados.

    Apenas jobs finalizados (FAILED ou CANCELLED) podem ser removidos.
    Jobs pendentes ou em processamento devem ser cancelados primeiro.
    """
    logger.info(f"DELETE /queue/jobs/{job_id} - user={current_user.id}")

    job = _get_job_with_permission(
        job_id,
        current_user,
        allowed_statuses={JobStatus.FAILED, JobStatus.CANCELLED}
    )
    logger.info(f"Job encontrado: id={job.id}, status={job.status}, file={job.file_path}")

    deleted = processing_queue.delete_job(job_id)
    logger.info(f"delete_job resultado: deleted={deleted}")

    log_action(
        logger, "job_deleted",
        user_id=current_user.id,
        resource_type="job",
        job_id=job_id,
        deleted=deleted,
    )

    return JobDeleteResponse(status="ok", deleted=deleted)
