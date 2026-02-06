"""
Testes para o servico de storage.

Testa LocalStorageBackend, SupabaseStorageBackend e funcoes factory
definidas em services/storage_service.py.
"""
import io
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, PropertyMock

from services.storage_service import (
    LocalStorageBackend,
    SupabaseStorageBackend,
    StorageBackend,
    get_storage,
    reset_storage,
    _storage_instance,
)
import services.storage_service as storage_module


# =============================================================================
# LocalStorageBackend
# =============================================================================


class TestLocalStorageBackend:
    """Testes para o backend de storage local (filesystem)."""

    @pytest.fixture
    def local_storage(self, tmp_path):
        """Cria instancia de LocalStorageBackend com diretorio temporario."""
        return LocalStorageBackend(base_dir=str(tmp_path))

    def test_local_upload_creates_file(self, local_storage, tmp_path):
        """Upload cria arquivo no disco com conteudo correto."""
        content = b"conteudo do arquivo de teste"
        file_obj = io.BytesIO(content)

        result = local_storage.upload(file_obj, "documento.pdf")

        expected_path = tmp_path / "documento.pdf"
        assert expected_path.exists()
        assert expected_path.read_bytes() == content
        assert result == str(expected_path)

    def test_local_upload_creates_directories(self, local_storage, tmp_path):
        """Upload cria subdiretorios intermediarios quando necessario."""
        content = b"nested file content"
        file_obj = io.BytesIO(content)

        result = local_storage.upload(file_obj, "users/1/atestados/doc.pdf")

        expected_path = tmp_path / "users" / "1" / "atestados" / "doc.pdf"
        assert expected_path.exists()
        assert expected_path.read_bytes() == content

    def test_local_download_existing_file(self, local_storage, tmp_path):
        """Download retorna conteudo de arquivo existente."""
        content = b"conteudo para download"
        file_path = tmp_path / "download_test.pdf"
        file_path.write_bytes(content)

        result = local_storage.download("download_test.pdf")

        assert result == content

    def test_local_download_nonexistent_file(self, local_storage):
        """Download retorna None para arquivo inexistente."""
        result = local_storage.download("nao_existe.pdf")

        assert result is None

    def test_local_delete_existing_file(self, local_storage, tmp_path):
        """Delete remove arquivo existente e retorna True."""
        file_path = tmp_path / "para_deletar.pdf"
        file_path.write_bytes(b"dados")

        result = local_storage.delete("para_deletar.pdf")

        assert result is True
        assert not file_path.exists()

    def test_local_delete_nonexistent_file(self, local_storage):
        """Delete de arquivo inexistente retorna True (nao e erro)."""
        result = local_storage.delete("nao_existe.pdf")

        assert result is True

    def test_local_delete_os_error(self, local_storage, tmp_path):
        """Delete retorna False quando ocorre OSError."""
        file_path = tmp_path / "erro.pdf"
        file_path.write_bytes(b"dados")

        with patch.object(Path, "unlink", side_effect=OSError("permissao negada")):
            result = local_storage.delete("erro.pdf")

        assert result is False

    def test_local_exists_true(self, local_storage, tmp_path):
        """Exists retorna True para arquivo existente."""
        file_path = tmp_path / "existe.pdf"
        file_path.write_bytes(b"dados")

        assert local_storage.exists("existe.pdf") is True

    def test_local_exists_false(self, local_storage):
        """Exists retorna False para arquivo inexistente."""
        assert local_storage.exists("nao_existe.pdf") is False

    def test_local_get_url(self, local_storage, tmp_path):
        """get_url retorna caminho completo no filesystem."""
        result = local_storage.get_url("users/1/doc.pdf")

        expected = str(tmp_path / "users" / "1" / "doc.pdf")
        assert result == expected


# =============================================================================
# SupabaseStorageBackend (mock HTTP)
# =============================================================================


