from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from database import Base

if TYPE_CHECKING:
    from models.usuario import Usuario


class Analise(Base):
    """Modelo de analise de licitacao."""
    __tablename__ = "analises"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True)

    nome_licitacao: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    arquivo_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    exigencias_json: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(JSON, nullable=True)
    resultado_json: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(JSON, nullable=True)

    # FK para licitacao (nullable - backward compat com analises existentes)
    licitacao_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("licitacoes.id", ondelete="SET NULL"), nullable=True, index=True
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relacionamentos
    usuario: Mapped["Usuario"] = relationship("Usuario", back_populates="analises")

    # Índice composto para listagem ordenada por usuário
    __table_args__ = (
        Index('ix_analises_user_created', 'user_id', 'created_at'),
    )
