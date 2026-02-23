"""
Worker background que processa lembretes pendentes e verifica validade de documentos.
"""
import asyncio
import time
from datetime import datetime, timedelta, timezone

from config.base import (
    DOCUMENT_EXPIRY_CHECK_INTERVAL,
    REMINDER_CHECK_INTERVAL,
    REMINDER_LOOKAHEAD_MINUTES,
)
from logging_config import get_logger

logger = get_logger("services.notification.scheduler")


class ReminderScheduler:
    """Worker que verifica periodicamente lembretes pendentes e dispara notificacoes."""

    def __init__(self):
        self._is_running = False
        self._task = None
        self._check_interval = REMINDER_CHECK_INTERVAL
        self._lookahead_minutes = REMINDER_LOOKAHEAD_MINUTES
        self._doc_check_interval = DOCUMENT_EXPIRY_CHECK_INTERVAL
        self._last_doc_check: float = 0

    async def start(self):
        """Inicia o worker em background."""
        self._is_running = True
        self._task = asyncio.create_task(self._worker())
        logger.info(
            f"ReminderScheduler iniciado (interval={self._check_interval}s, "
            f"lookahead={self._lookahead_minutes}min)"
        )

    async def stop(self):
        """Para o worker."""
        self._is_running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("ReminderScheduler parado")

    async def _worker(self):
        """Loop principal do worker."""
        while self._is_running:
            try:
                await self._check_lembretes()
            except Exception:
                logger.error("Erro no ReminderScheduler (lembretes)", exc_info=True)

            # Verificar documentos vencendo (intervalo mais longo)
            try:
                now = time.time()
                if now - self._last_doc_check >= self._doc_check_interval:
                    from services.notification.document_checker import document_checker
                    await document_checker.check()
                    self._last_doc_check = now
            except Exception:
                logger.error("Erro no ReminderScheduler (documentos)", exc_info=True)

            await asyncio.sleep(self._check_interval)

    async def _check_lembretes(self):
        """Busca lembretes pendentes e dispara notificacoes."""
        # Late imports para evitar circular deps
        from database import SessionLocal
        from repositories.lembrete_repository import lembrete_repository
        from services.notification.notification_service import notification_service

        antes_de = datetime.now(timezone.utc) + timedelta(minutes=self._lookahead_minutes)

        db = SessionLocal()
        try:
            pendentes = lembrete_repository.get_pendentes_para_envio(db, antes_de)
            if not pendentes:
                return

            logger.info(f"Processando {len(pendentes)} lembretes pendentes")
            for lembrete in pendentes:
                try:
                    notification_service.notify_lembrete(db, lembrete)
                    lembrete_repository.marcar_enviado(db, lembrete)
                    logger.info(f"Lembrete {lembrete.id} processado")
                except Exception:
                    logger.error(
                        f"Erro ao processar lembrete {lembrete.id}", exc_info=True
                    )
        finally:
            db.close()


reminder_scheduler = ReminderScheduler()
