"""remove_legacy_auth_columns

Revision ID: f6a0i91439hh
Revises: c33b97c43bf4
Create Date: 2026-02-03

Remove legacy authentication columns from usuarios table.
Now all authentication is handled by Supabase Auth.
"""
from typing import Sequence, Union

from alembic import op  # type: ignore[attr-defined]
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f6a0i91439hh'
down_revision: Union[str, Sequence[str], None] = 'c33b97c43bf4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Remove legacy auth columns and make supabase_id required."""
    # First, ensure all users have supabase_id (required check)
    # If any user lacks supabase_id, this migration should not run
    # In production, migrate users first using the migration script

    # Make supabase_id non-nullable (all users must be migrated)
    op.alter_column(
        'usuarios',
        'supabase_id',
        existing_type=sa.String(36),
        nullable=False
    )

    # Drop legacy auth columns
    op.drop_column('usuarios', 'senha_hash')
    op.drop_column('usuarios', 'failed_login_attempts')
    op.drop_column('usuarios', 'locked_until')


def downgrade() -> None:
    """Restore legacy auth columns (data will be lost!)."""
    # Re-add legacy columns
    op.add_column(
        'usuarios',
        sa.Column('senha_hash', sa.String(255), nullable=True)
    )
    op.add_column(
        'usuarios',
        sa.Column('failed_login_attempts', sa.Integer(), nullable=False, server_default='0')
    )
    op.add_column(
        'usuarios',
        sa.Column('locked_until', sa.DateTime(timezone=True), nullable=True)
    )

    # Make supabase_id nullable again
    op.alter_column(
        'usuarios',
        'supabase_id',
        existing_type=sa.String(36),
        nullable=True
    )
