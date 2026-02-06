"""
Testes para utils.file_helpers - utilitarios de manipulacao de arquivos temporarios.

Cobre cleanup_temp_file e temp_file_from_storage context manager.
"""

import os
from unittest.mock import patch, MagicMock

import pytest

from utils.file_helpers import cleanup_temp_file, temp_file_from_storage


# ============================================================
# cleanup_temp_file
# ============================================================


class TestCleanupTempFile:
    """Testes para a funcao cleanup_temp_file."""

    def test_cleanup_temp_file_success(self, tmp_path):
        """Arquivo existente e removido com sucesso, retorna True."""
        temp_file = tmp_path / "test_file.pdf"
        temp_file.write_text("conteudo temporario")
        assert temp_file.exists()

        result = cleanup_temp_file(str(temp_file))
        assert result is True
        assert not temp_file.exists()

    def test_cleanup_temp_file_not_exists(self, tmp_path):
        """Arquivo que nao existe retorna True (nada a fazer)."""
        fake_path = str(tmp_path / "nao_existe.pdf")
        assert not os.path.exists(fake_path)

        result = cleanup_temp_file(fake_path)
        assert result is True

    def test_cleanup_temp_file_empty_path(self):
        """String vazia retorna True sem erro."""
        result = cleanup_temp_file("")
        assert result is True

    def test_cleanup_temp_file_none_path(self):
        """None retorna True sem erro."""
        result = cleanup_temp_file(None)
        assert result is True

    def test_cleanup_temp_file_permission_error(self, tmp_path):
        """PermissionError na remocao retorna False."""
        temp_file = tmp_path / "locked.pdf"
        temp_file.write_text("bloqueado")

        with patch("utils.file_helpers.os.unlink", side_effect=PermissionError("denied")):
            result = cleanup_temp_file(str(temp_file))

        assert result is False

    def test_cleanup_temp_file_os_error(self, tmp_path):
        """OSError generico na remocao retorna False."""
        temp_file = tmp_path / "erro.pdf"
        temp_file.write_text("vai falhar")

        with patch("utils.file_helpers.os.unlink", side_effect=OSError("disk error")):
            result = cleanup_temp_file(str(temp_file))

        assert result is False

    def test_cleanup_temp_file_race_condition(self, tmp_path):
        """Arquivo desaparece entre exists() e unlink() - retorna True."""
        temp_file = tmp_path / "race.pdf"
        temp_file.write_text("efemero")

        with patch(
            "utils.file_helpers.os.unlink",
            side_effect=FileNotFoundError("already gone"),
        ):
            result = cleanup_temp_file(str(temp_file))

        assert result is True


# ============================================================
# temp_file_from_storage (context manager)
# ============================================================


class TestTempFileFromStorage:
    """Testes para o context manager temp_file_from_storage."""

    def test_temp_file_from_storage_success(self):
        """Arquivo baixado, yield path, cleanup apos saida do bloco."""
        def fake_save(storage_path, local_path):
            # Simula download escrevendo conteudo no path local
            with open(local_path, "w") as f:
                f.write("conteudo baixado")
            return True

        with temp_file_from_storage("bucket/file.pdf", fake_save, suffix=".pdf") as path:
            # Dentro do bloco, arquivo existe com conteudo
            assert os.path.exists(path)
            assert path.endswith(".pdf")
            with open(path) as f:
                assert f.read() == "conteudo baixado"
            saved_path = path

        # Apos sair do bloco, arquivo foi removido
        assert not os.path.exists(saved_path)

    def test_temp_file_from_storage_cleanup_on_error(self):
        """Excecao no corpo do with ainda faz cleanup do arquivo."""
        def fake_save(storage_path, local_path):
            with open(local_path, "w") as f:
                f.write("dados")
            return True

        saved_path = None
        with pytest.raises(ValueError, match="erro no processamento"):
            with temp_file_from_storage("bucket/file.pdf", fake_save) as path:
                saved_path = path
                assert os.path.exists(path)
                raise ValueError("erro no processamento")

        # Arquivo limpo mesmo com excecao
        assert saved_path is not None
        assert not os.path.exists(saved_path)

    def test_temp_file_from_storage_download_fails(self):
        """save_func retorna False, levanta IOError."""
        def failing_save(storage_path, local_path):
            return False

        with pytest.raises(IOError, match="Falha ao baixar arquivo do storage"):
            with temp_file_from_storage("bucket/missing.pdf", failing_save) as path:
                # Nunca deve chegar aqui
                pytest.fail("Nao deveria ter entrado no bloco with")
