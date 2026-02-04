"""
Repositório para operações de Usuario.
"""
from typing import Optional, List
from sqlalchemy.orm import Session, load_only
from sqlalchemy import func, case, and_

from models import Usuario
from .base import BaseRepository

# Colunas necessárias para listagem de usuários (evita lazy loading)
_USER_LIST_COLUMNS = [
    Usuario.id,
    Usuario.email,
    Usuario.nome,
    Usuario.is_admin,
    Usuario.is_approved,
    Usuario.is_active,
    Usuario.tema_preferido,
    Usuario.created_at,
    Usuario.approved_at,
    Usuario.approved_by,
]


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
        return db.query(Usuario).options(
            load_only(*_USER_LIST_COLUMNS)
        ).filter(
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
        return db.query(Usuario).options(
            load_only(*_USER_LIST_COLUMNS)
        ).filter(
            Usuario.is_active.is_(True)
        ).order_by(Usuario.created_at.desc()).all()

    def get_all_ordered(self, db: Session) -> List[Usuario]:
        """
        Busca todos os usuários ordenados por data de criação.

        Usa load_only para evitar N+1 queries com relacionamentos.

        Args:
            db: Sessão do banco

        Returns:
            Lista de usuários
        """
        return db.query(Usuario).options(
            load_only(*_USER_LIST_COLUMNS)
        ).order_by(Usuario.created_at.desc()).all()

    def get_stats(self, db: Session) -> dict:
        """
        Retorna estatísticas de usuários em uma única query.

        Args:
            db: Sessão do banco

        Returns:
            Dicionário com estatísticas
        """
        result = db.query(
            func.count(Usuario.id).label("total"),
            func.sum(case((Usuario.is_approved.is_(True), 1), else_=0)).label("aprovados"),
            func.sum(case(
                (and_(Usuario.is_approved.is_(False), Usuario.is_active.is_(True)), 1),
                else_=0
            )).label("pendentes"),
            func.sum(case((Usuario.is_active.is_(False), 1), else_=0)).label("inativos"),
        ).first()

        if result is None:
            return {
                "total_usuarios": 0,
                "usuarios_aprovados": 0,
                "usuarios_pendentes": 0,
                "usuarios_inativos": 0
            }

        return {
            "total_usuarios": result.total or 0,
            "usuarios_aprovados": int(result.aprovados or 0),
            "usuarios_pendentes": int(result.pendentes or 0),
            "usuarios_inativos": int(result.inativos or 0)
        }

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
