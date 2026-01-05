"""
Rotas para gerenciamento e status dos provedores de IA.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import Dict, Any
import os
import uuid

from auth import get_current_active_user
from models import Usuario
from services.ai_provider import ai_provider
from services.processing_queue import processing_queue, JobStatus

router = APIRouter(prefix="/api/ai", tags=["ai"])


@router.get("/status")
async def get_ai_status(
    current_user: Usuario = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """
    Retorna o status dos provedores de IA configurados.
    """
    return {
        "status": "ok",
        "providers": ai_provider.get_status(),
        "statistics": ai_provider.get_stats()
    }


@router.get("/queue/status")
async def get_queue_status(
    current_user: Usuario = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """
    Retorna o status da fila de processamento.
    """
    return {
        "status": "ok",
        "queue": processing_queue.get_status()
    }


@router.get("/queue/jobs")
async def get_user_jobs(
    limit: int = 20,
    current_user: Usuario = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """
    Retorna os jobs do usuário atual.
    """
    jobs = processing_queue.get_user_jobs(current_user.id, limit=limit)
    return {
        "status": "ok",
        "jobs": [job.to_dict() for job in jobs]
    }


@router.get("/queue/jobs/{job_id}")
async def get_job_status(
    job_id: str,
    current_user: Usuario = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """
    Retorna o status de um job específico.
    """
    job = processing_queue.get_job(job_id)

    if not job:
        raise HTTPException(status_code=404, detail="Job não encontrado")

    if job.user_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Acesso negado")

    return {
        "status": "ok",
        "job": job.to_dict()
    }


@router.post("/queue/jobs/{job_id}/cancel")
async def cancel_job(
    job_id: str,
    current_user: Usuario = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """
    Cancela um job pendente ou em processamento.
    """
    job = processing_queue.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job nao encontrado")

    if job.user_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Acesso negado")

    if job.status in {JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED}:
        raise HTTPException(status_code=400, detail="Job ja finalizado")

    updated = processing_queue.cancel_job(job_id)
    return {
        "status": "ok",
        "job": updated.to_dict() if updated else None
    }


@router.post("/queue/jobs/{job_id}/retry")
async def retry_job(
    job_id: str,
    current_user: Usuario = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """
    Reenvia um job falhado/cancelado para a fila.
    """
    job = processing_queue.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job nao encontrado")

    if job.user_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Acesso negado")

    if job.status not in {JobStatus.FAILED, JobStatus.CANCELLED}:
        raise HTTPException(status_code=400, detail="Job nao pode ser reprocessado")

    if not job.file_path or not os.path.exists(job.file_path):
        raise HTTPException(status_code=400, detail="Arquivo do job nao encontrado")

    new_job_id = str(uuid.uuid4())
    new_job = processing_queue.add_job(
        job_id=new_job_id,
        user_id=job.user_id,
        file_path=job.file_path,
        job_type=job.job_type
    )
    return {
        "status": "ok",
        "job": new_job.to_dict()
    }


@router.delete("/queue/jobs/{job_id}")
async def delete_job(
    job_id: str,
    current_user: Usuario = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """
    Remove um job da fila e do banco (apenas falhados/cancelados).
    """
    job = processing_queue.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job nao encontrado")

    if job.user_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Acesso negado")

    if job.status not in {JobStatus.FAILED, JobStatus.CANCELLED}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Somente jobs falhados ou cancelados podem ser removidos"
        )

    deleted = processing_queue.delete_job(job_id)
    return {"status": "ok", "deleted": deleted}
