"""
Repositorio para PreferenciaNotificacao.
"""
from sqlalchemy.orm import Session

from models.lembrete import PreferenciaNotificacao
from repositories.base import BaseRepository


class PreferenciaNotificacaoRepository(BaseRepository[PreferenciaNotificacao]):
    def __init__(self):
        super().__init__(PreferenciaNotificacao)

    def get_or_create(
        self, db: Session, user_id: int
    ) -> PreferenciaNotificacao:
        """Busca preferencias do usuario ou cria com defaults."""
        pref = (
            db.query(PreferenciaNotificacao)
            .filter(PreferenciaNotificacao.user_id == user_id)
            .first()
        )
        if pref is None:
            pref = PreferenciaNotificacao(user_id=user_id)
            db.add(pref)
            db.commit()
            db.refresh(pref)
        return pref


preferencia_repository = PreferenciaNotificacaoRepository()
