"""
Testes para a camada de repositorios.

Testa BaseRepository (CRUD generico), AtestadoRepository, AnaliseRepository
e UsuarioRepository usando banco SQLite de teste via fixtures do conftest.py.

JobRepository usa AUTOCOMMIT com engine direto e e testado em
test_job_repository.py com mocks. Aqui testamos os repositorios que herdam
de BaseRepository e recebem Session como parametro.
"""
import uuid
from datetime import date

import pytest
from sqlalchemy.orm import Session

from models import Usuario, Atestado, Analise
from repositories import (
    atestado_repository,
    analise_repository,
    usuario_repository,
    AtestadoRepository,
    AnaliseRepository,
    UsuarioRepository,
)
from repositories.base import BaseRepository


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_user(db: Session, *, email: str = "repo@teste.com",
               nome: str = "Repo User", is_approved: bool = True,
               is_active: bool = True, is_admin: bool = False) -> Usuario:
    """Cria e persiste um usuario auxiliar."""
    user = Usuario(
        email=email,
        nome=nome,
        supabase_id=str(uuid.uuid4()),
        is_active=is_active,
        is_approved=is_approved,
        is_admin=is_admin,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _make_atestado(db: Session, user_id: int, *,
                   descricao: str = "Servico generico",
                   quantidade: float = 1000.0,
                   contratante: str = "Contratante Teste",
                   arquivo_path: str | None = None,
                   servicos_json=None) -> Atestado:
    """Cria e persiste um atestado auxiliar."""
    atestado = Atestado(
        user_id=user_id,
        descricao_servico=descricao,
        quantidade=quantidade,
        unidade="m2",
        contratante=contratante,
        data_emissao=date(2024, 1, 15),
        arquivo_path=arquivo_path or f"uploads/{uuid.uuid4().hex}.pdf",
        servicos_json=servicos_json,
    )
    db.add(atestado)
    db.commit()
    db.refresh(atestado)
    return atestado


def _make_analise(db: Session, user_id: int, *,
                  nome_licitacao: str = "Edital Generico",
                  arquivo_path: str | None = None) -> Analise:
    """Cria e persiste uma analise auxiliar."""
    analise = Analise(
        user_id=user_id,
        nome_licitacao=nome_licitacao,
        arquivo_path=arquivo_path or f"uploads/{uuid.uuid4().hex}.pdf",
        exigencias_json=[{"descricao": "Exigencia A", "quantidade_minima": 500.0, "unidade": "m2"}],
        resultado_json=[],
    )
    db.add(analise)
    db.commit()
    db.refresh(analise)
    return analise


# ===========================================================================
# 1-5: BaseRepository CRUD via AtestadoRepository (concrete implementation)
# ===========================================================================

class TestBaseRepositoryCRUD:
    """Testa operacoes CRUD genericas do BaseRepository usando AtestadoRepository."""

    def test_create_and_get_by_id_roundtrip(self, db_session: Session):
        """create() persiste entidade e get_by_id() recupera com todos os campos."""
        user = _make_user(db_session, email="crud@teste.com")
        repo = AtestadoRepository()

        atestado = Atestado(
            user_id=user.id,
            descricao_servico="Drenagem pluvial",
            quantidade=150.0,
            unidade="ml",
            contratante="Prefeitura ABC",
        )
        created = repo.create(db_session, atestado)
        assert created.id is not None

        fetched = repo.get_by_id(db_session, created.id)
        assert fetched is not None
        assert fetched.descricao_servico == "Drenagem pluvial"
        assert fetched.user_id == user.id

    def test_get_by_id_returns_none_for_missing(self, db_session: Session):
        """get_by_id() retorna None quando id nao existe."""
        repo = AtestadoRepository()
        assert repo.get_by_id(db_session, 999_999) is None

    def test_update_persists_changes(self, db_session: Session):
        """update() persiste alteracoes na entidade existente."""
        user = _make_user(db_session, email="upd@teste.com")
        repo = AtestadoRepository()
        atestado = _make_atestado(db_session, user.id, descricao="Original")

        atestado.descricao_servico = "Atualizado"
        atestado.quantidade = 9999.0
        repo.update(db_session, atestado)

        db_session.expire_all()
        fetched = repo.get_by_id(db_session, atestado.id)
        assert fetched is not None
        assert fetched.descricao_servico == "Atualizado"

    def test_delete_removes_record(self, db_session: Session):
        """delete() remove o registro do banco."""
        user = _make_user(db_session, email="del@teste.com")
        repo = AtestadoRepository()
        atestado = _make_atestado(db_session, user.id)
        aid = atestado.id

        repo.delete(db_session, atestado)

        db_session.expire_all()
        assert repo.get_by_id(db_session, aid) is None

    def test_delete_by_id_for_user_checks_ownership(self, db_session: Session):
        """delete_by_id_for_user() retorna False quando usuario nao e dono."""
        user_a = _make_user(db_session, email="owner@teste.com")
        user_b = _make_user(db_session, email="other@teste.com")
        repo = AtestadoRepository()
        atestado = _make_atestado(db_session, user_a.id)

        # Tentativa de deletar com usuario errado
        result = repo.delete_by_id_for_user(db_session, atestado.id, user_b.id)
        assert result is False

        # Tentativa com usuario correto
        result = repo.delete_by_id_for_user(db_session, atestado.id, user_a.id)
        assert result is True

        db_session.expire_all()
        assert repo.get_by_id(db_session, atestado.id) is None


# ===========================================================================
# 6-8: BaseRepository query methods (pagination, bulk, exists)
# ===========================================================================

class TestBaseRepositoryQueries:
    """Testa metodos de consulta e operacoes em lote do BaseRepository."""

    def test_get_all_for_user_with_pagination(self, db_session: Session):
        """get_all_for_user() com offset/limit pagina corretamente."""
        user = _make_user(db_session, email="pag@teste.com")
        for i in range(5):
            _make_atestado(db_session, user.id, descricao=f"Pag {i}")

        page1 = atestado_repository.get_all_for_user(
            db_session, user_id=user.id, offset=0, limit=2)
        page2 = atestado_repository.get_all_for_user(
            db_session, user_id=user.id, offset=2, limit=2)
        page3 = atestado_repository.get_all_for_user(
            db_session, user_id=user.id, offset=4, limit=2)

        assert len(page1) == 2
        assert len(page2) == 2
        assert len(page3) == 1

        all_ids = {a.id for a in page1} | {a.id for a in page2} | {a.id for a in page3}
        assert len(all_ids) == 5  # sem sobreposicao

    def test_bulk_create_and_bulk_delete(self, db_session: Session):
        """bulk_create() cria multiplos; bulk_delete_for_user() remove por ids."""
        user = _make_user(db_session, email="bulk@teste.com")
        repo = AtestadoRepository()

        entities = [
            Atestado(user_id=user.id, descricao_servico=f"Bulk {i}")
            for i in range(4)
        ]
        created = repo.bulk_create(db_session, entities)
        assert len(created) == 4
        assert all(c.id is not None for c in created)

        ids_to_delete = [created[0].id, created[2].id]
        deleted_count = repo.bulk_delete_for_user(db_session, ids_to_delete, user.id)
        assert deleted_count == 2

        remaining = repo.count_for_user(db_session, user.id)
        assert remaining == 2

    def test_exists_for_user(self, db_session: Session):
        """exists_for_user() retorna True/False baseado em ownership."""
        user_a = _make_user(db_session, email="exists_a@teste.com")
        user_b = _make_user(db_session, email="exists_b@teste.com")
        repo = AtestadoRepository()
        atestado = _make_atestado(db_session, user_a.id)

        assert repo.exists_for_user(db_session, atestado.id, user_a.id) is True
        assert repo.exists_for_user(db_session, atestado.id, user_b.id) is False
        assert repo.exists_for_user(db_session, 999_999, user_a.id) is False


# ===========================================================================
# 9-12: AtestadoRepository specific methods
# ===========================================================================

class TestAtestadoRepository:
    """Testa metodos especificos do AtestadoRepository."""

    def test_get_by_file_path_found(self, db_session: Session):
        """get_by_file_path() retorna atestado com arquivo correspondente."""
        user = _make_user(db_session, email="fpath@teste.com")
        _make_atestado(
            db_session, user.id,
            descricao="Com arquivo",
            arquivo_path="uploads/doc_especial.pdf",
        )

        found = atestado_repository.get_by_file_path(
            db_session, user.id, "uploads/doc_especial.pdf")
        assert found is not None
        assert found.arquivo_path == "uploads/doc_especial.pdf"

    def test_get_by_file_path_returns_none(self, db_session: Session):
        """get_by_file_path() retorna None quando arquivo nao existe."""
        user = _make_user(db_session, email="fpath_none@teste.com")
        found = atestado_repository.get_by_file_path(
            db_session, user.id, "uploads/inexistente.pdf")
        assert found is None

    def test_get_all_with_services_includes_json(self, db_session: Session):
        """get_all_with_services() retorna atestados com servicos_json preenchido."""
        user = _make_user(db_session, email="services@teste.com")
        servicos = [
            {"item": "1.1", "descricao": "Asfalto", "quantidade": 1000.0, "unidade": "M2"},
        ]
        _make_atestado(db_session, user.id, servicos_json=servicos)

        results = atestado_repository.get_all_with_services(db_session, user_id=user.id)
        assert len(results) == 1
        assert results[0].servicos_json is not None
        assert results[0].servicos_json[0]["descricao"] == "Asfalto"

    def test_get_all_ordered_returns_newest_first(self, db_session: Session):
        """get_all_ordered() retorna atestados em ordem decrescente de criacao."""
        user = _make_user(db_session, email="ordered@teste.com")
        for i in range(3):
            _make_atestado(db_session, user.id, descricao=f"Ord {i}")

        results = atestado_repository.get_all_ordered(db_session, user_id=user.id)
        assert len(results) == 3
        # Ultimo criado vem primeiro (desc)
        assert results[0].descricao_servico == "Ord 2"


# ===========================================================================
# 13-14: AnaliseRepository specific methods
# ===========================================================================

class TestAnaliseRepository:
    """Testa metodos especificos do AnaliseRepository."""

    def test_get_by_file_path_found(self, db_session: Session):
        """get_by_file_path() retorna analise com arquivo correspondente."""
        user = _make_user(db_session, email="an_fp@teste.com")
        _make_analise(
            db_session, user.id,
            nome_licitacao="Edital arquivo",
            arquivo_path="uploads/edital_x.pdf",
        )

        found = analise_repository.get_by_file_path(
            db_session, user.id, "uploads/edital_x.pdf")
        assert found is not None
        assert found.nome_licitacao == "Edital arquivo"

    def test_get_all_ordered_returns_newest_first(self, db_session: Session):
        """get_all_ordered() retorna analises em ordem decrescente de criacao."""
        user = _make_user(db_session, email="an_ord@teste.com")
        for i in range(3):
            _make_analise(db_session, user.id, nome_licitacao=f"Edital {i}")

        results = analise_repository.get_all_ordered(db_session, user_id=user.id)
        assert len(results) == 3
        assert results[0].nome_licitacao == "Edital 2"


# ===========================================================================
# 15-17: UsuarioRepository specific methods
# ===========================================================================

class TestUsuarioRepository:
    """Testa metodos especificos do UsuarioRepository."""

    def test_get_by_email_found_and_missing(self, db_session: Session):
        """get_by_email() retorna usuario existente e None para inexistente."""
        user = _make_user(db_session, email="busca@teste.com", nome="Busca")

        found = usuario_repository.get_by_email(db_session, "busca@teste.com")
        assert found is not None
        assert found.id == user.id

        missing = usuario_repository.get_by_email(db_session, "nao@existe.com")
        assert missing is None

    def test_get_pending_approval_filters_correctly(self, db_session: Session):
        """get_pending_approval() retorna apenas usuarios ativos nao aprovados."""
        _make_user(db_session, email="apr@t.com", is_approved=True, is_active=True)
        _make_user(db_session, email="pend@t.com", is_approved=False, is_active=True)
        _make_user(db_session, email="inact@t.com", is_approved=False, is_active=False)

        results = usuario_repository.get_pending_approval(db_session)
        emails = [u.email for u in results]

        assert "pend@t.com" in emails
        assert "apr@t.com" not in emails
        assert "inact@t.com" not in emails

    def test_get_stats_returns_correct_counts(self, db_session: Session):
        """get_stats() retorna contagens corretas por categoria."""
        _make_user(db_session, email="s1@t.com", is_approved=True, is_active=True)
        _make_user(db_session, email="s2@t.com", is_approved=True, is_active=True)
        _make_user(db_session, email="s3@t.com", is_approved=False, is_active=True)
        _make_user(db_session, email="s4@t.com", is_approved=False, is_active=False)

        stats = usuario_repository.get_stats(db_session)

        assert stats["total_usuarios"] == 4
        assert stats["usuarios_aprovados"] == 2
        assert stats["usuarios_pendentes"] == 1
        assert stats["usuarios_inativos"] == 1


# ===========================================================================
# 18: Error handling / edge cases in repository operations
# ===========================================================================

class TestRepositoryErrorHandling:
    """Testa casos limites e tratamento de erros nos repositorios."""

    def test_query_for_user_ignores_invalid_filter_column(self, db_session: Session):
        """query_for_user() ignora filtros com colunas inexistentes no modelo."""
        user = _make_user(db_session, email="qfilter@teste.com")
        _make_atestado(db_session, user.id, descricao="Filtro valido")

        # coluna_inexistente nao existe no modelo Atestado - deve ser ignorada
        results = atestado_repository.query_for_user(
            db_session, user.id, coluna_inexistente="valor_qualquer")

        assert len(results) == 1
        assert results[0].descricao_servico == "Filtro valido"
