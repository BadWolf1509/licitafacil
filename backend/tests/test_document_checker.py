"""Tests for DocumentExpiryChecker service."""
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from models.documento import DocumentoLicitacao, DocumentoStatus

# ===========================================================================
# DocumentExpiryChecker.check()
# ===========================================================================


class TestDocumentExpiryCheckerCheck:

    @pytest.mark.asyncio
    async def test_check_calls_atualizar_status_validade(self):
        """check() should call atualizar_status_validade on the repository."""
        with (
            patch("database.SessionLocal") as MockSession,
            patch(
                "repositories.documento_repository.documento_repository"
            ) as mock_repo,
        ):
            mock_db = MagicMock()
            MockSession.return_value = mock_db
            mock_repo.atualizar_status_validade.return_value = 0

            from services.notification.document_checker import DocumentExpiryChecker

            checker = DocumentExpiryChecker()
            await checker.check()

            mock_repo.atualizar_status_validade.assert_called_once()
            mock_db.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_calls_notificar_when_updated(self):
        """check() should call _notificar_vencimentos after updating."""
        with (
            patch("database.SessionLocal") as MockSession,
            patch(
                "repositories.documento_repository.documento_repository"
            ) as mock_repo,
        ):
            mock_db = MagicMock()
            MockSession.return_value = mock_db
            mock_repo.atualizar_status_validade.return_value = 3

            from services.notification.document_checker import DocumentExpiryChecker

            checker = DocumentExpiryChecker()

            with patch.object(checker, "_notificar_vencimentos") as mock_notificar:
                await checker.check()
                mock_notificar.assert_called_once_with(mock_db)

    @pytest.mark.asyncio
    async def test_check_handles_exception_gracefully(self):
        """check() should catch and log exceptions without raising."""
        with (
            patch("database.SessionLocal") as MockSession,
            patch(
                "repositories.documento_repository.documento_repository"
            ) as mock_repo,
        ):
            mock_db = MagicMock()
            MockSession.return_value = mock_db
            mock_repo.atualizar_status_validade.side_effect = RuntimeError("DB error")

            from services.notification.document_checker import DocumentExpiryChecker

            checker = DocumentExpiryChecker()

            # Should not raise
            await checker.check()

            # db.close() should still be called in finally block
            mock_db.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_logs_when_docs_updated(self):
        """check() should log when documents were updated."""
        with (
            patch("database.SessionLocal") as MockSession,
            patch(
                "repositories.documento_repository.documento_repository"
            ) as mock_repo,
            patch("services.notification.document_checker.logger") as mock_logger,
        ):
            mock_db = MagicMock()
            MockSession.return_value = mock_db
            mock_repo.atualizar_status_validade.return_value = 5

            from services.notification.document_checker import DocumentExpiryChecker

            checker = DocumentExpiryChecker()

            with patch.object(checker, "_notificar_vencimentos"):
                await checker.check()

            mock_logger.info.assert_called_once()
            assert "5" in str(mock_logger.info.call_args)


# ===========================================================================
# DocumentExpiryChecker._notificar_vencimentos()
# ===========================================================================


class TestDocumentExpiryCheckerNotificar:

    def test_notificar_creates_notification_for_vencendo(self):
        """Should create notification for docs that haven't been notified yet."""
        mock_db = MagicMock()

        # Mock doc vencendo
        doc = MagicMock(spec=DocumentoLicitacao)
        doc.id = 1
        doc.user_id = 10
        doc.nome = "Certidao Federal"
        doc.data_validade = datetime.now(timezone.utc) + timedelta(days=15)
        doc.status = DocumentoStatus.VENCENDO

        # query for docs_vencendo
        mock_docs_query = MagicMock()
        mock_db.query.return_value = mock_docs_query
        mock_docs_query.filter.return_value = mock_docs_query
        mock_docs_query.all.return_value = [doc]

        # query for ja_notificado check -> None (not yet notified)
        mock_notif_query = MagicMock()
        # The second call to db.query (for Notificacao) returns the notif query
        mock_db.query.side_effect = [mock_docs_query, mock_notif_query]
        mock_notif_query.filter.return_value = mock_notif_query
        mock_notif_query.first.return_value = None

        with patch(
            "services.notification.notification_service.notification_service"
        ) as mock_notif_service:
            from services.notification.document_checker import DocumentExpiryChecker

            checker = DocumentExpiryChecker()
            checker._notificar_vencimentos(mock_db)

            mock_notif_service.notify.assert_called_once()
            call_kwargs = mock_notif_service.notify.call_args
            assert (
                call_kwargs.kwargs.get("user_id") == 10
                or call_kwargs[1].get("user_id") == 10
            )

    def test_notificar_skips_already_notified(self):
        """Should skip docs that already have a notification."""
        mock_db = MagicMock()

        doc = MagicMock(spec=DocumentoLicitacao)
        doc.id = 1
        doc.user_id = 10
        doc.nome = "Certidao FGTS"
        doc.data_validade = datetime.now(timezone.utc) + timedelta(days=10)
        doc.status = DocumentoStatus.VENCENDO

        mock_docs_query = MagicMock()
        mock_notif_query = MagicMock()
        mock_db.query.side_effect = [mock_docs_query, mock_notif_query]
        mock_docs_query.filter.return_value = mock_docs_query
        mock_docs_query.all.return_value = [doc]

        # ja_notificado returns a notification (already notified)
        mock_notif_query.filter.return_value = mock_notif_query
        mock_notif_query.first.return_value = MagicMock()  # existing notification

        with patch(
            "services.notification.notification_service.notification_service"
        ) as mock_notif_service:
            from services.notification.document_checker import DocumentExpiryChecker

            checker = DocumentExpiryChecker()
            checker._notificar_vencimentos(mock_db)

            mock_notif_service.notify.assert_not_called()

    def test_notificar_with_no_vencendo_docs(self):
        """Should do nothing when no documents are vencendo."""
        mock_db = MagicMock()

        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = []

        with patch(
            "services.notification.notification_service.notification_service"
        ) as mock_notif_service:
            from services.notification.document_checker import DocumentExpiryChecker

            checker = DocumentExpiryChecker()
            checker._notificar_vencimentos(mock_db)

            mock_notif_service.notify.assert_not_called()


# ===========================================================================
# Integration with ReminderScheduler
# ===========================================================================


class TestDocumentCheckerSchedulerIntegration:

    @pytest.mark.asyncio
    async def test_scheduler_calls_document_checker(self):
        """ReminderScheduler should call document_checker.check() when interval elapsed."""
        import time

        with (
            patch("database.SessionLocal"),
            patch("repositories.lembrete_repository.lembrete_repository"),
            patch(
                "services.notification.notification_service.notification_service"
            ),
        ):
            from services.notification.reminder_scheduler import ReminderScheduler

            scheduler = ReminderScheduler()
            # Force interval to have elapsed
            scheduler._last_doc_check = 0

            with patch(
                "services.notification.document_checker.document_checker"
            ) as mock_checker:
                mock_checker.check = AsyncMock()
                now = time.time()
                if now - scheduler._last_doc_check >= scheduler._doc_check_interval:
                    await mock_checker.check()
                    scheduler._last_doc_check = now

                mock_checker.check.assert_called_once()
