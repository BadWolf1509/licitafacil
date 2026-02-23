"""add_lembretes_notificacoes

Revision ID: j0e4m35873ll
Revises: i9d3l24762kk
Create Date: 2026-02-11

Add lembretes, notificacoes, preferencias_notificacao tables.
"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op  # type: ignore[attr-defined]

# revision identifiers, used by Alembic.
revision: str = "j0e4m35873ll"
down_revision: Union[str, None] = "i9d3l24762kk"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(table_name: str) -> bool:
    """Check if a table exists in PostgreSQL."""
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            "SELECT EXISTS ("
            "SELECT FROM information_schema.tables "
            "WHERE table_name = :name"
            ")"
        ),
        {"name": table_name},
    )
    return bool(result.scalar())


def _index_exists(index_name: str) -> bool:
    """Check if an index exists in PostgreSQL."""
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            "SELECT EXISTS ("
            "SELECT FROM pg_indexes "
            "WHERE indexname = :name"
            ")"
        ),
        {"name": index_name},
    )
    return bool(result.scalar())


def upgrade() -> None:
    # --- lembretes ---
    if not _table_exists("lembretes"):
        op.create_table(
            "lembretes",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column(
                "user_id",
                sa.Integer(),
                sa.ForeignKey("usuarios.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "licitacao_id",
                sa.Integer(),
                sa.ForeignKey("licitacoes.id", ondelete="CASCADE"),
                nullable=True,
            ),
            sa.Column("titulo", sa.String(255), nullable=False),
            sa.Column("descricao", sa.Text(), nullable=True),
            sa.Column(
                "data_lembrete", sa.DateTime(timezone=True), nullable=False
            ),
            sa.Column("data_evento", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "tipo", sa.String(50), nullable=False, server_default="manual"
            ),
            sa.Column("recorrencia", sa.String(30), nullable=True),
            sa.Column("canais", sa.JSON(), nullable=True),
            sa.Column(
                "status",
                sa.String(20),
                nullable=False,
                server_default="pendente",
            ),
            sa.Column("enviado_em", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
            ),
        )

    # Indexes for lembretes
    for idx_name, cols in [
        ("ix_lembretes_id", ["id"]),
        ("ix_lembretes_user_id", ["user_id"]),
        ("ix_lembretes_licitacao_id", ["licitacao_id"]),
        ("ix_lembretes_data_lembrete", ["data_lembrete"]),
        ("ix_lembretes_user_status_data", ["user_id", "status", "data_lembrete"]),
        ("ix_lembretes_status_data", ["status", "data_lembrete"]),
    ]:
        if not _index_exists(idx_name):
            op.create_index(idx_name, "lembretes", cols)

    # --- notificacoes ---
    if not _table_exists("notificacoes"):
        op.create_table(
            "notificacoes",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column(
                "user_id",
                sa.Integer(),
                sa.ForeignKey("usuarios.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("titulo", sa.String(255), nullable=False),
            sa.Column("mensagem", sa.Text(), nullable=False),
            sa.Column("tipo", sa.String(50), nullable=False),
            sa.Column("link", sa.String(500), nullable=True),
            sa.Column("lida", sa.Boolean(), server_default="false", nullable=False),
            sa.Column("lida_em", sa.DateTime(timezone=True), nullable=True),
            sa.Column("referencia_tipo", sa.String(50), nullable=True),
            sa.Column("referencia_id", sa.Integer(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
            ),
        )

    for idx_name, cols in [
        ("ix_notificacoes_id", ["id"]),
        ("ix_notificacoes_user_id", ["user_id"]),
        ("ix_notificacoes_lida", ["lida"]),
        ("ix_notificacoes_user_lida", ["user_id", "lida"]),
        ("ix_notificacoes_user_created", ["user_id", "created_at"]),
    ]:
        if not _index_exists(idx_name):
            op.create_index(idx_name, "notificacoes", cols)

    # --- preferencias_notificacao ---
    if not _table_exists("preferencias_notificacao"):
        op.create_table(
            "preferencias_notificacao",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column(
                "user_id",
                sa.Integer(),
                sa.ForeignKey("usuarios.id", ondelete="CASCADE"),
                nullable=False,
                unique=True,
            ),
            sa.Column(
                "email_habilitado",
                sa.Boolean(),
                server_default="true",
                nullable=False,
            ),
            sa.Column(
                "app_habilitado",
                sa.Boolean(),
                server_default="true",
                nullable=False,
            ),
            sa.Column(
                "antecedencia_horas",
                sa.Integer(),
                server_default="24",
                nullable=False,
            ),
            sa.Column(
                "email_resumo_diario",
                sa.Boolean(),
                server_default="false",
                nullable=False,
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
            ),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        )

    for idx_name, cols in [
        ("ix_preferencias_notificacao_id", ["id"]),
        ("ix_preferencias_notificacao_user_id", ["user_id"]),
    ]:
        if not _index_exists(idx_name):
            op.create_index(idx_name, "preferencias_notificacao", cols)


def downgrade() -> None:
    op.drop_table("preferencias_notificacao")
    op.drop_table("notificacoes")
    op.drop_table("lembretes")
