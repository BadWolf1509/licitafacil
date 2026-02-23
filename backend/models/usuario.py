from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from database import Base

if TYPE_CHECKING:
    from models.analise import Analise
    from models.atestado import Atestado


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
