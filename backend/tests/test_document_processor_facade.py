"""
Testes para services.document_processor (fachada).

Verifica que DocumentProcessor delega corretamente para sub-processadores
(pipeline, edital_processor, postprocessor) e que get_status retorna
campos obrigatorios.
"""
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# test_document_processor_singleton_exists
# ---------------------------------------------------------------------------

class TestDocumentProcessorSingletonExists:
    """get_document_processor returns instance."""

    def test_singleton_is_not_none(self):
        from services.document_processor import document_processor
        assert document_processor is not None

    def test_singleton_is_document_processor(self):
        from services.document_processor import DocumentProcessor, document_processor
        assert isinstance(document_processor, DocumentProcessor)


# ---------------------------------------------------------------------------
# test_process_atestado_delegates
# ---------------------------------------------------------------------------

class TestProcessAtestadoDelegates:
    """Mock pipeline, verify delegation."""

    @patch("services.atestado.pipeline.AtestadoPipeline")
    def test_delegates_to_pipeline(self, MockPipeline):
        expected = {"servicos": [], "texto_extraido": "abc"}
        MockPipeline.return_value.run.return_value = expected

        from services.document_processor import DocumentProcessor
        dp = DocumentProcessor()
        result = dp.process_atestado("/tmp/file.pdf", use_vision=False)

        MockPipeline.assert_called_once_with(dp, "/tmp/file.pdf", False, None, None)
        MockPipeline.return_value.run.assert_called_once()
        assert result == expected

    @patch("services.atestado.pipeline.AtestadoPipeline")
    def test_passes_callbacks(self, MockPipeline):
        MockPipeline.return_value.run.return_value = {}
        progress_cb = MagicMock()
        cancel_ck = MagicMock()

        from services.document_processor import DocumentProcessor
        dp = DocumentProcessor()
        dp.process_atestado("/tmp/f.pdf", progress_callback=progress_cb, cancel_check=cancel_ck)

        MockPipeline.assert_called_once_with(dp, "/tmp/f.pdf", True, progress_cb, cancel_ck)


# ---------------------------------------------------------------------------
# test_process_edital_delegates
# ---------------------------------------------------------------------------

class TestProcessEditalDelegates:
    """Mock edital_processor, verify delegation."""

    @patch("services.document_processor.edital_processor")
    def test_delegates_to_edital_processor(self, mock_edital):
        expected = {"exigencias": [{"descricao": "Obra"}]}
        mock_edital.process.return_value = expected

        from services.document_processor import DocumentProcessor
        dp = DocumentProcessor()
        result = dp.process_edital("/tmp/edital.pdf")

        mock_edital.process.assert_called_once_with("/tmp/edital.pdf", None, None)
        assert result == expected

    @patch("services.document_processor.edital_processor")
    def test_passes_callbacks(self, mock_edital):
        mock_edital.process.return_value = {}
        progress_cb = MagicMock()
        cancel_ck = MagicMock()

        from services.document_processor import DocumentProcessor
        dp = DocumentProcessor()
        dp.process_edital("/tmp/edital.pdf", progress_callback=progress_cb, cancel_check=cancel_ck)

        mock_edital.process.assert_called_once_with("/tmp/edital.pdf", progress_cb, cancel_ck)


# ---------------------------------------------------------------------------
# test_analyze_qualification_delegates
# ---------------------------------------------------------------------------

class TestAnalyzeQualificationDelegates:
    """Mock edital_processor, verify delegation."""

    @patch("services.document_processor.edital_processor")
    def test_delegates_to_edital_processor(self, mock_edital):
        exigencias = [{"descricao": "Pav", "quantidade_minima": 1000}]
        atestados = [{"id": 1, "descricao_servico": "Pav"}]
        expected = [{"status": "atende"}]
        mock_edital.analyze_qualification.return_value = expected

        from services.document_processor import DocumentProcessor
        dp = DocumentProcessor()
        result = dp.analyze_qualification(exigencias, atestados)

        mock_edital.analyze_qualification.assert_called_once_with(exigencias, atestados)
        assert result == expected


