"""
Router para gestão de notificações.

Endpoints:
    GET    /notificacoes/                  - Listar notificações (paginado)
    GET    /notificacoes/nao-lidas/count   - Contagem de não lidas
    GET    /notificacoes/preferencias      - Preferências do usuário
    PUT    /notificacoes/preferencias      - Atualizar preferências
    POST   /notificacoes/marcar-todas-lidas - Marcar todas como lidas
    PATCH  /notificacoes/{id}/lida         - Marcar uma como lida
    DELETE /notificacoes/{id}              - Excluir notificação
"""
from typing import Optional

from fastapi import Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from auth import get_current_approved_user
from config import Messages
from database import get_db
from logging_config import get_logger
from models import Usuario
from repositories.notificacao_repository import notificacao_repository
from repositories.preferencia_repository import preferencia_repository
from routers.base import AuthenticatedRouter
from schemas import (
    Mensagem,
    NotificacaoCountResponse,
    NotificacaoResponse,
    PaginatedNotificacaoResponse,
    PreferenciaNotificacaoResponse,
    PreferenciaNotificacaoUpdate,
)
from utils.pagination import PaginationParams, paginate_query

logger = get_logger("routers.notificacoes")
router = AuthenticatedRouter(prefix="/notificacoes", tags=["Notificações"])


@router.get("/nao-lidas/count", response_model=NotificacaoCountResponse)
def count_nao_lidas(
    current_user: Usuario = Depends(get_current_approved_user),
    db: Session = Depends(get_db),
):
    """Retorna contagem de notificações não lidas."""
    count = notificacao_repository.count_nao_lidas(db, current_user.id)
    return NotificacaoCountResponse(count=count)


@router.get("/preferencias", response_model=PreferenciaNotificacaoResponse)
def get_preferencias(
    current_user: Usuario = Depends(get_current_approved_user),
    db: Session = Depends(get_db),
):
    """Retorna preferências de notificação do usuário (cria se não existir)."""
    pref = preferencia_repository.get_or_create(db, current_user.id)
    return pref


@router.put("/preferencias", response_model=PreferenciaNotificacaoResponse)
def update_preferencias(
    dados: PreferenciaNotificacaoUpdate,
    current_user: Usuario = Depends(get_current_approved_user),
    db: Session = Depends(get_db),
):
    """Atualiza preferências de notificação do usuário."""
    pref = preferencia_repository.get_or_create(db, current_user.id)
    update_data = dados.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(pref, field, value)
    db.commit()
    db.refresh(pref)
    return pref


@router.post("/marcar-todas-lidas", response_model=Mensagem)
def marcar_todas_lidas(
    current_user: Usuario = Depends(get_current_approved_user),
    db: Session = Depends(get_db),
):
    """Marca todas as notificações do usuário como lidas."""
    count = notificacao_repository.marcar_todas_lidas(db, current_user.id)
    return Mensagem(
        mensagem=f"{Messages.TODAS_LIDAS} ({count})",
        sucesso=True,
    )


@router.get("/", response_model=PaginatedNotificacaoResponse)
def list_notificacoes(
    pagination: PaginationParams = Depends(),
    lida: Optional[bool] = Query(None),
    tipo: Optional[str] = Query(None),
    current_user: Usuario = Depends(get_current_approved_user),
    db: Session = Depends(get_db),
):
    """Lista notificações do usuário com filtros e paginação."""
    query = notificacao_repository.get_filtered(
        db, current_user.id, lida=lida, tipo=tipo,
    )
    return paginate_query(query, pagination, PaginatedNotificacaoResponse)


@router.patch("/{notificacao_id}/lida", response_model=NotificacaoResponse)
def marcar_lida(
    notificacao_id: int,
    current_user: Usuario = Depends(get_current_approved_user),
    db: Session = Depends(get_db),
):
    """Marca uma notificação como lida."""
    notificacao = notificacao_repository.get_by_id_for_user(
        db, notificacao_id, current_user.id,
    )
    if not notificacao:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=Messages.NOTIFICACAO_NOT_FOUND,
        )
    notificacao = notificacao_repository.marcar_lida(db, notificacao)
    return notificacao


@router.delete("/{notificacao_id}", response_model=Mensagem)
def delete_notificacao(
    notificacao_id: int,
    current_user: Usuario = Depends(get_current_approved_user),
    db: Session = Depends(get_db),
):
    """Exclui uma notificação."""
    notificacao = notificacao_repository.get_by_id_for_user(
        db, notificacao_id, current_user.id,
    )
    if not notificacao:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=Messages.NOTIFICACAO_NOT_FOUND,
        )
    notificacao_repository.delete(db, notificacao)
    return Mensagem(mensagem=Messages.NOTIFICACAO_DELETED, sucesso=True)
