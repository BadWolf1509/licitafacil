"""
Repositório para operações de Analise.
"""
from typing import Optional, List
from sqlalchemy.orm import Session, joinedload

from models import Analise
from .base import BaseRepository


class AnaliseRepository(BaseRepository[Analise]):
    """Repositório para operações CRUD de Analise."""

    def __init__(self):
        super().__init__(Analise)

    def get_by_file_path(
        self, db: Session, user_id: int, file_path: str
    ) -> Optional[Analise]:
        """
        Busca análise por caminho do arquivo do edital.

        Args:
            db: Sessão do banco
            user_id: ID do usuário
            file_path: Caminho do arquivo

        Returns:
            Análise ou None
        """
        return db.query(Analise).filter(
            Analise.user_id == user_id,
            Analise.arquivo_path == file_path
        ).first()

    def get_all_ordered(
        self, db: Session, user_id: int
    ) -> List[Analise]:
        """
        Busca todas as análises ordenadas por data de criação.
        Usa eager loading para evitar N+1 queries.

        Args:
            db: Sessão do banco
            user_id: ID do usuário

        Returns:
            Lista de análises ordenadas
        """
        return db.query(Analise).options(
            joinedload(Analise.usuario)
        ).filter(
            Analise.user_id == user_id
        ).order_by(Analise.created_at.desc()).all()


# Instância singleton do repositório
analise_repository = AnaliseRepository()
