"""
Repositorio para operacoes de Lembrete.
"""
from datetime import datetime
from typing import List, Optional

from sqlalchemy.orm import Session

from models.lembrete import Lembrete, LembreteStatus
from repositories.base import BaseRepository


class LembreteRepository(BaseRepository[Lembrete]):
    def __init__(self):
        super().__init__(Lembrete)

    def get_calendario(
        self,
        db: Session,
        user_id: int,
        data_inicio: datetime,
        data_fim: datetime,
    ) -> List[Lembrete]:
        """Lembretes por range de data (para calendario)."""
        return (
            db.query(Lembrete)
            .filter(
                Lembrete.user_id == user_id,
                Lembrete.data_lembrete >= data_inicio,
                Lembrete.data_lembrete <= data_fim,
            )
            .order_by(Lembrete.data_lembrete.asc())
            .all()
        )

    def get_pendentes_para_envio(
        self, db: Session, antes_de: datetime
    ) -> List[Lembrete]:
        """Lembretes pendentes com data_lembrete <= antes_de."""
        return (
            db.query(Lembrete)
            .filter(
                Lembrete.status == LembreteStatus.PENDENTE,
                Lembrete.data_lembrete <= antes_de,
            )
            .all()
        )

    def get_filtered(
        self,
        db: Session,
        user_id: int,
        status: Optional[str] = None,
        tipo: Optional[str] = None,
        licitacao_id: Optional[int] = None,
    ):
        """Query filtravel para paginacao."""
        query = db.query(Lembrete).filter(Lembrete.user_id == user_id)
        if status:
            query = query.filter(Lembrete.status == status)
        if tipo:
            query = query.filter(Lembrete.tipo == tipo)
        if licitacao_id is not None:
            query = query.filter(Lembrete.licitacao_id == licitacao_id)
        return query.order_by(Lembrete.data_lembrete.desc())

    def marcar_enviado(self, db: Session, lembrete: Lembrete) -> Lembrete:
        """Marca status=enviado + enviado_em=now()."""
        lembrete.status = LembreteStatus.ENVIADO
        lembrete.enviado_em = datetime.now()
        db.commit()
        db.refresh(lembrete)
        return lembrete


lembrete_repository = LembreteRepository()
