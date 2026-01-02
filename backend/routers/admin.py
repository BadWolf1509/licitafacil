from datetime import datetime
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from models import Usuario
from schemas import UsuarioAdminResponse, Mensagem
from auth import get_current_admin_user

router = APIRouter(prefix="/admin", tags=["Administração"])


@router.get("/usuarios/pendentes", response_model=List[UsuarioAdminResponse])
def listar_usuarios_pendentes(
    current_user: Usuario = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Lista todos os usuários pendentes de aprovação."""
    usuarios = db.query(Usuario).filter(
        Usuario.is_approved == False,
        Usuario.is_active == True
    ).order_by(Usuario.created_at.desc()).all()
    return usuarios


@router.get("/usuarios", response_model=List[UsuarioAdminResponse])
def listar_todos_usuarios(
    current_user: Usuario = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Lista todos os usuários do sistema."""
    usuarios = db.query(Usuario).order_by(Usuario.created_at.desc()).all()
    return usuarios


@router.post("/usuarios/{user_id}/aprovar", response_model=Mensagem)
def aprovar_usuario(
    user_id: int,
    current_user: Usuario = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Aprova um usuário pendente."""
    usuario = db.query(Usuario).filter(Usuario.id == user_id).first()
    if not usuario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuário não encontrado"
        )

    if usuario.is_approved:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Usuário já está aprovado"
        )

    usuario.is_approved = True
    usuario.approved_at = datetime.utcnow()
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
    usuario = db.query(Usuario).filter(Usuario.id == user_id).first()
    if not usuario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuário não encontrado"
        )

    if usuario.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Você não pode desativar sua própria conta"
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
    usuario = db.query(Usuario).filter(Usuario.id == user_id).first()
    if not usuario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuário não encontrado"
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
    total_usuarios = db.query(Usuario).count()
    usuarios_aprovados = db.query(Usuario).filter(Usuario.is_approved == True).count()
    usuarios_pendentes = db.query(Usuario).filter(
        Usuario.is_approved == False,
        Usuario.is_active == True
    ).count()
    usuarios_inativos = db.query(Usuario).filter(Usuario.is_active == False).count()

    return {
        "total_usuarios": total_usuarios,
        "usuarios_aprovados": usuarios_aprovados,
        "usuarios_pendentes": usuarios_pendentes,
        "usuarios_inativos": usuarios_inativos
    }
