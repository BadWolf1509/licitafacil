from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from database import Base

if TYPE_CHECKING:
    from models.usuario import Usuario

# === Status Constants ===


class LicitacaoStatus:
    """Status possíveis de uma licitação e suas transições."""

    IDENTIFICADA = "identificada"
    EM_ANALISE = "em_analise"
    GO_NOGO = "go_nogo"
    ELABORANDO_PROPOSTA = "elaborando_proposta"
    PROPOSTA_ENVIADA = "proposta_enviada"
    EM_DISPUTA = "em_disputa"
    VENCIDA = "vencida"
    PERDIDA = "perdida"
    CONTRATO_ASSINADO = "contrato_assinado"
    EM_EXECUCAO = "em_execucao"
    CONCLUIDA = "concluida"
    DESISTIDA = "desistida"
    CANCELADA = "cancelada"

    ALL = [
        IDENTIFICADA, EM_ANALISE, GO_NOGO, ELABORANDO_PROPOSTA,
        PROPOSTA_ENVIADA, EM_DISPUTA, VENCIDA, PERDIDA,
        CONTRATO_ASSINADO, EM_EXECUCAO, CONCLUIDA,
        DESISTIDA, CANCELADA,
    ]

    # Mapa de transições válidas: status_atual -> [status_destino_permitidos]
    TRANSITIONS = {
        IDENTIFICADA: [EM_ANALISE, DESISTIDA, CANCELADA],
        EM_ANALISE: [GO_NOGO, DESISTIDA, CANCELADA],
        GO_NOGO: [ELABORANDO_PROPOSTA, DESISTIDA, CANCELADA],
        ELABORANDO_PROPOSTA: [PROPOSTA_ENVIADA, DESISTIDA, CANCELADA],
        PROPOSTA_ENVIADA: [EM_DISPUTA, DESISTIDA, CANCELADA],
        EM_DISPUTA: [VENCIDA, PERDIDA, CANCELADA],
        VENCIDA: [CONTRATO_ASSINADO, CANCELADA],
        PERDIDA: [],  # Estado final
        CONTRATO_ASSINADO: [EM_EXECUCAO, CANCELADA],
        EM_EXECUCAO: [CONCLUIDA, CANCELADA],
        CONCLUIDA: [],  # Estado final
        DESISTIDA: [],  # Estado final
        CANCELADA: [],  # Estado final
    }

    # Labels amigáveis para o frontend
    LABELS = {
        IDENTIFICADA: "Identificada",
        EM_ANALISE: "Em Análise",
        GO_NOGO: "GO/NO-GO",
        ELABORANDO_PROPOSTA: "Elaborando Proposta",
        PROPOSTA_ENVIADA: "Proposta Enviada",
        EM_DISPUTA: "Em Disputa",
        VENCIDA: "Vencida",
        PERDIDA: "Perdida",
        CONTRATO_ASSINADO: "Contrato Assinado",
        EM_EXECUCAO: "Em Execução",
        CONCLUIDA: "Concluída",
        DESISTIDA: "Desistida",
        CANCELADA: "Cancelada",
    }


class LicitacaoFonte:
    """Fontes de origem de uma licitação."""

    MANUAL = "manual"
    PNCP = "pncp"
    IMPORTADO = "importado"


class Licitacao(Base):
    """Entidade central: uma licitação que o usuário acompanha."""

    __tablename__ = "licitacoes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True
    )

    numero: Mapped[str] = mapped_column(String(100), nullable=False)
    orgao: Mapped[str] = mapped_column(String(500), nullable=False)
    objeto: Mapped[str] = mapped_column(Text, nullable=False)
    modalidade: Mapped[str] = mapped_column(String(100), nullable=False)

    numero_controle_pncp: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, unique=True, index=True
    )

    valor_estimado: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2), nullable=True)
    valor_homologado: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2), nullable=True)
    valor_proposta: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2), nullable=True)

    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default=LicitacaoStatus.IDENTIFICADA, index=True
    )
    decisao_go: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    motivo_nogo: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    data_publicacao: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    data_abertura: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    data_encerramento: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    data_resultado: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    uf: Mapped[Optional[str]] = mapped_column(String(2), nullable=True, index=True)
    municipio: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    esfera: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    link_edital: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    link_sistema_origem: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)

    observacoes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    fonte: Mapped[str] = mapped_column(String(30), nullable=False, default=LicitacaoFonte.MANUAL)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    usuario: Mapped["Usuario"] = relationship("Usuario", backref="licitacoes")
    tags: Mapped[List["LicitacaoTag"]] = relationship(
        "LicitacaoTag", back_populates="licitacao", cascade="all, delete-orphan"
    )
    historico: Mapped[List["LicitacaoHistorico"]] = relationship(
        "LicitacaoHistorico", back_populates="licitacao", cascade="all, delete-orphan",
        order_by="LicitacaoHistorico.created_at.desc()"
    )

    __table_args__ = (
        Index('ix_licitacoes_user_status', 'user_id', 'status'),
        Index('ix_licitacoes_user_created', 'user_id', 'created_at'),
        Index('ix_licitacoes_uf_modalidade', 'uf', 'modalidade'),
    )


class LicitacaoTag(Base):
    """Tags livres associadas a uma licitação."""

    __tablename__ = "licitacao_tags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    licitacao_id: Mapped[int] = mapped_column(
        ForeignKey("licitacoes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tag: Mapped[str] = mapped_column(String(100), nullable=False, index=True)

    licitacao: Mapped["Licitacao"] = relationship("Licitacao", back_populates="tags")

    __table_args__ = (
        UniqueConstraint('licitacao_id', 'tag', name='uq_licitacao_tag'),
    )


class LicitacaoHistorico(Base):
    """Log de mudanças de status de uma licitação."""

    __tablename__ = "licitacao_historico"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    licitacao_id: Mapped[int] = mapped_column(
        ForeignKey("licitacoes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    status_anterior: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    status_novo: Mapped[str] = mapped_column(String(30), nullable=False)
    observacao: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    licitacao: Mapped["Licitacao"] = relationship("Licitacao", back_populates="historico")

    __table_args__ = (
        Index('ix_historico_licitacao_created', 'licitacao_id', 'created_at'),
    )
