from datetime import datetime, timezone
from typing import List
from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from models import Usuario
from schemas import UsuarioAdminResponse, Mensagem
from auth import get_current_admin_user
from config import Messages
from repositories import usuario_repository
from routers.base import AdminRouter

router = AdminRouter(prefix="/admin", tags=["Administração"])


@router.get("/usuarios/pendentes", response_model=List[UsuarioAdminResponse])
def listar_usuarios_pendentes(
    current_user: Usuario = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Lista todos os usuários pendentes de aprovação."""
    return usuario_repository.get_pending_approval(db)


@router.get("/usuarios", response_model=List[UsuarioAdminResponse])
def listar_todos_usuarios(
    current_user: Usuario = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Lista todos os usuários do sistema."""
    return usuario_repository.get_all_ordered(db)


@router.post("/usuarios/{user_id}/aprovar", response_model=Mensagem)
def aprovar_usuario(
    user_id: int,
    current_user: Usuario = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Aprova um usuário pendente."""
    usuario = usuario_repository.get_by_id(db, user_id)
    if not usuario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=Messages.USER_NOT_FOUND
        )

    if usuario.is_approved:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Usuário já está aprovado"
        )

    usuario.is_approved = True
    usuario.approved_at = datetime.now(timezone.utc)
    usuario.approved_by = current_user.id
    db.commit()

    return Mensagem(
        mensagem=f"Usuário {usuario.nome} aprovado com sucesso!",
        sucesso=True
    )


@router.post("/usuarios/{user_id}/rejeitar", response_model=Mensagem)
def rejeitar_usuario(
    user_id: int,
    current_user: Usuario = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Rejeita (desativa) um usuário."""
    usuario = usuario_repository.get_by_id(db, user_id)
    if not usuario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=Messages.USER_NOT_FOUND
        )

    if usuario.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=Messages.CANNOT_DEACTIVATE_SELF
        )

    usuario.is_active = False
    db.commit()

    return Mensagem(
        mensagem=f"Usuário {usuario.nome} desativado com sucesso!",
        sucesso=True
    )


@router.post("/usuarios/{user_id}/reativar", response_model=Mensagem)
def reativar_usuario(
    user_id: int,
    current_user: Usuario = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Reativa um usuário desativado."""
    usuario = usuario_repository.get_by_id(db, user_id)
    if not usuario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=Messages.USER_NOT_FOUND
        )

    if usuario.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Usuário já está ativo"
        )

    usuario.is_active = True
    db.commit()

    return Mensagem(
        mensagem=f"Usuário {usuario.nome} reativado com sucesso!",
        sucesso=True
    )


@router.get("/estatisticas")
def obter_estatisticas(
    current_user: Usuario = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Retorna estatísticas gerais do sistema."""
    return usuario_repository.get_stats(db)
