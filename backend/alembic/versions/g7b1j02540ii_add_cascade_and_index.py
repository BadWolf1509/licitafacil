"""add_cascade_rules_and_jobs_index

Revision ID: g7b1j02540ii
Revises: f6a0i91439hh
Create Date: 2026-02-05

Add ON DELETE CASCADE/SET NULL to foreign keys and composite index on processing_jobs.
"""
from typing import Sequence, Union

from alembic import op  # type: ignore[attr-defined]


# revision identifiers, used by Alembic.
revision: str = 'g7b1j02540ii'
down_revision: Union[str, Sequence[str], None] = 'f6a0i91439hh'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add CASCADE rules to FKs and composite index on processing_jobs."""
    # 1. atestados.user_id -> ON DELETE CASCADE
    op.drop_constraint('atestados_user_id_fkey', 'atestados', type_='foreignkey')
    op.create_foreign_key(
        'atestados_user_id_fkey', 'atestados', 'usuarios',
        ['user_id'], ['id'], ondelete='CASCADE'
    )

    # 2. analises.user_id -> ON DELETE CASCADE
    op.drop_constraint('analises_user_id_fkey', 'analises', type_='foreignkey')
    op.create_foreign_key(
        'analises_user_id_fkey', 'analises', 'usuarios',
        ['user_id'], ['id'], ondelete='CASCADE'
    )

    # 3. usuarios.approved_by -> ON DELETE SET NULL
    op.drop_constraint('usuarios_approved_by_fkey', 'usuarios', type_='foreignkey')
    op.create_foreign_key(
        'usuarios_approved_by_fkey', 'usuarios', 'usuarios',
        ['approved_by'], ['id'], ondelete='SET NULL'
    )

    # 4. Add composite index (user_id, created_at) on processing_jobs
    op.create_index('ix_jobs_user_created', 'processing_jobs', ['user_id', 'created_at'])


def downgrade() -> None:
    """Remove CASCADE rules and index."""
    op.drop_index('ix_jobs_user_created', table_name='processing_jobs')

    # Restore FKs without CASCADE
    op.drop_constraint('usuarios_approved_by_fkey', 'usuarios', type_='foreignkey')
    op.create_foreign_key(
        'usuarios_approved_by_fkey', 'usuarios', 'usuarios',
        ['approved_by'], ['id']
    )

    op.drop_constraint('analises_user_id_fkey', 'analises', type_='foreignkey')
    op.create_foreign_key(
        'analises_user_id_fkey', 'analises', 'usuarios',
        ['user_id'], ['id']
    )

    op.drop_constraint('atestados_user_id_fkey', 'atestados', type_='foreignkey')
    op.create_foreign_key(
        'atestados_user_id_fkey', 'atestados', 'usuarios',
        ['user_id'], ['id']
    )
