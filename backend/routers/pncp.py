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
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from auth import get_current_approved_user
from config import Messages
from database import get_db
from logging_config import get_logger, log_action
from models import Licitacao, Usuario
from models.lembrete import Lembrete, LembreteTipo
from models.pncp import PncpMonitoramento, PncpResultadoStatus
from repositories.lembrete_repository import lembrete_repository
from repositories.licitacao_repository import licitacao_repository
from repositories.pncp_repository import (
    pncp_monitoramento_repository,
    pncp_resultado_repository,
)
from routers.base import AuthenticatedRouter
from schemas import Mensagem
from schemas.pncp import (
    GerenciarRequest,
    GerenciarResponse,
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
from services.pncp.client import pncp_client
from services.pncp.mapper import pncp_mapper
from utils.pagination import PaginationParams, paginate_query

logger = get_logger("routers.pncp")
router = AuthenticatedRouter(prefix="/pncp", tags=["PNCP"])

MODALIDADES_PADRAO = ["4", "5", "6", "7", "8"]


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
    data_inicial: str = Query(..., description="Data sessão inicial YYYYMMDD"),
    data_final: str = Query(..., description="Data sessão final YYYYMMDD"),
    codigo_modalidade: Optional[str] = Query(
        None,
        description="Código da modalidade PNCP. Se omitido, busca nas modalidades padrão.",
    ),
    uf: Optional[str] = Query(None),
    valor_minimo: Optional[float] = Query(None, description="Filtro client-side de valor mínimo"),
    valor_maximo: Optional[float] = Query(None, description="Filtro client-side de valor máximo"),
    current_user: Usuario = Depends(get_current_approved_user),
):
    """
    Busca no PNCP com filtros ricos usando estratégia dual-endpoint:
    - /proposta: filtra por dataEncerramentoProposta (data da sessão) no range solicitado
    - /publicacao: filtra por publicações com dataAberturaProposta no range (lookback 1 dia)
    Resultados são mesclados e deduplicados por numeroControlePNCP.
    """
    modalidades = [codigo_modalidade] if codigo_modalidade else MODALIDADES_PADRAO

    try:
        dt_ini = datetime.strptime(data_inicial, "%Y%m%d")
        dt_fim = datetime.strptime(data_final, "%Y%m%d")
        dt_fim_fim = dt_fim.replace(hour=23, minute=59, second=59)
        # Lookback de 1 dia em publicacao para capturar publicações do dia anterior ao período
        pub_inicial = (dt_ini - timedelta(days=1)).strftime("%Y%m%d")

        async def buscar_modalidade_proposta(modalidade: str) -> list:
            kwargs: dict = {"codigo_modalidade": modalidade}
            if uf:
                kwargs["uf"] = uf
            return await pncp_client.buscar_todas_paginas(
                data_inicial=data_inicial,
                data_final=data_final,
                max_paginas=3,
                endpoint="proposta",
                **kwargs,
            )

        async def buscar_modalidade_publicacao(modalidade: str) -> list:
            kwargs: dict = {"codigo_modalidade": modalidade}
            if uf:
                kwargs["uf"] = uf
            return await pncp_client.buscar_todas_paginas(
                data_inicial=pub_inicial,
                data_final=data_final,
                max_paginas=3,
                endpoint="publicacao",
                **kwargs,
            )

        # Executar todas as chamadas em paralelo (proposta + publicacao para cada modalidade)
        tarefas_proposta = [buscar_modalidade_proposta(m) for m in modalidades]
        tarefas_publicacao = [buscar_modalidade_publicacao(m) for m in modalidades]
        resultados = await asyncio.gather(*tarefas_proposta, *tarefas_publicacao)

        n = len(modalidades)
        items_proposta = [item for lista in resultados[:n] for item in lista]
        items_publicacao_raw = [item for lista in resultados[n:] for item in lista]

        # Filtrar publicacao por dataAberturaProposta dentro do range
        items_publicacao = []
        for item in items_publicacao_raw:
            abertura_str = item.get("dataAberturaProposta")
            if not abertura_str:
                continue
            try:
                abertura = datetime.fromisoformat(abertura_str)
            except (ValueError, TypeError):
                continue
            if dt_ini <= abertura <= dt_fim_fim:
                items_publicacao.append(item)

        # Mesclar: proposta primeiro (prioridade), depois publicacao não duplicadas
        vistos: set = set()
        todos_items = []
        for item in items_proposta:
            chave = item.get("numeroControlePNCP") or None
            if chave is None or chave not in vistos:
                if chave is not None:
                    vistos.add(chave)
                todos_items.append(item)
        for item in items_publicacao:
            chave = item.get("numeroControlePNCP") or None
            if chave is None or chave not in vistos:
                if chave is not None:
                    vistos.add(chave)
                todos_items.append(item)

        # Filtrar por valor (client-side)
        filtrados = []
        for item in todos_items:
            valor = item.get("valorTotalEstimado")
            if valor_minimo is not None and valor is not None and float(valor) < valor_minimo:
                continue
            if valor_maximo is not None and valor is not None and float(valor) > valor_maximo:
                continue
            filtrados.append(item)

        return PncpBuscaResponse(
            data=filtrados,
            total_registros=len(filtrados),
            total_paginas=1,
            numero_pagina=1,
            paginas_restantes=0,
        )
    except HTTPException:
        raise
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


