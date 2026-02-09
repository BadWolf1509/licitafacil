"""
Utilitários de paginação para endpoints da API.
"""
from typing import Any, Type, TypeVar

from fastapi import Query
from sqlalchemy.orm import Query as SQLQuery

from config import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE

T = TypeVar('T')


class PaginationParams:
    """
    Parâmetros de paginação como dependência do FastAPI.

    Uso:
        @router.get("/items")
        def list_items(pagination: PaginationParams = Depends()):
            ...
    """

    def __init__(
        self,
        page: int = Query(1, ge=1, description="Número da página"),
        page_size: int = Query(
            DEFAULT_PAGE_SIZE,
            ge=1,
            le=MAX_PAGE_SIZE,
            description="Itens por página"
        )
    ):
        self.page = page
        self.page_size = page_size
        self.offset = (page - 1) * page_size


def paginate_query(
    query: SQLQuery,
    pagination: PaginationParams,
    response_class: Type[Any]
) -> Any:
    """
    Aplica paginação a uma query SQLAlchemy.

    Args:
        query: Query base para paginar
        pagination: Parâmetros de paginação
        response_class: Classe de resposta paginada (deve ter método create)

    Returns:
        Resposta paginada
    """
    total = query.count()
    items = query.offset(pagination.offset).limit(pagination.page_size).all()

    return response_class.create(
        items=items,
        total=total,
        page=pagination.page,
        page_size=pagination.page_size
    )
