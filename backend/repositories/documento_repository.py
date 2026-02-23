"""Repositório para operações de DocumentoLicitacao e ChecklistEdital."""
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from sqlalchemy import func as sa_func
from sqlalchemy.orm import Session

from models.documento import (
    ChecklistEdital,
    DocumentoLicitacao,
    DocumentoStatus,
)
from repositories.base import BaseRepository


class DocumentoLicitacaoRepository(BaseRepository[DocumentoLicitacao]):
    """Repositório de documentos de licitação."""

    def __init__(self) -> None:
        super().__init__(DocumentoLicitacao)

    def get_filtered(
        self,
        db: Session,
        user_id: int,
        tipo_documento: Optional[str] = None,
        status: Optional[str] = None,
        licitacao_id: Optional[int] = None,
        busca: Optional[str] = None,
    ):
        """Retorna query filtrável para paginação."""
        query = db.query(DocumentoLicitacao).filter(
            DocumentoLicitacao.user_id == user_id,
        )
        if tipo_documento:
            query = query.filter(DocumentoLicitacao.tipo_documento == tipo_documento)
        if status:
            query = query.filter(DocumentoLicitacao.status == status)
        if licitacao_id is not None:
            query = query.filter(DocumentoLicitacao.licitacao_id == licitacao_id)
        if busca:
            busca_like = f"%{busca}%"
            query = query.filter(DocumentoLicitacao.nome.ilike(busca_like))
        return query.order_by(DocumentoLicitacao.created_at.desc())

    def get_by_licitacao(
        self, db: Session, licitacao_id: int, user_id: int,
    ) -> List[DocumentoLicitacao]:
        """Documentos de uma licitação específica."""
        return (
            db.query(DocumentoLicitacao)
            .filter(
                DocumentoLicitacao.licitacao_id == licitacao_id,
                DocumentoLicitacao.user_id == user_id,
            )
            .order_by(DocumentoLicitacao.tipo_documento, DocumentoLicitacao.nome)
            .all()
        )

    def get_vencendo(
        self, db: Session, user_id: int, dias: int = 30,
    ) -> List[DocumentoLicitacao]:
        """Documentos vencendo nos próximos N dias."""
        agora = datetime.now(timezone.utc)
        limite = agora + timedelta(days=dias)
        return (
            db.query(DocumentoLicitacao)
            .filter(
                DocumentoLicitacao.user_id == user_id,
                DocumentoLicitacao.data_validade.isnot(None),
                DocumentoLicitacao.data_validade <= limite,
                DocumentoLicitacao.data_validade > agora,
                DocumentoLicitacao.status != DocumentoStatus.NAO_APLICAVEL,
            )
            .order_by(DocumentoLicitacao.data_validade)
            .all()
        )

    def get_vencidos(
        self, db: Session, user_id: int,
    ) -> List[DocumentoLicitacao]:
        """Documentos já vencidos."""
        agora = datetime.now(timezone.utc)
        return (
            db.query(DocumentoLicitacao)
            .filter(
                DocumentoLicitacao.user_id == user_id,
                DocumentoLicitacao.data_validade.isnot(None),
                DocumentoLicitacao.data_validade <= agora,
            )
            .order_by(DocumentoLicitacao.data_validade)
            .all()
        )

    def get_resumo(self, db: Session, user_id: int) -> Dict:
        """Resumo de saúde documental (contagem por status)."""
        base = db.query(DocumentoLicitacao).filter(
            DocumentoLicitacao.user_id == user_id,
        )
        total = base.count()
        por_status: dict[str, int] = {
            row[0]: row[1]
            for row in base.with_entities(
                DocumentoLicitacao.status, sa_func.count(DocumentoLicitacao.id),
            )
            .group_by(DocumentoLicitacao.status)
            .all()
        }
        return {
            "total": total,
            "validos": por_status.get(DocumentoStatus.VALIDO, 0),
            "vencendo": por_status.get(DocumentoStatus.VENCENDO, 0),
            "vencidos": por_status.get(DocumentoStatus.VENCIDO, 0),
            "nao_aplicavel": por_status.get(DocumentoStatus.NAO_APLICAVEL, 0),
        }

    def atualizar_status_validade(self, db: Session, dias_alerta: int = 30) -> int:
        """Atualiza status de todos os documentos com base na data_validade."""
        agora = datetime.now(timezone.utc)
        limite = agora + timedelta(days=dias_alerta)
        count = 0

        # Marcar vencidos
        vencidos = (
            db.query(DocumentoLicitacao)
            .filter(
                DocumentoLicitacao.data_validade.isnot(None),
                DocumentoLicitacao.data_validade <= agora,
                DocumentoLicitacao.status != DocumentoStatus.VENCIDO,
                DocumentoLicitacao.status != DocumentoStatus.NAO_APLICAVEL,
            )
            .all()
        )
        for doc in vencidos:
            doc.status = DocumentoStatus.VENCIDO
            count += 1

        # Marcar vencendo
        vencendo = (
            db.query(DocumentoLicitacao)
            .filter(
                DocumentoLicitacao.data_validade.isnot(None),
                DocumentoLicitacao.data_validade > agora,
                DocumentoLicitacao.data_validade <= limite,
                DocumentoLicitacao.status == DocumentoStatus.VALIDO,
            )
            .all()
        )
        for doc in vencendo:
            doc.status = DocumentoStatus.VENCENDO
            count += 1

        # Reverter válidos (se data_validade foi atualizada para o futuro)
        revalidados = (
            db.query(DocumentoLicitacao)
            .filter(
                DocumentoLicitacao.data_validade.isnot(None),
                DocumentoLicitacao.data_validade > limite,
                DocumentoLicitacao.status.in_([
                    DocumentoStatus.VENCENDO, DocumentoStatus.VENCIDO,
                ]),
            )
            .all()
        )
        for doc in revalidados:
            doc.status = DocumentoStatus.VALIDO
            count += 1

        if count > 0:
            db.commit()
        return count


