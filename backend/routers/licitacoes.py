"""
Router para gestão de licitações.

Endpoints:
    GET    /licitacoes/              - Listar licitações (paginado, filtros)
    GET    /licitacoes/estatisticas  - Estatísticas do usuário
    GET    /licitacoes/{id}          - Detalhe com histórico
    POST   /licitacoes/              - Criar licitação
    PUT    /licitacoes/{id}          - Atualizar licitação
    DELETE /licitacoes/{id}          - Excluir licitação
    PATCH  /licitacoes/{id}/status   - Mudar status
    GET    /licitacoes/{id}/historico - Histórico de status
    POST   /licitacoes/{id}/tags     - Adicionar tag
    DELETE /licitacoes/{id}/tags/{t} - Remover tag
"""
from typing import Optional

from fastapi import Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from auth import get_current_approved_user
from config import Messages
from database import get_db
from logging_config import get_logger, log_action
from models import Licitacao, LicitacaoStatus, Usuario
from repositories.licitacao_repository import licitacao_repository
from routers.base import AuthenticatedRouter
from schemas import (
    LicitacaoCreate,
    LicitacaoDetalheResponse,
    LicitacaoEstatisticasResponse,
    LicitacaoHistoricoResponse,
    LicitacaoResponse,
    LicitacaoStatusUpdate,
    LicitacaoTagCreate,
    LicitacaoTagResponse,
    LicitacaoUpdate,
    Mensagem,
    PaginatedLicitacaoResponse,
)
from utils.http_helpers import get_user_resource_or_404
from utils.pagination import PaginationParams, paginate_query

logger = get_logger("routers.licitacoes")
router = AuthenticatedRouter(prefix="/licitacoes", tags=["Licitações"])


@router.get("/", response_model=PaginatedLicitacaoResponse)
def list_licitacoes(
    pagination: PaginationParams = Depends(),
    status_filter: Optional[str] = Query(None, alias="status"),
    uf: Optional[str] = Query(None),
    modalidade: Optional[str] = Query(None),
    busca: Optional[str] = Query(None),
    current_user: Usuario = Depends(get_current_approved_user),
    db: Session = Depends(get_db),
):
    query = licitacao_repository.get_filtered(
        db,
        current_user.id,
        status=status_filter,
        uf=uf,
        modalidade=modalidade,
        busca=busca,
    )
    return paginate_query(query, pagination, PaginatedLicitacaoResponse)


@router.get("/estatisticas", response_model=LicitacaoEstatisticasResponse)
def get_estatisticas(
    current_user: Usuario = Depends(get_current_approved_user),
    db: Session = Depends(get_db),
):
    stats = licitacao_repository.get_estatisticas(db, current_user.id)
    return LicitacaoEstatisticasResponse(**stats)


@router.get("/{licitacao_id}", response_model=LicitacaoDetalheResponse)
def get_licitacao(
    licitacao_id: int,
    current_user: Usuario = Depends(get_current_approved_user),
    db: Session = Depends(get_db),
):
    licitacao = licitacao_repository.get_by_id_with_relations(
        db, licitacao_id, current_user.id
    )
    if not licitacao:
        raise HTTPException(status_code=404, detail=Messages.LICITACAO_NOT_FOUND)
    return licitacao


@router.post("/", response_model=LicitacaoResponse, status_code=201)
def create_licitacao(
    dados: LicitacaoCreate,
    current_user: Usuario = Depends(get_current_approved_user),
    db: Session = Depends(get_db),
):
    licitacao = Licitacao(user_id=current_user.id, **dados.model_dump())
    licitacao = licitacao_repository.create(db, licitacao)

    licitacao_repository.transition_status(
        db, licitacao, LicitacaoStatus.IDENTIFICADA,
        current_user.id, "Licitação criada",
    )

    log_action(
        logger, "licitacao_created",
        user_id=current_user.id, resource_type="licitacao", resource_id=licitacao.id,
    )
    return licitacao


