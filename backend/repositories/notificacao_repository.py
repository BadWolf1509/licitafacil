"""
Repositório para operações de Notificação.
"""
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from models.lembrete import Notificacao
from repositories.base import BaseRepository


class NotificacaoRepository(BaseRepository[Notificacao]):
    def __init__(self):
        super().__init__(Notificacao)

    def count_nao_lidas(self, db: Session, user_id: int) -> int:
        """Conta notificações não lidas do usuário."""
        return (
            db.query(Notificacao)
            .filter(
                Notificacao.user_id == user_id,
                Notificacao.lida == False,  # noqa: E712
            )
            .count()
        )

    def get_filtered(
        self,
        db: Session,
        user_id: int,
        lida: Optional[bool] = None,
        tipo: Optional[str] = None,
    ):
        """Query filtrável para paginação."""
        query = db.query(Notificacao).filter(Notificacao.user_id == user_id)
        if lida is not None:
            query = query.filter(Notificacao.lida == lida)
        if tipo:
            query = query.filter(Notificacao.tipo == tipo)
        return query.order_by(Notificacao.created_at.desc())

    def marcar_lida(self, db: Session, notificacao: Notificacao) -> Notificacao:
        """Marca notificação como lida."""
        notificacao.lida = True
        notificacao.lida_em = datetime.now()
        db.commit()
        db.refresh(notificacao)
        return notificacao

    def marcar_todas_lidas(self, db: Session, user_id: int) -> int:
        """Marca todas as notificações do usuário como lidas. Retorna count."""
        count = (
            db.query(Notificacao)
            .filter(
                Notificacao.user_id == user_id,
                Notificacao.lida == False,  # noqa: E712
            )
            .update(
                {"lida": True, "lida_em": datetime.now()},
                synchronize_session=False,
            )
        )
        db.commit()
        return count


notificacao_repository = NotificacaoRepository()
