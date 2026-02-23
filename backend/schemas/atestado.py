from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, Field, model_validator

from schemas.base import PaginatedResponse


class ServicoAtestado(BaseModel):
    """Representa um serviço individual dentro de um atestado."""
    item: Optional[str] = Field(None, max_length=50)
    descricao: Optional[str] = Field(None, max_length=1000)
    quantidade: Optional[float] = None
    unidade: Optional[str] = Field(None, max_length=50)

    @model_validator(mode="after")
    def validate_descricao_not_empty(self) -> "ServicoAtestado":
        if self.descricao is not None and not self.descricao.strip():
            raise ValueError("descrição não pode ser uma string vazia")
        return self


class AtestadoBase(BaseModel):
    descricao_servico: str
    quantidade: Optional[Decimal] = None
    unidade: Optional[str] = None
    contratante: Optional[str] = None
    data_emissao: Optional[datetime] = None


class AtestadoCreate(AtestadoBase):
    pass


class AtestadoUpdate(BaseModel):
    descricao_servico: Optional[str] = None
    quantidade: Optional[Decimal] = None
    unidade: Optional[str] = None
    contratante: Optional[str] = None
    data_emissao: Optional[datetime] = None


class AtestadoServicosUpdate(BaseModel):
    """Schema para atualizar apenas os serviços de um atestado."""
    servicos_json: List[ServicoAtestado]


class AtestadoResponse(AtestadoBase):
    id: int
    user_id: int
    arquivo_path: Optional[str] = None
    texto_extraido: Optional[str] = None
    servicos_json: Optional[List[ServicoAtestado]] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class PaginatedAtestadoResponse(PaginatedResponse[AtestadoResponse]):
    """Resposta paginada de atestados."""
    pass
