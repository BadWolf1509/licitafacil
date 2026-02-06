"""
Testes para services.sync_processor.

Verifica processamento sincrono de atestados: criacao, atualizacao,
tratamento de erros e singleton.
"""
import pytest
from datetime import date
from unittest.mock import patch, MagicMock, PropertyMock

from models import Atestado


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_resultado(**overrides):
    """Retorna um dicionario-resultado padrao para testes."""
    base = {
        "descricao_servico": "Pavimentacao asfaltica",
        "quantidade": 1500.0,
        "unidade": "m2",
        "contratante": "Prefeitura de Teste",
        "data_emissao": "2024-01-15",
        "texto_extraido": "Texto extraido do PDF",
        "servicos": [
            {"item": "1.1", "descricao": "Asfalto CBUQ", "quantidade": 1500.0, "unidade": "M2"},
        ],
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# test_process_atestado_success
# ---------------------------------------------------------------------------

class TestProcessAtestadoSuccess:
    """Mock processor.process, verify return dict."""

    @patch("services.sync_processor.AtestadoProcessor")
    def test_returns_success_dict(self, MockProcessor, db_session, test_user):
        resultado = _make_resultado()
        MockProcessor.return_value.process.return_value = resultado

        from services.sync_processor import SyncProcessor
        sp = SyncProcessor()
        sp._processor = MockProcessor.return_value

        resp = sp.process_atestado(
            db=db_session,
            user_id=test_user.id,
            file_path="/tmp/fake.pdf",
            original_filename="fake.pdf",
        )

        assert resp["success"] is True
        assert resp["atestado_id"] is not None
        assert resp["servicos_count"] == 1
        assert "dados" in resp
        MockProcessor.return_value.process.assert_called_once_with(
            "/tmp/fake.pdf", use_vision=True
        )


# ---------------------------------------------------------------------------
# test_process_atestado_creates_new_record
# ---------------------------------------------------------------------------

class TestProcessAtestadoCreatesNewRecord:
    """Verify DB insert via mock pipeline."""

    @patch("services.sync_processor.AtestadoProcessor")
    def test_new_atestado_persisted(self, MockProcessor, db_session, test_user):
        resultado = _make_resultado()
        MockProcessor.return_value.process.return_value = resultado

        from services.sync_processor import SyncProcessor
        sp = SyncProcessor()
        sp._processor = MockProcessor.return_value

        resp = sp.process_atestado(
            db=db_session,
            user_id=test_user.id,
            file_path="/tmp/new_file.pdf",
            original_filename="new_file.pdf",
        )

        assert resp["success"] is True
        atestado = db_session.query(Atestado).filter_by(id=resp["atestado_id"]).first()
        assert atestado is not None
        assert atestado.user_id == test_user.id
        assert atestado.arquivo_path == "/tmp/new_file.pdf"
        assert atestado.descricao_servico == "Pavimentacao asfaltica"


# ---------------------------------------------------------------------------
# test_process_atestado_updates_existing_record
# ---------------------------------------------------------------------------

class TestProcessAtestadoUpdatesExistingRecord:
    """When file already processed, should update existing row."""

    @patch("services.sync_processor.AtestadoProcessor")
    def test_existing_atestado_updated(self, MockProcessor, db_session, test_user):
        # Criar atestado existente com o mesmo arquivo
        existing = Atestado(
            user_id=test_user.id,
            descricao_servico="Descricao antiga",
            quantidade=100.0,
            unidade="m",
            arquivo_path="/tmp/existing.pdf",
        )
        db_session.add(existing)
        db_session.commit()
        db_session.refresh(existing)
        existing_id = existing.id

        resultado = _make_resultado(descricao_servico="Descricao nova", quantidade=9999.0)
        MockProcessor.return_value.process.return_value = resultado

        from services.sync_processor import SyncProcessor
        sp = SyncProcessor()
        sp._processor = MockProcessor.return_value

        resp = sp.process_atestado(
            db=db_session,
            user_id=test_user.id,
            file_path="/tmp/existing.pdf",
            original_filename="existing.pdf",
        )

        assert resp["success"] is True
        assert resp["atestado_id"] == existing_id

        db_session.expire_all()
        updated = db_session.query(Atestado).filter_by(id=existing_id).first()
        assert updated.descricao_servico == "Descricao nova"
        assert float(updated.quantidade) == pytest.approx(9999.0)


# ---------------------------------------------------------------------------
# test_process_atestado_failure
# ---------------------------------------------------------------------------

class TestProcessAtestadoFailure:
    """Exception returns success=False."""

    @patch("services.sync_processor.AtestadoProcessor")
    def test_exception_returns_failure(self, MockProcessor, db_session, test_user):
        MockProcessor.return_value.process.side_effect = RuntimeError("OCR falhou")

        from services.sync_processor import SyncProcessor
        sp = SyncProcessor()
        sp._processor = MockProcessor.return_value

        resp = sp.process_atestado(
            db=db_session,
            user_id=test_user.id,
            file_path="/tmp/bad.pdf",
            original_filename="bad.pdf",
        )

        assert resp["success"] is False
        assert "OCR falhou" in resp["error"]
        assert resp["atestado_id"] is None


# ---------------------------------------------------------------------------
# test_process_atestado_with_storage_path
# ---------------------------------------------------------------------------

class TestProcessAtestadoWithStoragePath:
    """When storage_path is provided, it should be used for arquivo_path."""

    @patch("services.sync_processor.AtestadoProcessor")
    def test_storage_path_used(self, MockProcessor, db_session, test_user):
        resultado = _make_resultado()
        MockProcessor.return_value.process.return_value = resultado

        from services.sync_processor import SyncProcessor
        sp = SyncProcessor()
        sp._processor = MockProcessor.return_value

        resp = sp.process_atestado(
            db=db_session,
            user_id=test_user.id,
            file_path="/tmp/local.pdf",
            original_filename="doc.pdf",
            storage_path="supabase/bucket/doc.pdf",
        )

        assert resp["success"] is True
        atestado = db_session.query(Atestado).filter_by(id=resp["atestado_id"]).first()
        assert atestado.arquivo_path == "supabase/bucket/doc.pdf"


# ---------------------------------------------------------------------------
# test_process_atestado_without_storage_path
# ---------------------------------------------------------------------------

class TestProcessAtestadoWithoutStoragePath:
    """When no storage_path, file_path should be used for arquivo_path."""

    @patch("services.sync_processor.AtestadoProcessor")
    def test_file_path_used(self, MockProcessor, db_session, test_user):
        resultado = _make_resultado()
        MockProcessor.return_value.process.return_value = resultado

        from services.sync_processor import SyncProcessor
        sp = SyncProcessor()
        sp._processor = MockProcessor.return_value

        resp = sp.process_atestado(
            db=db_session,
            user_id=test_user.id,
            file_path="/tmp/local_only.pdf",
            original_filename="local_only.pdf",
        )

        assert resp["success"] is True
        atestado = db_session.query(Atestado).filter_by(id=resp["atestado_id"]).first()
        assert atestado.arquivo_path == "/tmp/local_only.pdf"


# ---------------------------------------------------------------------------
# test_save_atestado_parses_date
# ---------------------------------------------------------------------------

class TestSaveAtestadoParsesDate:
    """Verify date parsing via _save_atestado."""

    @patch("services.sync_processor.AtestadoProcessor")
    def test_iso_date_parsed(self, MockProcessor, db_session, test_user):
        resultado = _make_resultado(data_emissao="2024-06-30")
        MockProcessor.return_value.process.return_value = resultado

        from services.sync_processor import SyncProcessor
        sp = SyncProcessor()
        sp._processor = MockProcessor.return_value

        resp = sp.process_atestado(
            db=db_session,
            user_id=test_user.id,
            file_path="/tmp/date_test.pdf",
            original_filename="date_test.pdf",
        )

        atestado = db_session.query(Atestado).filter_by(id=resp["atestado_id"]).first()
        assert atestado.data_emissao is not None
        # data_emissao pode ser date ou datetime; verificar ano/mes/dia
        assert atestado.data_emissao.year == 2024
        assert atestado.data_emissao.month == 6
        assert atestado.data_emissao.day == 30


# ---------------------------------------------------------------------------
# test_save_atestado_orders_services
# ---------------------------------------------------------------------------

class TestSaveAtestadoOrdersServices:
    """Verify ordenar_servicos is called."""

    @patch("services.sync_processor.AtestadoProcessor")
    def test_services_are_ordered(self, MockProcessor, db_session, test_user):
        servicos = [
            {"item": "2.1", "descricao": "B", "quantidade": 10, "unidade": "M2"},
            {"item": "1.1", "descricao": "A", "quantidade": 20, "unidade": "ML"},
        ]
        resultado = _make_resultado(servicos=servicos)
        MockProcessor.return_value.process.return_value = resultado

        from services.sync_processor import SyncProcessor
        sp = SyncProcessor()
        sp._processor = MockProcessor.return_value

        resp = sp.process_atestado(
            db=db_session,
            user_id=test_user.id,
            file_path="/tmp/order_test.pdf",
            original_filename="order_test.pdf",
        )

        atestado = db_session.query(Atestado).filter_by(id=resp["atestado_id"]).first()
        assert atestado.servicos_json is not None
        items = [s["item"] for s in atestado.servicos_json]
        assert items == ["1.1", "2.1"], "Services should be ordered by item number"


# ---------------------------------------------------------------------------
# test_get_sync_processor_singleton
# ---------------------------------------------------------------------------

class TestGetSyncProcessorSingleton:
    """Returns same instance on repeated calls."""

    def test_singleton_identity(self):
        import services.sync_processor as mod
        # Reset singleton state
        mod._sync_processor = None

        first = mod.get_sync_processor()
        second = mod.get_sync_processor()

        assert first is second
        assert isinstance(first, mod.SyncProcessor)

        # Cleanup: reset so other tests are unaffected
        mod._sync_processor = None


# ---------------------------------------------------------------------------
# test_process_atestado_empty_services
# ---------------------------------------------------------------------------

class TestProcessAtestadoEmptyServices:
    """When no services extracted, servicos_count should be 0."""

    @patch("services.sync_processor.AtestadoProcessor")
    def test_empty_services(self, MockProcessor, db_session, test_user):
        resultado = _make_resultado(servicos=[])
        MockProcessor.return_value.process.return_value = resultado

        from services.sync_processor import SyncProcessor
        sp = SyncProcessor()
        sp._processor = MockProcessor.return_value

        resp = sp.process_atestado(
            db=db_session,
            user_id=test_user.id,
            file_path="/tmp/empty_svc.pdf",
            original_filename="empty_svc.pdf",
        )

        assert resp["success"] is True
        assert resp["servicos_count"] == 0
        atestado = db_session.query(Atestado).filter_by(id=resp["atestado_id"]).first()
        # Empty list -> servicos_json should be None (falsy list is stored as None)
        assert atestado.servicos_json is None