# ---------------------------------------------------------------------------
# test_get_status_includes_all_fields
# ---------------------------------------------------------------------------

class TestGetStatusIncludesAllFields:
    """Verify status dict has required keys."""

    @patch("services.document_processor.document_ai_service")
    @patch("services.document_processor.ai_provider")
    def test_required_keys_present(self, mock_ai, mock_doc_ai):
        mock_ai.get_status.return_value = {"provider_configurado": "disabled"}
        mock_ai.is_configured = False
        mock_ai.available_providers = []
        mock_doc_ai.is_available = False
        mock_doc_ai.is_configured = False

        from services.document_processor import DocumentProcessor
        dp = DocumentProcessor()
        status = dp.get_status()

        required_keys = [
            "pdf_extractor",
            "ocr_service",
            "ai_provider",
            "document_ai",
            "is_configured",
            "mensagem",
        ]
        for key in required_keys:
            assert key in status, f"Missing required key: {key}"

    @patch("services.document_processor.document_ai_service")
    @patch("services.document_processor.ai_provider")
    def test_document_ai_sub_keys(self, mock_ai, mock_doc_ai):
        mock_ai.get_status.return_value = {}
        mock_ai.is_configured = False
        mock_ai.available_providers = []
        mock_doc_ai.is_available = True
        mock_doc_ai.is_configured = True

        from services.document_processor import DocumentProcessor
        dp = DocumentProcessor()
        status = dp.get_status()

        doc_ai = status["document_ai"]
        assert "available" in doc_ai
        assert "configured" in doc_ai
        assert "enabled" in doc_ai
        assert "paid_services_enabled" in doc_ai


# ---------------------------------------------------------------------------
# test_get_status_when_ai_configured
# ---------------------------------------------------------------------------

class TestGetStatusWhenAIConfigured:
    """Mock AI availability."""

    @patch("services.document_processor.PAID_SERVICES_ENABLED", True)
    @patch("services.document_processor.document_ai_service")
    @patch("services.document_processor.ai_provider")
    def test_message_mentions_configured(self, mock_ai, mock_doc_ai):
        mock_ai.get_status.return_value = {}
        mock_ai.is_configured = True
        mock_ai.available_providers = ["openai"]
        mock_doc_ai.is_available = False
        mock_doc_ai.is_configured = False

        from services.document_processor import DocumentProcessor
        dp = DocumentProcessor()
        status = dp.get_status()

        assert status["is_configured"] is True
        assert "IA configurada" in status["mensagem"]
        assert "openai" in status["mensagem"]


# ---------------------------------------------------------------------------
# test_get_status_when_ai_not_configured
# ---------------------------------------------------------------------------

class TestGetStatusWhenAINotConfigured:
    """When AI is not configured, message should prompt configuration."""

    @patch("services.document_processor.PAID_SERVICES_ENABLED", True)
    @patch("services.document_processor.document_ai_service")
    @patch("services.document_processor.ai_provider")
    def test_message_prompts_configuration(self, mock_ai, mock_doc_ai):
        mock_ai.get_status.return_value = {}
        mock_ai.is_configured = False
        mock_ai.available_providers = []
        mock_doc_ai.is_available = False
        mock_doc_ai.is_configured = False

        from services.document_processor import DocumentProcessor
        dp = DocumentProcessor()
        status = dp.get_status()

        assert status["is_configured"] is False
        assert "Configure" in status["mensagem"]


# ---------------------------------------------------------------------------
# test_get_status_paid_services_disabled
# ---------------------------------------------------------------------------

