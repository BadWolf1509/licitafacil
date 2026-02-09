"""
Routers base com autenticação integrada.

Fornece classes de router que incluem dependências de autenticação
automaticamente, reduzindo repetição de código nos endpoints.
"""

from fastapi import APIRouter, Depends

from auth import get_current_admin_user, get_current_approved_user


class AuthenticatedRouter(APIRouter):
    """
    Router que requer usuário autenticado e aprovado.

    Todos os endpoints definidos neste router automaticamente
    requerem um token JWT válido de um usuário aprovado.

    Exemplo:
        router = AuthenticatedRouter(prefix="/items", tags=["Items"])

        @router.get("/")
        def list_items(current_user: Usuario = Depends(get_current_approved_user)):
            ...
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.dependencies = [Depends(get_current_approved_user)]


class AdminRouter(APIRouter):
    """
    Router que requer usuário administrador.

    Todos os endpoints definidos neste router automaticamente
    requerem um token JWT válido de um usuário administrador.

    Exemplo:
        router = AdminRouter(prefix="/admin", tags=["Admin"])

        @router.get("/users")
        def list_users(current_user: Usuario = Depends(get_current_admin_user)):
            ...
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.dependencies = [Depends(get_current_admin_user)]
