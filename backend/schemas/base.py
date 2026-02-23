from typing import Any, Generic, List, Sequence, TypeVar

from pydantic import BaseModel, Field

T = TypeVar('T')


# ============== MENSAGENS ==============

class Mensagem(BaseModel):
    mensagem: str
    sucesso: bool = True


class JobResponse(BaseModel):
    mensagem: str
    sucesso: bool = True
    job_id: str


# ============== PAGINAÇÃO ==============

class PaginatedResponse(BaseModel, Generic[T]):
    """Resposta paginada genérica."""
    items: List[T]
    total: int
    page: int = Field(ge=1)
    page_size: int = Field(ge=1)
    total_pages: int = Field(ge=0)

    @classmethod
    def create(
        cls,
        items: Sequence[Any],
        total: int,
        page: int,
        page_size: int
    ) -> "PaginatedResponse[T]":
        """Cria uma resposta paginada."""
        total_pages = (total + page_size - 1) // page_size if page_size > 0 else 0
        return cls(
            items=list(items),
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages
        )
