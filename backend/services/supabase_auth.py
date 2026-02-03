"""
Serviço de autenticação usando Supabase Auth.

Fornece validação de tokens JWT do Supabase e gerenciamento de usuários.
"""
from typing import Optional, Dict, Any

from config import SUPABASE_URL, SUPABASE_SERVICE_KEY, SUPABASE_ANON_KEY
from logging_config import get_logger

logger = get_logger('services.supabase_auth')

# Cliente Supabase (lazy initialization)
_supabase_client = None


def _get_supabase_client():
    """Retorna cliente Supabase com lazy initialization."""
    global _supabase_client

    if _supabase_client is None:
        if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
            raise ValueError("SUPABASE_URL e SUPABASE_SERVICE_KEY são obrigatórios")

        from supabase import create_client
        _supabase_client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
        logger.info("[SUPABASE_AUTH] Cliente inicializado")

    return _supabase_client


def verify_supabase_token(access_token: str) -> Optional[Dict[str, Any]]:
    """
    Verifica um token JWT do Supabase e retorna os dados do usuário.

    Args:
        access_token: Token JWT do Supabase Auth

    Returns:
        Dicionário com dados do usuário ou None se token inválido
    """
    try:
        client = _get_supabase_client()
        response = client.auth.get_user(access_token)

        if response and response.user:
            user = response.user
            return {
                "id": user.id,
                "email": user.email,
                "email_confirmed": user.email_confirmed_at is not None,
                "phone": user.phone,
                "created_at": str(user.created_at) if user.created_at else None,
                "last_sign_in": str(user.last_sign_in_at) if user.last_sign_in_at else None,
                "app_metadata": user.app_metadata,
                "user_metadata": user.user_metadata,
            }

        return None

    except Exception as e:
        logger.warning(f"[SUPABASE_AUTH] Erro ao verificar token: {e}")
        return None


def create_supabase_user(email: str, password: str, user_metadata: Optional[Dict] = None) -> Optional[Dict[str, Any]]:
    """
    Cria um novo usuário no Supabase Auth.

    Args:
        email: Email do usuário
        password: Senha do usuário
        user_metadata: Metadados adicionais (nome, empresa, etc.)

    Returns:
        Dicionário com dados do usuário criado ou None em caso de erro
    """
    try:
        client = _get_supabase_client()

        options = {}
        if user_metadata:
            options["data"] = user_metadata

        response = client.auth.admin.create_user({
            "email": email,
            "password": password,
            "email_confirm": True,  # Auto-confirmar email para desenvolvimento
            "user_metadata": user_metadata or {}
        })

        if response and response.user:
            logger.info(f"[SUPABASE_AUTH] Usuário criado: {email}")
            return {
                "id": response.user.id,
                "email": response.user.email,
            }

        return None

    except Exception as e:
        logger.error(f"[SUPABASE_AUTH] Erro ao criar usuário: {e}")
        raise


def get_supabase_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    """
    Busca usuário no Supabase Auth pelo email.

    Args:
        email: Email do usuário

    Returns:
        Dicionário com dados do usuário ou None se não encontrado
    """
    try:
        client = _get_supabase_client()

        # Usar admin API para buscar usuários
        response = client.auth.admin.list_users()

        if response:
            for user in response:
                if user.email == email:
                    return {
                        "id": user.id,
                        "email": user.email,
                        "created_at": str(user.created_at) if user.created_at else None,
                    }

        return None

    except Exception as e:
        logger.warning(f"[SUPABASE_AUTH] Erro ao buscar usuário: {e}")
        return None


def delete_supabase_user(supabase_id: str) -> bool:
    """
    Remove um usuário do Supabase Auth.

    Args:
        supabase_id: UUID do usuário no Supabase

    Returns:
        True se removido com sucesso
    """
    try:
        client = _get_supabase_client()
        client.auth.admin.delete_user(supabase_id)
        logger.info(f"[SUPABASE_AUTH] Usuário removido: {supabase_id}")
        return True

    except Exception as e:
        logger.error(f"[SUPABASE_AUTH] Erro ao remover usuário: {e}")
        return False


def update_supabase_user_metadata(supabase_id: str, metadata: Dict[str, Any]) -> bool:
    """
    Atualiza metadados do usuário no Supabase Auth.

    Args:
        supabase_id: UUID do usuário no Supabase
        metadata: Dicionário com metadados a atualizar

    Returns:
        True se atualizado com sucesso
    """
    try:
        client = _get_supabase_client()
        client.auth.admin.update_user_by_id(
            supabase_id,
            {"user_metadata": metadata}
        )
        logger.info(f"[SUPABASE_AUTH] Metadados atualizados: {supabase_id}")
        return True

    except Exception as e:
        logger.error(f"[SUPABASE_AUTH] Erro ao atualizar metadados: {e}")
        return False


def sign_in_with_password(email: str, password: str) -> Optional[Dict[str, Any]]:
    """
    Autentica usuário com email e senha.

    NOTA: Esta função usa a API de admin para autenticação server-side.
    Em produção, o login deve ser feito pelo frontend usando supabase-js.

    Args:
        email: Email do usuário
        password: Senha do usuário

    Returns:
        Dicionário com tokens de acesso ou None se falhar
    """
    try:
        # Para login server-side, precisamos usar a anon key
        from supabase import create_client  # type: ignore[attr-defined]
        anon_client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

        response = anon_client.auth.sign_in_with_password({
            "email": email,
            "password": password
        })

        if response and response.session and response.user:
            return {
                "access_token": response.session.access_token,
                "refresh_token": response.session.refresh_token,
                "expires_in": response.session.expires_in,
                "user": {
                    "id": response.user.id,
                    "email": response.user.email,
                }
            }

        return None

    except Exception as e:
        logger.warning(f"[SUPABASE_AUTH] Erro ao fazer login: {e}")
        return None


def refresh_session(refresh_token: str) -> Optional[Dict[str, Any]]:
    """
    Renova sessão usando refresh token.

    Args:
        refresh_token: Token de refresh

    Returns:
        Nova sessão ou None se falhar
    """
    try:
        from supabase import create_client  # type: ignore[attr-defined]
        anon_client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

        response = anon_client.auth.refresh_session(refresh_token)

        if response and response.session:
            return {
                "access_token": response.session.access_token,
                "refresh_token": response.session.refresh_token,
                "expires_in": response.session.expires_in,
            }

        return None

    except Exception as e:
        logger.warning(f"[SUPABASE_AUTH] Erro ao renovar sessão: {e}")
        return None


# Configurações do Supabase para o frontend
def get_supabase_config() -> Dict[str, str]:
    """
    Retorna configurações públicas do Supabase para o frontend.

    Apenas a anon key é retornada - NUNCA a service key!
    """
    return {
        "url": SUPABASE_URL,
        "anon_key": SUPABASE_ANON_KEY,
    }
