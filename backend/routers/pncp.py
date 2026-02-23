"""
Router para monitoramento PNCP.

Endpoints:
    GET    /pncp/monitoramentos              - Listar monitoramentos (paginado)
    POST   /pncp/monitoramentos              - Criar monitoramento
    GET    /pncp/monitoramentos/{id}         - Detalhe do monitoramento
    PUT    /pncp/monitoramentos/{id}         - Atualizar monitoramento
    DELETE /pncp/monitoramentos/{id}         - Excluir monitoramento
    PATCH  /pncp/monitoramentos/{id}/toggle  - Ativar/desativar monitoramento
    GET    /pncp/resultados                  - Listar resultados (paginado)
    PATCH  /pncp/resultados/{id}/status      - Atualizar status de resultado
    POST   /pncp/resultados/{id}/importar    - Importar resultado como licitação
    GET    /pncp/busca                       - Busca direta no PNCP
    POST   /pncp/busca/importar              - Importar item da busca direta como licitação
    POST   /pncp/sincronizar                 - Sincronização manual
"""
import asyncio
from typing import Optional

from fastapi import Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from auth import get_current_approved_user
from config import Messages
from database import get_db
from logging_config import get_logger, log_action
from models import Licitacao, Usuario
from models.pncp import PncpMonitoramento, PncpResultadoStatus
from repositories.pncp_repository import (
    pncp_monitoramento_repository,
    pncp_resultado_repository,
)
from routers.base import AuthenticatedRouter
from schemas import Mensagem
from schemas.pncp import (
    PaginatedMonitoramentoResponse,
    PaginatedResultadoResponse,
    PncpBuscaResponse,
    PncpImportarRequest,
    PncpMonitoramentoCreate,
    PncpMonitoramentoResponse,
    PncpMonitoramentoUpdate,
    PncpResultadoResponse,
    PncpResultadoStatusUpdate,
)
from services.pncp.mapper import pncp_mapper
from utils.pagination import PaginationParams, paginate_query

logger = get_logger("routers.pncp")
router = AuthenticatedRouter(prefix="/pncp", tags=["PNCP"])


# ===================== Monitoramentos =====================


@router.get("/monitoramentos", response_model=PaginatedMonitoramentoResponse)
def list_monitoramentos(
    pagination: PaginationParams = Depends(),
    ativo: Optional[bool] = Query(None),
    busca: Optional[str] = Query(None),
    current_user: Usuario = Depends(get_current_approved_user),
    db: Session = Depends(get_db),
):
    """Lista monitoramentos do usuário."""
    query = pncp_monitoramento_repository.get_filtered(
        db, current_user.id, ativo=ativo, busca=busca,
    )
    return paginate_query(query, pagination, PaginatedMonitoramentoResponse)


@router.post(
    "/monitoramentos",
    response_model=PncpMonitoramentoResponse,
    status_code=201,
)
def create_monitoramento(
    dados: PncpMonitoramentoCreate,
    current_user: Usuario = Depends(get_current_approved_user),
    db: Session = Depends(get_db),
):
    """Cria um novo monitoramento PNCP."""
    monitor = PncpMonitoramento(
        user_id=current_user.id,
        **dados.model_dump(),
    )
    monitor = pncp_monitoramento_repository.create(db, monitor)
    log_action(
        logger, "pncp_monitor_create",
        user_id=current_user.id,
        resource_type="pncp_monitoramento",
        resource_id=monitor.id,
    )
    return monitor


@router.get("/monitoramentos/{monitor_id}", response_model=PncpMonitoramentoResponse)
def get_monitoramento(
    monitor_id: int,
    current_user: Usuario = Depends(get_current_approved_user),
    db: Session = Depends(get_db),
):
    """Retorna detalhe de um monitoramento."""
    monitor = pncp_monitoramento_repository.get_by_id_for_user(
        db, monitor_id, current_user.id,
    )
    if not monitor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=Messages.PNCP_MONITOR_NOT_FOUND,
        )
    return monitor


