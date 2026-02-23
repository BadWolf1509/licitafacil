from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel

from schemas.atestado import ServicoAtestado
from schemas.base import PaginatedResponse


class ExigenciaEdital(BaseModel):
    """Representa uma exigência extraída do edital."""
    descricao: Optional[str] = None
    quantidade_minima: Optional[Decimal] = None
    unidade: Optional[str] = None
    permitir_soma: Optional[bool] = None
    exige_unico: Optional[bool] = None


class AtestadoMatch(BaseModel):
    """Representa um atestado que pode atender uma exigência."""
    atestado_id: int
    descricao_servico: str
    quantidade: Decimal
    unidade: str
    percentual_cobertura: float
    itens: Optional[List[ServicoAtestado]] = None


class ResultadoExigencia(BaseModel):
    """Resultado da análise de uma exigência específica."""
    exigencia: ExigenciaEdital
    status: str  # "atende", "parcial", "nao_atende"
    atestados_recomendados: List[AtestadoMatch]
    soma_quantidades: Decimal
    percentual_total: float


class AnaliseCreate(BaseModel):
    nome_licitacao: str


class AnaliseManualCreate(BaseModel):
    """Schema para criar análise manualmente (sem PDF)."""
    nome_licitacao: str
    exigencias: List[ExigenciaEdital]


class AnaliseResponse(BaseModel):
    id: int
    user_id: int
    nome_licitacao: str
    arquivo_path: Optional[str] = None
    exigencias_json: Optional[List[ExigenciaEdital]] = None
    resultado_json: Optional[List[ResultadoExigencia]] = None
    created_at: datetime

    class Config:
        from_attributes = True


class PaginatedAnaliseResponse(PaginatedResponse[AnaliseResponse]):
    """Resposta paginada de análises."""
    pass
