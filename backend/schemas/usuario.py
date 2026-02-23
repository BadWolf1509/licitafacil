from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr

from schemas.base import PaginatedResponse


class UsuarioBase(BaseModel):
    email: EmailStr
    nome: str


class UsuarioCreate(UsuarioBase):
    senha: str


class UsuarioLogin(BaseModel):
    email: EmailStr
    senha: str


class UsuarioUpdate(BaseModel):
    nome: Optional[str] = None
    tema_preferido: Optional[str] = None


class UsuarioResponse(UsuarioBase):
    id: int
    is_admin: bool
    is_approved: bool
    is_active: bool
    tema_preferido: str
    created_at: datetime
    approved_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class UsuarioAdminResponse(UsuarioResponse):
    """Resposta com mais detalhes para o admin."""
    approved_by: Optional[int] = None


class PaginatedUsuarioResponse(PaginatedResponse[UsuarioAdminResponse]):
    """Resposta paginada de usuários (admin)."""
    pass
