from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    JSON,
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

# === Constantes ===


class LembreteTipo:
    MANUAL = "manual"
    ABERTURA_LICITACAO = "abertura_licitacao"
    ENCERRAMENTO_PROPOSTA = "encerramento_proposta"
    VENCIMENTO_DOCUMENTO = "vencimento_documento"
    ENTREGA_CONTRATO = "entrega_contrato"
    PRAZO_RECURSO = "prazo_recurso"
    ALL = [
        MANUAL, ABERTURA_LICITACAO, ENCERRAMENTO_PROPOSTA,
        VENCIMENTO_DOCUMENTO, ENTREGA_CONTRATO, PRAZO_RECURSO,
    ]


class LembreteStatus:
    PENDENTE = "pendente"
    ENVIADO = "enviado"
    LIDO = "lido"
    CANCELADO = "cancelado"
    ALL = [PENDENTE, ENVIADO, LIDO, CANCELADO]


class LembreteRecorrencia:
    DIARIO = "diario"
    SEMANAL = "semanal"
    MENSAL = "mensal"
    ALL = [DIARIO, SEMANAL, MENSAL]


class NotificacaoTipo:
    LEMBRETE = "lembrete"
    DOCUMENTO_VENCENDO = "documento_vencendo"
    LICITACAO_ATUALIZADA = "licitacao_atualizada"
    PNCP_NOVA_LICITACAO = "pncp_nova_licitacao"
    CONTRATO_PRAZO = "contrato_prazo"
    SISTEMA = "sistema"
    ALL = [
        LEMBRETE, DOCUMENTO_VENCENDO, LICITACAO_ATUALIZADA,
        PNCP_NOVA_LICITACAO, CONTRATO_PRAZO, SISTEMA,
    ]


# === Models ===


class Lembrete(Base):
    """Lembrete vinculado a uma licitação ou avulso."""

    __tablename__ = "lembretes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    licitacao_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("licitacoes.id", ondelete="CASCADE"), nullable=True, index=True,
    )

    titulo: Mapped[str] = mapped_column(String(255), nullable=False)
    descricao: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    data_lembrete: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True,
    )
    data_evento: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    tipo: Mapped[str] = mapped_column(
        String(50), nullable=False, default=LembreteTipo.MANUAL,
    )
    recorrencia: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    canais: Mapped[Optional[list]] = mapped_column(JSON, default=["app"])
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=LembreteStatus.PENDENTE,
    )
    enviado_em: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
    )

    # Relationships
    usuario: Mapped["Usuario"] = relationship("Usuario")
    licitacao: Mapped[Optional["Licitacao"]] = relationship("Licitacao")

    __table_args__ = (
        Index("ix_lembretes_user_status_data", "user_id", "status", "data_lembrete"),
        Index("ix_lembretes_status_data", "status", "data_lembrete"),
    )


class Notificacao(Base):
    """Notificação in-app para o usuário."""

    __tablename__ = "notificacoes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True,
    )

    titulo: Mapped[str] = mapped_column(String(255), nullable=False)
    mensagem: Mapped[str] = mapped_column(Text, nullable=False)
    tipo: Mapped[str] = mapped_column(String(50), nullable=False)
    link: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    lida: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    lida_em: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    referencia_tipo: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    referencia_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
    )

    # Relationships
    usuario: Mapped["Usuario"] = relationship("Usuario")
    __table_args__ = (
        Index("ix_notificacoes_user_lida", "user_id", "lida"),
        Index("ix_notificacoes_user_created", "user_id", "created_at"),
    )


class PreferenciaNotificacao(Base):
    """Preferências de notificação do usuário."""

    __tablename__ = "preferencias_notificacao"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("usuarios.id", ondelete="CASCADE"),
        nullable=False, unique=True, index=True,
    )

    email_habilitado: Mapped[bool] = mapped_column(Boolean, default=True)
    app_habilitado: Mapped[bool] = mapped_column(Boolean, default=True)
    antecedencia_horas: Mapped[int] = mapped_column(Integer, default=24)
    email_resumo_diario: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(),
    )

    # Relationships
    usuario: Mapped["Usuario"] = relationship("Usuario")
