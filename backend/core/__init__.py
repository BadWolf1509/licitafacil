"""
Core abstractions and utilities for LicitaFacil.
"""
from .file_storage import FileStorage, LocalFileStorage, get_file_storage, set_file_storage
from .repository import BaseRepository
from .repositories import AtestadoRepository, AnaliseRepository

__all__ = [
    "FileStorage",
    "LocalFileStorage",
    "get_file_storage",
    "set_file_storage",
    "BaseRepository",
    "AtestadoRepository",
    "AnaliseRepository",
]
