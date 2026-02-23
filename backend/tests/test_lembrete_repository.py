"""Tests for LembreteRepository."""
import uuid
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from models import Lembrete, Usuario
from repositories.lembrete_repository import lembrete_repository

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_user(db: Session, *, email: str = "lem@teste.com") -> Usuario:
    user = Usuario(
        email=email, nome="Lem User",
        supabase_id=str(uuid.uuid4()),
        is_active=True, is_approved=True, is_admin=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _make_lembrete(
    db: Session, user_id: int, *,
    titulo: str = "Lembrete Teste",
    data_lembrete: datetime | None = None,
    status: str = "pendente",
    tipo: str = "manual",
    licitacao_id: int | None = None,
) -> Lembrete:
    if data_lembrete is None:
        data_lembrete = datetime.now() + timedelta(hours=1)
    lem = Lembrete(
        user_id=user_id,
        titulo=titulo,
        data_lembrete=data_lembrete,
        status=status,
        tipo=tipo,
        licitacao_id=licitacao_id,
    )
    db.add(lem)
    db.commit()
    db.refresh(lem)
    return lem


# ===========================================================================
# CRUD Basico
# ===========================================================================

class TestLembreteRepositoryCRUD:

    def test_create_and_get_by_id(self, db_session: Session):
        user = _make_user(db_session, email="crud@lem.com")
        lem = _make_lembrete(db_session, user.id)

        found = lembrete_repository.get_by_id(db_session, lem.id)
        assert found is not None
        assert found.titulo == "Lembrete Teste"
        assert found.user_id == user.id

    def test_get_by_id_for_user_ownership(self, db_session: Session):
        user_a = _make_user(db_session, email="a@lem.com")
        user_b = _make_user(db_session, email="b@lem.com")
        lem = _make_lembrete(db_session, user_a.id)

        assert lembrete_repository.get_by_id_for_user(db_session, lem.id, user_a.id) is not None
        assert lembrete_repository.get_by_id_for_user(db_session, lem.id, user_b.id) is None

    def test_delete(self, db_session: Session):
        user = _make_user(db_session, email="del@lem.com")
        lem = _make_lembrete(db_session, user.id)
        lem_id = lem.id

        lembrete_repository.delete(db_session, lem)
        assert lembrete_repository.get_by_id(db_session, lem_id) is None


# ===========================================================================
# Calendario
# ===========================================================================

class TestLembreteCalendario:

    def test_get_calendario_range(self, db_session: Session):
        user = _make_user(db_session, email="cal@lem.com")
        now = datetime.now()

        _make_lembrete(db_session, user.id, titulo="Dentro",
                       data_lembrete=now + timedelta(hours=1))
        _make_lembrete(db_session, user.id, titulo="Fora",
                       data_lembrete=now + timedelta(days=30))

        inicio = now - timedelta(hours=1)
        fim = now + timedelta(days=2)
        result = lembrete_repository.get_calendario(db_session, user.id, inicio, fim)
        assert len(result) == 1
        assert result[0].titulo == "Dentro"

    def test_get_calendario_empty(self, db_session: Session):
        user = _make_user(db_session, email="calempty@lem.com")
        inicio = datetime(2020, 1, 1)
        fim = datetime(2020, 1, 31)
        result = lembrete_repository.get_calendario(db_session, user.id, inicio, fim)
        assert len(result) == 0

    def test_get_calendario_user_isolation(self, db_session: Session):
        user_a = _make_user(db_session, email="cala@lem.com")
        user_b = _make_user(db_session, email="calb@lem.com")
        now = datetime.now()

        _make_lembrete(db_session, user_a.id, data_lembrete=now + timedelta(hours=1))
        _make_lembrete(db_session, user_b.id, data_lembrete=now + timedelta(hours=1))

        inicio = now - timedelta(hours=1)
        fim = now + timedelta(days=1)
        result = lembrete_repository.get_calendario(db_session, user_a.id, inicio, fim)
        assert len(result) == 1


# ===========================================================================
# Pendentes para Envio
# ===========================================================================

class TestLembretePendentes:

    def test_get_pendentes_para_envio(self, db_session: Session):
        user = _make_user(db_session, email="pend@lem.com")
        now = datetime.now()

        _make_lembrete(db_session, user.id, titulo="Pronto",
                       data_lembrete=now - timedelta(hours=1), status="pendente")
        _make_lembrete(db_session, user.id, titulo="Futuro",
                       data_lembrete=now + timedelta(days=5), status="pendente")
        _make_lembrete(db_session, user.id, titulo="Ja enviado",
                       data_lembrete=now - timedelta(hours=2), status="enviado")

        result = lembrete_repository.get_pendentes_para_envio(db_session, now)
        assert len(result) == 1
        assert result[0].titulo == "Pronto"

    def test_marcar_enviado(self, db_session: Session):
        user = _make_user(db_session, email="env@lem.com")
        lem = _make_lembrete(db_session, user.id)
        assert lem.status == "pendente"
        assert lem.enviado_em is None

        result = lembrete_repository.marcar_enviado(db_session, lem)
        assert result.status == "enviado"
        assert result.enviado_em is not None


# ===========================================================================
# Filtros
# ===========================================================================

class TestLembreteFilters:

    def test_get_filtered_by_status(self, db_session: Session):
        user = _make_user(db_session, email="filt@lem.com")
        _make_lembrete(db_session, user.id, titulo="L1", status="pendente")
        _make_lembrete(db_session, user.id, titulo="L2", status="enviado")

        results = lembrete_repository.get_filtered(
            db_session, user.id, status="pendente"
        ).all()
        assert len(results) == 1
        assert results[0].titulo == "L1"

    def test_get_filtered_by_tipo(self, db_session: Session):
        user = _make_user(db_session, email="tipo@lem.com")
        _make_lembrete(db_session, user.id, titulo="L1", tipo="manual")
        _make_lembrete(db_session, user.id, titulo="L2", tipo="abertura_licitacao")

        results = lembrete_repository.get_filtered(
            db_session, user.id, tipo="abertura_licitacao"
        ).all()
        assert len(results) == 1
        assert results[0].titulo == "L2"

    def test_get_filtered_user_isolation(self, db_session: Session):
        user_a = _make_user(db_session, email="isoa@lem.com")
        user_b = _make_user(db_session, email="isob@lem.com")
        _make_lembrete(db_session, user_a.id, titulo="LA")
        _make_lembrete(db_session, user_b.id, titulo="LB")

        results_a = lembrete_repository.get_filtered(db_session, user_a.id).all()
        assert len(results_a) == 1
        assert results_a[0].titulo == "LA"
