"""
Concrete repository implementations for LicitaFacil models.
"""
from sqlalchemy.orm import Session

from .repository import BaseRepository
from models import Atestado, Analise


class AtestadoRepository(BaseRepository[Atestado]):
    """Repository for Atestado operations."""

    model = Atestado

    def get_by_path(self, user_id: int, path: str) -> Atestado | None:
        """
        Get an atestado by file path.

        Args:
            user_id: User ID
            path: File path

        Returns:
            The atestado or None if not found
        """
        return self.db.query(self.model).filter(
            self.model.user_id == user_id,
            self.model.arquivo_path == path
        ).first()


class AnaliseRepository(BaseRepository[Analise]):
    """Repository for Analise operations."""

    model = Analise


# Dependency injection helpers
def get_atestado_repository(db: Session) -> AtestadoRepository:
    """Get an AtestadoRepository instance."""
    return AtestadoRepository(db)


def get_analise_repository(db: Session) -> AnaliseRepository:
    """Get an AnaliseRepository instance."""
    return AnaliseRepository(db)
