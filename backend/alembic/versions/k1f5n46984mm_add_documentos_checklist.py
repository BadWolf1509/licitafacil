"""Adiciona tabelas documentos_licitacao e checklist_edital.

Revision ID: k1f5n46984mm
Revises: j0e4m35873ll
Create Date: 2026-02-11
"""
import sqlalchemy as sa

from alembic import op

revision = "k1f5n46984mm"
down_revision = "j0e4m35873ll"
branch_labels = None
depends_on = None


def _table_exists(table_name: str) -> bool:
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = :t)"
        ),
        {"t": table_name},
    )
    return bool(result.scalar())


def _index_exists(index_name: str) -> bool:
    conn = op.get_bind()
    result = conn.execute(
        sa.text("SELECT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = :i)"),
        {"i": index_name},
    )
    return bool(result.scalar())


def upgrade():
    # === documentos_licitacao ===
    if not _table_exists("documentos_licitacao"):
        op.create_table(
            "documentos_licitacao",
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
                sa.ForeignKey("licitacoes.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("nome", sa.String(255), nullable=False),
            sa.Column("tipo_documento", sa.String(100), nullable=False),
            sa.Column("arquivo_path", sa.String(500), nullable=True),
            sa.Column("tamanho_bytes", sa.Integer(), nullable=True),
            sa.Column("data_emissao", sa.DateTime(timezone=True), nullable=True),
            sa.Column("data_validade", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "status", sa.String(20), nullable=False, server_default="valido"
            ),
            sa.Column("obrigatorio", sa.Boolean(), server_default="false"),
            sa.Column("observacoes", sa.Text(), nullable=True),
            sa.Column(
                "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
            ),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        )

    # Indexes individuais
    for idx_name, columns in [
        ("ix_documentos_licitacao_id", ["id"]),
        ("ix_documentos_licitacao_user_id", ["user_id"]),
        ("ix_documentos_licitacao_licitacao_id", ["licitacao_id"]),
        ("ix_documentos_licitacao_data_validade", ["data_validade"]),
    ]:
        if not _index_exists(idx_name):
            op.create_index(idx_name, "documentos_licitacao", columns)

    # Indexes compostos
    for idx_name, columns in [
        ("ix_documentos_user_tipo", ["user_id", "tipo_documento"]),
        ("ix_documentos_user_status", ["user_id", "status"]),
        ("ix_documentos_user_licitacao", ["user_id", "licitacao_id"]),
        ("ix_documentos_validade_status", ["data_validade", "status"]),
    ]:
        if not _index_exists(idx_name):
            op.create_index(idx_name, "documentos_licitacao", columns)

    # === checklist_edital ===
    if not _table_exists("checklist_edital"):
        op.create_table(
            "checklist_edital",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column(
                "licitacao_id",
                sa.Integer(),
                sa.ForeignKey("licitacoes.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "user_id",
                sa.Integer(),
                sa.ForeignKey("usuarios.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("descricao", sa.Text(), nullable=False),
            sa.Column("tipo_documento", sa.String(100), nullable=True),
            sa.Column("obrigatorio", sa.Boolean(), server_default="true"),
            sa.Column("cumprido", sa.Boolean(), server_default="false"),
            sa.Column(
                "documento_id",
                sa.Integer(),
                sa.ForeignKey("documentos_licitacao.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("observacao", sa.Text(), nullable=True),
            sa.Column("ordem", sa.Integer(), server_default="0"),
            sa.Column(
                "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
            ),
        )

    for idx_name, columns in [
        ("ix_checklist_edital_id", ["id"]),
        ("ix_checklist_edital_licitacao_id", ["licitacao_id"]),
        ("ix_checklist_licitacao_ordem", ["licitacao_id", "ordem"]),
    ]:
        if not _index_exists(idx_name):
            op.create_index(idx_name, "checklist_edital", columns)


def downgrade():
    op.drop_table("checklist_edital")
    op.drop_table("documentos_licitacao")
