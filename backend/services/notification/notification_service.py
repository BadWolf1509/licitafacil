"""
Servico orquestrador de notificacoes.
"""
from typing import List, Optional

from sqlalchemy.orm import Session

from logging_config import get_logger
from models.lembrete import Lembrete, Notificacao, NotificacaoTipo
from repositories.notificacao_repository import notificacao_repository
from repositories.preferencia_repository import preferencia_repository
from services.notification.email_service import email_service

logger = get_logger("services.notification")


class NotificationService:
    """Cria notificacoes in-app e envia emails conforme preferencias."""

    def notify(
        self,
        db: Session,
        user_id: int,
        titulo: str,
        mensagem: str,
        tipo: str,
        canais: Optional[List[str]] = None,
        link: Optional[str] = None,
        referencia_tipo: Optional[str] = None,
        referencia_id: Optional[int] = None,
        user_email: Optional[str] = None,
    ) -> Optional[Notificacao]:
        """
        Cria notificacao in-app e envia email se configurado.

        1. Verifica preferencias do usuario
        2. Se app_habilitado: cria Notificacao no DB
        3. Se email em canais e email_habilitado: envia via EmailService
        """
        if canais is None:
            canais = ["app"]

        pref = preferencia_repository.get_or_create(db, user_id)
        notificacao = None

        # Notificacao in-app
        if pref.app_habilitado and "app" in canais:
            notificacao = Notificacao(
                user_id=user_id,
                titulo=titulo,
                mensagem=mensagem,
                tipo=tipo,
                link=link,
                referencia_tipo=referencia_tipo,
                referencia_id=referencia_id,
            )
            notificacao = notificacao_repository.create(db, notificacao)

        # Email
        if pref.email_habilitado and "email" in canais and user_email:
            html_body = email_service.render_lembrete(titulo, mensagem, None)
            email_service.send(user_email, f"LicitaFacil - {titulo}", html_body)

        return notificacao

    def notify_lembrete(self, db: Session, lembrete: Lembrete) -> Optional[Notificacao]:
        """Notifica sobre um lembrete disparado."""
        canais = lembrete.canais or ["app"]

        link = None
        if lembrete.licitacao_id:
            link = f"/licitacoes.html?id={lembrete.licitacao_id}"

        user_email = None
        if lembrete.usuario:
            user_email = lembrete.usuario.email

        return self.notify(
            db=db,
            user_id=lembrete.user_id,
            titulo=f"Lembrete: {lembrete.titulo}",
            mensagem=lembrete.descricao or lembrete.titulo,
            tipo=NotificacaoTipo.LEMBRETE,
            canais=canais,
            link=link,
            referencia_tipo="lembrete",
            referencia_id=lembrete.id,
            user_email=user_email,
        )


notification_service = NotificationService()
