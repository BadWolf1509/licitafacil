"""
Testes para o modulo de excecoes customizadas.
"""
import pytest


class TestLicitaFacilError:
    """Testes para a excecao base."""

    def test_base_exception(self):
        """Testa criacao de excecao base."""
        from exceptions import LicitaFacilError

        exc = LicitaFacilError("Erro de teste")
        assert exc.message == "Erro de teste"
        assert exc.details is None
        assert str(exc) == "Erro de teste"

    def test_base_exception_with_details(self):
        """Testa excecao base com detalhes."""
        from exceptions import LicitaFacilError

        exc = LicitaFacilError("Erro", details="Detalhes adicionais")
        assert exc.message == "Erro"
        assert exc.details == "Detalhes adicionais"


class TestConfigurationErrors:
    """Testes para excecoes de configuracao."""

    def test_ai_not_configured_generic(self):
        """Testa AINotConfiguredError sem provedor especifico."""
        from exceptions import AINotConfiguredError

        exc = AINotConfiguredError()
        assert "Nenhum provedor de IA" in exc.message

    def test_ai_not_configured_specific(self):
        """Testa AINotConfiguredError com provedor especifico."""
        from exceptions import AINotConfiguredError

        exc = AINotConfiguredError(provider="OpenAI")
        assert "OpenAI" in exc.message

    def test_azure_not_configured(self):
        """Testa AzureNotConfiguredError."""
        from exceptions import AzureNotConfiguredError

        exc = AzureNotConfiguredError()
        assert "Azure" in exc.message
        assert "AZURE_DOCUMENT_INTELLIGENCE" in exc.message

    def test_dependency_not_installed(self):
        """Testa DependencyNotInstalledError."""
        from exceptions import DependencyNotInstalledError

        exc = DependencyNotInstalledError("opencv-python")
        assert "opencv-python" in exc.message
        assert "pip install" in exc.message


class TestProcessingErrors:
    """Testes para excecoes de processamento."""

    def test_processing_cancelled(self):
        """Testa ProcessingCancelledError."""
        from exceptions import ProcessingCancelledError

        exc = ProcessingCancelledError()
        assert "cancelado" in exc.message.lower()

    def test_ocr_error(self):
        """Testa OCRError."""
        from exceptions import OCRError

        exc = OCRError("Falha na extracao")
        assert "OCR" in exc.message
        assert "Falha na extracao" in exc.message

    def test_pdf_error(self):
        """Testa PDFError."""
        from exceptions import PDFError

        exc = PDFError("converter")
        assert "PDF" in exc.message
        assert "converter" in exc.message

    def test_text_extraction_error(self):
        """Testa TextExtractionError."""
        from exceptions import TextExtractionError

        exc = TextExtractionError("imagem")
        assert "extrair texto" in exc.message.lower()
        assert "imagem" in exc.message


class TestValidationErrors:
    """Testes para excecoes de validacao."""

    def test_unsupported_file_default(self):
        """Testa UnsupportedFileError com formatos padrao."""
        from exceptions import UnsupportedFileError

        exc = UnsupportedFileError(".doc")
        assert ".doc" in exc.message
        assert "PDF" in exc.message or "suportado" in exc.message.lower()

    def test_unsupported_file_custom_list(self):
        """Testa UnsupportedFileError com lista customizada."""
        from exceptions import UnsupportedFileError

        exc = UnsupportedFileError(".txt", supported=[".csv", ".xlsx"])
        assert ".txt" in exc.message
        assert ".csv" in exc.message
        assert ".xlsx" in exc.message

    def test_invalid_file(self):
        """Testa InvalidFileError."""
        from exceptions import InvalidFileError

        exc = InvalidFileError()
        assert "inválido" in exc.message.lower() or "corrompido" in exc.message.lower()


