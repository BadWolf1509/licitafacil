from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Generic, TypeVar, Any, Sequence
from datetime import datetime
from decimal import Decimal

T = TypeVar('T')


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


# ============== ATESTADO ==============

class ServicoAtestado(BaseModel):
    """Representa um serviço individual dentro de um atestado."""
    item: Optional[str] = None
    descricao: Optional[str] = None
    quantidade: Optional[float] = None
    unidade: Optional[str] = None



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
    servicos_json: Optional[List[ServicoAtestado]] = None  # Lista de serviços detalhados
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ============== ANÁLISE ==============

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


class PaginatedAtestadoResponse(PaginatedResponse[AtestadoResponse]):
    """Resposta paginada de atestados."""
    pass


class PaginatedAnaliseResponse(PaginatedResponse[AnaliseResponse]):
    """Resposta paginada de análises."""
    pass
