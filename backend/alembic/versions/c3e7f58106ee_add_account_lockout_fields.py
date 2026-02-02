"""add_account_lockout_fields

Revision ID: c3e7f58106ee
Revises: b2d6b47995dd
Create Date: 2026-02-01

Adiciona campos para bloqueio de conta apos tentativas de login falhas:
- failed_login_attempts: contador de tentativas falhas
- locked_until: data/hora ate quando a conta esta bloqueada
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3e7f58106ee'
down_revision: Union[str, Sequence[str], None] = 'b2d6b47995dd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Adiciona campos de bloqueio de conta na tabela usuarios."""
    # Adicionar coluna failed_login_attempts com valor padrao 0
    op.add_column(
        'usuarios',
        sa.Column('failed_login_attempts', sa.Integer(), nullable=False, server_default='0')
    )

    # Adicionar coluna locked_until (nullable)
    op.add_column(
        'usuarios',
        sa.Column('locked_until', sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    """Remove campos de bloqueio de conta."""
    op.drop_column('usuarios', 'locked_until')
    op.drop_column('usuarios', 'failed_login_attempts')
