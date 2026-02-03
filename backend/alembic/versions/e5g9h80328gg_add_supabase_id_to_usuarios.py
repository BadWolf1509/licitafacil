"""add_supabase_id_to_usuarios

Revision ID: e5g9h80328gg
Revises: d4f8g69217ff
Create Date: 2026-02-02

Adiciona campo supabase_id para integração com Supabase Auth.
Também torna senha_hash nullable para permitir migração gradual.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e5g9h80328gg'
down_revision: Union[str, Sequence[str], None] = 'd4f8g69217ff'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Adiciona supabase_id e torna senha_hash nullable."""
    # Adicionar coluna supabase_id (UUID do Supabase Auth)
    op.add_column(
        'usuarios',
        sa.Column('supabase_id', sa.String(36), nullable=True, unique=True)
    )

    # Criar índice para supabase_id
    op.create_index('ix_usuarios_supabase_id', 'usuarios', ['supabase_id'], unique=True)

    # Tornar senha_hash nullable para período de migração
    # NOTA: Esta operação pode variar entre bancos de dados
    op.alter_column(
        'usuarios',
        'senha_hash',
        existing_type=sa.String(255),
        nullable=True
    )


def downgrade() -> None:
    """Remove supabase_id e restaura senha_hash como not null."""
    # Restaurar senha_hash como not null
    # NOTA: Isso falhará se houver registros com senha_hash NULL
    op.alter_column(
        'usuarios',
        'senha_hash',
        existing_type=sa.String(255),
        nullable=False
    )

    # Remover índice e coluna supabase_id
    op.drop_index('ix_usuarios_supabase_id', table_name='usuarios')
    op.drop_column('usuarios', 'supabase_id')
