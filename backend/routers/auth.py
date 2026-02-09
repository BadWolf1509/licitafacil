"""
Endpoints de autenticação do LicitaFácil.

Autenticação gerenciada pelo Supabase Auth.
O frontend usa supabase-js para login/registro.
Este router fornece endpoints auxiliares e sincronização.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from auth import (
    SUPABASE_AUTH_ENABLED,
    get_auth_mode,
    get_current_active_user,
    get_current_approved_user,
    get_user_by_email,
    is_supabase_auth_enabled,
)
from database import get_db
from logging_config import get_logger, log_action
from models import Usuario
from repositories import usuario_repository
from schemas import (
    AuthConfigResponse,
    Mensagem,
    PasswordPolicy,
    PasswordRequirementsResponse,
    Token,
    UserStatusResponse,
    UsuarioCreate,
    UsuarioLogin,
    UsuarioResponse,
    UsuarioUpdate,
)
from services.cache import cached
from utils.password_validator import get_password_policy, get_password_requirements, validate_password

logger = get_logger('routers.auth')

router = APIRouter(prefix="/auth", tags=["Autenticação"])


# === Endpoints de Configuração ===

@cached(ttl=3600, prefix="auth_config")
def _get_auth_config_cached() -> dict:
    """Função cacheada para obter configuração de autenticação."""
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


@router.get(
    "/config",
    response_model=AuthConfigResponse,
    summary="Obter configuração de autenticação",
    responses={
        200: {"description": "Configuração retornada com sucesso"},
    }
)
def get_auth_config() -> AuthConfigResponse:
    """
    Retorna configuração de autenticação para o frontend.

    Inclui modo de autenticação e credenciais do Supabase (se habilitado).
    O resultado é cacheado por 1 hora para reduzir carga no servidor.

    **Retorna:**
    - `mode`: Modo de autenticação ("supabase" ou "local")
    - `supabase_enabled`: Se autenticação Supabase está ativa
    - `supabase_url`: URL do projeto Supabase (se habilitado)
    - `supabase_anon_key`: Chave anônima do Supabase (se habilitado)
    """
    return AuthConfigResponse(**_get_auth_config_cached())


@router.get(
    "/password-requirements",
    response_model=PasswordRequirementsResponse,
    summary="Obter requisitos de senha",
    responses={
        200: {"description": "Lista de requisitos retornada"},
    }
)
def get_password_requirements_info() -> PasswordRequirementsResponse:
    """
    Retorna os requisitos de complexidade de senha para exibição no frontend.

    Útil para mostrar ao usuário quais critérios a senha deve atender
    durante o cadastro ou alteração de senha.

    **Exemplo de resposta:**
    ```json
    {
      "requisitos": [
        "Mínimo de 8 caracteres",
        "Pelo menos uma letra maiúscula",
        "Pelo menos um número"
      ]
    }
    ```
    """
    return PasswordRequirementsResponse(
        requisitos=get_password_requirements(),
        policy=PasswordPolicy(**get_password_policy())
    )


# === Endpoints de Registro ===

@router.post(
    "/registrar",
    response_model=Mensagem,
    summary="Registrar novo usuário",
    responses={
        200: {"description": "Usuário registrado com sucesso"},
        400: {"description": "Email já cadastrado ou senha inválida"},
        503: {"description": "Serviço de autenticação não configurado"},
    }
)
def register_user(usuario: UsuarioCreate, db: Session = Depends(get_db)):
    """
    Registra um novo usuário no sistema via Supabase Auth.

    O usuário ficará pendente de aprovação pelo administrador.
    A senha deve atender aos requisitos de complexidade configurados.

    **Fluxo:**
    1. Valida complexidade da senha
    2. Verifica se email já existe
    3. Cria usuário no Supabase Auth
    4. Cria registro local vinculado
    5. Usuário aguarda aprovação do admin
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
        logger.info(f"[AUTH] Usuário criado no Supabase: sub={supabase_id}")

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

    log_action(
        logger, "user_registered",
        resource_type="usuario",
        resource_id=novo_usuario.id,
    )

    return Mensagem(
        mensagem="Cadastro realizado com sucesso! Aguarde a aprovação do administrador.",
        sucesso=True
    )


# === Endpoints de Login Supabase ===

