"""Tests for DocumentoLicitacaoRepository and ChecklistRepository."""
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

from sqlalchemy.orm import Session

from models.documento import (
    ChecklistEdital,
    DocumentoLicitacao,
    DocumentoStatus,
    DocumentoTipo,
)
from repositories.documento_repository import (
    ChecklistRepository,
    DocumentoLicitacaoRepository,
    checklist_repository,
    documento_repository,
)

# ===========================================================================
# Helpers
# ===========================================================================

def _mock_doc(**overrides) -> MagicMock:
    """Create a mock DocumentoLicitacao with defaults."""
    defaults = {
        "id": 1,
        "user_id": 10,
        "licitacao_id": None,
        "nome": "Certidao Federal",
        "tipo_documento": DocumentoTipo.CERTIDAO_FEDERAL,
        "arquivo_path": None,
        "tamanho_bytes": None,
        "data_emissao": None,
        "data_validade": None,
        "status": DocumentoStatus.VALIDO,
        "obrigatorio": False,
        "observacoes": None,
        "created_at": datetime.now(timezone.utc),
        "updated_at": None,
    }
    defaults.update(overrides)
    doc = MagicMock(spec=DocumentoLicitacao)
    for k, v in defaults.items():
        setattr(doc, k, v)
    return doc


def _mock_checklist_item(**overrides) -> MagicMock:
    """Create a mock ChecklistEdital with defaults."""
    defaults = {
        "id": 1,
        "licitacao_id": 100,
        "user_id": 10,
        "descricao": "Certidao FGTS",
        "tipo_documento": DocumentoTipo.CERTIDAO_FGTS,
        "obrigatorio": True,
        "cumprido": False,
        "documento_id": None,
        "observacao": None,
        "ordem": 0,
        "created_at": datetime.now(timezone.utc),
    }
    defaults.update(overrides)
    item = MagicMock(spec=ChecklistEdital)
    for k, v in defaults.items():
        setattr(item, k, v)
    return item


# ===========================================================================
# DocumentoLicitacaoRepository
# ===========================================================================