class TestExternalAPIErrors:
    """Testes para excecoes de APIs externas."""

    def test_openai_error(self):
        """Testa OpenAIError."""
        from exceptions import OpenAIError

        exc = OpenAIError(details="Rate limit exceeded")
        assert "OpenAI" in exc.message
        assert exc.details == "Rate limit exceeded"

    def test_gemini_error(self):
        """Testa GeminiError."""
        from exceptions import GeminiError

        exc = GeminiError()
        assert "Gemini" in exc.message

    def test_azure_api_error(self):
        """Testa AzureAPIError."""
        from exceptions import AzureAPIError

        exc = AzureAPIError(details="Service unavailable")
        assert "Azure" in exc.message
        assert exc.details == "Service unavailable"


class TestDatabaseErrors:
    """Testes para excecoes de banco de dados."""

    def test_record_not_found_generic(self):
        """Testa RecordNotFoundError sem ID."""
        from exceptions import RecordNotFoundError

        exc = RecordNotFoundError("Atestado")
        assert "Atestado" in exc.message
        assert "não encontrado" in exc.message.lower()

    def test_record_not_found_with_id(self):
        """Testa RecordNotFoundError com ID."""
        from exceptions import RecordNotFoundError

        exc = RecordNotFoundError("Analise", identifier=123)
        assert "Analise" in exc.message
        assert "123" in exc.message

    def test_duplicate_record_generic(self):
        """Testa DuplicateRecordError generico."""
        from exceptions import DuplicateRecordError

        exc = DuplicateRecordError("Usuario")
        assert "Usuario" in exc.message
        assert "já existe" in exc.message.lower()

    def test_duplicate_record_with_field(self):
        """Testa DuplicateRecordError com campo especifico."""
        from exceptions import DuplicateRecordError

        exc = DuplicateRecordError("Usuario", field="email")
        assert "Usuario" in exc.message
        assert "email" in exc.message

    def test_integrity_error(self):
        """Testa IntegrityError."""
        from exceptions import IntegrityError

        exc = IntegrityError()
        assert "integridade" in exc.message.lower()

    def test_connection_error(self):
        """Testa ConnectionError."""
        from exceptions import ConnectionError

        exc = ConnectionError(details="Timeout")
        assert "conectar" in exc.message.lower()
        assert exc.details == "Timeout"


class TestExceptionHierarchy:
    """Testes para verificar hierarquia de excecoes."""

    def test_all_inherit_from_base(self):
        """Verifica que todas as excecoes herdam de LicitaFacilError."""
        from exceptions import (
            ConfigurationError,
            DatabaseError,
            ExternalAPIError,
            LicitaFacilError,
            ProcessingError,
            ValidationError,
        )

        assert issubclass(ConfigurationError, LicitaFacilError)
        assert issubclass(ProcessingError, LicitaFacilError)
        assert issubclass(ValidationError, LicitaFacilError)
        assert issubclass(ExternalAPIError, LicitaFacilError)
        assert issubclass(DatabaseError, LicitaFacilError)

    def test_specific_inherit_from_category(self):
        """Verifica que excecoes especificas herdam da categoria."""
        from exceptions import (
            AINotConfiguredError,
            ConfigurationError,
            DatabaseError,
            ExternalAPIError,
            OCRError,
            OpenAIError,
            ProcessingError,
            RecordNotFoundError,
            UnsupportedFileError,
            ValidationError,
        )

        assert issubclass(AINotConfiguredError, ConfigurationError)
        assert issubclass(OCRError, ProcessingError)
        assert issubclass(UnsupportedFileError, ValidationError)
        assert issubclass(OpenAIError, ExternalAPIError)
        assert issubclass(RecordNotFoundError, DatabaseError)

    def test_can_catch_by_base(self):
        """Verifica que excecoes podem ser capturadas pela base."""
        from exceptions import LicitaFacilError, RecordNotFoundError

        try:
            raise RecordNotFoundError("Teste")
        except LicitaFacilError as e:
            assert "Teste" in e.message
        except Exception:
            pytest.fail("Deveria ter capturado como LicitaFacilError")
