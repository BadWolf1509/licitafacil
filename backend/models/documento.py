"""Modelos de gestão documental."""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from database import Base

if TYPE_CHECKING:
    from models.licitacao import Licitacao
    from models.usuario import Usuario


class DocumentoTipo:
    """Tipos de documento de licitação."""

    EDITAL = "edital"
    CERTIDAO_NEGATIVA = "certidao_negativa"
    BALANCO = "balanco"
    CONTRATO_SOCIAL = "contrato_social"
    PROCURACAO = "procuracao"
    DECLARACAO = "declaracao"
    PLANILHA = "planilha"
    ATESTADO_CAPACIDADE = "atestado_capacidade"
    COMPROVANTE_ENDERECO = "comprovante_endereco"
    CERTIDAO_FGTS = "certidao_fgts"
    CERTIDAO_TRABALHISTA = "certidao_trabalhista"
    CERTIDAO_FEDERAL = "certidao_federal"
    CERTIDAO_ESTADUAL = "certidao_estadual"
    CERTIDAO_MUNICIPAL = "certidao_municipal"
    OUTRO = "outro"
    ALL = [
        EDITAL, CERTIDAO_NEGATIVA, BALANCO, CONTRATO_SOCIAL,
        PROCURACAO, DECLARACAO, PLANILHA, ATESTADO_CAPACIDADE,
        COMPROVANTE_ENDERECO, CERTIDAO_FGTS, CERTIDAO_TRABALHISTA,
        CERTIDAO_FEDERAL, CERTIDAO_ESTADUAL, CERTIDAO_MUNICIPAL,
        OUTRO,
    ]


class DocumentoStatus:
    """Status de validade do documento."""

    VALIDO = "valido"
    VENCENDO = "vencendo"
    VENCIDO = "vencido"
    NAO_APLICAVEL = "nao_aplicavel"
    ALL = [VALIDO, VENCENDO, VENCIDO, NAO_APLICAVEL]


class DocumentoLicitacao(Base):
    """Documento vinculado a uma licitação ou ao acervo geral do usuário."""

    __tablename__ = "documentos_licitacao"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    licitacao_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("licitacoes.id", ondelete="SET NULL"), nullable=True, index=True,
    )
    nome: Mapped[str] = mapped_column(String(255), nullable=False)
    tipo_documento: Mapped[str] = mapped_column(String(100), nullable=False)
    arquivo_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    tamanho_bytes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    data_emissao: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    data_validade: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True,
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=DocumentoStatus.VALIDO,
    )
    obrigatorio: Mapped[bool] = mapped_column(Boolean, default=False)
    observacoes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(),
    )

    usuario: Mapped["Usuario"] = relationship("Usuario")
    licitacao: Mapped[Optional["Licitacao"]] = relationship("Licitacao")

    __table_args__ = (
        Index("ix_documentos_user_tipo", "user_id", "tipo_documento"),
        Index("ix_documentos_user_status", "user_id", "status"),
        Index("ix_documentos_user_licitacao", "user_id", "licitacao_id"),
        Index("ix_documentos_validade_status", "data_validade", "status"),
    )


class ChecklistEdital(Base):
    """Item obrigatório de um edital de licitação."""

    __tablename__ = "checklist_edital"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    licitacao_id: Mapped[int] = mapped_column(
        ForeignKey("licitacoes.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False,
    )
    descricao: Mapped[str] = mapped_column(Text, nullable=False)
    tipo_documento: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    obrigatorio: Mapped[bool] = mapped_column(Boolean, default=True)
    cumprido: Mapped[bool] = mapped_column(Boolean, default=False)
    documento_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("documentos_licitacao.id", ondelete="SET NULL"), nullable=True,
    )
    observacao: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ordem: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
    )

    licitacao: Mapped["Licitacao"] = relationship("Licitacao")
    usuario: Mapped["Usuario"] = relationship("Usuario")
    documento: Mapped[Optional["DocumentoLicitacao"]] = relationship("DocumentoLicitacao")

    __table_args__ = (
        Index("ix_checklist_licitacao_ordem", "licitacao_id", "ordem"),
    )