class TestGetStatusPaidServicesDisabled:
    """When PAID_SERVICES_ENABLED is False."""

    @patch("services.document_processor.PAID_SERVICES_ENABLED", False)
    @patch("services.document_processor.document_ai_service")
    @patch("services.document_processor.ai_provider")
    def test_message_mentions_disabled(self, mock_ai, mock_doc_ai):
        mock_ai.get_status.return_value = {}
        mock_ai.is_configured = False
        mock_ai.available_providers = []
        mock_doc_ai.is_available = False
        mock_doc_ai.is_configured = False

        from services.document_processor import DocumentProcessor
        dp = DocumentProcessor()
        status = dp.get_status()

        assert "desativados" in status["mensagem"].lower() or "desativados" in status["mensagem"]


# ---------------------------------------------------------------------------
# test_postprocess_servicos_delegates
# ---------------------------------------------------------------------------

class TestPostprocessServicosDelegates:
    """Verify delegation to postprocessor."""

    @patch("services.document_processor.postprocessor")
    def test_delegates_to_postprocessor(self, mock_pp):
        mock_pp.postprocess_servicos.return_value = [{"item": "1.1"}]

        from services.document_processor import DocumentProcessor
        dp = DocumentProcessor()
        result = dp._postprocess_servicos(
            servicos=[{"item": "1.1", "descricao": "X"}],
            use_ai=False,
            table_used=True,
            servicos_table=[],
            texto="texto",
        )

        mock_pp.postprocess_servicos.assert_called_once_with(
            [{"item": "1.1", "descricao": "X"}],
            False, True, [], "texto",
            False, False,
        )
        assert result == [{"item": "1.1"}]


# ---------------------------------------------------------------------------
# test_filter_items_without_code_delegates
# ---------------------------------------------------------------------------

class TestFilterItemsWithoutCodeDelegates:
    """Verify delegation to postprocessor."""

    @patch("services.document_processor.postprocessor")
    def test_delegates(self, mock_pp):
        input_servicos = [{"item": "1.1"}, {"item": ""}]
        mock_pp.filter_items_without_code.return_value = [{"item": "1.1"}]

        from services.document_processor import DocumentProcessor
        dp = DocumentProcessor()
        result = dp._filter_items_without_code(input_servicos, min_items_with_code=3)

        mock_pp.filter_items_without_code.assert_called_once_with(input_servicos, 3)
        assert result == [{"item": "1.1"}]


# ---------------------------------------------------------------------------
# test_build_restart_prefix_maps_delegates
# ---------------------------------------------------------------------------

class TestBuildRestartPrefixMapsDelegates:
    """Verify delegation to postprocessor."""

    @patch("services.document_processor.postprocessor")
    def test_delegates(self, mock_pp):
        expected = ({(1,): "S2"}, {"1.1": "S2-1.1"})
        mock_pp.build_restart_prefix_maps.return_value = expected

        from services.document_processor import DocumentProcessor
        dp = DocumentProcessor()
        result = dp._build_restart_prefix_maps([{"item": "1.1"}])

        mock_pp.build_restart_prefix_maps.assert_called_once_with([{"item": "1.1"}])
        assert result == expected


# ---------------------------------------------------------------------------
# test_should_replace_desc_delegates
# ---------------------------------------------------------------------------

class TestShouldReplaceDescDelegates:
    """Verify delegation to postprocessor."""

    @patch("services.document_processor.postprocessor")
    def test_delegates_true(self, mock_pp):
        mock_pp.should_replace_desc.return_value = True

        from services.document_processor import DocumentProcessor
        dp = DocumentProcessor()
        result = dp._should_replace_desc("current", "candidate")

        mock_pp.should_replace_desc.assert_called_once_with("current", "candidate")
        assert result is True

    @patch("services.document_processor.postprocessor")
    def test_delegates_false(self, mock_pp):
        mock_pp.should_replace_desc.return_value = False

        from services.document_processor import DocumentProcessor
        dp = DocumentProcessor()
        result = dp._should_replace_desc("current", "candidate")

        assert result is False