@router.put("/monitoramentos/{monitor_id}", response_model=PncpMonitoramentoResponse)
def update_monitoramento(
    monitor_id: int,
    dados: PncpMonitoramentoUpdate,
    current_user: Usuario = Depends(get_current_approved_user),
    db: Session = Depends(get_db),
):
    """Atualiza um monitoramento."""
    monitor = pncp_monitoramento_repository.get_by_id_for_user(
        db, monitor_id, current_user.id,
    )
    if not monitor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=Messages.PNCP_MONITOR_NOT_FOUND,
        )
    update_data = dados.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(monitor, field, value)
    db.commit()
    db.refresh(monitor)
    log_action(
        logger, "pncp_monitor_update",
        user_id=current_user.id,
        resource_type="pncp_monitoramento",
        resource_id=monitor.id,
    )
    return monitor


@router.delete("/monitoramentos/{monitor_id}", response_model=Mensagem)
def delete_monitoramento(
    monitor_id: int,
    current_user: Usuario = Depends(get_current_approved_user),
    db: Session = Depends(get_db),
):
    """Exclui um monitoramento e seus resultados."""
    monitor = pncp_monitoramento_repository.get_by_id_for_user(
        db, monitor_id, current_user.id,
    )
    if not monitor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=Messages.PNCP_MONITOR_NOT_FOUND,
        )
    pncp_monitoramento_repository.delete(db, monitor)
    log_action(
        logger, "pncp_monitor_delete",
        user_id=current_user.id,
        resource_type="pncp_monitoramento",
        resource_id=monitor_id,
    )
    return Mensagem(mensagem=Messages.PNCP_MONITOR_DELETED, sucesso=True)


@router.patch(
    "/monitoramentos/{monitor_id}/toggle",
    response_model=PncpMonitoramentoResponse,
)
def toggle_monitoramento(
    monitor_id: int,
    current_user: Usuario = Depends(get_current_approved_user),
    db: Session = Depends(get_db),
):
    """Ativa/desativa um monitoramento."""
    monitor = pncp_monitoramento_repository.get_by_id_for_user(
        db, monitor_id, current_user.id,
    )
    if not monitor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=Messages.PNCP_MONITOR_NOT_FOUND,
        )
    monitor.ativo = not monitor.ativo
    db.commit()
    db.refresh(monitor)
    return monitor


# ===================== Resultados =====================


@router.get("/resultados", response_model=PaginatedResultadoResponse)
def list_resultados(
    pagination: PaginationParams = Depends(),
    monitoramento_id: Optional[int] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    uf: Optional[str] = Query(None),
    busca: Optional[str] = Query(None),
    current_user: Usuario = Depends(get_current_approved_user),
    db: Session = Depends(get_db),
):
    """Lista resultados PNCP do usuário."""
    query = pncp_resultado_repository.get_filtered(
        db, current_user.id,
        monitoramento_id=monitoramento_id,
        status=status_filter,
        uf=uf,
        busca=busca,
    )
    return paginate_query(query, pagination, PaginatedResultadoResponse)


@router.patch("/resultados/{resultado_id}/status", response_model=PncpResultadoResponse)
def update_resultado_status(
    resultado_id: int,
    dados: PncpResultadoStatusUpdate,
    current_user: Usuario = Depends(get_current_approved_user),
    db: Session = Depends(get_db),
):
    """Atualiza o status de um resultado PNCP."""
    resultado = pncp_resultado_repository.get_by_id_for_user(
        db, resultado_id, current_user.id,
    )
    if not resultado:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=Messages.PNCP_RESULTADO_NOT_FOUND,
        )
    resultado.status = dados.status
    db.commit()
    db.refresh(resultado)
    return resultado


# ===================== Importar =====================


@router.post("/resultados/{resultado_id}/importar", response_model=PncpResultadoResponse)
def importar_resultado(
    resultado_id: int,
    dados: PncpImportarRequest,
    current_user: Usuario = Depends(get_current_approved_user),
    db: Session = Depends(get_db),
):
    """Importa um resultado PNCP como licitação no sistema."""
    resultado = pncp_resultado_repository.get_by_id_for_user(
        db, resultado_id, current_user.id,
    )
    if not resultado:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=Messages.PNCP_RESULTADO_NOT_FOUND,
        )
    if resultado.status == PncpResultadoStatus.IMPORTADO:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=Messages.PNCP_RESULTADO_JA_IMPORTADO,
        )

    # Mapear para licitação
    campos = pncp_mapper.resultado_para_licitacao(resultado)
    if dados.observacoes:
        campos["observacoes"] = f"{campos.get('observacoes', '')} | {dados.observacoes}"

    licitacao = Licitacao(user_id=current_user.id, **campos)
    db.add(licitacao)
    db.commit()
    db.refresh(licitacao)

    # Atualizar resultado
    resultado.status = PncpResultadoStatus.IMPORTADO
    resultado.licitacao_id = licitacao.id
    db.commit()
    db.refresh(resultado)

    log_action(
        logger, "pncp_resultado_importar",
        user_id=current_user.id,
        resource_type="pncp_resultado",
        resource_id=resultado.id,
    )
    return resultado