class TestDocumentoLicitacaoRepository:

    def test_singleton_instance(self):
        assert isinstance(documento_repository, DocumentoLicitacaoRepository)

    def test_get_filtered_no_filters(self):
        db = MagicMock(spec=Session)
        repo = DocumentoLicitacaoRepository()

        mock_query = MagicMock()
        db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query

        repo.get_filtered(db, user_id=10)

        db.query.assert_called_once_with(DocumentoLicitacao)
        mock_query.filter.assert_called_once()
        mock_query.order_by.assert_called_once()

    def test_get_filtered_by_tipo_documento(self):
        db = MagicMock(spec=Session)
        repo = DocumentoLicitacaoRepository()

        mock_query = MagicMock()
        db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query

        repo.get_filtered(db, user_id=10, tipo_documento="certidao_fgts")

        # filter is called twice: once for user_id, once for tipo_documento
        assert mock_query.filter.call_count == 2

    def test_get_filtered_by_status(self):
        db = MagicMock(spec=Session)
        repo = DocumentoLicitacaoRepository()

        mock_query = MagicMock()
        db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query

        repo.get_filtered(db, user_id=10, status="vencendo")

        assert mock_query.filter.call_count == 2

    def test_get_filtered_by_licitacao_id(self):
        db = MagicMock(spec=Session)
        repo = DocumentoLicitacaoRepository()

        mock_query = MagicMock()
        db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query

        repo.get_filtered(db, user_id=10, licitacao_id=5)

        assert mock_query.filter.call_count == 2

    def test_get_filtered_by_busca(self):
        db = MagicMock(spec=Session)
        repo = DocumentoLicitacaoRepository()

        mock_query = MagicMock()
        db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query

        repo.get_filtered(db, user_id=10, busca="certidao")

        assert mock_query.filter.call_count == 2

    def test_get_filtered_all_filters(self):
        db = MagicMock(spec=Session)
        repo = DocumentoLicitacaoRepository()

        mock_query = MagicMock()
        db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query

        repo.get_filtered(
            db, user_id=10,
            tipo_documento="edital",
            status="valido",
            licitacao_id=1,
            busca="pav",
        )

        # user_id + tipo + status + licitacao_id + busca = 5 filter calls
        assert mock_query.filter.call_count == 5

    def test_get_by_licitacao(self):
        db = MagicMock(spec=Session)
        repo = DocumentoLicitacaoRepository()

        docs = [_mock_doc(id=1), _mock_doc(id=2)]
        mock_query = MagicMock()
        db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = docs

        result = repo.get_by_licitacao(db, licitacao_id=5, user_id=10)

        assert len(result) == 2
        db.query.assert_called_once_with(DocumentoLicitacao)

    def test_get_vencendo(self):
        db = MagicMock(spec=Session)
        repo = DocumentoLicitacaoRepository()

        docs = [_mock_doc(status=DocumentoStatus.VENCENDO)]
        mock_query = MagicMock()
        db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = docs

        result = repo.get_vencendo(db, user_id=10, dias=30)

        assert len(result) == 1
        db.query.assert_called_once_with(DocumentoLicitacao)

    def test_get_vencidos(self):
        db = MagicMock(spec=Session)
        repo = DocumentoLicitacaoRepository()

        docs = [_mock_doc(status=DocumentoStatus.VENCIDO)]
        mock_query = MagicMock()
        db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = docs

        result = repo.get_vencidos(db, user_id=10)

        assert len(result) == 1

    def test_get_resumo(self):
        db = MagicMock(spec=Session)
        repo = DocumentoLicitacaoRepository()

        mock_base = MagicMock()
        db.query.return_value = mock_base
        mock_base.filter.return_value = mock_base
        mock_base.count.return_value = 10

        # Mock with_entities chain
        mock_entities = MagicMock()
        mock_base.with_entities.return_value = mock_entities
        mock_entities.group_by.return_value = mock_entities
        mock_entities.all.return_value = [
            (DocumentoStatus.VALIDO, 5),
            (DocumentoStatus.VENCENDO, 3),
            (DocumentoStatus.VENCIDO, 1),
            (DocumentoStatus.NAO_APLICAVEL, 1),
        ]

        result = repo.get_resumo(db, user_id=10)

        assert result["total"] == 10
        assert result["validos"] == 5
        assert result["vencendo"] == 3
        assert result["vencidos"] == 1
        assert result["nao_aplicavel"] == 1

    def test_get_resumo_empty(self):
        db = MagicMock(spec=Session)
        repo = DocumentoLicitacaoRepository()

        mock_base = MagicMock()
        db.query.return_value = mock_base
        mock_base.filter.return_value = mock_base
        mock_base.count.return_value = 0

        mock_entities = MagicMock()
        mock_base.with_entities.return_value = mock_entities
        mock_entities.group_by.return_value = mock_entities
        mock_entities.all.return_value = []

        result = repo.get_resumo(db, user_id=10)

        assert result["total"] == 0
        assert result["validos"] == 0
        assert result["vencendo"] == 0
        assert result["vencidos"] == 0
        assert result["nao_aplicavel"] == 0

    def test_atualizar_status_validade_marks_vencidos(self):
        db = MagicMock(spec=Session)
        repo = DocumentoLicitacaoRepository()

        doc = _mock_doc(
            status=DocumentoStatus.VALIDO,
            data_validade=datetime.now(timezone.utc) - timedelta(days=1),
        )

        mock_query = MagicMock()
        db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query

        # First .all() for vencidos, second for vencendo, third for revalidados
        mock_query.all.side_effect = [[doc], [], []]

        count = repo.atualizar_status_validade(db, dias_alerta=30)

        assert count == 1
        assert doc.status == DocumentoStatus.VENCIDO
        db.commit.assert_called_once()

    def test_atualizar_status_validade_marks_vencendo(self):
        db = MagicMock(spec=Session)
        repo = DocumentoLicitacaoRepository()

        doc = _mock_doc(
            status=DocumentoStatus.VALIDO,
            data_validade=datetime.now(timezone.utc) + timedelta(days=10),
        )

        mock_query = MagicMock()
        db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query

        # First vencidos=[], then vencendo=[doc], then revalidados=[]
        mock_query.all.side_effect = [[], [doc], []]

        count = repo.atualizar_status_validade(db, dias_alerta=30)

        assert count == 1
        assert doc.status == DocumentoStatus.VENCENDO
        db.commit.assert_called_once()

    def test_atualizar_status_validade_revalidates(self):
        db = MagicMock(spec=Session)
        repo = DocumentoLicitacaoRepository()

        doc = _mock_doc(
            status=DocumentoStatus.VENCIDO,
            data_validade=datetime.now(timezone.utc) + timedelta(days=90),
        )

        mock_query = MagicMock()
        db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query

        # vencidos=[], vencendo=[], revalidados=[doc]
        mock_query.all.side_effect = [[], [], [doc]]

        count = repo.atualizar_status_validade(db, dias_alerta=30)

        assert count == 1
        assert doc.status == DocumentoStatus.VALIDO
        db.commit.assert_called_once()

    def test_atualizar_status_validade_no_changes(self):
        db = MagicMock(spec=Session)
        repo = DocumentoLicitacaoRepository()

        mock_query = MagicMock()
        db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.side_effect = [[], [], []]

        count = repo.atualizar_status_validade(db, dias_alerta=30)

        assert count == 0
        db.commit.assert_not_called()


