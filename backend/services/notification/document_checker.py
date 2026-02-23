"""
Verificador de validade de documentos.
Integra-se com o ReminderScheduler existente.
"""
from datetime import datetime, timedelta, timezone

from config.base import DOCUMENT_EXPIRY_WARNING_DAYS
from logging_config import get_logger

logger = get_logger("services.notification.document_checker")


class DocumentExpiryChecker:
    """Verifica documentos vencendo e gera notificações."""

    async def check(self) -> None:
        """
        Chamado periodicamente pelo ReminderScheduler.
        1. Atualiza status de validade de todos os documentos
        2. Notifica usuários sobre documentos que mudaram para 'vencendo'
        """
        # Late imports para evitar circular deps
        from database import SessionLocal
        from repositories.documento_repository import documento_repository

        db = SessionLocal()
        try:
            updated = documento_repository.atualizar_status_validade(
                db, dias_alerta=DOCUMENT_EXPIRY_WARNING_DAYS,
            )
            if updated > 0:
                logger.info(f"Atualizados {updated} status de documentos")

            self._notificar_vencimentos(db)
        except Exception:
            logger.error("Erro ao verificar validade de documentos", exc_info=True)
        finally:
            db.close()

    def _notificar_vencimentos(self, db) -> None:  # type: ignore[no-untyped-def]
        """Gera notificações para documentos vencendo."""
        from models.documento import DocumentoLicitacao, DocumentoStatus
        from models.lembrete import Notificacao, NotificacaoTipo
        from services.notification.notification_service import notification_service

        agora = datetime.now(timezone.utc)
        limite = agora + timedelta(days=DOCUMENT_EXPIRY_WARNING_DAYS)

        docs_vencendo = (
            db.query(DocumentoLicitacao)
            .filter(
                DocumentoLicitacao.data_validade.isnot(None),
                DocumentoLicitacao.data_validade > agora,
                DocumentoLicitacao.data_validade <= limite,
                DocumentoLicitacao.status == DocumentoStatus.VENCENDO,
            )
            .all()
        )

        for doc in docs_vencendo:
            # Verificar se já foi notificado (evita spam)
            ja_notificado = (
                db.query(Notificacao)
                .filter(
                    Notificacao.user_id == doc.user_id,
                    Notificacao.referencia_tipo == "documento",
                    Notificacao.referencia_id == doc.id,
                    Notificacao.tipo == NotificacaoTipo.DOCUMENTO_VENCENDO,
                )
                .first()
            )

            if not ja_notificado:
                dias_restantes = (doc.data_validade - agora).days
                notification_service.notify(
                    db=db,
                    user_id=doc.user_id,
                    titulo=f"Documento vencendo em {dias_restantes} dias",
                    mensagem=(
                        f'O documento "{doc.nome}" vence em '
                        f'{doc.data_validade.strftime("%d/%m/%Y")}.'
                    ),
                    tipo=NotificacaoTipo.DOCUMENTO_VENCENDO,
                    link=f"documentos.html?id={doc.id}",
                    referencia_tipo="documento",
                    referencia_id=doc.id,
                )


document_checker = DocumentExpiryChecker()
