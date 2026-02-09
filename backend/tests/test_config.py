"""
Testes para o modulo de configuracao.
"""
import os
from unittest.mock import patch


class TestConfig:
    """Testes para config.py."""

    def test_upload_dir_default(self):
        """Verifica que UPLOAD_DIR tem valor padrao."""
        from config import UPLOAD_DIR
        assert UPLOAD_DIR is not None
        assert isinstance(UPLOAD_DIR, str)

    def test_allowed_extensions(self):
        """Verifica que extensoes permitidas estao definidas."""
        from config import ALLOWED_DOCUMENT_EXTENSIONS, ALLOWED_IMAGE_EXTENSIONS, ALLOWED_PDF_EXTENSIONS
        assert ".pdf" in ALLOWED_PDF_EXTENSIONS
        assert ".png" in ALLOWED_IMAGE_EXTENSIONS
        assert ".jpg" in ALLOWED_IMAGE_EXTENSIONS
        assert len(ALLOWED_DOCUMENT_EXTENSIONS) == len(ALLOWED_PDF_EXTENSIONS) + len(ALLOWED_IMAGE_EXTENSIONS)

    def test_is_allowed_extension_pdf(self):
        """Verifica validacao de extensao PDF."""
        from config import ALLOWED_PDF_EXTENSIONS, is_allowed_extension
        assert is_allowed_extension("documento.pdf", ALLOWED_PDF_EXTENSIONS) is True
        assert is_allowed_extension("documento.PDF", ALLOWED_PDF_EXTENSIONS) is True
        assert is_allowed_extension("documento.doc", ALLOWED_PDF_EXTENSIONS) is False

    def test_is_allowed_extension_images(self):
        """Verifica validacao de extensao de imagens."""
        from config import ALLOWED_IMAGE_EXTENSIONS, is_allowed_extension
        assert is_allowed_extension("foto.png", ALLOWED_IMAGE_EXTENSIONS) is True
        assert is_allowed_extension("foto.jpg", ALLOWED_IMAGE_EXTENSIONS) is True
        assert is_allowed_extension("foto.jpeg", ALLOWED_IMAGE_EXTENSIONS) is True
        assert is_allowed_extension("foto.gif", ALLOWED_IMAGE_EXTENSIONS) is True
        assert is_allowed_extension("foto.webp", ALLOWED_IMAGE_EXTENSIONS) is True

    def test_is_allowed_extension_all_documents(self):
        """Verifica validacao para todos os tipos de documento."""
        from config import is_allowed_extension
        # Usa o padrao (todos os documentos)
        assert is_allowed_extension("documento.pdf") is True
        assert is_allowed_extension("imagem.png") is True
        assert is_allowed_extension("arquivo.exe") is False

    def test_get_file_extension(self):
        """Verifica extracao de extensao."""
        from config import get_file_extension
        assert get_file_extension("documento.pdf") == ".pdf"
        assert get_file_extension("DOCUMENTO.PDF") == ".pdf"
        assert get_file_extension("arquivo.tar.gz") == ".gz"
        assert get_file_extension("sem_extensao") == ""


class TestMessages:
    """Testes para mensagens padronizadas."""

    def test_messages_exist(self):
        """Verifica que mensagens padronizadas existem."""
        from config import Messages
        assert hasattr(Messages, 'NOT_FOUND')
        assert hasattr(Messages, 'JOB_NOT_FOUND')
        assert hasattr(Messages, 'ACCESS_DENIED')
        assert hasattr(Messages, 'FILE_NOT_FOUND')
        assert hasattr(Messages, 'RATE_LIMIT_EXCEEDED')
        assert hasattr(Messages, 'DB_ERROR')

    def test_messages_are_strings(self):
        """Verifica que mensagens sao strings."""
        from config import Messages
        assert isinstance(Messages.NOT_FOUND, str)
        assert isinstance(Messages.JOB_NOT_FOUND, str)
        assert len(Messages.NOT_FOUND) > 0


class TestCORSConfig:
    """Testes para configuracao CORS."""

    def test_cors_origins_default_development(self):
        """Verifica origens CORS em desenvolvimento."""
        with patch.dict(os.environ, {"ENVIRONMENT": "development", "CORS_ORIGINS": ""}):
            # Reimportar para pegar novos valores
            import importlib

            import config
            importlib.reload(config)

            origins = config.get_cors_origins()
            assert "http://localhost:8000" in origins or len(origins) > 0

    def test_cors_origins_custom(self):
        """Verifica origens CORS customizadas."""
        with patch.dict(os.environ, {"CORS_ORIGINS": "https://meusite.com,https://api.meusite.com"}):
            import importlib

            import config
            importlib.reload(config)

            origins = config.get_cors_origins()
            assert "https://meusite.com" in origins
            assert "https://api.meusite.com" in origins


class TestRateLimitConfig:
    """Testes para configuracao de rate limiting."""

    def test_rate_limit_defaults(self):
        """Verifica valores padrao de rate limiting."""
        from config import RATE_LIMIT_ENABLED, RATE_LIMIT_REQUESTS, RATE_LIMIT_WINDOW
        assert isinstance(RATE_LIMIT_ENABLED, bool)
        assert isinstance(RATE_LIMIT_REQUESTS, int)
        assert isinstance(RATE_LIMIT_WINDOW, int)
        assert RATE_LIMIT_REQUESTS > 0
        assert RATE_LIMIT_WINDOW > 0
