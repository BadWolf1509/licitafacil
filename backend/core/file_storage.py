"""
File storage abstraction for LicitaFacil.

Provides an abstract interface for file operations that can be implemented
for different storage backends (local filesystem, S3, Azure Blob, etc.).
"""
import os
import shutil
import uuid
from abc import ABC, abstractmethod
from typing import BinaryIO, Optional

from config import UPLOAD_DIR


class FileStorage(ABC):
    """Abstract base class for file storage operations."""

    @abstractmethod
    def save(self, file: BinaryIO, user_id: int, category: str, extension: str) -> str:
        """
        Save a file to storage.

        Args:
            file: File-like object to save
            user_id: User ID for organizing files
            category: Category subdirectory (e.g., 'atestados', 'editais')
            extension: File extension including dot (e.g., '.pdf')

        Returns:
            Full path to the saved file
        """
        pass

    @abstractmethod
    def delete(self, path: str) -> bool:
        """
        Delete a file from storage.

        Args:
            path: Full path to the file

        Returns:
            True if deleted, False if file didn't exist
        """
        pass

    @abstractmethod
    def exists(self, path: str) -> bool:
        """
        Check if a file exists.

        Args:
            path: Full path to the file

        Returns:
            True if file exists
        """
        pass

    @abstractmethod
    def read(self, path: str) -> Optional[bytes]:
        """
        Read a file from storage.

        Args:
            path: Full path to the file

        Returns:
            File contents as bytes, or None if file doesn't exist
        """
        pass


class LocalFileStorage(FileStorage):
    """Local filesystem implementation of FileStorage."""

    def __init__(self, base_dir: str = UPLOAD_DIR):
        """
        Initialize local file storage.

        Args:
            base_dir: Base directory for file storage
        """
        self.base_dir = base_dir

    def _get_user_dir(self, user_id: int, category: str) -> str:
        """Get the directory path for a user's files in a category."""
        return os.path.join(self.base_dir, str(user_id), category)

    def _ensure_dir(self, path: str) -> None:
        """Ensure a directory exists."""
        os.makedirs(path, exist_ok=True)

    def save(self, file: BinaryIO, user_id: int, category: str, extension: str) -> str:
        """Save a file to the local filesystem."""
        user_dir = self._get_user_dir(user_id, category)
        self._ensure_dir(user_dir)

        filename = f"{uuid.uuid4()}{extension}"
        filepath = os.path.join(user_dir, filename)

        with open(filepath, "wb") as buffer:
            shutil.copyfileobj(file, buffer)

        return filepath

    def delete(self, path: str) -> bool:
        """Delete a file from the local filesystem."""
        if os.path.exists(path):
            os.remove(path)
            return True
        return False

    def exists(self, path: str) -> bool:
        """Check if a file exists in the local filesystem."""
        return os.path.exists(path)

    def read(self, path: str) -> Optional[bytes]:
        """Read a file from the local filesystem."""
        if not os.path.exists(path):
            return None
        with open(path, "rb") as f:
            return f.read()


# Default instance for dependency injection
_default_storage: Optional[FileStorage] = None


def get_file_storage() -> FileStorage:
    """
    Get the file storage instance.

    This function can be used as a FastAPI dependency.
    """
    global _default_storage
    if _default_storage is None:
        _default_storage = LocalFileStorage()
    return _default_storage


def set_file_storage(storage: FileStorage) -> None:
    """
    Set the file storage instance.

    Useful for testing or switching to different storage backends.
    """
    global _default_storage
    _default_storage = storage
