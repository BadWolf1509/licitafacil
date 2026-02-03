"""
Endpoints de autenticação do LicitaFácil.

Autenticação gerenciada pelo Supabase Auth.
O frontend usa supabase-js para login/registro.
Este router fornece endpoints auxiliares e sincronização.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
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
)
from auth import (
    get_current_approved_user,
    get_current_active_user,
    get_user_by_email,
    is_supabase_auth_enabled,
    get_auth_mode,
    SUPABASE_AUTH_ENABLED
)
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

    Inclui URL e anon key do Supabase.
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


@router.get("/debug-token")
def debug_token_validation(
    token: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    DEBUG: Endpoint temporário para diagnosticar problemas de autenticação.
    Remover após resolver o problema.
    """
    from config import SUPABASE_URL, SUPABASE_SERVICE_KEY, SUPABASE_ANON_KEY

    result = {
        "supabase_url_set": bool(SUPABASE_URL),
        "supabase_url_prefix": SUPABASE_URL[:30] + "..." if SUPABASE_URL and len(SUPABASE_URL) > 30 else SUPABASE_URL,
        "service_key_set": bool(SUPABASE_SERVICE_KEY),
        "service_key_prefix": SUPABASE_SERVICE_KEY[:20] + "..." if SUPABASE_SERVICE_KEY and len(SUPABASE_SERVICE_KEY) > 20 else "NOT SET",
        "anon_key_set": bool(SUPABASE_ANON_KEY),
        "supabase_auth_enabled": SUPABASE_AUTH_ENABLED,
    }

    if token:
        try:
            from services.supabase_auth import verify_supabase_token, _get_supabase_client

            # Tentar obter cliente
            try:
                _get_supabase_client()  # Verifica se cliente pode ser criado
                result["client_created"] = True
            except Exception as e:
                result["client_created"] = False
                result["client_error"] = str(e)
                return result

            # Tentar validar token
            user_data = verify_supabase_token(token)
            if user_data:
                result["token_valid"] = True
                result["supabase_user_id"] = user_data.get("id")
                result["supabase_email"] = user_data.get("email")

                # Verificar se usuário existe localmente
                from auth import get_user_by_supabase_id
                supabase_id = user_data.get("id")
                local_user = get_user_by_supabase_id(db, supabase_id) if supabase_id else None
                result["local_user_found"] = local_user is not None
                if local_user:
                    result["local_user_email"] = local_user.email
            else:
                result["token_valid"] = False
                result["token_error"] = "verify_supabase_token returned None"
        except Exception as e:
            result["token_valid"] = False
            result["token_error"] = str(e)

    return result


# === Endpoints de Registro ===

@router.post("/registrar", response_model=Mensagem)
def registrar_usuario(usuario: UsuarioCreate, db: Session = Depends(get_db)):
    """
    Registra um novo usuário no sistema via Supabase Auth.
    O usuário ficará pendente de aprovação pelo administrador.
    """
    if not SUPABASE_AUTH_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Serviço de autenticação não está configurado"
        )

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

    # Criar usuário no Supabase
    try:
        from services.supabase_auth import create_supabase_user

        supabase_user = create_supabase_user(
            email=usuario.email,
            password=usuario.senha,
            user_metadata={"nome": usuario.nome}
        )

        if not supabase_user:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Erro ao criar usuário no serviço de autenticação"
            )

        supabase_id = supabase_user["id"]
        logger.info(f"[AUTH] Usuário criado no Supabase: {usuario.email}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[AUTH] Erro ao criar usuário no Supabase: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao criar usuário no serviço de autenticação"
        )

    # Criar usuário local vinculado ao Supabase
    novo_usuario = Usuario(
        email=usuario.email,
        nome=usuario.nome,
        supabase_id=supabase_id,
        is_approved=False,
        is_admin=False
    )
    db.add(novo_usuario)
    db.commit()

    return Mensagem(
        mensagem="Cadastro realizado com sucesso! Aguarde a aprovação do administrador.",
        sucesso=True
    )


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
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Serviço de autenticação não está configurado"
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
        "auth_mode": get_auth_mode()
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

        # Atualizar metadados no Supabase
        if current_user.supabase_id:
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