# ===================== Gerenciar =====================


@router.post("/gerenciar", response_model=GerenciarResponse, status_code=201)
def gerenciar_licitacao(
    dados: GerenciarRequest,
    current_user: Usuario = Depends(get_current_approved_user),
    db: Session = Depends(get_db),
):
    """
    Cria atomicamente uma Licitação (M1) + Lembrete no calendário (M2)
    a partir de dados de um item PNCP.

    - Se a licitação já existe (mesmo numero_controle_pncp), retorna a existente.
    - Se criar_lembrete=True e data_abertura presente, cria Lembrete com
      data = data_abertura - antecedencia_horas.
    - Se pncp_resultado_id fornecido, marca o PncpResultado como 'importado'.
    """
    # 1. Verificar duplicata
    existente = licitacao_repository.get_by_numero_controle_pncp(
        db, current_user.id, dados.numero_controle_pncp,
    )
    if existente:
        log_action(
            logger, "pncp_gerenciar_existente",
            user_id=current_user.id,
            resource_type="licitacao",
            resource_id=existente.id,
        )
        return JSONResponse(
            status_code=200,
            content=GerenciarResponse(
                licitacao_id=existente.id,
                lembrete_id=None,
                licitacao_ja_existia=True,
                mensagem=Messages.PNCP_GERENCIAR_JA_EXISTIA,
            ).model_dump(),
        )

    # 2. Criar Licitacao
    numero_controle = dados.numero_controle_pncp
    numero = (
        f"PNCP-{numero_controle[-10:]}"
        if len(numero_controle) > 10
        else f"PNCP-{numero_controle}"
    )
    licitacao = Licitacao(
        user_id=current_user.id,
        numero=numero,
        objeto=dados.objeto_compra,
        orgao=dados.orgao_razao_social,
        modalidade=dados.modalidade_nome or "Não informada",
        fonte="pncp",
        status=dados.status_inicial,
        numero_controle_pncp=numero_controle,
        valor_estimado=dados.valor_estimado,
        data_abertura=dados.data_abertura,
        uf=dados.uf,
        municipio=dados.municipio,
        link_sistema_origem=dados.link_sistema_origem,
        observacoes=dados.observacoes or f"Importado do PNCP. Controle: {numero_controle}",
    )
    db.add(licitacao)
    db.commit()
    db.refresh(licitacao)

    # 3. Criar Lembrete (se solicitado e data disponível)
    lembrete_id = None
    if dados.criar_lembrete and dados.data_abertura:
        data_lembrete = dados.data_abertura - timedelta(hours=dados.antecedencia_horas)
        titulo = f"Abertura: {dados.objeto_compra[:80]}"
        lembrete = Lembrete(
            user_id=current_user.id,
            licitacao_id=licitacao.id,
            titulo=titulo,
            descricao=f"Abertura da disputa — {dados.orgao_razao_social}",
            data_lembrete=data_lembrete,
            data_evento=dados.data_abertura,
            tipo=LembreteTipo.ABERTURA_LICITACAO,
            canais=["app"],
        )
        db.add(lembrete)
        db.commit()
        db.refresh(lembrete)
        lembrete_id = lembrete.id

    # 4. Atualizar PncpResultado se fornecido
    if dados.pncp_resultado_id:
        resultado = pncp_resultado_repository.get_by_id_for_user(
            db, dados.pncp_resultado_id, current_user.id,
        )
        if resultado:
            resultado.status = PncpResultadoStatus.IMPORTADO
            resultado.licitacao_id = licitacao.id
            db.commit()

    log_action(
        logger, "pncp_gerenciar",
        user_id=current_user.id,
        resource_type="licitacao",
        resource_id=licitacao.id,
    )

    mensagem = (
        Messages.PNCP_GERENCIAR_CRIADO
        if lembrete_id
        else Messages.PNCP_GERENCIAR_SEM_DATA
    )
    return GerenciarResponse(
        licitacao_id=licitacao.id,
        lembrete_id=lembrete_id,
        licitacao_ja_existia=False,
        mensagem=mensagem,
    )