# ===========================================================================
# ChecklistRepository
# ===========================================================================

class TestChecklistRepository:

    def test_singleton_instance(self):
        assert isinstance(checklist_repository, ChecklistRepository)

    def test_get_by_licitacao(self):
        db = MagicMock(spec=Session)
        repo = ChecklistRepository()

        items = [_mock_checklist_item(id=1), _mock_checklist_item(id=2)]
        mock_query = MagicMock()
        db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = items

        result = repo.get_by_licitacao(db, licitacao_id=100, user_id=10)

        assert len(result) == 2
        db.query.assert_called_once_with(ChecklistEdital)

    def test_get_item_for_user_found(self):
        db = MagicMock(spec=Session)
        repo = ChecklistRepository()

        item = _mock_checklist_item(id=5)
        mock_query = MagicMock()
        db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = item

        result = repo.get_item_for_user(db, item_id=5, user_id=10)

        assert result is not None
        assert result.id == 5

    def test_get_item_for_user_not_found(self):
        db = MagicMock(spec=Session)
        repo = ChecklistRepository()

        mock_query = MagicMock()
        db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None

        result = repo.get_item_for_user(db, item_id=999, user_id=10)

        assert result is None

    def test_get_resumo_with_items(self):
        db = MagicMock(spec=Session)
        repo = ChecklistRepository()

        items = [
            _mock_checklist_item(id=1, cumprido=True, obrigatorio=True),
            _mock_checklist_item(id=2, cumprido=False, obrigatorio=True),
            _mock_checklist_item(id=3, cumprido=True, obrigatorio=False),
            _mock_checklist_item(id=4, cumprido=False, obrigatorio=False),
        ]
        mock_query = MagicMock()
        db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = items

        result = repo.get_resumo(db, licitacao_id=100, user_id=10)

        assert result["licitacao_id"] == 100
        assert result["total"] == 4
        assert result["cumpridos"] == 2
        assert result["pendentes"] == 2
        assert result["obrigatorios_pendentes"] == 1
        assert result["percentual"] == 50.0

    def test_get_resumo_empty(self):
        db = MagicMock(spec=Session)
        repo = ChecklistRepository()

        mock_query = MagicMock()
        db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = []

        result = repo.get_resumo(db, licitacao_id=100, user_id=10)

        assert result["total"] == 0
        assert result["cumpridos"] == 0
        assert result["percentual"] == 0

    def test_get_resumo_all_cumpridos(self):
        db = MagicMock(spec=Session)
        repo = ChecklistRepository()

        items = [
            _mock_checklist_item(id=1, cumprido=True, obrigatorio=True),
            _mock_checklist_item(id=2, cumprido=True, obrigatorio=True),
        ]
        mock_query = MagicMock()
        db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = items

        result = repo.get_resumo(db, licitacao_id=100, user_id=10)

        assert result["cumpridos"] == 2
        assert result["pendentes"] == 0
        assert result["obrigatorios_pendentes"] == 0
        assert result["percentual"] == 100.0

    def test_bulk_create_items(self):
        db = MagicMock(spec=Session)
        repo = ChecklistRepository()

        itens_data = [
            {"descricao": "Item 1", "tipo_documento": "certidao_fgts", "obrigatorio": True},
            {"descricao": "Item 2", "obrigatorio": False},
            {"descricao": "Item 3", "observacao": "Nota"},
        ]

        result = repo.bulk_create_items(
            db, licitacao_id=100, user_id=10, itens=itens_data,
        )

        assert len(result) == 3
        assert db.add.call_count == 3
        db.commit.assert_called_once()
        assert db.refresh.call_count == 3
