"""Tests for LicitacaoRepository."""
import uuid

import pytest
from sqlalchemy.orm import Session

from models import Licitacao, LicitacaoHistorico, LicitacaoTag, Usuario
from repositories.licitacao_repository import licitacao_repository

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_user(db: Session, *, email: str = "lic@teste.com") -> Usuario:
    user = Usuario(
        email=email,
        nome="Lic User",
        supabase_id=str(uuid.uuid4()),
        is_active=True,
        is_approved=True,
        is_admin=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _make_licitacao(
    db: Session, user_id: int, *,
    numero: str = "PE 001/2026",
    orgao: str = "Prefeitura Teste",
    objeto: str = "Pavimentacao",
    modalidade: str = "Pregao Eletronico",
    status: str = "identificada",
    uf: str | None = "SP",
    valor_estimado: float | None = None,
) -> Licitacao:
    lic = Licitacao(
        user_id=user_id,
        numero=numero,
        orgao=orgao,
        objeto=objeto,
        modalidade=modalidade,
        status=status,
        uf=uf,
        valor_estimado=valor_estimado,
    )
    db.add(lic)
    db.commit()
    db.refresh(lic)
    return lic


# ===========================================================================
# CRUD Basico
# ===========================================================================

class TestLicitacaoRepositoryCRUD:

    def test_create_and_get_by_id(self, db_session: Session):
        user = _make_user(db_session, email="crud@lic.com")
        lic = _make_licitacao(db_session, user.id)

        found = licitacao_repository.get_by_id(db_session, lic.id)
        assert found is not None
        assert found.numero == "PE 001/2026"
        assert found.user_id == user.id

    def test_get_by_id_for_user_ownership(self, db_session: Session):
        user_a = _make_user(db_session, email="a@lic.com")
        user_b = _make_user(db_session, email="b@lic.com")
        lic = _make_licitacao(db_session, user_a.id)

        assert licitacao_repository.get_by_id_for_user(db_session, lic.id, user_a.id) is not None
        assert licitacao_repository.get_by_id_for_user(db_session, lic.id, user_b.id) is None

    def test_get_by_id_with_relations(self, db_session: Session):
        user = _make_user(db_session, email="rel@lic.com")
        lic = _make_licitacao(db_session, user.id)

        # Add tag and historico
        tag = LicitacaoTag(licitacao_id=lic.id, tag="teste")
        db_session.add(tag)
        hist = LicitacaoHistorico(
            licitacao_id=lic.id, user_id=user.id,
            status_anterior=None, status_novo="identificada",
        )
        db_session.add(hist)
        db_session.commit()

        loaded = licitacao_repository.get_by_id_with_relations(db_session, lic.id, user.id)
        assert loaded is not None
        assert len(loaded.tags) == 1
        assert len(loaded.historico) == 1

    def test_delete_cascades_to_tags_and_historico(self, db_session: Session):
        user = _make_user(db_session, email="del@lic.com")
        lic = _make_licitacao(db_session, user.id)
        lic_id = lic.id

        db_session.add(LicitacaoTag(licitacao_id=lic_id, tag="tag1"))
        db_session.add(LicitacaoHistorico(
            licitacao_id=lic_id, user_id=user.id,
            status_anterior=None, status_novo="identificada",
        ))
        db_session.commit()

        licitacao_repository.delete(db_session, lic)

        assert db_session.query(LicitacaoTag).filter_by(licitacao_id=lic_id).count() == 0
        assert db_session.query(LicitacaoHistorico).filter_by(licitacao_id=lic_id).count() == 0


# ===========================================================================
# Filtros
# ===========================================================================

class TestLicitacaoRepositoryFilters:

    def test_get_filtered_by_status(self, db_session: Session):
        user = _make_user(db_session, email="filt@lic.com")
        _make_licitacao(db_session, user.id, numero="L1", status="identificada")
        _make_licitacao(db_session, user.id, numero="L2", status="vencida")
        _make_licitacao(db_session, user.id, numero="L3", status="identificada")

        results = licitacao_repository.get_filtered(
            db_session, user.id, status="identificada"
        ).all()
        assert len(results) == 2

    def test_get_filtered_by_uf(self, db_session: Session):
        user = _make_user(db_session, email="uf@lic.com")
        _make_licitacao(db_session, user.id, numero="L1", uf="SP")
        _make_licitacao(db_session, user.id, numero="L2", uf="RJ")

        results = licitacao_repository.get_filtered(
            db_session, user.id, uf="RJ"
        ).all()
        assert len(results) == 1
        assert results[0].uf == "RJ"

    def test_get_filtered_by_modalidade(self, db_session: Session):
        user = _make_user(db_session, email="mod@lic.com")
        _make_licitacao(db_session, user.id, numero="L1", modalidade="Pregao Eletronico")
        _make_licitacao(db_session, user.id, numero="L2", modalidade="Concorrencia")

        results = licitacao_repository.get_filtered(
            db_session, user.id, modalidade="Concorrencia"
        ).all()
        assert len(results) == 1

    def test_get_filtered_by_busca(self, db_session: Session):
        user = _make_user(db_session, email="busca@lic.com")
        _make_licitacao(db_session, user.id, numero="PE 001", objeto="Pavimentacao")
        _make_licitacao(db_session, user.id, numero="CC 002", objeto="Drenagem pluvial")

        results = licitacao_repository.get_filtered(
            db_session, user.id, busca="drenagem"
        ).all()
        assert len(results) == 1
        assert "Drenagem" in results[0].objeto

    def test_get_filtered_busca_by_orgao(self, db_session: Session):
        user = _make_user(db_session, email="buscaorg@lic.com")
        _make_licitacao(db_session, user.id, orgao="DNIT")
        _make_licitacao(db_session, user.id, orgao="Prefeitura SP")

        results = licitacao_repository.get_filtered(
            db_session, user.id, busca="DNIT"
        ).all()
        assert len(results) == 1

    def test_get_filtered_user_isolation(self, db_session: Session):
        user_a = _make_user(db_session, email="isoa@lic.com")
        user_b = _make_user(db_session, email="isob@lic.com")
        _make_licitacao(db_session, user_a.id, numero="L-A")
        _make_licitacao(db_session, user_b.id, numero="L-B")

        results_a = licitacao_repository.get_filtered(db_session, user_a.id).all()
        results_b = licitacao_repository.get_filtered(db_session, user_b.id).all()
        assert len(results_a) == 1
        assert len(results_b) == 1
        assert results_a[0].numero == "L-A"

    def test_get_filtered_combined(self, db_session: Session):
        user = _make_user(db_session, email="comb@lic.com")
        _make_licitacao(db_session, user.id, numero="L1", status="identificada", uf="SP", modalidade="Pregao Eletronico")
        _make_licitacao(db_session, user.id, numero="L2", status="identificada", uf="RJ", modalidade="Pregao Eletronico")
        _make_licitacao(db_session, user.id, numero="L3", status="vencida", uf="SP", modalidade="Pregao Eletronico")

        results = licitacao_repository.get_filtered(
            db_session, user.id, status="identificada", uf="SP"
        ).all()
        assert len(results) == 1
        assert results[0].numero == "L1"


# ===========================================================================
# Status Transitions
# ===========================================================================

class TestStatusTransitions:

    def test_transition_creates_historico(self, db_session: Session):
        user = _make_user(db_session, email="trans@lic.com")
        lic = _make_licitacao(db_session, user.id, status="identificada")

        hist = licitacao_repository.transition_status(
            db_session, lic, "em_analise", user.id, "Iniciando analise"
        )

        assert hist.status_anterior == "identificada"
        assert hist.status_novo == "em_analise"
        assert hist.observacao == "Iniciando analise"
        assert lic.status == "em_analise"

    def test_transition_updates_decisao_go_on_desistida(self, db_session: Session):
        user = _make_user(db_session, email="nogo@lic.com")
        lic = _make_licitacao(db_session, user.id, status="identificada")
        assert lic.decisao_go is None

        licitacao_repository.transition_status(
            db_session, lic, "desistida", user.id
        )
        assert lic.decisao_go is False

    def test_multiple_transitions(self, db_session: Session):
        user = _make_user(db_session, email="multi@lic.com")
        lic = _make_licitacao(db_session, user.id, status="identificada")

        licitacao_repository.transition_status(db_session, lic, "em_analise", user.id)
        licitacao_repository.transition_status(db_session, lic, "go_nogo", user.id)
        licitacao_repository.transition_status(db_session, lic, "elaborando_proposta", user.id)

        historico = licitacao_repository.get_historico(db_session, lic.id)
        assert len(historico) == 3
        assert lic.status == "elaborando_proposta"


# ===========================================================================
# Tags
# ===========================================================================

class TestLicitacaoTags:

    def test_add_tag(self, db_session: Session):
        user = _make_user(db_session, email="tag@lic.com")
        lic = _make_licitacao(db_session, user.id)

        tag = licitacao_repository.add_tag(db_session, lic.id, "infraestrutura")
        assert tag.tag == "infraestrutura"
        assert tag.licitacao_id == lic.id

    def test_add_tag_normalizes_to_lowercase(self, db_session: Session):
        user = _make_user(db_session, email="lower@lic.com")
        lic = _make_licitacao(db_session, user.id)

        tag = licitacao_repository.add_tag(db_session, lic.id, "  URGENTE  ")
        assert tag.tag == "urgente"

    def test_add_duplicate_tag_raises(self, db_session: Session):
        user = _make_user(db_session, email="dup@lic.com")
        lic = _make_licitacao(db_session, user.id)

        licitacao_repository.add_tag(db_session, lic.id, "teste")
        with pytest.raises(Exception):
            licitacao_repository.add_tag(db_session, lic.id, "teste")

    def test_remove_tag(self, db_session: Session):
        user = _make_user(db_session, email="rmtag@lic.com")
        lic = _make_licitacao(db_session, user.id)
        licitacao_repository.add_tag(db_session, lic.id, "remover")

        result = licitacao_repository.remove_tag(db_session, lic.id, "remover")
        assert result is True

        result = licitacao_repository.remove_tag(db_session, lic.id, "remover")
        assert result is False

    def test_remove_nonexistent_tag(self, db_session: Session):
        user = _make_user(db_session, email="notag@lic.com")
        lic = _make_licitacao(db_session, user.id)

        result = licitacao_repository.remove_tag(db_session, lic.id, "inexistente")
        assert result is False


# ===========================================================================
# Estatisticas
# ===========================================================================

class TestLicitacaoEstatisticas:

    def test_get_estatisticas_empty(self, db_session: Session):
        user = _make_user(db_session, email="empty@lic.com")
        stats = licitacao_repository.get_estatisticas(db_session, user.id)
        assert stats["total"] == 0
        assert stats["por_status"] == {}

    def test_get_estatisticas_with_data(self, db_session: Session):
        user = _make_user(db_session, email="stats@lic.com")
        _make_licitacao(db_session, user.id, numero="L1", status="identificada", uf="SP", modalidade="Pregao Eletronico")
        _make_licitacao(db_session, user.id, numero="L2", status="identificada", uf="SP", modalidade="Concorrencia")
        _make_licitacao(db_session, user.id, numero="L3", status="vencida", uf="RJ", modalidade="Pregao Eletronico")

        stats = licitacao_repository.get_estatisticas(db_session, user.id)
        assert stats["total"] == 3
        assert stats["por_status"]["identificada"] == 2
        assert stats["por_status"]["vencida"] == 1
        assert stats["por_uf"]["SP"] == 2
        assert stats["por_uf"]["RJ"] == 1
        assert stats["por_modalidade"]["Pregao Eletronico"] == 2


# ===========================================================================
# Historico
# ===========================================================================

class TestLicitacaoHistorico:

    def test_get_historico_ordered_desc(self, db_session: Session):
        user = _make_user(db_session, email="hist@lic.com")
        lic = _make_licitacao(db_session, user.id, status="identificada")

        licitacao_repository.transition_status(db_session, lic, "em_analise", user.id, "Passo 1")
        licitacao_repository.transition_status(db_session, lic, "go_nogo", user.id, "Passo 2")

        historico = licitacao_repository.get_historico(db_session, lic.id)
        assert len(historico) == 2
        # Mais recente primeiro
        assert historico[0].status_novo == "go_nogo"
        assert historico[1].status_novo == "em_analise"
