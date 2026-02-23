from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import JSON, DateTime, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from database import Base


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