@router.put("/{licitacao_id}", response_model=LicitacaoResponse)
def update_licitacao(
    licitacao_id: int,
    dados: LicitacaoUpdate,
    current_user: Usuario = Depends(get_current_approved_user),
    db: Session = Depends(get_db),
):
    licitacao = get_user_resource_or_404(
        db, Licitacao, licitacao_id, current_user.id, Messages.LICITACAO_NOT_FOUND
    )
    update_data = dados.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(licitacao, field, value)
    db.commit()
    db.refresh(licitacao)
    return licitacao


@router.delete("/{licitacao_id}", response_model=Mensagem)
def delete_licitacao(
    licitacao_id: int,
    current_user: Usuario = Depends(get_current_approved_user),
    db: Session = Depends(get_db),
):
    licitacao = get_user_resource_or_404(
        db, Licitacao, licitacao_id, current_user.id, Messages.LICITACAO_NOT_FOUND
    )
    db.delete(licitacao)
    db.commit()
    log_action(
        logger, "licitacao_deleted",
        user_id=current_user.id, resource_type="licitacao", resource_id=licitacao_id,
    )
    return Mensagem(mensagem=Messages.LICITACAO_DELETED, sucesso=True)


@router.patch("/{licitacao_id}/status", response_model=LicitacaoResponse)
def update_status(
    licitacao_id: int,
    dados: LicitacaoStatusUpdate,
    current_user: Usuario = Depends(get_current_approved_user),
    db: Session = Depends(get_db),
):
    licitacao = get_user_resource_or_404(
        db, Licitacao, licitacao_id, current_user.id, Messages.LICITACAO_NOT_FOUND
    )
    allowed = LicitacaoStatus.TRANSITIONS.get(licitacao.status, [])
    if dados.status not in allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{Messages.INVALID_STATUS_TRANSITION}: "
                   f"{licitacao.status} -> {dados.status}",
        )
    licitacao_repository.transition_status(
        db, licitacao, dados.status, current_user.id, dados.observacao
    )
    log_action(
        logger, "licitacao_status_changed",
        user_id=current_user.id, resource_type="licitacao", resource_id=licitacao_id,
    )
    db.refresh(licitacao)
    return licitacao


@router.get(
    "/{licitacao_id}/historico",
    response_model=list[LicitacaoHistoricoResponse],
)
def get_historico(
    licitacao_id: int,
    current_user: Usuario = Depends(get_current_approved_user),
    db: Session = Depends(get_db),
):
    get_user_resource_or_404(
        db, Licitacao, licitacao_id, current_user.id, Messages.LICITACAO_NOT_FOUND
    )
    return licitacao_repository.get_historico(db, licitacao_id)


@router.post(
    "/{licitacao_id}/tags",
    response_model=LicitacaoTagResponse,
    status_code=201,
)
def add_tag(
    licitacao_id: int,
    dados: LicitacaoTagCreate,
    current_user: Usuario = Depends(get_current_approved_user),
    db: Session = Depends(get_db),
):
    get_user_resource_or_404(
        db, Licitacao, licitacao_id, current_user.id, Messages.LICITACAO_NOT_FOUND
    )
    try:
        tag = licitacao_repository.add_tag(db, licitacao_id, dados.tag)
        return tag
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=Messages.TAG_ALREADY_EXISTS,
        )


@router.delete("/{licitacao_id}/tags/{tag}", response_model=Mensagem)
def remove_tag(
    licitacao_id: int,
    tag: str,
    current_user: Usuario = Depends(get_current_approved_user),
    db: Session = Depends(get_db),
):
    get_user_resource_or_404(
        db, Licitacao, licitacao_id, current_user.id, Messages.LICITACAO_NOT_FOUND
    )
    removed = licitacao_repository.remove_tag(db, licitacao_id, tag)
    if not removed:
        raise HTTPException(status_code=404, detail=Messages.TAG_NOT_FOUND)
    return Mensagem(mensagem="Tag removida com sucesso", sucesso=True)
