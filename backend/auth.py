from datetime import datetime, timedelta
from typing import Optional
import os

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session
from dotenv import load_dotenv

from database import get_db
from models import Usuario
from schemas import TokenData

load_dotenv()

# Configurações
SECRET_KEY = os.getenv("SECRET_KEY", "chave-padrao-insegura-mude-em-producao")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))

# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifica se a senha em texto plano corresponde ao hash."""
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


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Cria um token JWT."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def get_user_by_email(db: Session, email: str) -> Optional[Usuario]:
    """Busca usuário pelo email."""
    return db.query(Usuario).filter(Usuario.email == email).first()


def authenticate_user(db: Session, email: str, password: str) -> Optional[Usuario]:
    """Autentica usuário verificando email e senha."""
    user = get_user_by_email(db, email)
    if not user:
        return None
    if not verify_password(password, user.senha_hash):
        return None
    return user


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> Usuario:
    """Dependency para obter o usuário atual a partir do token JWT."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciais inválidas",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")
        user_id = payload.get("user_id")
        if email is None:
            raise credentials_exception
        token_data = TokenData(email=email, user_id=user_id)
    except JWTError:
        raise credentials_exception

    if token_data.email is None:
        raise credentials_exception
    user = get_user_by_email(db, email=token_data.email)
    if user is None:
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
