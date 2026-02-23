"""Schemas Pydantic para monitoramento PNCP."""
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from models.pncp import PncpResultadoStatus
from schemas.base import PaginatedResponse

# ==================== Monitoramento ====================


class PncpMonitoramentoBase(BaseModel):
    nome: str = Field(..., min_length=1, max_length=200)
    ativo: bool = True
    palavras_chave: Optional[List[str]] = None
    ufs: Optional[List[str]] = None
    modalidades: Optional[List[str]] = None
    esferas: Optional[List[str]] = None
    valor_minimo: Optional[Decimal] = None
    valor_maximo: Optional[Decimal] = None

    @field_validator("palavras_chave")
    @classmethod
    def validar_palavras_chave(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        if v is not None and len(v) > 20:
            msg = "Máximo de 20 palavras-chave"
            raise ValueError(msg)
        return v

    @field_validator("ufs")
    @classmethod
    def validar_ufs(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        if v is not None and len(v) > 27:
            msg = "Máximo de 27 UFs"
            raise ValueError(msg)
        return v

    @field_validator("valor_minimo", "valor_maximo")
    @classmethod
    def validar_valores(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        if v is not None and v < 0:
            msg = "Valor não pode ser negativo"
            raise ValueError(msg)
        return v


class PncpMonitoramentoCreate(PncpMonitoramentoBase):
    pass


class PncpMonitoramentoUpdate(BaseModel):
    nome: Optional[str] = Field(None, min_length=1, max_length=200)
    ativo: Optional[bool] = None
    palavras_chave: Optional[List[str]] = None
    ufs: Optional[List[str]] = None
    modalidades: Optional[List[str]] = None
    esferas: Optional[List[str]] = None
    valor_minimo: Optional[Decimal] = None
    valor_maximo: Optional[Decimal] = None


class PncpMonitoramentoResponse(PncpMonitoramentoBase):
    id: int
    user_id: int
    ultimo_check: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class PaginatedMonitoramentoResponse(PaginatedResponse[PncpMonitoramentoResponse]):
    pass


# ==================== Resultado ====================


class PncpResultadoResponse(BaseModel):
    id: int
    monitoramento_id: int
    user_id: int
    numero_controle_pncp: str
    orgao_cnpj: Optional[str] = None
    orgao_razao_social: Optional[str] = None
    objeto_compra: Optional[str] = None
    modalidade_nome: Optional[str] = None
    uf: Optional[str] = None
    municipio: Optional[str] = None
    valor_estimado: Optional[Decimal] = None
    data_abertura: Optional[datetime] = None
    data_encerramento: Optional[datetime] = None
    link_sistema_origem: Optional[str] = None
    status: str
    licitacao_id: Optional[int] = None
    encontrado_em: datetime

    model_config = {"from_attributes": True}


class PaginatedResultadoResponse(PaginatedResponse[PncpResultadoResponse]):
    pass


class PncpResultadoStatusUpdate(BaseModel):
    status: str

    @field_validator("status")
    @classmethod
    def validar_status(cls, v: str) -> str:
        if v not in PncpResultadoStatus.ALL:
            msg = f"Status inválido. Valores permitidos: {PncpResultadoStatus.ALL}"
            raise ValueError(msg)
        return v


# ==================== Busca ====================


class PncpBuscaResponse(BaseModel):
    data: List[dict]
    total_registros: int = 0
    total_paginas: int = 0
    numero_pagina: int = 1
    paginas_restantes: int = 0


class PncpImportarRequest(BaseModel):
    observacoes: Optional[str] = None
