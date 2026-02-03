"""
Módulo de autenticação do LicitaFácil.

Suporta dois modos de autenticação:
1. Supabase Auth (recomendado) - valida tokens JWT do Supabase
2. Legacy Auth (em deprecação) - JWT próprio com bcrypt

Durante o período de migração, ambos os métodos são suportados.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from database import get_db
from models import Usuario
from schemas import TokenData
from config import SECRET_KEY, JWT_ALGORITHM as ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES
from config import SUPABASE_URL, SUPABASE_SERVICE_KEY
from config.security import MAX_FAILED_LOGIN_ATTEMPTS, ACCOUNT_LOCKOUT_MINUTES
from logging_config import get_logger

logger = get_logger('auth')

# Usar HTTPBearer para suportar ambos os tipos de token
security = HTTPBearer(auto_error=False)

# Flag para habilitar Supabase Auth
SUPABASE_AUTH_ENABLED = bool(SUPABASE_URL and SUPABASE_SERVICE_KEY)


# === Funções de Bloqueio de Conta (Legacy) ===

def is_account_locked(user: Usuario) -> bool:
    """
    Verifica se a conta do usuario esta bloqueada.

    Args:
        user: Usuario a verificar

    Returns:
        True se a conta esta bloqueada, False caso contrario
    """
    if not user.locked_until:
        return False
    return datetime.now(timezone.utc) < user.locked_until


def get_lockout_remaining_seconds(user: Usuario) -> int:
    """
    Retorna o tempo restante de bloqueio em segundos.

    Args:
        user: Usuario bloqueado

    Returns:
        Segundos restantes ou 0 se nao esta bloqueado
    """
    if not user.locked_until:
        return 0
    remaining = user.locked_until - datetime.now(timezone.utc)
    return max(0, int(remaining.total_seconds()))


def record_failed_login(db: Session, user: Usuario) -> None:
    """
    Registra uma tentativa de login falha.
    Bloqueia a conta se atingir o limite de tentativas.

    Args:
        db: Sessao do banco de dados
        user: Usuario que falhou no login
    """
    user.failed_login_attempts += 1
    if user.failed_login_attempts >= MAX_FAILED_LOGIN_ATTEMPTS:
        user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=ACCOUNT_LOCKOUT_MINUTES)
    db.commit()


def reset_failed_attempts(db: Session, user: Usuario) -> None:
    """
    Reseta o contador de tentativas falhas apos login bem sucedido.

    Args:
        db: Sessao do banco de dados
        user: Usuario que fez login com sucesso
    """
    if user.failed_login_attempts > 0 or user.locked_until is not None:
        user.failed_login_attempts = 0
        user.locked_until = None
        db.commit()


# === Funções de Senha (Legacy) ===

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifica se a senha em texto plano corresponde ao hash."""
    if not hashed_password:
        return False
    return bcrypt.checkpw(
        plain_password.encode("utf-8"),
        hashed_password.encode("utf-8")
    )


def get_password_hash(password: str) -> str:
    """Gera hash da senha."""
    return bcrypt.hashpw(
        password.encode("utf-8"),
        bcrypt.gensalt()
    ).decode("utf-8")


# === Funções de Token JWT (Legacy) ===

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Cria um token JWT (legacy)."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


# === Funções de Busca de Usuário ===

def get_user_by_email(db: Session, email: str) -> Optional[Usuario]:
    """Busca usuário pelo email."""
    return db.query(Usuario).filter(Usuario.email == email).first()


def get_user_by_supabase_id(db: Session, supabase_id: str) -> Optional[Usuario]:
    """Busca usuário pelo supabase_id."""
    return db.query(Usuario).filter(Usuario.supabase_id == supabase_id).first()


# === Autenticação Legacy (JWT + bcrypt) ===

def authenticate_user(db: Session, email: str, password: str) -> Optional[Usuario]:
    """
    Autentica usuario verificando email e senha (modo legacy).
    Implementa bloqueio de conta apos tentativas falhas.

    Returns:
        Usuario se autenticado com sucesso, None caso contrario

    Raises:
        HTTPException: Se a conta estiver bloqueada
    """
    user = get_user_by_email(db, email)
    if not user:
        return None

    # Verificar se a conta esta bloqueada
    if is_account_locked(user):
        remaining = get_lockout_remaining_seconds(user)
        minutes = remaining // 60
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail=f"Conta bloqueada por muitas tentativas falhas. Tente novamente em {minutes + 1} minuto(s)."
        )

    # Verificar senha (apenas se tiver senha_hash - modo legacy)
    if not user.senha_hash:
        # Usuário migrado para Supabase Auth, não pode usar login legacy
        logger.warning(f"[AUTH] Tentativa de login legacy para usuário migrado: {email}")
        return None

    if not verify_password(password, user.senha_hash):
        record_failed_login(db, user)
        return None

    # Login bem sucedido - resetar contador
    reset_failed_attempts(db, user)
    return user


def _validate_legacy_token(token: str, db: Session) -> Optional[Usuario]:
    """Valida token JWT legacy e retorna usuário."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")
        if email is None:
            return None

        user = get_user_by_email(db, email=email)
        return user

    except JWTError:
        return None


# === Autenticação Supabase ===

def _validate_supabase_token(token: str, db: Session) -> Optional[Usuario]:
    """Valida token JWT do Supabase e retorna usuário local."""
    if not SUPABASE_AUTH_ENABLED:
        return None

    try:
        from services.supabase_auth import verify_supabase_token

        supabase_user = verify_supabase_token(token)
        if not supabase_user:
            return None

        supabase_id = supabase_user.get("id")
        email = supabase_user.get("email")

        if not supabase_id:
            return None

        # Primeiro tenta buscar por supabase_id
        user = get_user_by_supabase_id(db, supabase_id)

        # Se não encontrou, tenta por email (usuário ainda não migrado)
        if not user and email:
            user = get_user_by_email(db, email)
            if user and not user.supabase_id:
                # Vincular supabase_id ao usuário existente
                user.supabase_id = supabase_id
                db.commit()
                logger.info(f"[AUTH] Usuário vinculado ao Supabase: {email}")

        return user

    except Exception as e:
        logger.debug(f"[AUTH] Erro ao validar token Supabase: {e}")
        return None


# === Dependency de Autenticação Principal ===

async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db)
) -> Usuario:
    """
    Dependency para obter o usuário atual.

    Suporta dois tipos de autenticação:
    1. Token Supabase (preferencial)
    2. Token JWT legacy (fallback)

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
    user = None

    # 1. Tentar Supabase Auth primeiro (se habilitado)
    if SUPABASE_AUTH_ENABLED:
        user = _validate_supabase_token(token, db)
        if user:
            logger.debug(f"[AUTH] Autenticado via Supabase: {user.email}")

    # 2. Fallback para JWT legacy
    if not user:
        user = _validate_legacy_token(token, db)
        if user:
            logger.debug(f"[AUTH] Autenticado via JWT legacy: {user.email}")

    if not user:
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
    if SUPABASE_AUTH_ENABLED:
        return "supabase"
    return "legacy"


def is_supabase_auth_enabled() -> bool:
    """Verifica se Supabase Auth está habilitado."""
    return SUPABASE_AUTH_ENABLED
