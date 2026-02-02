from datetime import datetime, timezone
from typing import List
from fastapi import Depends, HTTPException, status, Request
from sqlalchemy.orm import Session

from database import get_db
from models import Usuario
from schemas import UsuarioAdminResponse, Mensagem
from auth import get_current_admin_user
from config import Messages
from repositories import usuario_repository
from routers.base import AdminRouter
from services.audit_service import audit_service, AuditAction

router = AdminRouter(prefix="/admin", tags=["Administração"])


def _get_client_ip(request: Request) -> str:
    """Extrai IP do cliente, considerando proxies."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip
    return request.client.host if request.client else "unknown"


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
    request: Request,
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

    # Registrar auditoria
    audit_service.log_action(
        db=db,
        user_id=current_user.id,
        action=AuditAction.USER_APPROVED,
        resource_type="usuario",
        resource_id=usuario.id,
        details={"email": usuario.email, "nome": usuario.nome},
        ip_address=_get_client_ip(request)
    )

    return Mensagem(
        mensagem=f"Usuário {usuario.nome} aprovado com sucesso!",
        sucesso=True
    )


@router.post("/usuarios/{user_id}/rejeitar", response_model=Mensagem)
def rejeitar_usuario(
    user_id: int,
    request: Request,
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

    # Registrar auditoria
    audit_service.log_action(
        db=db,
        user_id=current_user.id,
        action=AuditAction.USER_DEACTIVATED,
        resource_type="usuario",
        resource_id=usuario.id,
        details={"email": usuario.email, "nome": usuario.nome},
        ip_address=_get_client_ip(request)
    )

    return Mensagem(
        mensagem=f"Usuário {usuario.nome} desativado com sucesso!",
        sucesso=True
    )


@router.post("/usuarios/{user_id}/reativar", response_model=Mensagem)
def reativar_usuario(
    user_id: int,
    request: Request,
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

    # Registrar auditoria
    audit_service.log_action(
        db=db,
        user_id=current_user.id,
        action=AuditAction.USER_REACTIVATED,
        resource_type="usuario",
        resource_id=usuario.id,
        details={"email": usuario.email, "nome": usuario.nome},
        ip_address=_get_client_ip(request)
    )

    return Mensagem(
        mensagem=f"Usuário {usuario.nome} reativado com sucesso!",
        sucesso=True
    )


@router.delete("/usuarios/{user_id}", response_model=Mensagem)
def excluir_usuario(
    user_id: int,
    request: Request,
    current_user: Usuario = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Exclui permanentemente um usuário do sistema."""
    usuario = usuario_repository.get_by_id(db, user_id)
    if not usuario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=Messages.USER_NOT_FOUND
        )

    if usuario.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Não é possível excluir sua própria conta"
        )

    if usuario.is_admin:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Não é possível excluir um administrador"
        )

    nome = usuario.nome
    email = usuario.email
    deleted_user_id = usuario.id

    db.delete(usuario)
    db.commit()

    # Registrar auditoria
    audit_service.log_action(
        db=db,
        user_id=current_user.id,
        action=AuditAction.USER_DELETED,
        resource_type="usuario",
        resource_id=deleted_user_id,
        details={"email": email, "nome": nome},
        ip_address=_get_client_ip(request)
    )

    return Mensagem(
        mensagem=f"Usuário {nome} excluído permanentemente!",
        sucesso=True
    )


@router.get("/estatisticas")
def obter_estatisticas(
    current_user: Usuario = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Retorna estatísticas gerais do sistema."""
    return usuario_repository.get_stats(db)
