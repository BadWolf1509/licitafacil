"""Add PNCP monitoramento module.

Revision ID: l2g6o57095nn
Revises: k1f5n46984mm
Create Date: 2026-02-11
"""
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON

from alembic import op

revision = "l2g6o57095nn"
down_revision = "k1f5n46984mm"
branch_labels = None
depends_on = None


def _table_exists(connection, table_name):
    result = connection.execute(
        sa.text(
            "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = :t)"
        ),
        {"t": table_name},
    )
    return result.scalar()


def _index_exists(connection, index_name):
    result = connection.execute(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = :i)"
        ),
        {"i": index_name},
    )
    return result.scalar()


def upgrade():
    connection = op.get_bind()

    # --- pncp_monitoramentos ---
    if not _table_exists(connection, "pncp_monitoramentos"):
        op.create_table(
            "pncp_monitoramentos",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column(
                "user_id",
                sa.Integer(),
                sa.ForeignKey("usuarios.id", ondelete="CASCADE"),
                nullable=False,
                index=True,
            ),
            sa.Column("nome", sa.String(200), nullable=False),
            sa.Column("ativo", sa.Boolean(), server_default=sa.text("true"), index=True),
            sa.Column("palavras_chave", JSON, nullable=True),
            sa.Column("ufs", JSON, nullable=True),
            sa.Column("modalidades", JSON, nullable=True),
            sa.Column("esferas", JSON, nullable=True),
            sa.Column("valor_minimo", sa.Numeric(18, 2), nullable=True),
            sa.Column("valor_maximo", sa.Numeric(18, 2), nullable=True),
            sa.Column("ultimo_check", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
            ),
        )

    if not _index_exists(connection, "ix_pncp_monitor_user_ativo"):
        op.create_index(
            "ix_pncp_monitor_user_ativo",
            "pncp_monitoramentos",
            ["user_id", "ativo"],
        )

    # --- pncp_resultados ---
    if not _table_exists(connection, "pncp_resultados"):
        op.create_table(
            "pncp_resultados",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column(
                "monitoramento_id",
                sa.Integer(),
                sa.ForeignKey("pncp_monitoramentos.id", ondelete="CASCADE"),
                nullable=False,
                index=True,
            ),
            sa.Column(
                "user_id",
                sa.Integer(),
                sa.ForeignKey("usuarios.id", ondelete="CASCADE"),
                nullable=False,
                index=True,
            ),
            sa.Column("numero_controle_pncp", sa.String(100), nullable=False, index=True),
            sa.Column("orgao_cnpj", sa.String(20), nullable=True),
            sa.Column("orgao_razao_social", sa.String(500), nullable=True),
            sa.Column("objeto_compra", sa.Text(), nullable=True),
            sa.Column("modalidade_nome", sa.String(100), nullable=True),
            sa.Column("uf", sa.String(2), nullable=True, index=True),
            sa.Column("municipio", sa.String(200), nullable=True),
            sa.Column("valor_estimado", sa.Numeric(18, 2), nullable=True),
            sa.Column("data_abertura", sa.DateTime(timezone=True), nullable=True),
            sa.Column("data_encerramento", sa.DateTime(timezone=True), nullable=True),
            sa.Column("link_sistema_origem", sa.String(1000), nullable=True),
            sa.Column("dados_completos", JSON, nullable=True),
            sa.Column(
                "status",
                sa.String(20),
                server_default=sa.text("'novo'"),
                nullable=False,
                index=True,
            ),
            sa.Column(
                "licitacao_id",
                sa.Integer(),
                sa.ForeignKey("licitacoes.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column(
                "encontrado_em",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
            ),
        )

    if not _index_exists(connection, "ix_pncp_resultado_user_status"):
        op.create_index(
            "ix_pncp_resultado_user_status",
            "pncp_resultados",
            ["user_id", "status"],
        )

    if not _index_exists(connection, "ix_pncp_resultado_controle_user"):
        op.create_index(
            "ix_pncp_resultado_controle_user",
            "pncp_resultados",
            ["numero_controle_pncp", "user_id"],
        )


def downgrade():
    op.drop_table("pncp_resultados")
    op.drop_table("pncp_monitoramentos")
