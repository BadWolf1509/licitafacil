"""add_indexes_for_performance

Revision ID: c33b97c43bf4
Revises: e5g9h80328gg
Create Date: 2026-02-03 10:09:21.494606

"""
from typing import Sequence, Union

from alembic import op  # type: ignore[attr-defined]

# revision identifiers, used by Alembic.
revision: str = 'c33b97c43bf4'
down_revision: Union[str, Sequence[str], None] = 'e5g9h80328gg'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add index for data_emissao on atestados table.

    Note: Other indexes (contratante, nome_licitacao) already exist
    in the database with different naming conventions (idx_ vs ix_).
    """
    # Add new index for data_emissao (did not exist before)
    op.create_index(
        'ix_atestados_data_emissao',
        'atestados',
        ['data_emissao'],
        unique=False,
        if_not_exists=True
    )


def downgrade() -> None:
    """Remove the data_emissao index."""
    op.drop_index('ix_atestados_data_emissao', table_name='atestados', if_exists=True)