class TestSupabaseStorageBackend:
    """Testes para o backend de storage Supabase com HTTP mockado."""

    MOCK_URL = "https://xyzproject.supabase.co"
    MOCK_KEY = "fake-service-key-12345"

    @pytest.fixture
    def supabase_storage(self):
        """Cria instancia de SupabaseStorageBackend com bucket mockado."""
        with patch("urllib.request.urlopen") as mock_urlopen:
            # Mock _ensure_bucket (chamado no __init__)
            mock_urlopen.return_value.__enter__ = MagicMock(return_value=MagicMock())
            mock_urlopen.return_value.__exit__ = MagicMock(return_value=False)
            backend = SupabaseStorageBackend(
                supabase_url=self.MOCK_URL,
                service_key=self.MOCK_KEY,
            )
        return backend

    def test_supabase_upload_success(self, supabase_storage):
        """Upload envia POST para Supabase Storage e retorna URL."""
        content = b"pdf content"
        file_obj = io.BytesIO(content)

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_response = MagicMock()
            mock_urlopen.return_value = mock_response

            result = supabase_storage.upload(file_obj, "users/1/doc.pdf", "application/pdf")

        expected_url = f"{self.MOCK_URL}/storage/v1/object/authenticated/uploads/users/1/doc.pdf"
        assert result == expected_url

    def test_supabase_upload_conflict_upserts(self, supabase_storage):
        """Upload com conflito 409 faz upsert via PUT."""
        import urllib.error

        content = b"pdf content"
        file_obj = io.BytesIO(content)

        # Primeira chamada (POST) retorna 409, segunda (PUT) sucede
        http_error_409 = urllib.error.HTTPError(
            url="", code=409, msg="Conflict", hdrs=None, fp=io.BytesIO(b"")
        )

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = [http_error_409, MagicMock()]

            result = supabase_storage.upload(file_obj, "users/1/doc.pdf")

        expected_url = f"{self.MOCK_URL}/storage/v1/object/authenticated/uploads/users/1/doc.pdf"
        assert result == expected_url
        # Deve ter feito 2 chamadas: POST (falhou 409) + PUT (sucesso)
        assert mock_urlopen.call_count == 2

    def test_supabase_download_success(self, supabase_storage):
        """Download retorna bytes do arquivo."""
        expected_content = b"conteudo baixado"

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_response = MagicMock()
            mock_response.read.return_value = expected_content
            mock_response.__enter__ = MagicMock(return_value=mock_response)
            mock_response.__exit__ = MagicMock(return_value=False)
            mock_urlopen.return_value = mock_response

            result = supabase_storage.download("users/1/doc.pdf")

        assert result == expected_content

    def test_supabase_download_not_found(self, supabase_storage):
        """Download retorna None quando arquivo nao existe (404)."""
        import urllib.error

        http_error_404 = urllib.error.HTTPError(
            url="", code=404, msg="Not Found", hdrs=None, fp=io.BytesIO(b"")
        )

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = http_error_404

            result = supabase_storage.download("nao_existe.pdf")

        assert result is None

    def test_supabase_delete_success(self, supabase_storage):
        """Delete envia DELETE para Supabase e retorna True."""
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value = MagicMock()

            result = supabase_storage.delete("users/1/doc.pdf")

        assert result is True

    def test_supabase_delete_error(self, supabase_storage):
        """Delete retorna False quando ocorre erro HTTP."""
        import urllib.error

        http_error_500 = urllib.error.HTTPError(
            url="", code=500, msg="Server Error", hdrs=None, fp=io.BytesIO(b"")
        )

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = http_error_500

            result = supabase_storage.delete("users/1/doc.pdf")

        assert result is False

    def test_supabase_exists_true(self, supabase_storage):
        """Exists retorna True quando HEAD retorna 200."""
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value = MagicMock()

            result = supabase_storage.exists("users/1/doc.pdf")

        assert result is True

    def test_supabase_exists_false(self, supabase_storage):
        """Exists retorna False quando HEAD retorna erro HTTP."""
        import urllib.error

        http_error_404 = urllib.error.HTTPError(
            url="", code=404, msg="Not Found", hdrs=None, fp=io.BytesIO(b"")
        )

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = http_error_404

            result = supabase_storage.exists("nao_existe.pdf")

        assert result is False

    def test_supabase_get_url_format(self, supabase_storage):
        """get_url retorna URL autenticada no formato correto."""
        result = supabase_storage.get_url("users/1/doc.pdf")

        expected = f"{self.MOCK_URL}/storage/v1/object/authenticated/uploads/users/1/doc.pdf"
        assert result == expected


# =============================================================================
# Factory functions (get_storage, reset_storage)
# =============================================================================


class TestStorageFactory:
    """Testes para funcoes factory e singleton do storage."""

    def setup_method(self):
        """Reseta singleton antes de cada teste."""
        reset_storage()

    def teardown_method(self):
        """Reseta singleton apos cada teste."""
        reset_storage()

    def test_get_storage_returns_local_by_default(self, tmp_path):
        """Sem variaveis Supabase, retorna LocalStorageBackend."""
        with patch.object(storage_module, "SUPABASE_URL", None), \
             patch.object(storage_module, "SUPABASE_SERVICE_KEY", None), \
             patch.object(storage_module, "UPLOAD_DIR", str(tmp_path)):

            storage = get_storage()

        assert isinstance(storage, LocalStorageBackend)

    def test_get_storage_returns_singleton(self, tmp_path):
        """get_storage retorna a mesma instancia nas chamadas subsequentes."""
        with patch.object(storage_module, "SUPABASE_URL", None), \
             patch.object(storage_module, "SUPABASE_SERVICE_KEY", None), \
             patch.object(storage_module, "UPLOAD_DIR", str(tmp_path)):

            storage1 = get_storage()
            storage2 = get_storage()

        assert storage1 is storage2

    def test_reset_storage_clears_singleton(self, tmp_path):
        """reset_storage limpa singleton para que get_storage crie nova instancia."""
        with patch.object(storage_module, "SUPABASE_URL", None), \
             patch.object(storage_module, "SUPABASE_SERVICE_KEY", None), \
             patch.object(storage_module, "UPLOAD_DIR", str(tmp_path)):

            storage1 = get_storage()
            reset_storage()
            storage2 = get_storage()

        # Novas instancias devem ser objetos diferentes
        assert storage1 is not storage2
        assert isinstance(storage2, LocalStorageBackend)
