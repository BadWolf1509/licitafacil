from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from database import get_db
from models import Usuario
from schemas import (
    UsuarioCreate,
    UsuarioResponse,
    UsuarioLogin,
    Token,
    Mensagem,
    UsuarioUpdate
)
from auth import (
    get_password_hash,
    authenticate_user,
    create_access_token,
    get_current_approved_user,
    get_current_active_user,
    ACCESS_TOKEN_EXPIRE_MINUTES
)

router = APIRouter(prefix="/auth", tags=["Autenticação"])


def _perform_login(email: str, password: str, db: Session) -> Token:
    """
    Lógica compartilhada de login.
    Autentica usuário e retorna token JWT.
    """
    user = authenticate_user(db, email, password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou senha incorretos",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuário inativo"
        )

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email, "user_id": user.id},
        expires_delta=access_token_expires
    )

    return Token(access_token=access_token, token_type="bearer")


@router.post("/registrar", response_model=Mensagem)
def registrar_usuario(usuario: UsuarioCreate, db: Session = Depends(get_db)):
    """
    Registra um novo usuário no sistema.
    O usuário ficará pendente de aprovação pelo administrador.
    """
    # Verificar se email já existe
    db_user = db.query(Usuario).filter(Usuario.email == usuario.email).first()
    if db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email já cadastrado"
        )

    # Criar novo usuário
    novo_usuario = Usuario(
        email=usuario.email,
        nome=usuario.nome,
        senha_hash=get_password_hash(usuario.senha),
        is_approved=False,
        is_admin=False
    )
    db.add(novo_usuario)
    db.commit()

    return Mensagem(
        mensagem="Cadastro realizado com sucesso! Aguarde a aprovação do administrador.",
        sucesso=True
    )


@router.post("/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """
    Realiza login e retorna token JWT.
    Funciona com OAuth2PasswordRequestForm para compatibilidade com Swagger UI.
    """
    return _perform_login(form_data.username, form_data.password, db)


@router.post("/login-json", response_model=Token)
def login_json(credentials: UsuarioLogin, db: Session = Depends(get_db)):
    """
    Realiza login via JSON e retorna token JWT.
    Alternativa ao endpoint /login para uso via JavaScript.
    """
    return _perform_login(credentials.email, credentials.senha, db)


@router.get("/me", response_model=UsuarioResponse)
def obter_usuario_atual(current_user: Usuario = Depends(get_current_active_user)):
    """Retorna os dados do usuário logado."""
    return current_user


@router.get("/status")
def verificar_status(current_user: Usuario = Depends(get_current_active_user)):
    """
    Verifica o status do usuário logado.
    Útil para o frontend saber se o usuário está aprovado.
    """
    return {
        "aprovado": current_user.is_approved,
        "admin": current_user.is_admin,
        "nome": current_user.nome
    }


@router.put("/me", response_model=UsuarioResponse)
def atualizar_perfil(
    dados: UsuarioUpdate,
    current_user: Usuario = Depends(get_current_approved_user),
    db: Session = Depends(get_db)
):
    """Atualiza os dados do perfil do usuário."""
    if dados.nome is not None:
        current_user.nome = dados.nome
    if dados.tema_preferido is not None:
        if dados.tema_preferido not in ["light", "dark"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Tema deve ser 'light' ou 'dark'"
            )
        current_user.tema_preferido = dados.tema_preferido

    db.commit()
    db.refresh(current_user)
    return current_user
