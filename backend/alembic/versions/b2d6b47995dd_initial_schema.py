"""initial_schema

Revision ID: b2d6b47995dd
Revises:
Create Date: 2026-02-01 16:49:35.960770

Esta é a migration baseline que registra o estado inicial do banco.
As tabelas já existem, apenas adicionamos os novos índices compostos.
"""
from typing import Sequence, Union

from alembic import op  # type: ignore[attr-defined]

# revision identifiers, used by Alembic.
revision: str = 'b2d6b47995dd'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - adiciona índices compostos para performance."""
    # Criar índices compostos novos (se não existirem)
    # Usamos postgresql_if_not_exists para evitar erros se o índice já existir

    # Usuarios: índices para queries de listagem com filtros
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_usuarios_approved_created
        ON usuarios (is_approved, created_at)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_usuarios_active_created
        ON usuarios (is_active, created_at)
    """)

    # Atestados: índice para listagem por usuário ordenada por data
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_atestados_user_created
        ON atestados (user_id, created_at)
    """)

    # Analises: índice para listagem por usuário ordenada por data
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_analises_user_created
        ON analises (user_id, created_at)
    """)

    # Processing Jobs: índice composto para queries de jobs por usuário e status
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_jobs_user_status
        ON processing_jobs (user_id, status)
    """)


def downgrade() -> None:
    """Downgrade schema - remove índices compostos adicionados."""
    op.execute("DROP INDEX IF EXISTS ix_usuarios_approved_created")
    op.execute("DROP INDEX IF EXISTS ix_usuarios_active_created")
    op.execute("DROP INDEX IF EXISTS ix_atestados_user_created")
    op.execute("DROP INDEX IF EXISTS ix_analises_user_created")
    op.execute("DROP INDEX IF EXISTS ix_jobs_user_status")
