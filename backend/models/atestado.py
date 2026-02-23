from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from database import Base

if TYPE_CHECKING:
    from models.usuario import Usuario


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
