from pydantic import BaseModel, EmailStr
from typing import Optional, List, Any
from datetime import datetime
from decimal import Decimal


# ============== USUÁRIO ==============

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
    """Resposta com mais detalhes para admin."""
    approved_by: Optional[int] = None


# ============== AUTENTICAÇÃO ==============

class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    email: Optional[str] = None
    user_id: Optional[int] = None


# ============== ATESTADO ==============

class ServicoAtestado(BaseModel):
    """Representa um serviço individual dentro de um atestado."""
    descricao: str
    quantidade: float
    unidade: str


class AtestadoBase(BaseModel):
    descricao_servico: str
    quantidade: Decimal
    unidade: str
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


class AtestadoResponse(AtestadoBase):
    id: int
    user_id: int
    arquivo_path: Optional[str] = None
    texto_extraido: Optional[str] = None
    servicos_json: Optional[List[ServicoAtestado]] = None  # Lista de serviços detalhados
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ============== ANÁLISE ==============

class ExigenciaEdital(BaseModel):
    """Representa uma exigência extraída do edital."""
    descricao: str
    quantidade_minima: Decimal
    unidade: str


class AtestadoMatch(BaseModel):
    """Representa um atestado que pode atender uma exigência."""
    atestado_id: int
    descricao_servico: str
    quantidade: Decimal
    unidade: str
    percentual_cobertura: float


class ResultadoExigencia(BaseModel):
    """Resultado da análise de uma exigência específica."""
    exigencia: ExigenciaEdital
    status: str  # "atende", "parcial", "nao_atende"
    atestados_recomendados: List[AtestadoMatch]
    soma_quantidades: Decimal
    percentual_total: float


class AnaliseCreate(BaseModel):
    nome_licitacao: str


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


# ============== MENSAGENS ==============

class Mensagem(BaseModel):
    mensagem: str
    sucesso: bool = True
