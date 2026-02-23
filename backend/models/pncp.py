"""Modelos de monitoramento PNCP."""
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
)
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from database import Base

if TYPE_CHECKING:
    from models.licitacao import Licitacao
    from models.usuario import Usuario


class PncpResultadoStatus:
    """Status de um resultado PNCP."""

    NOVO = "novo"
    INTERESSANTE = "interessante"
    DESCARTADO = "descartado"
    IMPORTADO = "importado"
    ALL = [NOVO, INTERESSANTE, DESCARTADO, IMPORTADO]


class PncpMonitoramento(Base):
    """Monitor de busca PNCP configurado pelo usuário."""

    __tablename__ = "pncp_monitoramentos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    nome: Mapped[str] = mapped_column(String(200), nullable=False)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    palavras_chave: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    ufs: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    modalidades: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    esferas: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    valor_minimo: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(18, 2), nullable=True,
    )
    valor_maximo: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(18, 2), nullable=True,
    )
    ultimo_check: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
    )

    usuario: Mapped["Usuario"] = relationship("Usuario")
    resultados: Mapped[List["PncpResultado"]] = relationship(
        "PncpResultado", back_populates="monitoramento", cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_pncp_monitor_user_ativo", "user_id", "ativo"),
    )


class PncpResultado(Base):
    """Resultado encontrado no PNCP por um monitoramento."""

    __tablename__ = "pncp_resultados"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    monitoramento_id: Mapped[int] = mapped_column(
        ForeignKey("pncp_monitoramentos.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    numero_controle_pncp: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True,
    )
    orgao_cnpj: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    orgao_razao_social: Mapped[Optional[str]] = mapped_column(
        String(500), nullable=True,
    )
    objeto_compra: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    modalidade_nome: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True,
    )
    uf: Mapped[Optional[str]] = mapped_column(String(2), nullable=True, index=True)
    municipio: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    valor_estimado: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(18, 2), nullable=True,
    )
    data_abertura: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    data_encerramento: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    link_sistema_origem: Mapped[Optional[str]] = mapped_column(
        String(1000), nullable=True,
    )
    dados_completos: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=PncpResultadoStatus.NOVO, index=True,
    )
    licitacao_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("licitacoes.id", ondelete="SET NULL"), nullable=True,
    )
    encontrado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
    )

    monitoramento: Mapped["PncpMonitoramento"] = relationship(
        "PncpMonitoramento", back_populates="resultados",
    )
    usuario: Mapped["Usuario"] = relationship("Usuario")
    licitacao: Mapped[Optional["Licitacao"]] = relationship("Licitacao")

    __table_args__ = (
        Index("ix_pncp_resultado_user_status", "user_id", "status"),
        Index("ix_pncp_resultado_controle_user", "numero_controle_pncp", "user_id"),
    )
