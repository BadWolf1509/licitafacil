"""add_fk_processing_jobs_user_id

Revision ID: h8c2k13651jj
Revises: g7b1j02540ii
Create Date: 2026-02-05

Add foreign key constraint on processing_jobs.user_id -> usuarios.id with CASCADE delete.
"""
from typing import Sequence, Union

from alembic import op  # type: ignore[attr-defined]


# revision identifiers, used by Alembic.
revision: str = 'h8c2k13651jj'
down_revision: Union[str, None] = 'g7b1j02540ii'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_foreign_key(
        'fk_processing_jobs_user_id',
        'processing_jobs', 'usuarios',
        ['user_id'], ['id'],
        ondelete='CASCADE'
    )


def downgrade() -> None:
    op.drop_constraint('fk_processing_jobs_user_id', 'processing_jobs', type_='foreignkey')
