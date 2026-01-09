"""
Repositório para operações de Atestado.
"""
from typing import Optional, List
from sqlalchemy.orm import Session

from models import Atestado
from .base import BaseRepository


class AtestadoRepository(BaseRepository[Atestado]):
    """Repositório para operações CRUD de Atestado."""

    def __init__(self):
        super().__init__(Atestado)

    def get_by_file_path(
        self, db: Session, user_id: int, file_path: str
    ) -> Optional[Atestado]:
        """
        Busca atestado por caminho do arquivo.

        Args:
            db: Sessão do banco
            user_id: ID do usuário
            file_path: Caminho do arquivo

        Returns:
            Atestado ou None
        """
        return db.query(Atestado).filter(
            Atestado.user_id == user_id,
            Atestado.arquivo_path == file_path
        ).first()

    def get_all_with_services(
        self, db: Session, user_id: int
    ) -> List[Atestado]:
        """
        Busca todos os atestados do usuário com serviços.

        Args:
            db: Sessão do banco
            user_id: ID do usuário

        Returns:
            Lista de atestados
        """
        return db.query(Atestado).filter(
            Atestado.user_id == user_id
        ).all()

    def get_all_ordered(
        self, db: Session, user_id: int
    ) -> List[Atestado]:
        """
        Busca todos os atestados ordenados por data de criação.

        Args:
            db: Sessão do banco
            user_id: ID do usuário

        Returns:
            Lista de atestados ordenados
        """
        return db.query(Atestado).filter(
            Atestado.user_id == user_id
        ).order_by(Atestado.created_at.desc()).all()


# Instância singleton do repositório
atestado_repository = AtestadoRepository()
