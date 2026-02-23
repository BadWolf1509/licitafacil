"""Tests for PNCP repositories with mocked SQLAlchemy session."""
from datetime import datetime
from unittest.mock import MagicMock

import pytest

from models.pncp import PncpMonitoramento, PncpResultado
from repositories.pncp_repository import (
    PncpMonitoramentoRepository,
    PncpResultadoRepository,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_db():
    """Create a mocked SQLAlchemy Session."""
    db = MagicMock()
    # Build a fluent query chain that returns itself on chained calls
    query = MagicMock()
    query.filter.return_value = query
    query.order_by.return_value = query
    query.group_by.return_value = query
    query.all.return_value = []
    query.first.return_value = None
    query.count.return_value = 0
    db.query.return_value = query
    return db


@pytest.fixture
def monit_repo():
    return PncpMonitoramentoRepository()


@pytest.fixture
def result_repo():
    return PncpResultadoRepository()


# ===========================================================================
# PncpMonitoramentoRepository
# ===========================================================================


class TestPncpMonitoramentoRepositoryInit:

    def test_model_is_pncp_monitoramento(self, monit_repo):
        assert monit_repo.model is PncpMonitoramento


class TestMonitoramentoGetFiltered:

    def test_get_filtered_user_id_only(self, mock_db, monit_repo):
        """Filters by user_id and orders by created_at desc."""
        monit_repo.get_filtered(mock_db, user_id=1)
        mock_db.query.assert_called_once_with(PncpMonitoramento)
        query = mock_db.query.return_value
        query.filter.assert_called_once()
        query.order_by.assert_called_once()

    def test_get_filtered_with_ativo_true(self, mock_db, monit_repo):
        """Adds ativo filter when provided."""
        monit_repo.get_filtered(mock_db, user_id=1, ativo=True)
        query = mock_db.query.return_value
        # Two filter calls: user_id + ativo
        assert query.filter.call_count == 2

    def test_get_filtered_with_ativo_false(self, mock_db, monit_repo):
        monit_repo.get_filtered(mock_db, user_id=1, ativo=False)
        query = mock_db.query.return_value
        assert query.filter.call_count == 2

    def test_get_filtered_with_busca(self, mock_db, monit_repo):
        """Adds ilike filter for nome when busca is provided."""
        monit_repo.get_filtered(mock_db, user_id=1, busca="pavimentacao")
        query = mock_db.query.return_value
        # Two filter calls: user_id + busca ilike
        assert query.filter.call_count == 2

    def test_get_filtered_with_all_params(self, mock_db, monit_repo):
        """All three filter layers applied."""
        monit_repo.get_filtered(mock_db, user_id=1, ativo=True, busca="asfalto")
        query = mock_db.query.return_value
        # Three filter calls: user_id + ativo + busca
        assert query.filter.call_count == 3

    def test_get_filtered_returns_query(self, mock_db, monit_repo):
        result = monit_repo.get_filtered(mock_db, user_id=1)
        # Should return the final query chain (after order_by)
        assert result is not None


class TestMonitoramentoGetAtivos:

    def test_get_ativos_returns_all_active(self, mock_db, monit_repo):
        mock_monitor = MagicMock(spec=PncpMonitoramento)
        mock_monitor.ativo = True
        mock_db.query.return_value.filter.return_value.all.return_value = [mock_monitor]

        result = monit_repo.get_ativos(mock_db)
        assert len(result) == 1
        mock_db.query.assert_called_once_with(PncpMonitoramento)

    def test_get_ativos_empty(self, mock_db, monit_repo):
        mock_db.query.return_value.filter.return_value.all.return_value = []
        result = monit_repo.get_ativos(mock_db)
        assert result == []


class TestMonitoramentoAtualizarUltimoCheck:

    def test_atualizar_ultimo_check_found(self, mock_db, monit_repo):
        mock_monitor = MagicMock(spec=PncpMonitoramento)
        mock_db.query.return_value.filter.return_value.first.return_value = mock_monitor
        now = datetime(2026, 1, 15, 10, 0)

        monit_repo.atualizar_ultimo_check(mock_db, monitoramento_id=1, data=now)

        assert mock_monitor.ultimo_check == now
        mock_db.commit.assert_called_once()

    def test_atualizar_ultimo_check_not_found(self, mock_db, monit_repo):
        mock_db.query.return_value.filter.return_value.first.return_value = None
        now = datetime(2026, 1, 15, 10, 0)

        monit_repo.atualizar_ultimo_check(mock_db, monitoramento_id=999, data=now)
        # Should NOT commit if monitor not found
        mock_db.commit.assert_not_called()


# ===========================================================================
# PncpResultadoRepository
# ===========================================================================


class TestPncpResultadoRepositoryInit:

    def test_model_is_pncp_resultado(self, result_repo):
        assert result_repo.model is PncpResultado


class TestResultadoGetFiltered:

    def test_get_filtered_user_id_only(self, mock_db, result_repo):
        result_repo.get_filtered(mock_db, user_id=1)
        mock_db.query.assert_called_once_with(PncpResultado)
        query = mock_db.query.return_value
        query.filter.assert_called_once()
        query.order_by.assert_called_once()

    def test_get_filtered_with_monitoramento_id(self, mock_db, result_repo):
        result_repo.get_filtered(mock_db, user_id=1, monitoramento_id=5)
        query = mock_db.query.return_value
        assert query.filter.call_count == 2

    def test_get_filtered_with_status(self, mock_db, result_repo):
        result_repo.get_filtered(mock_db, user_id=1, status="novo")
        query = mock_db.query.return_value
        assert query.filter.call_count == 2

    def test_get_filtered_with_uf(self, mock_db, result_repo):
        result_repo.get_filtered(mock_db, user_id=1, uf="SP")
        query = mock_db.query.return_value
        assert query.filter.call_count == 2

    def test_get_filtered_with_busca(self, mock_db, result_repo):
        result_repo.get_filtered(mock_db, user_id=1, busca="asfalto")
        query = mock_db.query.return_value
        assert query.filter.call_count == 2

    def test_get_filtered_with_all_filters(self, mock_db, result_repo):
        result_repo.get_filtered(
            mock_db, user_id=1,
            monitoramento_id=5, status="novo", uf="SP", busca="asfalto",
        )
        query = mock_db.query.return_value
        # user_id + monitoramento_id + status + uf + busca
        assert query.filter.call_count == 5

    def test_get_filtered_returns_query(self, mock_db, result_repo):
        result = result_repo.get_filtered(mock_db, user_id=1)
        assert result is not None


class TestResultadoExisteResultado:

    def test_existe_resultado_true(self, mock_db, result_repo):
        mock_resultado = MagicMock(spec=PncpResultado)
        mock_db.query.return_value.filter.return_value.first.return_value = mock_resultado

        assert result_repo.existe_resultado(mock_db, "CTRL-001", user_id=1) is True

    def test_existe_resultado_false(self, mock_db, result_repo):
        mock_db.query.return_value.filter.return_value.first.return_value = None

        assert result_repo.existe_resultado(mock_db, "CTRL-999", user_id=1) is False


class TestResultadoContarPorStatus:

    def test_contar_por_status_with_data(self, mock_db, result_repo):
        mock_db.query.return_value.filter.return_value.group_by.return_value.all.return_value = [
            ("novo", 5),
            ("interessante", 3),
            ("descartado", 1),
        ]

        result = result_repo.contar_por_status(mock_db, user_id=1)
        assert result == {"novo": 5, "interessante": 3, "descartado": 1}

    def test_contar_por_status_empty(self, mock_db, result_repo):
        mock_db.query.return_value.filter.return_value.group_by.return_value.all.return_value = []

        result = result_repo.contar_por_status(mock_db, user_id=1)
        assert result == {}

    def test_contar_por_status_single_status(self, mock_db, result_repo):
        mock_db.query.return_value.filter.return_value.group_by.return_value.all.return_value = [
            ("importado", 10),
        ]

        result = result_repo.contar_por_status(mock_db, user_id=1)
        assert result == {"importado": 10}
