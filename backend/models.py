from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from database import Base


class Usuario(Base):
    """Modelo de usuario do sistema."""
    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    senha_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    nome: Mapped[str] = mapped_column(String(255), nullable=False)

    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    is_approved: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    tema_preferido: Mapped[str] = mapped_column(String(10), default="light")  # light ou dark

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_by: Mapped[Optional[int]] = mapped_column(ForeignKey("usuarios.id"), nullable=True)

    # Relacionamentos
    atestados: Mapped[List["Atestado"]] = relationship("Atestado", back_populates="usuario")
    analises: Mapped[List["Analise"]] = relationship("Analise", back_populates="usuario")
    aprovador: Mapped[Optional["Usuario"]] = relationship(
        "Usuario",
        remote_side=[id],
        foreign_keys=[approved_by]
    )


class Atestado(Base):
    """Modelo de atestado de capacidade tecnica."""
    __tablename__ = "atestados"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), nullable=False)

    descricao_servico: Mapped[str] = mapped_column(Text, nullable=False)
    quantidade: Mapped[Decimal] = mapped_column(Numeric(15, 4), nullable=False)
    unidade: Mapped[str] = mapped_column(String(20), nullable=False)

    contratante: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    data_emissao: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    arquivo_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    texto_extraido: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    servicos_json: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), onupdate=func.now())

    # Relacionamentos
    usuario: Mapped["Usuario"] = relationship("Usuario", back_populates="atestados")


class Analise(Base):
    """Modelo de analise de licitacao."""
    __tablename__ = "analises"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), nullable=False)

    nome_licitacao: Mapped[str] = mapped_column(String(255), nullable=False)
    arquivo_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    exigencias_json: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(JSON, nullable=True)
    resultado_json: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relacionamentos
    usuario: Mapped["Usuario"] = relationship("Usuario", back_populates="analises")