@router.post(
    "/supabase-login",
    response_model=Token,
    summary="Login via Supabase",
    responses={
        200: {"description": "Login realizado com sucesso"},
        401: {"description": "Credenciais inválidas"},
        403: {"description": "Usuário inativo"},
        503: {"description": "Serviço de autenticação não configurado"},
    }
)
def supabase_login(credentials: UsuarioLogin, db: Session = Depends(get_db)):
    """
    Realiza login via Supabase Auth (server-side).

    Retorna tokens do Supabase que podem ser usados para autenticação.

    **Nota:** Em produção, o login deve ser feito diretamente pelo frontend
    usando supabase-js para melhor UX (refresh automático, etc).

    **Segurança:** Mensagens de erro são genéricas para prevenir
    enumeração de usuários.
    """
    if not SUPABASE_AUTH_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Serviço de autenticação não está configurado"
        )

    from services.supabase_auth import sign_in_with_password

    # Mensagem genérica para evitar user enumeration
    INVALID_CREDENTIALS = "Credenciais inválidas"

    result = sign_in_with_password(credentials.email, credentials.senha)
    if not result:
        logger.warning("[AUTH] Login falhou: credenciais invalidas")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=INVALID_CREDENTIALS,
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Verificar se usuário existe localmente e está ativo
    user = get_user_by_email(db, credentials.email)
    if not user:
        logger.warning("[AUTH] Login falhou: usuario nao encontrado localmente")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=INVALID_CREDENTIALS
        )

    if not user.is_active:
        log_action(
            logger, "login_blocked",
            user_id=user.id,
            resource_type="auth",
            reason="inactive",
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuário inativo"
        )

    log_action(
        logger, "login_success",
        user_id=user.id,
        resource_type="auth",
    )

    return Token(
        access_token=result["access_token"],
        token_type="bearer"
    )


# === Endpoints de Usuário ===

@router.get(
    "/me",
    response_model=UsuarioResponse,
    summary="Obter dados do usuário atual",
    responses={
        200: {"description": "Dados do usuário retornados"},
        401: {"description": "Não autenticado"},
    }
)
def get_current_user_info(current_user: Usuario = Depends(get_current_active_user)):
    """
    Retorna os dados completos do usuário logado.

    Inclui nome, email, status de aprovação, preferências e timestamps.
    """
    return current_user


@router.get(
    "/status",
    response_model=UserStatusResponse,
    summary="Verificar status do usuário",
    responses={
        200: {"description": "Status retornado"},
        401: {"description": "Não autenticado"},
    }
)
def check_user_status(current_user: Usuario = Depends(get_current_active_user)) -> UserStatusResponse:
    """
    Verifica o status do usuário logado.

    Útil para o frontend verificar rapidamente se o usuário está aprovado
    e tem acesso às funcionalidades do sistema.

    **Retorna:**
    - `aprovado`: Se o usuário foi aprovado pelo admin
    - `admin`: Se o usuário é administrador
    - `nome`: Nome do usuário
    - `auth_mode`: Modo de autenticação ativo
    """
    return UserStatusResponse(
        aprovado=current_user.is_approved,
        admin=current_user.is_admin,
        nome=current_user.nome,
        auth_mode=get_auth_mode()
    )


@router.put(
    "/me",
    response_model=UsuarioResponse,
    summary="Atualizar perfil do usuário",
    responses={
        200: {"description": "Perfil atualizado com sucesso"},
        400: {"description": "Dados inválidos (ex: tema inválido)"},
        401: {"description": "Não autenticado"},
        403: {"description": "Usuário não aprovado"},
    }
)
def update_profile(
    dados: UsuarioUpdate,
    current_user: Usuario = Depends(get_current_approved_user),
    db: Session = Depends(get_db)
):
    """
    Atualiza os dados do perfil do usuário.

    Apenas usuários aprovados podem atualizar o perfil.
    Se o usuário estiver vinculado ao Supabase, os metadados também são atualizados.

    **Campos atualizáveis:**
    - `nome`: Nome de exibição
    - `tema_preferido`: "light" ou "dark"
    """
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

    log_action(
        logger, "profile_updated",
        user_id=current_user.id,
        resource_type="usuario",
        resource_id=current_user.id,
    )

    return current_user
