"""
Endpoints de autenticação do LicitaFácil.

Suporta dois modos:
1. Supabase Auth (recomendado) - autenticação gerenciada pelo Supabase
2. Legacy Auth - JWT próprio com bcrypt (em deprecação)
"""
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
    UsuarioUpdate,
    PasswordChange
)
from auth import (
    get_password_hash,
    verify_password,
    authenticate_user,
    create_access_token,
    get_current_approved_user,
    get_current_active_user,
    get_user_by_email,
    is_supabase_auth_enabled,
    get_auth_mode,
    SUPABASE_AUTH_ENABLED
)
from config import ACCESS_TOKEN_EXPIRE_MINUTES
from repositories import usuario_repository
from utils.password_validator import validate_password, get_password_requirements
from logging_config import get_logger

logger = get_logger('routers.auth')

router = APIRouter(prefix="/auth", tags=["Autenticação"])


# === Endpoints de Configuração ===

@router.get("/config")
def get_auth_config():
    """
    Retorna configuração de autenticação para o frontend.

    Inclui URL e anon key do Supabase se habilitado.
    """
    config = {
        "mode": get_auth_mode(),
        "supabase_enabled": is_supabase_auth_enabled(),
    }

    if is_supabase_auth_enabled():
        from services.supabase_auth import get_supabase_config
        supabase_config = get_supabase_config()
        config["supabase_url"] = supabase_config["url"]
        config["supabase_anon_key"] = supabase_config["anon_key"]

    return config


@router.get("/password-requirements")
def obter_requisitos_senha():
    """Retorna os requisitos de senha para exibição no frontend."""
    return {"requisitos": get_password_requirements()}


# === Endpoints de Registro ===

@router.post("/registrar", response_model=Mensagem)
def registrar_usuario(usuario: UsuarioCreate, db: Session = Depends(get_db)):
    """
    Registra um novo usuário no sistema.
    O usuário ficará pendente de aprovação pelo administrador.

    Se Supabase Auth estiver habilitado, cria o usuário lá também.
    """
    # Validar complexidade da senha
    is_valid, errors = validate_password(usuario.senha)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="; ".join(errors)
        )

    # Verificar se email já existe localmente
    if usuario_repository.get_by_email(db, usuario.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email já cadastrado"
        )

    supabase_id = None

    # Se Supabase Auth está habilitado, criar usuário lá
    if SUPABASE_AUTH_ENABLED:
        try:
            from services.supabase_auth import create_supabase_user

            supabase_user = create_supabase_user(
                email=usuario.email,
                password=usuario.senha,
                user_metadata={"nome": usuario.nome}
            )

            if supabase_user:
                supabase_id = supabase_user["id"]
                logger.info(f"[AUTH] Usuário criado no Supabase: {usuario.email}")
            else:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Erro ao criar usuário no serviço de autenticação"
                )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"[AUTH] Erro ao criar usuário no Supabase: {e}")
            # Se falhar no Supabase, ainda criar localmente com senha
            # Isso permite fallback para autenticação legacy

    # Criar usuário local
    novo_usuario = Usuario(
        email=usuario.email,
        nome=usuario.nome,
        supabase_id=supabase_id,
        # Só salva senha_hash se NÃO tiver supabase_id (modo legacy)
        senha_hash=get_password_hash(usuario.senha) if not supabase_id else None,
        is_approved=False,
        is_admin=False
    )
    db.add(novo_usuario)
    db.commit()

    return Mensagem(
        mensagem="Cadastro realizado com sucesso! Aguarde a aprovação do administrador.",
        sucesso=True
    )


# === Endpoints de Login Legacy ===

