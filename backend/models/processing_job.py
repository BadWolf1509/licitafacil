from __future__ import annotations

from typing import Any, Dict, Optional

from sqlalchemy import JSON, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


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
