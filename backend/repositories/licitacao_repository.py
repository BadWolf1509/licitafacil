"""
Repositorio para operacoes de Licitacao.
"""
from typing import Dict, List, Optional

from sqlalchemy import func as sa_func
from sqlalchemy.orm import Session, joinedload

from models.licitacao import (
    Licitacao,
    LicitacaoHistorico,
    LicitacaoStatus,
    LicitacaoTag,
)
from repositories.base import BaseRepository


class LicitacaoRepository(BaseRepository[Licitacao]):
    def __init__(self):
        super().__init__(Licitacao)

    def get_by_id_with_relations(
        self, db: Session, id: int, user_id: int
    ) -> Optional[Licitacao]:
        """Busca licitacao com tags e historico carregados."""
        return db.query(Licitacao).options(
            joinedload(Licitacao.tags),
            joinedload(Licitacao.historico),
        ).filter(
            Licitacao.id == id,
            Licitacao.user_id == user_id,
        ).first()

    def get_filtered(
        self,
        db: Session,
        user_id: int,
        status: Optional[str] = None,
        uf: Optional[str] = None,
        modalidade: Optional[str] = None,
        busca: Optional[str] = None,
    ):
        """Retorna query filtravel para paginacao."""
        query = db.query(Licitacao).filter(Licitacao.user_id == user_id)
        if status:
            query = query.filter(Licitacao.status == status)
        if uf:
            query = query.filter(Licitacao.uf == uf)
        if modalidade:
            query = query.filter(Licitacao.modalidade == modalidade)
        if busca:
            busca_like = f"%{busca}%"
            query = query.filter(
                (Licitacao.numero.ilike(busca_like))
                | (Licitacao.orgao.ilike(busca_like))
                | (Licitacao.objeto.ilike(busca_like))
            )
        return query.order_by(Licitacao.created_at.desc())

    def transition_status(
        self,
        db: Session,
        licitacao: Licitacao,
        novo_status: str,
        user_id: int,
        observacao: Optional[str] = None,
    ) -> LicitacaoHistorico:
        """Muda status e cria registro de historico."""
        status_anterior = licitacao.status
        licitacao.status = novo_status

        if novo_status == LicitacaoStatus.DESISTIDA and not licitacao.decisao_go:
            licitacao.decisao_go = False

        historico = LicitacaoHistorico(
            licitacao_id=licitacao.id,
            user_id=user_id,
            status_anterior=status_anterior,
            status_novo=novo_status,
            observacao=observacao,
        )
        db.add(historico)
        db.commit()
        db.refresh(licitacao)
        db.refresh(historico)
        return historico

    def add_tag(self, db: Session, licitacao_id: int, tag: str) -> LicitacaoTag:
        """Adiciona tag a uma licitacao."""
        nova_tag = LicitacaoTag(licitacao_id=licitacao_id, tag=tag.strip().lower())
        db.add(nova_tag)
        db.commit()
        db.refresh(nova_tag)
        return nova_tag

    def remove_tag(self, db: Session, licitacao_id: int, tag: str) -> bool:
        """Remove tag de uma licitacao."""
        result = db.query(LicitacaoTag).filter(
            LicitacaoTag.licitacao_id == licitacao_id,
            LicitacaoTag.tag == tag.strip().lower(),
        ).delete()
        db.commit()
        return result > 0

    def get_estatisticas(self, db: Session, user_id: int) -> Dict:
        """Retorna contagens agrupadas por status, uf e modalidade."""
        base = db.query(Licitacao).filter(Licitacao.user_id == user_id)

        total = base.count()

        por_status: dict[str, int] = {
            row[0]: row[1] for row in base.with_entities(
                Licitacao.status, sa_func.count(Licitacao.id)
            ).group_by(Licitacao.status).all()
        }

        por_uf: dict[str | None, int] = {
            row[0]: row[1] for row in base.filter(Licitacao.uf.isnot(None)).with_entities(
                Licitacao.uf, sa_func.count(Licitacao.id)
            ).group_by(Licitacao.uf).all()
        }

        por_modalidade: dict[str, int] = {
            row[0]: row[1] for row in base.with_entities(
                Licitacao.modalidade, sa_func.count(Licitacao.id)
            ).group_by(Licitacao.modalidade).all()
        }

        return {
            "total": total,
            "por_status": por_status,
            "por_uf": por_uf,
            "por_modalidade": por_modalidade,
        }

    def get_historico(
        self, db: Session, licitacao_id: int
    ) -> List[LicitacaoHistorico]:
        """Retorna historico de mudancas de status."""
        return (
            db.query(LicitacaoHistorico)
            .filter(LicitacaoHistorico.licitacao_id == licitacao_id)
            .order_by(LicitacaoHistorico.created_at.desc())
            .all()
        )


licitacao_repository = LicitacaoRepository()
