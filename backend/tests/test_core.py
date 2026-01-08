"""
Testes para o módulo core (file_storage, repository).
"""
import os
import tempfile
from io import BytesIO
from unittest.mock import MagicMock

from core.file_storage import LocalFileStorage, get_file_storage, set_file_storage
from core.repository import BaseRepository


class TestLocalFileStorage:
    """Testes para LocalFileStorage."""

    def test_save_creates_file(self):
        """Deve criar arquivo no diretório correto."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = LocalFileStorage(base_dir=tmpdir)
            file_content = b"test content"
            file = BytesIO(file_content)

            path = storage.save(file, user_id=1, category="test", extension=".txt")

            assert os.path.exists(path)
            assert os.path.dirname(path) == os.path.join(tmpdir, "1", "test")
            with open(path, "rb") as f:
                assert f.read() == file_content

    def test_save_uses_uuid_filename(self):
        """Deve usar UUID como nome do arquivo."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = LocalFileStorage(base_dir=tmpdir)
            file = BytesIO(b"test")

            path = storage.save(file, user_id=1, category="test", extension=".pdf")

            filename = os.path.basename(path)
            # UUID format: 8-4-4-4-12 chars = 36 chars + extension
            assert len(filename) == 36 + 4  # UUID + ".pdf"
            assert filename.endswith(".pdf")

    def test_delete_removes_file(self):
        """Deve remover arquivo existente."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = LocalFileStorage(base_dir=tmpdir)
            file = BytesIO(b"test")
            path = storage.save(file, user_id=1, category="test", extension=".txt")

            result = storage.delete(path)

            assert result is True
            assert not os.path.exists(path)

    def test_delete_returns_false_for_nonexistent(self):
        """Deve retornar False para arquivo inexistente."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = LocalFileStorage(base_dir=tmpdir)

            result = storage.delete(os.path.join(tmpdir, "nonexistent.txt"))

            assert result is False

    def test_exists_returns_true_for_existing(self):
        """Deve retornar True para arquivo existente."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = LocalFileStorage(base_dir=tmpdir)
            file = BytesIO(b"test")
            path = storage.save(file, user_id=1, category="test", extension=".txt")

            assert storage.exists(path) is True

    def test_exists_returns_false_for_nonexistent(self):
        """Deve retornar False para arquivo inexistente."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = LocalFileStorage(base_dir=tmpdir)

            assert storage.exists(os.path.join(tmpdir, "nonexistent.txt")) is False

    def test_read_returns_content(self):
        """Deve retornar conteúdo do arquivo."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = LocalFileStorage(base_dir=tmpdir)
            content = b"test content 123"
            file = BytesIO(content)
            path = storage.save(file, user_id=1, category="test", extension=".txt")

            result = storage.read(path)

            assert result == content

    def test_read_returns_none_for_nonexistent(self):
        """Deve retornar None para arquivo inexistente."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = LocalFileStorage(base_dir=tmpdir)

            result = storage.read(os.path.join(tmpdir, "nonexistent.txt"))

            assert result is None


class TestFileStorageDependency:
    """Testes para injeção de dependência de FileStorage."""

    def test_get_file_storage_returns_instance(self):
        """Deve retornar instância de FileStorage."""
        storage = get_file_storage()
        assert storage is not None
        assert isinstance(storage, LocalFileStorage)

    def test_set_file_storage_replaces_instance(self):
        """Deve permitir substituir instância."""
        original = get_file_storage()
        mock_storage = MagicMock()

        set_file_storage(mock_storage)
        assert get_file_storage() is mock_storage

        # Restore original
        set_file_storage(original)


class TestBaseRepository:
    """Testes para BaseRepository."""

    def test_init_stores_db_session(self):
        """Deve armazenar sessão do banco."""
        mock_db = MagicMock()

        class TestRepo(BaseRepository[object]):
            model = MagicMock()

        repo = TestRepo(mock_db)

        assert repo.db is mock_db

    def test_get_queries_by_id(self):
        """Deve buscar por ID."""
        mock_db = MagicMock()
        mock_model = MagicMock()
        mock_model.id = "id_column"

        class TestRepo(BaseRepository[object]):
            model = mock_model

        repo = TestRepo(mock_db)
        repo.get(1)

        mock_db.query.assert_called_once_with(mock_model)

    def test_count_by_user_returns_count(self):
        """Deve retornar contagem de registros do usuário."""
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.count.return_value = 5
        mock_model = MagicMock()

        class TestRepo(BaseRepository[object]):
            model = mock_model

        repo = TestRepo(mock_db)
        result = repo.count_by_user(1)

        assert result == 5

    def test_create_adds_and_commits(self):
        """Deve adicionar e commitar novo registro."""
        mock_db = MagicMock()
        mock_model = MagicMock()
        mock_instance = MagicMock()
        mock_model.return_value = mock_instance

        class TestRepo(BaseRepository[object]):
            model = mock_model

        repo = TestRepo(mock_db)
        repo.create(name="test")

        mock_model.assert_called_once_with(name="test")
        mock_db.add.assert_called_once_with(mock_instance)
        mock_db.commit.assert_called_once()

    def test_delete_removes_and_commits(self):
        """Deve deletar e commitar."""
        mock_db = MagicMock()
        mock_instance = MagicMock()

        class TestRepo(BaseRepository[object]):
            model = MagicMock()

        repo = TestRepo(mock_db)
        repo.delete(mock_instance)

        mock_db.delete.assert_called_once_with(mock_instance)
        mock_db.commit.assert_called_once()