documento_repository = DocumentoLicitacaoRepository()


class ChecklistRepository(BaseRepository[ChecklistEdital]):
    """Repositório de checklist de edital."""

    def __init__(self) -> None:
        super().__init__(ChecklistEdital)

    def get_by_licitacao(
        self, db: Session, licitacao_id: int, user_id: int,
    ) -> List[ChecklistEdital]:
        """Itens do checklist de uma licitação, ordenados."""
        return (
            db.query(ChecklistEdital)
            .filter(
                ChecklistEdital.licitacao_id == licitacao_id,
                ChecklistEdital.user_id == user_id,
            )
            .order_by(ChecklistEdital.ordem, ChecklistEdital.id)
            .all()
        )

    def get_item_for_user(
        self, db: Session, item_id: int, user_id: int,
    ) -> Optional[ChecklistEdital]:
        """Busca item específico validando ownership."""
        return (
            db.query(ChecklistEdital)
            .filter(
                ChecklistEdital.id == item_id,
                ChecklistEdital.user_id == user_id,
            )
            .first()
        )

    def get_resumo(self, db: Session, licitacao_id: int, user_id: int) -> Dict:
        """Resumo de progresso do checklist."""
        itens = self.get_by_licitacao(db, licitacao_id, user_id)
        total = len(itens)
        cumpridos = sum(1 for i in itens if i.cumprido)
        obrigatorios_pendentes = sum(
            1 for i in itens if i.obrigatorio and not i.cumprido
        )
        return {
            "licitacao_id": licitacao_id,
            "total": total,
            "cumpridos": cumpridos,
            "pendentes": total - cumpridos,
            "obrigatorios_pendentes": obrigatorios_pendentes,
            "percentual": round((cumpridos / total * 100) if total > 0 else 0, 1),
        }

    def bulk_create_items(
        self,
        db: Session,
        licitacao_id: int,
        user_id: int,
        itens: list,
    ) -> List[ChecklistEdital]:
        """Cria múltiplos itens de checklist de uma vez."""
        novos = []
        for i, item_data in enumerate(itens):
            item = ChecklistEdital(
                licitacao_id=licitacao_id,
                user_id=user_id,
                descricao=item_data["descricao"],
                tipo_documento=item_data.get("tipo_documento"),
                obrigatorio=item_data.get("obrigatorio", True),
                observacao=item_data.get("observacao"),
                ordem=item_data.get("ordem", i),
            )
            db.add(item)
            novos.append(item)
        db.commit()
        for item in novos:
            db.refresh(item)
        return novos


checklist_repository = ChecklistRepository()
