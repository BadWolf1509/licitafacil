from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional

from pydantic import BaseModel, Field, field_validator

from models.licitacao import LicitacaoStatus
from schemas.base import PaginatedResponse


class LicitacaoBase(BaseModel):
    numero: str = Field(..., max_length=100)
    orgao: str = Field(..., max_length=500)
    objeto: str
    modalidade: str = Field(..., max_length=100)
    numero_controle_pncp: Optional[str] = Field(None, max_length=100)
    valor_estimado: Optional[Decimal] = None
    valor_homologado: Optional[Decimal] = None
    valor_proposta: Optional[Decimal] = None
    data_publicacao: Optional[datetime] = None
    data_abertura: Optional[datetime] = None
    data_encerramento: Optional[datetime] = None
    data_resultado: Optional[datetime] = None
    uf: Optional[str] = Field(None, max_length=2)
    municipio: Optional[str] = Field(None, max_length=200)
    esfera: Optional[str] = Field(None, max_length=20)
    link_edital: Optional[str] = Field(None, max_length=1000)
    link_sistema_origem: Optional[str] = Field(None, max_length=1000)
    observacoes: Optional[str] = None
    fonte: str = Field(default="manual", max_length=30)


class LicitacaoCreate(LicitacaoBase):
    pass


class LicitacaoUpdate(BaseModel):
    """Todos os campos opcionais para update parcial."""
    numero: Optional[str] = Field(None, max_length=100)
    orgao: Optional[str] = Field(None, max_length=500)
    objeto: Optional[str] = None
    modalidade: Optional[str] = Field(None, max_length=100)
    numero_controle_pncp: Optional[str] = Field(None, max_length=100)
    valor_estimado: Optional[Decimal] = None
    valor_homologado: Optional[Decimal] = None
    valor_proposta: Optional[Decimal] = None
    decisao_go: Optional[bool] = None
    motivo_nogo: Optional[str] = None
    data_publicacao: Optional[datetime] = None
    data_abertura: Optional[datetime] = None
    data_encerramento: Optional[datetime] = None
    data_resultado: Optional[datetime] = None
    uf: Optional[str] = Field(None, max_length=2)
    municipio: Optional[str] = Field(None, max_length=200)
    esfera: Optional[str] = Field(None, max_length=20)
    link_edital: Optional[str] = Field(None, max_length=1000)
    link_sistema_origem: Optional[str] = Field(None, max_length=1000)
    observacoes: Optional[str] = None


class LicitacaoStatusUpdate(BaseModel):
    """Schema para mudança de status com observação."""
    status: str
    observacao: Optional[str] = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        if v not in LicitacaoStatus.ALL:
            raise ValueError(f"Status inválido: {v}")
        return v


class LicitacaoTagCreate(BaseModel):
    tag: str = Field(..., max_length=100)


class LicitacaoTagResponse(BaseModel):
    id: int
    tag: str

    class Config:
        from_attributes = True


class LicitacaoHistoricoResponse(BaseModel):
    id: int
    licitacao_id: int
    user_id: int
    status_anterior: Optional[str] = None
    status_novo: str
    observacao: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class LicitacaoResponse(LicitacaoBase):
    id: int
    user_id: int
    status: str
    decisao_go: Optional[bool] = None
    motivo_nogo: Optional[str] = None
    tags: List[LicitacaoTagResponse] = []
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class LicitacaoDetalheResponse(LicitacaoResponse):
    """Response com histórico incluso (para GET /{id})."""
    historico: List[LicitacaoHistoricoResponse] = []


class PaginatedLicitacaoResponse(PaginatedResponse[LicitacaoResponse]):
    """Resposta paginada de licitações."""
    pass


class LicitacaoEstatisticasResponse(BaseModel):
    total: int
    por_status: Dict[str, int]
    por_uf: Dict[str, int]
    por_modalidade: Dict[str, int]