# ===================== Busca + Sync =====================


@router.get("/busca", response_model=PncpBuscaResponse)
async def buscar_pncp(
    data_inicial: str = Query(..., description="Data abertura inicial YYYYMMDD"),
    data_final: str = Query(..., description="Data abertura final YYYYMMDD"),
    codigo_modalidade: str = Query(..., description="Código da modalidade (obrigatório na API PNCP)"),
    uf: Optional[str] = Query(None),
    current_user: Usuario = Depends(get_current_approved_user),
):
    """Busca no PNCP filtrando por data de abertura de proposta."""
    from datetime import datetime, timedelta

    from services.pncp.client import pncp_client

    try:
        # A API PNCP só filtra por data de publicação.
        # Na prática, publicação e abertura diferem em 0-7 dias.
        # Recuamos 7 dias na publicação e filtramos por abertura.
        dt_ini = datetime.strptime(data_inicial, "%Y%m%d")
        dt_fim = datetime.strptime(data_final, "%Y%m%d")
        pub_inicial = (dt_ini - timedelta(days=7)).strftime("%Y%m%d")

        kwargs = {"codigo_modalidade": codigo_modalidade}
        if uf:
            kwargs["uf"] = uf

        todos_items = await pncp_client.buscar_todas_paginas(
            data_inicial=pub_inicial,
            data_final=data_final,
            max_paginas=5,
            **kwargs,
        )

        # Filtrar por dataAberturaProposta dentro do range solicitado
        filtrados = []
        for item in todos_items:
            abertura_str = item.get("dataAberturaProposta")
            if not abertura_str:
                continue
            try:
                abertura = datetime.fromisoformat(abertura_str)
            except (ValueError, TypeError):
                continue
            if dt_ini <= abertura <= dt_fim.replace(hour=23, minute=59, second=59):
                filtrados.append(item)

        return PncpBuscaResponse(
            data=filtrados,
            total_registros=len(filtrados),
            total_paginas=1,
            numero_pagina=1,
            paginas_restantes=0,
        )
    except Exception:
        logger.error("Erro na busca PNCP", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=Messages.PNCP_BUSCA_ERRO,
        )


@router.post("/busca/importar")
def importar_busca_direta(
    item_pncp: dict,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_approved_user),
):
    """Importa item da busca direta como licitação (sem PncpResultado intermediário)."""
    numero_controle = item_pncp.get("numeroControlePNCP", "")
    if not numero_controle:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Item inválido: campo numeroControlePNCP ausente.",
        )

    # Verificar duplicata
    existente = db.query(Licitacao).filter(
        Licitacao.user_id == current_user.id,
        Licitacao.numero_controle_pncp == numero_controle,
    ).first()
    if existente:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Esta licitação já foi importada anteriormente.",
        )

    campos = pncp_mapper.item_pncp_para_licitacao(item_pncp)
    licitacao = Licitacao(user_id=current_user.id, **campos)
    db.add(licitacao)
    db.commit()
    db.refresh(licitacao)

    log_action(
        logger, "pncp_busca_importar",
        user_id=current_user.id,
        resource_type="licitacao",
        resource_id=licitacao.id,
    )
    return {"message": "Licitação importada com sucesso!", "licitacao_id": licitacao.id}


@router.post("/sincronizar", response_model=Mensagem)
async def sincronizar_pncp(
    current_user: Usuario = Depends(get_current_approved_user),
):
    """Dispara sincronização manual dos monitores do usuário."""
    from services.pncp.sync_service import pncp_sync_service

    asyncio.create_task(pncp_sync_service._sync_all())
    log_action(
        logger, "pncp_sync_manual",
        user_id=current_user.id,
    )
    return Mensagem(mensagem=Messages.PNCP_SYNC_INICIADA, sucesso=True)
