"""add_licitacoes_module

Revision ID: i9d3l24762kk
Revises: h8c2k13651jj
Create Date: 2026-02-11

Add licitacoes, licitacao_tags, licitacao_historico tables.
Add licitacao_id FK to analises table.
"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op  # type: ignore[attr-defined]

# revision identifiers, used by Alembic.
revision: str = 'i9d3l24762kk'
down_revision: Union[str, None] = 'h8c2k13651jj'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(table_name: str) -> bool:
    """Check if a table already exists in the database."""
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
            "WHERE table_name = :t)"
        ),
        {"t": table_name},
    )
    return bool(result.scalar())


def _index_exists(index_name: str) -> bool:
    """Check if an index already exists."""
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM pg_indexes "
            "WHERE indexname = :i)"
        ),
        {"i": index_name},
    )
    return bool(result.scalar())


def _column_exists(table_name: str, column_name: str) -> bool:
    """Check if a column already exists in a table."""
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM information_schema.columns "
            "WHERE table_name = :t AND column_name = :c)"
        ),
        {"t": table_name, "c": column_name},
    )
    return bool(result.scalar())


def upgrade() -> None:
    # === 1. Tabela licitacoes ===
    if not _table_exists('licitacoes'):
        op.create_table(
            'licitacoes',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('numero', sa.String(100), nullable=False),
            sa.Column('orgao', sa.String(500), nullable=False),
            sa.Column('objeto', sa.Text(), nullable=False),
            sa.Column('modalidade', sa.String(100), nullable=False),
            sa.Column('numero_controle_pncp', sa.String(100), nullable=True),
            sa.Column('valor_estimado', sa.Numeric(18, 2), nullable=True),
            sa.Column('valor_homologado', sa.Numeric(18, 2), nullable=True),
            sa.Column('valor_proposta', sa.Numeric(18, 2), nullable=True),
            sa.Column('status', sa.String(30), nullable=False, server_default='identificada'),
            sa.Column('decisao_go', sa.Boolean(), nullable=True),
            sa.Column('motivo_nogo', sa.Text(), nullable=True),
            sa.Column('data_publicacao', sa.DateTime(timezone=True), nullable=True),
            sa.Column('data_abertura', sa.DateTime(timezone=True), nullable=True),
            sa.Column('data_encerramento', sa.DateTime(timezone=True), nullable=True),
            sa.Column('data_resultado', sa.DateTime(timezone=True), nullable=True),
            sa.Column('uf', sa.String(2), nullable=True),
            sa.Column('municipio', sa.String(200), nullable=True),
            sa.Column('esfera', sa.String(20), nullable=True),
            sa.Column('link_edital', sa.String(1000), nullable=True),
            sa.Column('link_sistema_origem', sa.String(1000), nullable=True),
            sa.Column('observacoes', sa.Text(), nullable=True),
            sa.Column('fonte', sa.String(30), nullable=False, server_default='manual'),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint('id'),
            sa.ForeignKeyConstraint(['user_id'], ['usuarios.id'], ondelete='CASCADE'),
        )
    for idx in [
        ('ix_licitacoes_id', 'licitacoes', ['id'], False),
        ('ix_licitacoes_user_id', 'licitacoes', ['user_id'], False),
        ('ix_licitacoes_status', 'licitacoes', ['status'], False),
        ('ix_licitacoes_numero_controle_pncp', 'licitacoes', ['numero_controle_pncp'], True),
        ('ix_licitacoes_data_abertura', 'licitacoes', ['data_abertura'], False),
        ('ix_licitacoes_uf', 'licitacoes', ['uf'], False),
        ('ix_licitacoes_user_status', 'licitacoes', ['user_id', 'status'], False),
        ('ix_licitacoes_user_created', 'licitacoes', ['user_id', 'created_at'], False),
        ('ix_licitacoes_uf_modalidade', 'licitacoes', ['uf', 'modalidade'], False),
    ]:
        if not _index_exists(idx[0]):
            op.create_index(idx[0], idx[1], idx[2], unique=idx[3])

    # === 2. Tabela licitacao_tags ===
    if not _table_exists('licitacao_tags'):
        op.create_table(
            'licitacao_tags',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('licitacao_id', sa.Integer(), nullable=False),
            sa.Column('tag', sa.String(100), nullable=False),
            sa.PrimaryKeyConstraint('id'),
            sa.ForeignKeyConstraint(['licitacao_id'], ['licitacoes.id'], ondelete='CASCADE'),
            sa.UniqueConstraint('licitacao_id', 'tag', name='uq_licitacao_tag'),
        )
    for idx in [
        ('ix_licitacao_tags_id', 'licitacao_tags', ['id'], False),
        ('ix_licitacao_tags_licitacao_id', 'licitacao_tags', ['licitacao_id'], False),
        ('ix_licitacao_tags_tag', 'licitacao_tags', ['tag'], False),
    ]:
        if not _index_exists(idx[0]):
            op.create_index(idx[0], idx[1], idx[2], unique=idx[3])

    # === 3. Tabela licitacao_historico ===
    if not _table_exists('licitacao_historico'):
        op.create_table(
            'licitacao_historico',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('licitacao_id', sa.Integer(), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('status_anterior', sa.String(30), nullable=True),
            sa.Column('status_novo', sa.String(30), nullable=False),
            sa.Column('observacao', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
            sa.PrimaryKeyConstraint('id'),
            sa.ForeignKeyConstraint(['licitacao_id'], ['licitacoes.id'], ondelete='CASCADE'),
        )
    for idx in [
        ('ix_licitacao_historico_id', 'licitacao_historico', ['id'], False),
        ('ix_licitacao_historico_licitacao_id', 'licitacao_historico', ['licitacao_id'], False),
        ('ix_historico_licitacao_created', 'licitacao_historico', ['licitacao_id', 'created_at'], False),
    ]:
        if not _index_exists(idx[0]):
            op.create_index(idx[0], idx[1], idx[2], unique=idx[3])

    # === 4. FK analises -> licitacoes ===
    if not _column_exists('analises', 'licitacao_id'):
        op.add_column('analises', sa.Column('licitacao_id', sa.Integer(), nullable=True))
    if not _index_exists('ix_analises_licitacao_id'):
        op.create_index('ix_analises_licitacao_id', 'analises', ['licitacao_id'])
    # FK - check if constraint exists before creating
    conn = op.get_bind()
    fk_exists = conn.execute(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM information_schema.table_constraints "
            "WHERE constraint_name = 'fk_analises_licitacao_id' AND table_name = 'analises')"
        )
    ).scalar()
    if not fk_exists:
        op.create_foreign_key(
            'fk_analises_licitacao_id',
            'analises', 'licitacoes',
            ['licitacao_id'], ['id'],
            ondelete='SET NULL',
        )


def downgrade() -> None:
    # === Reverter FK analises ===
    op.drop_constraint('fk_analises_licitacao_id', 'analises', type_='foreignkey')
    op.drop_index('ix_analises_licitacao_id', table_name='analises')
    op.drop_column('analises', 'licitacao_id')

    # === Reverter tabelas na ordem inversa ===
    op.drop_table('licitacao_historico')
    op.drop_table('licitacao_tags')
    op.drop_table('licitacoes')
