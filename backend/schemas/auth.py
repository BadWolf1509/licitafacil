from typing import List, Optional

from pydantic import BaseModel


class Token(BaseModel):
    access_token: str
    token_type: str


class AuthConfigResponse(BaseModel):
    """Configuração de autenticação para o frontend."""
    mode: str
    supabase_enabled: bool
    supabase_url: Optional[str] = None
    supabase_anon_key: Optional[str] = None


class UserStatusResponse(BaseModel):
    """Status do usuário logado."""
    aprovado: bool
    admin: bool
    nome: str
    auth_mode: str


class PasswordPolicy(BaseModel):
    """Política de senha estruturada para validação no frontend."""
    min_length: int
    require_uppercase: bool
    require_lowercase: bool
    require_digit: bool
    require_special: bool


class PasswordRequirementsResponse(BaseModel):
    """Requisitos de senha."""
    requisitos: List[str]
    policy: PasswordPolicy
