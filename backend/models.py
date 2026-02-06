from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, JSON, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from database import Base


class Usuario(Base):
    """Modelo de usuario do sistema."""
    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    nome: Mapped[str] = mapped_column(String(255), nullable=False)

    # Supabase Auth ID (UUID) - chave estrangeira para auth.users
    supabase_id: Mapped[str] = mapped_column(String(36), unique=True, index=True, nullable=False)

    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    is_approved: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)

    tema_preferido: Mapped[str] = mapped_column(String(10), default="light")  # light ou dark

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_by: Mapped[Optional[int]] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True)

    # Relacionamentos
    atestados: Mapped[List["Atestado"]] = relationship("Atestado", back_populates="usuario")
    analises: Mapped[List["Analise"]] = relationship("Analise", back_populates="usuario")
    aprovador: Mapped[Optional["Usuario"]] = relationship(
        "Usuario",
        remote_side=[id],
        foreign_keys=[approved_by]
    )

    # Índices compostos para queries frequentes
    __table_args__ = (
        Index('ix_usuarios_approved_created', 'is_approved', 'created_at'),
        Index('ix_usuarios_active_created', 'is_active', 'created_at'),
    )


class Atestado(Base):
    """Modelo de atestado de capacidade tecnica.

    Nota: Atestados e Analises usam hard-delete por design (conformidade LGPD).
    Usuarios usam soft-delete (is_active) para manter historico de aprovacao.
    """
    __tablename__ = "atestados"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True)

    descricao_servico: Mapped[str] = mapped_column(Text, nullable=False)
    quantidade: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 4), nullable=True)
    unidade: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    contratante: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    data_emissao: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    arquivo_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    texto_extraido: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    servicos_json: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), onupdate=func.now())

    # Relacionamentos
    usuario: Mapped["Usuario"] = relationship("Usuario", back_populates="atestados")

    # Índices para consultas otimizadas
    __table_args__ = (
        Index('ix_atestados_user_created', 'user_id', 'created_at'),
        Index('ix_atestados_contratante', 'contratante'),
        Index('ix_atestados_data_emissao', 'data_emissao'),
    )


class Analise(Base):
    """Modelo de analise de licitacao."""
    __tablename__ = "analises"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True)

    nome_licitacao: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    arquivo_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    exigencias_json: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(JSON, nullable=True)
    resultado_json: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relacionamentos
    usuario: Mapped["Usuario"] = relationship("Usuario", back_populates="analises")

    # Índice composto para listagem ordenada por usuário
    __table_args__ = (
        Index('ix_analises_user_created', 'user_id', 'created_at'),
    )


class ProcessingJobModel(Base):
    """Modelo SQLAlchemy para jobs de processamento."""
    __tablename__ = "processing_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True
    )

    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    original_filename: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    job_type: Mapped[str] = mapped_column(String(50), nullable=False, default="atestado")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)

    created_at: Mapped[str] = mapped_column(Text, nullable=False)
    started_at: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    completed_at: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    canceled_at: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    result: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)

    progress_current: Mapped[int] = mapped_column(Integer, default=0)
    progress_total: Mapped[int] = mapped_column(Integer, default=0)
    progress_stage: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    progress_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    pipeline: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Índices compostos para queries de jobs por usuário e status
    __table_args__ = (
        Index('ix_jobs_user_status', 'user_id', 'status'),
        Index('ix_jobs_user_created', 'user_id', 'created_at'),
    )


class AuditLog(Base):
    """Modelo de log de auditoria para acoes administrativas."""
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    # Acao realizada (ex: user_approved, user_rejected, atestado_deleted)
    action: Mapped[str] = mapped_column(String(50), nullable=False, index=True)

    # Tipo de recurso afetado (ex: usuario, atestado, analise)
    resource_type: Mapped[str] = mapped_column(String(50), nullable=False)

    # ID do recurso afetado (opcional)
    resource_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Detalhes adicionais em JSON
    details: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)

    # IP do cliente
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Indices para consultas frequentes
    __table_args__ = (
        Index('ix_audit_user_created', 'user_id', 'created_at'),
        Index('ix_audit_action_created', 'action', 'created_at'),
    )
