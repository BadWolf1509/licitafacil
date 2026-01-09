"""
Repositório para operações de Usuario.
"""
from typing import Optional, List
from sqlalchemy.orm import Session

from models import Usuario
from .base import BaseRepository


class UsuarioRepository(BaseRepository[Usuario]):
    """Repositório para operações CRUD de Usuario."""

    def __init__(self):
        super().__init__(Usuario)

    def get_by_email(self, db: Session, email: str) -> Optional[Usuario]:
        """
        Busca usuário por email.

        Args:
            db: Sessão do banco
            email: Email do usuário

        Returns:
            Usuário ou None
        """
        return db.query(Usuario).filter(Usuario.email == email).first()

    def get_pending_approval(self, db: Session) -> List[Usuario]:
        """
        Busca usuários pendentes de aprovação.

        Args:
            db: Sessão do banco

        Returns:
            Lista de usuários pendentes
        """
        return db.query(Usuario).filter(
            Usuario.is_approved.is_(False),
            Usuario.is_active.is_(True)
        ).order_by(Usuario.created_at.desc()).all()

    def get_all_active(self, db: Session) -> List[Usuario]:
        """
        Busca todos os usuários ativos.

        Args:
            db: Sessão do banco

        Returns:
            Lista de usuários ativos
        """
        return db.query(Usuario).filter(
            Usuario.is_active.is_(True)
        ).order_by(Usuario.created_at.desc()).all()

    def approve(self, db: Session, usuario: Usuario) -> Usuario:
        """
        Aprova um usuário.

        Args:
            db: Sessão do banco
            usuario: Usuário a aprovar

        Returns:
            Usuário aprovado
        """
        usuario.is_approved = True
        db.commit()
        db.refresh(usuario)
        return usuario

    def deactivate(self, db: Session, usuario: Usuario) -> Usuario:
        """
        Desativa um usuário.

        Args:
            db: Sessão do banco
            usuario: Usuário a desativar

        Returns:
            Usuário desativado
        """
        usuario.is_active = False
        db.commit()
        db.refresh(usuario)
        return usuario


# Instância singleton do repositório
usuario_repository = UsuarioRepository()
