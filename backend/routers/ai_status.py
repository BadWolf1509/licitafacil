"""
Rotas para gerenciamento e status dos provedores de IA.
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any
from ..auth import get_current_active_user
from ..models import Usuario
from ..services.ai_provider import ai_provider
from ..services.processing_queue import processing_queue

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
