"""Schemas Pydantic para gestão documental."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from models.documento import DocumentoTipo
from schemas.base import PaginatedResponse

# === Documento ===


class DocumentoBase(BaseModel):
    """Campos base do documento."""

    nome: str = Field(..., max_length=255)
    tipo_documento: str = Field(..., max_length=100)
    licitacao_id: Optional[int] = None
    data_emissao: Optional[datetime] = None
    data_validade: Optional[datetime] = None
    obrigatorio: bool = False
    observacoes: Optional[str] = None

    @field_validator("tipo_documento")
    @classmethod
    def validate_tipo(cls, v: str) -> str:
        if v not in DocumentoTipo.ALL:
            raise ValueError(
                f"Tipo de documento inválido: {v}. "
                f"Válidos: {', '.join(DocumentoTipo.ALL)}"
            )
        return v


class DocumentoCreate(DocumentoBase):
    """Schema para criação de documento (metadados, sem arquivo)."""

    pass


class DocumentoUpdate(BaseModel):
    """Todos os campos opcionais para update parcial."""

    nome: Optional[str] = Field(None, max_length=255)
    tipo_documento: Optional[str] = Field(None, max_length=100)
    licitacao_id: Optional[int] = None
    data_emissao: Optional[datetime] = None
    data_validade: Optional[datetime] = None
    obrigatorio: Optional[bool] = None
    observacoes: Optional[str] = None

    @field_validator("tipo_documento")
    @classmethod
    def validate_tipo(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in DocumentoTipo.ALL:
            raise ValueError(
                f"Tipo de documento inválido: {v}. "
                f"Válidos: {', '.join(DocumentoTipo.ALL)}"
            )
        return v


class DocumentoResponse(DocumentoBase):
    """Response de documento."""

    id: int
    user_id: int
    arquivo_path: Optional[str] = None
    tamanho_bytes: Optional[int] = None
    status: str
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class PaginatedDocumentoResponse(PaginatedResponse[DocumentoResponse]):
    """Resposta paginada de documentos."""

    pass


class DocumentoResumoResponse(BaseModel):
    """Resumo de saúde documental."""

    total: int
    validos: int
    vencendo: int
    vencidos: int
    nao_aplicavel: int


# === Checklist ===


class ChecklistItemBase(BaseModel):
    """Campos base do item de checklist."""

    descricao: str
    tipo_documento: Optional[str] = Field(None, max_length=100)
    obrigatorio: bool = True
    observacao: Optional[str] = None
    ordem: int = 0

    @field_validator("tipo_documento")
    @classmethod
    def validate_tipo(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in DocumentoTipo.ALL:
            raise ValueError(
                f"Tipo de documento inválido: {v}. "
                f"Válidos: {', '.join(DocumentoTipo.ALL)}"
            )
        return v


class ChecklistItemCreate(ChecklistItemBase):
    """Schema para criação de item de checklist."""

    pass


class ChecklistItemUpdate(BaseModel):
    """Update parcial de item de checklist."""

    descricao: Optional[str] = None
    tipo_documento: Optional[str] = Field(None, max_length=100)
    obrigatorio: Optional[bool] = None
    cumprido: Optional[bool] = None
    documento_id: Optional[int] = None
    observacao: Optional[str] = None
    ordem: Optional[int] = None


class ChecklistItemToggle(BaseModel):
    """Toggle cumprido + vincular documento."""

    cumprido: bool
    documento_id: Optional[int] = None


class ChecklistItemResponse(ChecklistItemBase):
    """Response de item de checklist."""

    id: int
    licitacao_id: int
    user_id: int
    cumprido: bool
    documento_id: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ChecklistResumoResponse(BaseModel):
    """Resumo de progresso do checklist."""

    licitacao_id: int
    total: int
    cumpridos: int
    pendentes: int
    obrigatorios_pendentes: int
    percentual: float
