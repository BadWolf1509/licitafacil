"""
Router para gestão de lembretes.

Endpoints:
    GET    /lembretes/              - Listar lembretes (paginado, filtros)
    GET    /lembretes/calendario    - Lembretes por range de data
    POST   /lembretes/              - Criar lembrete
    PUT    /lembretes/{id}          - Atualizar lembrete
    DELETE /lembretes/{id}          - Excluir lembrete
    PATCH  /lembretes/{id}/status   - Mudar status do lembrete
"""
from datetime import datetime
from typing import List, Optional

from fastapi import Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from auth import get_current_approved_user
from config import Messages
from database import get_db
from logging_config import get_logger, log_action
from models import Lembrete, Usuario
from repositories.lembrete_repository import lembrete_repository
from routers.base import AuthenticatedRouter
from schemas import (
    LembreteCreate,
    LembreteResponse,
    LembreteStatusUpdate,
    LembreteUpdate,
    Mensagem,
    PaginatedLembreteResponse,
)
from utils.pagination import PaginationParams, paginate_query

logger = get_logger("routers.lembretes")
router = AuthenticatedRouter(prefix="/lembretes", tags=["Lembretes"])


@router.get("/calendario", response_model=List[LembreteResponse])
def get_calendario(
    data_inicio: datetime = Query(...),
    data_fim: datetime = Query(...),
    current_user: Usuario = Depends(get_current_approved_user),
    db: Session = Depends(get_db),
):
    """Retorna lembretes dentro de um range de datas."""
    lembretes = lembrete_repository.get_calendario(
        db, current_user.id, data_inicio, data_fim,
    )
    return lembretes


@router.get("/", response_model=PaginatedLembreteResponse)
def list_lembretes(
    pagination: PaginationParams = Depends(),
    status_filter: Optional[str] = Query(None, alias="status"),
    tipo: Optional[str] = Query(None),
    licitacao_id: Optional[int] = Query(None),
    current_user: Usuario = Depends(get_current_approved_user),
    db: Session = Depends(get_db),
):
    """Lista lembretes do usuário com filtros e paginação."""
    query = lembrete_repository.get_filtered(
        db,
        current_user.id,
        status=status_filter,
        tipo=tipo,
        licitacao_id=licitacao_id,
    )
    return paginate_query(query, pagination, PaginatedLembreteResponse)


@router.post("/", response_model=LembreteResponse, status_code=201)
def create_lembrete(
    dados: LembreteCreate,
    current_user: Usuario = Depends(get_current_approved_user),
    db: Session = Depends(get_db),
):
    """Cria um novo lembrete."""
    lembrete = Lembrete(user_id=current_user.id, **dados.model_dump())
    lembrete = lembrete_repository.create(db, lembrete)
    log_action(
        logger, "lembrete_created",
        user_id=current_user.id, resource_type="lembrete", resource_id=lembrete.id,
    )
    return lembrete


@router.put("/{lembrete_id}", response_model=LembreteResponse)
def update_lembrete(
    lembrete_id: int,
    dados: LembreteUpdate,
    current_user: Usuario = Depends(get_current_approved_user),
    db: Session = Depends(get_db),
):
    """Atualiza um lembrete existente."""
    lembrete = lembrete_repository.get_by_id_for_user(
        db, lembrete_id, current_user.id,
    )
    if not lembrete:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=Messages.LEMBRETE_NOT_FOUND,
        )
    update_data = dados.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(lembrete, field, value)
    db.commit()
    db.refresh(lembrete)
    return lembrete


@router.delete("/{lembrete_id}", response_model=Mensagem)
def delete_lembrete(
    lembrete_id: int,
    current_user: Usuario = Depends(get_current_approved_user),
    db: Session = Depends(get_db),
):
    """Exclui um lembrete."""
    lembrete = lembrete_repository.get_by_id_for_user(
        db, lembrete_id, current_user.id,
    )
    if not lembrete:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=Messages.LEMBRETE_NOT_FOUND,
        )
    lembrete_repository.delete(db, lembrete)
    log_action(
        logger, "lembrete_deleted",
        user_id=current_user.id, resource_type="lembrete", resource_id=lembrete_id,
    )
    return Mensagem(mensagem=Messages.LEMBRETE_DELETED, sucesso=True)


@router.patch("/{lembrete_id}/status", response_model=LembreteResponse)
def update_status(
    lembrete_id: int,
    dados: LembreteStatusUpdate,
    current_user: Usuario = Depends(get_current_approved_user),
    db: Session = Depends(get_db),
):
    """Muda o status de um lembrete."""
    lembrete = lembrete_repository.get_by_id_for_user(
        db, lembrete_id, current_user.id,
    )
    if not lembrete:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=Messages.LEMBRETE_NOT_FOUND,
        )
    lembrete.status = dados.status
    db.commit()
    db.refresh(lembrete)
    return lembrete
