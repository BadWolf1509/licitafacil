"""Repositórios para monitoramento PNCP."""
from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy import func as sa_func
from sqlalchemy.orm import Session

from models.pncp import PncpMonitoramento, PncpResultado
from repositories.base import BaseRepository


class PncpMonitoramentoRepository(BaseRepository[PncpMonitoramento]):
    """Repositório de monitoramentos PNCP."""

    def __init__(self) -> None:
        super().__init__(PncpMonitoramento)

    def get_filtered(
        self,
        db: Session,
        user_id: int,
        ativo: Optional[bool] = None,
        busca: Optional[str] = None,
    ):
        """Retorna query filtrável para paginação."""
        query = db.query(PncpMonitoramento).filter(
            PncpMonitoramento.user_id == user_id,
        )
        if ativo is not None:
            query = query.filter(PncpMonitoramento.ativo == ativo)
        if busca:
            busca_like = f"%{busca}%"
            query = query.filter(PncpMonitoramento.nome.ilike(busca_like))
        return query.order_by(PncpMonitoramento.created_at.desc())

    def get_ativos(self, db: Session) -> List[PncpMonitoramento]:
        """Retorna todos os monitoramentos ativos (para sync service)."""
        return (
            db.query(PncpMonitoramento)
            .filter(PncpMonitoramento.ativo.is_(True))
            .all()
        )

    def atualizar_ultimo_check(
        self, db: Session, monitoramento_id: int, data: datetime,
    ) -> None:
        """Atualiza timestamp do último check."""
        monitor = db.query(PncpMonitoramento).filter(
            PncpMonitoramento.id == monitoramento_id,
        ).first()
        if monitor:
            monitor.ultimo_check = data
            db.commit()


pncp_monitoramento_repository = PncpMonitoramentoRepository()


class PncpResultadoRepository(BaseRepository[PncpResultado]):
    """Repositório de resultados PNCP."""

    def __init__(self) -> None:
        super().__init__(PncpResultado)

    def get_filtered(
        self,
        db: Session,
        user_id: int,
        monitoramento_id: Optional[int] = None,
        status: Optional[str] = None,
        uf: Optional[str] = None,
        busca: Optional[str] = None,
    ):
        """Retorna query filtrável para paginação."""
        query = db.query(PncpResultado).filter(
            PncpResultado.user_id == user_id,
        )
        if monitoramento_id is not None:
            query = query.filter(PncpResultado.monitoramento_id == monitoramento_id)
        if status:
            query = query.filter(PncpResultado.status == status)
        if uf:
            query = query.filter(PncpResultado.uf == uf)
        if busca:
            busca_like = f"%{busca}%"
            query = query.filter(
                PncpResultado.objeto_compra.ilike(busca_like)
                | PncpResultado.orgao_razao_social.ilike(busca_like),
            )
        return query.order_by(PncpResultado.encontrado_em.desc())

    def existe_resultado(
        self, db: Session, numero_controle: str, user_id: int,
    ) -> bool:
        """Verifica se resultado já existe para o usuário (deduplicação)."""
        return (
            db.query(PncpResultado)
            .filter(
                PncpResultado.numero_controle_pncp == numero_controle,
                PncpResultado.user_id == user_id,
            )
            .first()
            is not None
        )

    def contar_por_status(self, db: Session, user_id: int) -> Dict[str, int]:
        """Conta resultados por status para o usuário."""
        rows = (
            db.query(PncpResultado.status, sa_func.count(PncpResultado.id))
            .filter(PncpResultado.user_id == user_id)
            .group_by(PncpResultado.status)
            .all()
        )
        return {row[0]: row[1] for row in rows}


pncp_resultado_repository = PncpResultadoRepository()