def _perform_login(email: str, password: str, db: Session) -> Token:
    """
    Lógica compartilhada de login legacy.
    Autentica usuário e retorna token JWT próprio.
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


@router.post("/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """
    Realiza login legacy e retorna token JWT próprio.
    Funciona com OAuth2PasswordRequestForm para compatibilidade com Swagger UI.

    NOTA: Em modo Supabase, prefira usar o login pelo supabase-js no frontend.
    """
    return _perform_login(form_data.username, form_data.password, db)


@router.post("/login-json", response_model=Token)
def login_json(credentials: UsuarioLogin, db: Session = Depends(get_db)):
    """
    Realiza login legacy via JSON e retorna token JWT próprio.

    NOTA: Em modo Supabase, prefira usar o login pelo supabase-js no frontend.
    """
    return _perform_login(credentials.email, credentials.senha, db)


# === Endpoints de Login Supabase ===

@router.post("/supabase-login", response_model=Token)
def supabase_login(credentials: UsuarioLogin, db: Session = Depends(get_db)):
    """
    Realiza login via Supabase Auth (server-side).

    Retorna tokens do Supabase que podem ser usados para autenticação.

    NOTA: Em produção, o login deve ser feito diretamente pelo frontend
    usando supabase-js para melhor UX (refresh automático, etc).
    """
    if not SUPABASE_AUTH_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Supabase Auth não está habilitado"
        )

    from services.supabase_auth import sign_in_with_password

    result = sign_in_with_password(credentials.email, credentials.senha)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou senha incorretos",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Verificar se usuário existe localmente e está ativo
    user = get_user_by_email(db, credentials.email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário não encontrado no sistema"
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuário inativo"
        )

    # Atualizar supabase_id se necessário
    if not user.supabase_id and result.get("user"):
        user.supabase_id = result["user"]["id"]
        db.commit()

    return Token(
        access_token=result["access_token"],
        token_type="bearer"
    )


# === Endpoints de Usuário ===

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
        "nome": current_user.nome,
        "auth_mode": get_auth_mode(),
        "has_supabase_id": bool(current_user.supabase_id)
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

        # Atualizar metadados no Supabase se habilitado
        if SUPABASE_AUTH_ENABLED and current_user.supabase_id:
            try:
                from services.supabase_auth import update_supabase_user_metadata
                update_supabase_user_metadata(
                    current_user.supabase_id,
                    {"nome": dados.nome}
                )
            except Exception as e:
                logger.warning(f"[AUTH] Erro ao atualizar metadados no Supabase: {e}")

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


@router.post("/change-password", response_model=Mensagem)
def alterar_senha(
    dados: PasswordChange,
    current_user: Usuario = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Altera a senha do usuário logado.

    NOTA: Se o usuário usa Supabase Auth, a senha deve ser alterada
    pelo frontend usando supabase.auth.updateUser().
    """
    # Se usuário está no Supabase e não tem senha_hash local
    if current_user.supabase_id and not current_user.senha_hash:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Altere sua senha usando o painel de configurações do Supabase"
        )

    # Verificar senha atual (modo legacy)
    if not current_user.senha_hash:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Usuário não possui senha local configurada"
        )

    if not verify_password(dados.senha_atual, current_user.senha_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Senha atual incorreta"
        )

    # Validar complexidade da nova senha
    is_valid, errors = validate_password(dados.senha_nova)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="; ".join(errors)
        )

    # Atualizar senha
    current_user.senha_hash = get_password_hash(dados.senha_nova)
    db.commit()

    return Mensagem(mensagem="Senha alterada com sucesso", sucesso=True)


# === Endpoint de Migração ===

@router.post("/migrate-to-supabase", response_model=Mensagem)
def migrate_to_supabase(
    dados: UsuarioLogin,
    current_user: Usuario = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Migra um usuário legacy para Supabase Auth.

    O usuário deve fornecer sua senha atual para criar a conta no Supabase.
    Após a migração, o usuário deve fazer login via Supabase.
    """
    if not SUPABASE_AUTH_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Supabase Auth não está habilitado"
        )

    if current_user.supabase_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Usuário já está migrado para Supabase Auth"
        )

    # Verificar senha atual
    if not current_user.senha_hash or not verify_password(dados.senha, current_user.senha_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Senha incorreta"
        )

    try:
        from services.supabase_auth import create_supabase_user

        supabase_user = create_supabase_user(
            email=current_user.email,
            password=dados.senha,
            user_metadata={"nome": current_user.nome}
        )

        if not supabase_user:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Erro ao criar conta no Supabase"
            )

        # Atualizar usuário local
        current_user.supabase_id = supabase_user["id"]
        current_user.senha_hash = None  # Remover senha local
        db.commit()

        logger.info(f"[AUTH] Usuário migrado para Supabase: {current_user.email}")

        return Mensagem(
            mensagem="Conta migrada com sucesso! Faça login novamente.",
            sucesso=True
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[AUTH] Erro ao migrar usuário: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao migrar conta para Supabase"
        )
