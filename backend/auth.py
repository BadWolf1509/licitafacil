"""
Módulo de autenticação do LicitaFácil.

Autenticação via Supabase Auth - valida tokens JWT do Supabase.
"""
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from config import SUPABASE_SERVICE_KEY, SUPABASE_URL
from database import get_db
from logging_config import get_logger
from models import Usuario

logger = get_logger('auth')

# Usar HTTPBearer para tokens Supabase
security = HTTPBearer(auto_error=False)

# Supabase Auth deve estar sempre habilitado
SUPABASE_AUTH_ENABLED = bool(SUPABASE_URL and SUPABASE_SERVICE_KEY)

if not SUPABASE_AUTH_ENABLED:
    logger.warning("[AUTH] Supabase Auth não está configurado! Defina SUPABASE_URL e SUPABASE_SERVICE_KEY.")


# === Funções de Busca de Usuário ===

def get_user_by_email(db: Session, email: str) -> Optional[Usuario]:
    """Busca usuário pelo email."""
    return db.query(Usuario).filter(Usuario.email == email).first()


def get_user_by_supabase_id(db: Session, supabase_id: str) -> Optional[Usuario]:
    """Busca usuário pelo supabase_id."""
    return db.query(Usuario).filter(Usuario.supabase_id == supabase_id).first()


# === Autenticação Supabase ===

def _validate_supabase_token(token: str, db: Session) -> Optional[Usuario]:
    """Valida token JWT do Supabase e retorna usuário local."""
    if not SUPABASE_AUTH_ENABLED:
        logger.error("[AUTH] Supabase Auth não está habilitado")
        return None

    try:
        from services.supabase_auth import verify_supabase_token

        supabase_user = verify_supabase_token(token)
        if not supabase_user:
            return None

        supabase_id = supabase_user.get("id")

        if not supabase_id:
            return None

        # Buscar por supabase_id
        user = get_user_by_supabase_id(db, supabase_id)

        if not user:
            logger.warning(f"[AUTH] Usuário Supabase não encontrado localmente: sub={supabase_id}")

        return user

    except Exception as e:
        logger.warning(f"[AUTH] Erro ao validar token Supabase: {e}")
        return None


# === Dependency de Autenticação Principal ===

async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db)
) -> Usuario:
    """
    Dependency para obter o usuário atual via Supabase Auth.

    Raises:
        HTTPException: Se não autenticado ou token inválido
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciais inválidas",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if not credentials:
        raise credentials_exception

    token = credentials.credentials
    user = _validate_supabase_token(token, db)

    if user:
        logger.debug(f"[AUTH] User {user.id} autenticado via Supabase")
    else:
        raise credentials_exception

    return user


async def get_current_active_user(
    current_user: Usuario = Depends(get_current_user)
) -> Usuario:
    """Verifica se o usuário está ativo."""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuário inativo"
        )
    return current_user


async def get_current_approved_user(
    current_user: Usuario = Depends(get_current_active_user)
) -> Usuario:
    """Verifica se o usuário está aprovado."""
    if not current_user.is_approved:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuário aguardando aprovação do administrador"
        )
    return current_user


async def get_current_admin_user(
    current_user: Usuario = Depends(get_current_approved_user)
) -> Usuario:
    """Verifica se o usuário é administrador."""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso restrito a administradores"
        )
    return current_user


# === Utilitários ===

def get_auth_mode() -> str:
    """Retorna o modo de autenticação atual."""
    return "supabase"


def is_supabase_auth_enabled() -> bool:
    """Verifica se Supabase Auth está habilitado."""
    return SUPABASE_AUTH_ENABLED
