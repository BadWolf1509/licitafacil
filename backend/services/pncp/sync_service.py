"""Worker background para sincronização periódica com PNCP."""
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any

from config.base import (
    PNCP_SYNC_ENABLED,
    PNCP_SYNC_INTERVAL,
    PNCP_SYNC_LOOKBACK_DAYS,
)
from logging_config import get_logger

logger = get_logger("services.pncp.sync")


class PncpSyncService:
    """Worker que busca periodicamente novos resultados no PNCP."""

    def __init__(self) -> None:
        self._enabled = PNCP_SYNC_ENABLED
        self._interval = PNCP_SYNC_INTERVAL
        self._lookback_days = PNCP_SYNC_LOOKBACK_DAYS
        self._is_running = False
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        """Inicia o worker em background."""
        if not self._enabled:
            logger.info("PncpSyncService desabilitado (PNCP_SYNC_ENABLED=false)")
            return
        self._is_running = True
        self._task = asyncio.create_task(self._worker())
        logger.info(
            f"PncpSyncService iniciado (interval={self._interval}s, "
            f"lookback={self._lookback_days}d)",
        )

    async def stop(self) -> None:
        """Para o worker."""
        self._is_running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("PncpSyncService parado")

    async def _worker(self) -> None:
        """Loop principal do worker."""
        while self._is_running:
            try:
                await self._sync_all()
            except Exception:
                logger.error("Erro no PncpSyncService", exc_info=True)
            await asyncio.sleep(self._interval)

    async def _sync_all(self) -> None:
        """Sincroniza todos os monitores ativos."""
        # Late imports para evitar circular deps
        from database import SessionLocal
        from repositories.pncp_repository import pncp_monitoramento_repository

        db = SessionLocal()
        try:
            monitores = pncp_monitoramento_repository.get_ativos(db)
            if not monitores:
                return

            logger.info(f"Sincronizando {len(monitores)} monitores PNCP")
            for monitor in monitores:
                try:
                    await self._sync_monitor(db, monitor)
                except Exception:
                    logger.error(
                        f"Erro ao sincronizar monitor {monitor.id}",
                        exc_info=True,
                    )
        finally:
            db.close()

    async def _sync_monitor(self, db: Any, monitor: Any) -> None:
        """Sincroniza um monitor específico com o PNCP."""
        from models.pncp import PncpResultado
        from repositories.pncp_repository import (
            pncp_monitoramento_repository,
            pncp_resultado_repository,
        )
        from services.notification.notification_service import notification_service
        from services.pncp.client import pncp_client
        from services.pncp.mapper import pncp_mapper
        from services.pncp.matcher import pncp_matcher

        # Calcular range de datas
        agora = datetime.now(timezone.utc)
        data_final = agora.strftime("%Y%m%d")
        data_inicial = (agora - timedelta(days=self._lookback_days)).strftime("%Y%m%d")

        # Buscar resultados no PNCP
        # A API exige codigoModalidadeContratacao; iterar por modalidades do monitor
        # Se nenhuma modalidade definida, usar as mais comuns (pregão + concorrência)
        ufs = monitor.ufs or [None]
        modalidades = monitor.modalidades or ["4", "5", "6", "7", "8"]
        todos_items = []
        for modalidade in modalidades:
            for uf in ufs:
                kwargs: dict[str, Any] = {"codigo_modalidade": str(modalidade)}
                if uf:
                    kwargs["uf"] = uf
                items = await pncp_client.buscar_todas_paginas(
                    data_inicial=data_inicial,
                    data_final=data_final,
                    max_paginas=5,
                    **kwargs,
                )
                todos_items.extend(items)

        # Filtrar por critérios do monitor
        filtrados = pncp_matcher.filtrar_resultados(todos_items, monitor)

        # Deduplicar e salvar novos
        novos_count = 0
        for item in filtrados:
            numero_controle = item.get("numeroControlePNCP", "")
            if not numero_controle:
                continue
            if pncp_resultado_repository.existe_resultado(
                db, numero_controle, monitor.user_id,
            ):
                continue

            dados = pncp_mapper.extrair_resultado(item, monitor.id, monitor.user_id)
            resultado = PncpResultado(**dados)
            pncp_resultado_repository.create(db, resultado)
            novos_count += 1

        # Notificar se houver novos resultados
        if novos_count > 0:
            from models.lembrete import NotificacaoTipo

            notification_service.notify(
                db=db,
                user_id=monitor.user_id,
                titulo=f"PNCP: {novos_count} nova(s) licitação(ões)",
                mensagem=(
                    f"O monitor '{monitor.nome}' encontrou {novos_count} "
                    f"nova(s) licitação(ões) no PNCP."
                ),
                tipo=NotificacaoTipo.PNCP_NOVA_LICITACAO,
                link="/monitoramento.html",
                referencia_tipo="pncp_monitoramento",
                referencia_id=monitor.id,
            )
            logger.info(
                f"Monitor {monitor.id} ('{monitor.nome}'): {novos_count} novos resultados",
            )

        # Atualizar último check
        pncp_monitoramento_repository.atualizar_ultimo_check(db, monitor.id, agora)


pncp_sync_service = PncpSyncService()
