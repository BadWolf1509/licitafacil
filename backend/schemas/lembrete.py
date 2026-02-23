from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from models.lembrete import LembreteRecorrencia, LembreteStatus, LembreteTipo
from schemas.base import PaginatedResponse

# ============== LEMBRETE ==============


class LembreteBase(BaseModel):
    titulo: str = Field(..., max_length=255)
    descricao: Optional[str] = None
    data_lembrete: datetime
    data_evento: Optional[datetime] = None
    tipo: str = Field(default=LembreteTipo.MANUAL, max_length=50)
    recorrencia: Optional[str] = Field(None, max_length=30)
    canais: Optional[List[str]] = Field(default=["app"])
    licitacao_id: Optional[int] = None

    @field_validator("tipo")
    @classmethod
    def validate_tipo(cls, v: str) -> str:
        if v not in LembreteTipo.ALL:
            raise ValueError(f"Tipo de lembrete inválido: {v}")
        return v

    @field_validator("recorrencia")
    @classmethod
    def validate_recorrencia(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in LembreteRecorrencia.ALL:
            raise ValueError(f"Recorrência inválida: {v}")
        return v

    @field_validator("canais")
    @classmethod
    def validate_canais(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        if v is not None:
            valid = {"app", "email"}
            for canal in v:
                if canal not in valid:
                    raise ValueError(f"Canal inválido: {canal}. Válidos: {valid}")
        return v


class LembreteCreate(LembreteBase):
    pass


class LembreteUpdate(BaseModel):
    titulo: Optional[str] = Field(None, max_length=255)
    descricao: Optional[str] = None
    data_lembrete: Optional[datetime] = None
    data_evento: Optional[datetime] = None
    tipo: Optional[str] = Field(None, max_length=50)
    recorrencia: Optional[str] = Field(None, max_length=30)
    canais: Optional[List[str]] = None
    licitacao_id: Optional[int] = None

    @field_validator("tipo")
    @classmethod
    def validate_tipo(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in LembreteTipo.ALL:
            raise ValueError(f"Tipo de lembrete inválido: {v}")
        return v

    @field_validator("recorrencia")
    @classmethod
    def validate_recorrencia(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in LembreteRecorrencia.ALL:
            raise ValueError(f"Recorrência inválida: {v}")
        return v


class LembreteStatusUpdate(BaseModel):
    status: str

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        if v not in LembreteStatus.ALL:
            raise ValueError(f"Status de lembrete inválido: {v}")
        return v


class LembreteResponse(BaseModel):
    id: int
    user_id: int
    licitacao_id: Optional[int] = None
    titulo: str
    descricao: Optional[str] = None
    data_lembrete: datetime
    data_evento: Optional[datetime] = None
    tipo: str
    recorrencia: Optional[str] = None
    canais: Optional[List[str]] = None
    status: str
    enviado_em: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class PaginatedLembreteResponse(PaginatedResponse[LembreteResponse]):
    pass


# ============== NOTIFICAÇÃO ==============


class NotificacaoResponse(BaseModel):
    id: int
    user_id: int
    titulo: str
    mensagem: str
    tipo: str
    link: Optional[str] = None
    lida: bool
    lida_em: Optional[datetime] = None
    referencia_tipo: Optional[str] = None
    referencia_id: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True


class NotificacaoCountResponse(BaseModel):
    count: int


class PaginatedNotificacaoResponse(PaginatedResponse[NotificacaoResponse]):
    pass


# ============== PREFERÊNCIA NOTIFICAÇÃO ==============


class PreferenciaNotificacaoResponse(BaseModel):
    id: int
    user_id: int
    email_habilitado: bool
    app_habilitado: bool
    antecedencia_horas: int
    email_resumo_diario: bool
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class PreferenciaNotificacaoUpdate(BaseModel):
    email_habilitado: Optional[bool] = None
    app_habilitado: Optional[bool] = None
    antecedencia_horas: Optional[int] = Field(None, ge=1, le=168)
    email_resumo_diario: Optional[bool] = None


# ============== CALENDÁRIO ==============


class CalendarioQuery(BaseModel):
    data_inicio: datetime
    data_fim: datetime
