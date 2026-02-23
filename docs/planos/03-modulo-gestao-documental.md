# Plano Detalhado - Modulo 4: Gestao Documental

> **Status**: IMPLEMENTADO (2026-02-11)
> **Dependencias**: F1 (M1 Licitacoes) - IMPLEMENTADO
> **Migracao Alembic**: `k1f5n46984mm_add_documentos_checklist`
> **Fase no plano arquitetural**: F3

---

## Contexto

O Modulo 4 adiciona gestao documental ao LicitaFacil: upload e armazenamento de documentos vinculados a licitacoes (certidoes, balancos, procuracoes, etc.), controle de validade com alertas automaticos de vencimento, e checklist de documentos exigidos por edital. Integra-se com o sistema de notificacoes existente (M2) para avisar o usuario quando documentos estao proximos do vencimento.

**Valor para o usuario**: O licitante brasileiro precisa manter dezenas de certidoes e documentos atualizados. Um documento vencido pode desclassificar uma proposta. Este modulo centraliza o controle e evita esquecimentos.

---

## Passo 1: Models - DocumentoLicitacao, ChecklistEdital

### Arquivo: `backend/models/documento.py`

```python
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    Boolean, DateTime, ForeignKey, Index, Integer, String, Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from database import Base

if TYPE_CHECKING:
    from models.licitacao import Licitacao
    from models.usuario import Usuario


class DocumentoTipo:
    """Tipos de documento de licitacao."""
    EDITAL = "edital"
    CERTIDAO_NEGATIVA = "certidao_negativa"
    BALANCO = "balanco"
    CONTRATO_SOCIAL = "contrato_social"
    PROCURACAO = "procuracao"
    DECLARACAO = "declaracao"
    PLANILHA = "planilha"
    ATESTADO_CAPACIDADE = "atestado_capacidade"
    COMPROVANTE_ENDERECO = "comprovante_endereco"
    CERTIDAO_FGTS = "certidao_fgts"
    CERTIDAO_TRABALHISTA = "certidao_trabalhista"
    CERTIDAO_FEDERAL = "certidao_federal"
    CERTIDAO_ESTADUAL = "certidao_estadual"
    CERTIDAO_MUNICIPAL = "certidao_municipal"
    OUTRO = "outro"
    ALL = [
        EDITAL, CERTIDAO_NEGATIVA, BALANCO, CONTRATO_SOCIAL,
        PROCURACAO, DECLARACAO, PLANILHA, ATESTADO_CAPACIDADE,
        COMPROVANTE_ENDERECO, CERTIDAO_FGTS, CERTIDAO_TRABALHISTA,
        CERTIDAO_FEDERAL, CERTIDAO_ESTADUAL, CERTIDAO_MUNICIPAL,
        OUTRO,
    ]


class DocumentoStatus:
    """Status de validade do documento."""
    VALIDO = "valido"
    VENCENDO = "vencendo"       # Dentro do periodo de alerta (default 30 dias)
    VENCIDO = "vencido"
    NAO_APLICAVEL = "nao_aplicavel"  # Documentos sem validade (edital, planilha)
    ALL = [VALIDO, VENCENDO, VENCIDO, NAO_APLICAVEL]


class DocumentoLicitacao(Base):
    """Documento vinculado a uma licitacao ou ao acervo geral do usuario."""
    __tablename__ = "documentos_licitacao"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True)
    licitacao_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("licitacoes.id", ondelete="SET NULL"), nullable=True, index=True)
    nome: Mapped[str] = mapped_column(String(255), nullable=False)
    tipo_documento: Mapped[str] = mapped_column(String(100), nullable=False)
    arquivo_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    tamanho_bytes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    data_emissao: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True)
    data_validade: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=DocumentoStatus.VALIDO)
    obrigatorio: Mapped[bool] = mapped_column(Boolean, default=False)
    observacoes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), onupdate=func.now())

    usuario: Mapped["Usuario"] = relationship("Usuario")
    licitacao: Mapped[Optional["Licitacao"]] = relationship("Licitacao")

    __table_args__ = (
        Index('ix_documentos_user_tipo', 'user_id', 'tipo_documento'),
        Index('ix_documentos_user_status', 'user_id', 'status'),
        Index('ix_documentos_user_licitacao', 'user_id', 'licitacao_id'),
        Index('ix_documentos_validade_status', 'data_validade', 'status'),
    )


class ChecklistEdital(Base):
    """Item obrigatorio de um edital de licitacao."""
    __tablename__ = "checklist_edital"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    licitacao_id: Mapped[int] = mapped_column(
        ForeignKey("licitacoes.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False)
    descricao: Mapped[str] = mapped_column(Text, nullable=False)
    tipo_documento: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    obrigatorio: Mapped[bool] = mapped_column(Boolean, default=True)
    cumprido: Mapped[bool] = mapped_column(Boolean, default=False)
    documento_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("documentos_licitacao.id", ondelete="SET NULL"), nullable=True)
    observacao: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ordem: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now())

    licitacao: Mapped["Licitacao"] = relationship("Licitacao")
    usuario: Mapped["Usuario"] = relationship("Usuario")
    documento: Mapped[Optional["DocumentoLicitacao"]] = relationship("DocumentoLicitacao")

    __table_args__ = (
        Index('ix_checklist_licitacao_ordem', 'licitacao_id', 'ordem'),
    )
```

### Atualizar `models/__init__.py`

Adicionar:
```python
from models.documento import (
    ChecklistEdital,
    DocumentoLicitacao,
    DocumentoStatus,
    DocumentoTipo,
)
```

---

## Passo 2: Schemas

### Arquivo: `backend/schemas/documento.py`

```python
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from models.documento import DocumentoStatus, DocumentoTipo
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
                f"Tipo de documento invalido: {v}. "
                f"Validos: {', '.join(DocumentoTipo.ALL)}"
            )
        return v


class DocumentoCreate(DocumentoBase):
    """Schema para criacao de documento (metadados, sem arquivo)."""
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
                f"Tipo de documento invalido: {v}. "
                f"Validos: {', '.join(DocumentoTipo.ALL)}"
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
    """Resumo de saude documental."""
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
                f"Tipo de documento invalido: {v}. "
                f"Validos: {', '.join(DocumentoTipo.ALL)}"
            )
        return v


class ChecklistItemCreate(ChecklistItemBase):
    """Schema para criacao de item de checklist."""
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
```

### Atualizar `schemas/__init__.py`

Adicionar re-exports:
```python
from schemas.documento import (
    ChecklistItemCreate,
    ChecklistItemResponse,
    ChecklistItemToggle,
    ChecklistItemUpdate,
    ChecklistResumoResponse,
    DocumentoCreate,
    DocumentoResumoResponse,
    DocumentoResponse,
    DocumentoUpdate,
    PaginatedDocumentoResponse,
)
```

---

## Passo 3: Repositories

### Arquivo: `backend/repositories/documento_repository.py`

```python
"""Repositorio para operacoes de DocumentoLicitacao e ChecklistEdital."""
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from sqlalchemy import func as sa_func
from sqlalchemy.orm import Session

from models.documento import (
    ChecklistEdital,
    DocumentoLicitacao,
    DocumentoStatus,
)
from repositories.base import BaseRepository


class DocumentoLicitacaoRepository(BaseRepository[DocumentoLicitacao]):
    """Repositorio de documentos de licitacao."""

    def __init__(self):
        super().__init__(DocumentoLicitacao)

    def get_filtered(
        self,
        db: Session,
        user_id: int,
        tipo_documento: Optional[str] = None,
        status: Optional[str] = None,
        licitacao_id: Optional[int] = None,
        busca: Optional[str] = None,
    ):
        """Retorna query filtravel para paginacao."""
        query = db.query(DocumentoLicitacao).filter(
            DocumentoLicitacao.user_id == user_id
        )
        if tipo_documento:
            query = query.filter(DocumentoLicitacao.tipo_documento == tipo_documento)
        if status:
            query = query.filter(DocumentoLicitacao.status == status)
        if licitacao_id is not None:
            query = query.filter(DocumentoLicitacao.licitacao_id == licitacao_id)
        if busca:
            busca_like = f"%{busca}%"
            query = query.filter(DocumentoLicitacao.nome.ilike(busca_like))
        return query.order_by(DocumentoLicitacao.created_at.desc())

    def get_by_licitacao(
        self, db: Session, licitacao_id: int, user_id: int
    ) -> List[DocumentoLicitacao]:
        """Documentos de uma licitacao especifica."""
        return db.query(DocumentoLicitacao).filter(
            DocumentoLicitacao.licitacao_id == licitacao_id,
            DocumentoLicitacao.user_id == user_id,
        ).order_by(DocumentoLicitacao.tipo_documento, DocumentoLicitacao.nome).all()

    def get_vencendo(
        self, db: Session, user_id: int, dias: int = 30
    ) -> List[DocumentoLicitacao]:
        """Documentos vencendo nos proximos N dias."""
        agora = datetime.now(timezone.utc)
        limite = agora + timedelta(days=dias)
        return db.query(DocumentoLicitacao).filter(
            DocumentoLicitacao.user_id == user_id,
            DocumentoLicitacao.data_validade.isnot(None),
            DocumentoLicitacao.data_validade <= limite,
            DocumentoLicitacao.data_validade > agora,
            DocumentoLicitacao.status != DocumentoStatus.NAO_APLICAVEL,
        ).order_by(DocumentoLicitacao.data_validade).all()

    def get_vencidos(
        self, db: Session, user_id: int
    ) -> List[DocumentoLicitacao]:
        """Documentos ja vencidos."""
        agora = datetime.now(timezone.utc)
        return db.query(DocumentoLicitacao).filter(
            DocumentoLicitacao.user_id == user_id,
            DocumentoLicitacao.data_validade.isnot(None),
            DocumentoLicitacao.data_validade <= agora,
        ).order_by(DocumentoLicitacao.data_validade).all()

    def get_resumo(self, db: Session, user_id: int) -> Dict:
        """Resumo de saude documental (contagem por status)."""
        base = db.query(DocumentoLicitacao).filter(
            DocumentoLicitacao.user_id == user_id
        )
        total = base.count()
        por_status: dict[str, int] = {
            row[0]: row[1] for row in base.with_entities(
                DocumentoLicitacao.status, sa_func.count(DocumentoLicitacao.id)
            ).group_by(DocumentoLicitacao.status).all()
        }
        return {
            "total": total,
            "validos": por_status.get(DocumentoStatus.VALIDO, 0),
            "vencendo": por_status.get(DocumentoStatus.VENCENDO, 0),
            "vencidos": por_status.get(DocumentoStatus.VENCIDO, 0),
            "nao_aplicavel": por_status.get(DocumentoStatus.NAO_APLICAVEL, 0),
        }

    def atualizar_status_validade(self, db: Session, dias_alerta: int = 30) -> int:
        """
        Atualiza status de todos os documentos com base na data_validade.
        Chamado periodicamente pelo ReminderScheduler.
        Retorna quantidade de documentos atualizados.
        """
        agora = datetime.now(timezone.utc)
        limite = agora + timedelta(days=dias_alerta)
        count = 0

        # Marcar vencidos
        vencidos = db.query(DocumentoLicitacao).filter(
            DocumentoLicitacao.data_validade.isnot(None),
            DocumentoLicitacao.data_validade <= agora,
            DocumentoLicitacao.status != DocumentoStatus.VENCIDO,
            DocumentoLicitacao.status != DocumentoStatus.NAO_APLICAVEL,
        ).all()
        for doc in vencidos:
            doc.status = DocumentoStatus.VENCIDO
            count += 1

        # Marcar vencendo
        vencendo = db.query(DocumentoLicitacao).filter(
            DocumentoLicitacao.data_validade.isnot(None),
            DocumentoLicitacao.data_validade > agora,
            DocumentoLicitacao.data_validade <= limite,
            DocumentoLicitacao.status == DocumentoStatus.VALIDO,
        ).all()
        for doc in vencendo:
            doc.status = DocumentoStatus.VENCENDO
            count += 1

        # Reverter validos (se data_validade foi atualizada)
        revalidados = db.query(DocumentoLicitacao).filter(
            DocumentoLicitacao.data_validade.isnot(None),
            DocumentoLicitacao.data_validade > limite,
            DocumentoLicitacao.status.in_([
                DocumentoStatus.VENCENDO, DocumentoStatus.VENCIDO
            ]),
        ).all()
        for doc in revalidados:
            doc.status = DocumentoStatus.VALIDO
            count += 1

        if count > 0:
            db.commit()
        return count


documento_repository = DocumentoLicitacaoRepository()


class ChecklistRepository(BaseRepository[ChecklistEdital]):
    """Repositorio de checklist de edital."""

    def __init__(self):
        super().__init__(ChecklistEdital)

    def get_by_licitacao(
        self, db: Session, licitacao_id: int, user_id: int
    ) -> List[ChecklistEdital]:
        """Itens do checklist de uma licitacao, ordenados."""
        return db.query(ChecklistEdital).filter(
            ChecklistEdital.licitacao_id == licitacao_id,
            ChecklistEdital.user_id == user_id,
        ).order_by(ChecklistEdital.ordem, ChecklistEdital.id).all()

    def get_item_for_user(
        self, db: Session, item_id: int, user_id: int
    ) -> Optional[ChecklistEdital]:
        """Busca item especifico validando ownership."""
        return db.query(ChecklistEdital).filter(
            ChecklistEdital.id == item_id,
            ChecklistEdital.user_id == user_id,
        ).first()

    def get_resumo(
        self, db: Session, licitacao_id: int, user_id: int
    ) -> Dict:
        """Resumo de progresso do checklist."""
        itens = self.get_by_licitacao(db, licitacao_id, user_id)
        total = len(itens)
        cumpridos = sum(1 for i in itens if i.cumprido)
        obrigatorios = [i for i in itens if i.obrigatorio]
        obrigatorios_pendentes = sum(1 for i in obrigatorios if not i.cumprido)
        return {
            "licitacao_id": licitacao_id,
            "total": total,
            "cumpridos": cumpridos,
            "pendentes": total - cumpridos,
            "obrigatorios_pendentes": obrigatorios_pendentes,
            "percentual": round((cumpridos / total * 100) if total > 0 else 0, 1),
        }

    def bulk_create(
        self, db: Session, licitacao_id: int, user_id: int,
        itens: list,
    ) -> List[ChecklistEdital]:
        """Cria multiplos itens de checklist de uma vez."""
        novos = []
        for i, item_data in enumerate(itens):
            item = ChecklistEdital(
                licitacao_id=licitacao_id,
                user_id=user_id,
                ordem=item_data.get("ordem", i),
                **{k: v for k, v in item_data.items() if k != "ordem"},
            )
            db.add(item)
            novos.append(item)
        db.commit()
        for item in novos:
            db.refresh(item)
        return novos


checklist_repository = ChecklistRepository()
```

---

## Passo 4: Service - DocumentExpiryChecker

### Arquivo: `backend/services/notification/document_checker.py`

```python
"""
Verificador de validade de documentos.
Integra-se com o ReminderScheduler existente.
"""
from datetime import datetime, timedelta, timezone

from database import SessionLocal
from logging_config import get_logger
from models.documento import DocumentoLicitacao, DocumentoStatus
from repositories.documento_repository import documento_repository
from services.notification.notification_service import notification_service
from config.base import DOCUMENT_EXPIRY_WARNING_DAYS

logger = get_logger("services.document_checker")


class DocumentExpiryChecker:
    """Verifica documentos vencendo e gera notificacoes."""

    async def check(self):
        """
        Chamado periodicamente pelo ReminderScheduler.
        1. Atualiza status de validade de todos os documentos
        2. Notifica usuarios sobre documentos que mudaram para 'vencendo'
        """
        db = SessionLocal()
        try:
            # 1. Atualizar status
            updated = documento_repository.atualizar_status_validade(
                db, dias_alerta=DOCUMENT_EXPIRY_WARNING_DAYS
            )
            if updated > 0:
                logger.info(f"Atualizados {updated} status de documentos")

            # 2. Buscar documentos vencendo que ainda nao foram notificados
            #    (usar referencia_tipo="documento" + referencia_id para evitar duplicatas)
            self._notificar_vencimentos(db)
        except Exception:
            logger.error("Erro ao verificar validade de documentos", exc_info=True)
        finally:
            db.close()

    def _notificar_vencimentos(self, db):
        """Gera notificacoes para documentos vencendo."""
        from models.lembrete import NotificacaoTipo
        from models import Notificacao

        # Buscar documentos vencendo (todos os usuarios)
        agora = datetime.now(timezone.utc)
        limite = agora + timedelta(days=DOCUMENT_EXPIRY_WARNING_DAYS)

        docs_vencendo = db.query(DocumentoLicitacao).filter(
            DocumentoLicitacao.data_validade.isnot(None),
            DocumentoLicitacao.data_validade > agora,
            DocumentoLicitacao.data_validade <= limite,
            DocumentoLicitacao.status == DocumentoStatus.VENCENDO,
        ).all()

        for doc in docs_vencendo:
            # Verificar se ja foi notificado (evita spam)
            ja_notificado = db.query(Notificacao).filter(
                Notificacao.user_id == doc.user_id,
                Notificacao.referencia_tipo == "documento",
                Notificacao.referencia_id == doc.id,
                Notificacao.tipo == NotificacaoTipo.DOCUMENTO_VENCENDO,
            ).first()

            if not ja_notificado:
                dias_restantes = (doc.data_validade - agora).days
                notification_service.notify(
                    db=db,
                    user_id=doc.user_id,
                    titulo=f"Documento vencendo em {dias_restantes} dias",
                    mensagem=f'O documento "{doc.nome}" vence em '
                             f'{doc.data_validade.strftime("%d/%m/%Y")}.',
                    tipo=NotificacaoTipo.DOCUMENTO_VENCENDO,
                    link=f"documentos.html?id={doc.id}",
                    referencia_tipo="documento",
                    referencia_id=doc.id,
                )


document_checker = DocumentExpiryChecker()
```

### Modificar: `backend/services/notification/reminder_scheduler.py`

Adicionar chamada ao `document_checker` dentro do worker loop:

```python
# No __init__:
self._doc_check_interval = DOCUMENT_EXPIRY_CHECK_INTERVAL  # default 3600s
self._last_doc_check = 0

# No _worker(), apos _check_lembretes():
import time
now = time.time()
if now - self._last_doc_check >= self._doc_check_interval:
    from services.notification.document_checker import document_checker
    await document_checker.check()
    self._last_doc_check = now
```

---

## Passo 5: Config - Novas variaveis de ambiente

### Modificar: `backend/config/base.py`

Adicionar ao final (apos as constantes de REMINDER):
```python
# === Gestao Documental ===
DOCUMENT_EXPIRY_CHECK_INTERVAL = env_int("DOCUMENT_EXPIRY_CHECK_INTERVAL", 3600)
DOCUMENT_EXPIRY_WARNING_DAYS = env_int("DOCUMENT_EXPIRY_WARNING_DAYS", 30)
```

### Modificar: `backend/config/__init__.py`

Adicionar re-exports:
```python
from config.base import DOCUMENT_EXPIRY_CHECK_INTERVAL, DOCUMENT_EXPIRY_WARNING_DAYS
```

---

## Passo 6: Messages - Novas constantes

### Modificar: `backend/config/messages.py`

Adicionar ao final da classe Messages:
```python
    # Documentos
    DOCUMENTO_NOT_FOUND = "Documento nao encontrado"
    DOCUMENTO_DELETED = "Documento excluido com sucesso!"
    DOCUMENTO_UPLOAD_SUCCESS = "Documento enviado com sucesso!"
    DOCUMENTO_FILE_REQUIRED = "Arquivo e obrigatorio para upload"
    # Checklist
    CHECKLIST_ITEM_NOT_FOUND = "Item do checklist nao encontrado"
    CHECKLIST_ITEM_DELETED = "Item do checklist excluido!"
    CHECKLIST_UPDATED = "Checklist atualizado com sucesso!"
```

---

## Passo 7: Router

### Arquivo: `backend/routers/documentos.py`

```python
"""
Router para gestao documental.

Endpoints:
    GET    /documentos/                     - Listar documentos (paginado, filtros)
    GET    /documentos/vencendo             - Documentos vencendo em 30 dias
    GET    /documentos/resumo               - Resumo de saude documental
    GET    /documentos/{id}                 - Detalhe do documento
    POST   /documentos/upload               - Upload de documento
    POST   /documentos/                     - Criar documento (sem arquivo)
    PUT    /documentos/{id}                 - Atualizar metadados
    DELETE /documentos/{id}                 - Excluir documento
    GET    /documentos/licitacao/{id}       - Documentos de uma licitacao
    GET    /documentos/checklist/{id}       - Checklist de uma licitacao
    GET    /documentos/checklist/{id}/resumo - Resumo do checklist
    POST   /documentos/checklist/{id}       - Criar itens de checklist
    PUT    /documentos/checklist/item/{id}  - Atualizar item do checklist
    PATCH  /documentos/checklist/item/{id}/toggle - Toggle cumprido
    DELETE /documentos/checklist/item/{id}  - Excluir item do checklist
"""
import uuid
from typing import List, Optional

from fastapi import Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session

from auth import get_current_approved_user
from config import Messages
from config.validation import validate_upload_complete_or_raise
from database import get_db
from logging_config import get_logger, log_action
from models import DocumentoLicitacao, Licitacao, Usuario
from models.documento import DocumentoStatus, DocumentoTipo
from repositories.documento_repository import checklist_repository, documento_repository
from routers.base import AuthenticatedRouter
from schemas import (
    ChecklistItemCreate,
    ChecklistItemResponse,
    ChecklistItemToggle,
    ChecklistItemUpdate,
    ChecklistResumoResponse,
    DocumentoCreate,
    DocumentoResumoResponse,
    DocumentoResponse,
    DocumentoUpdate,
    Mensagem,
    PaginatedDocumentoResponse,
)
from services.storage_service import get_storage, safe_delete_file
from utils.pagination import PaginationParams, paginate_query

logger = get_logger("routers.documentos")
router = AuthenticatedRouter(prefix="/documentos", tags=["Documentos"])


# ===================== Rotas fixas ANTES de /{id} =====================

@router.get("/vencendo", response_model=List[DocumentoResponse])
def get_vencendo(
    dias: int = Query(30, ge=1, le=365),
    current_user: Usuario = Depends(get_current_approved_user),
    db: Session = Depends(get_db),
):
    """Retorna documentos vencendo nos proximos N dias."""
    return documento_repository.get_vencendo(db, current_user.id, dias)


@router.get("/resumo", response_model=DocumentoResumoResponse)
def get_resumo(
    current_user: Usuario = Depends(get_current_approved_user),
    db: Session = Depends(get_db),
):
    """Retorna resumo de saude documental do usuario."""
    return DocumentoResumoResponse(**documento_repository.get_resumo(db, current_user.id))


@router.get("/licitacao/{licitacao_id}", response_model=List[DocumentoResponse])
def get_by_licitacao(
    licitacao_id: int,
    current_user: Usuario = Depends(get_current_approved_user),
    db: Session = Depends(get_db),
):
    """Retorna documentos de uma licitacao especifica."""
    # Validar que a licitacao pertence ao usuario
    licitacao = db.query(Licitacao).filter(
        Licitacao.id == licitacao_id,
        Licitacao.user_id == current_user.id,
    ).first()
    if not licitacao:
        raise HTTPException(status_code=404, detail=Messages.LICITACAO_NOT_FOUND)
    return documento_repository.get_by_licitacao(db, licitacao_id, current_user.id)


# ===================== Checklist (rotas fixas) =====================

@router.get("/checklist/{licitacao_id}", response_model=List[ChecklistItemResponse])
def get_checklist(
    licitacao_id: int,
    current_user: Usuario = Depends(get_current_approved_user),
    db: Session = Depends(get_db),
):
    """Retorna checklist de uma licitacao."""
    _validate_licitacao_ownership(db, licitacao_id, current_user.id)
    return checklist_repository.get_by_licitacao(db, licitacao_id, current_user.id)


@router.get("/checklist/{licitacao_id}/resumo", response_model=ChecklistResumoResponse)
def get_checklist_resumo(
    licitacao_id: int,
    current_user: Usuario = Depends(get_current_approved_user),
    db: Session = Depends(get_db),
):
    """Retorna resumo de progresso do checklist."""
    _validate_licitacao_ownership(db, licitacao_id, current_user.id)
    resumo = checklist_repository.get_resumo(db, licitacao_id, current_user.id)
    return ChecklistResumoResponse(**resumo)


@router.post(
    "/checklist/{licitacao_id}",
    response_model=List[ChecklistItemResponse],
    status_code=201,
)
def create_checklist_items(
    licitacao_id: int,
    itens: List[ChecklistItemCreate],
    current_user: Usuario = Depends(get_current_approved_user),
    db: Session = Depends(get_db),
):
    """Cria multiplos itens de checklist para uma licitacao."""
    _validate_licitacao_ownership(db, licitacao_id, current_user.id)
    itens_data = [item.model_dump() for item in itens]
    return checklist_repository.bulk_create(db, licitacao_id, current_user.id, itens_data)


@router.put("/checklist/item/{item_id}", response_model=ChecklistItemResponse)
def update_checklist_item(
    item_id: int,
    dados: ChecklistItemUpdate,
    current_user: Usuario = Depends(get_current_approved_user),
    db: Session = Depends(get_db),
):
    """Atualiza um item do checklist."""
    item = checklist_repository.get_item_for_user(db, item_id, current_user.id)
    if not item:
        raise HTTPException(status_code=404, detail=Messages.CHECKLIST_ITEM_NOT_FOUND)
    update_data = dados.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(item, field, value)
    db.commit()
    db.refresh(item)
    return item


@router.patch("/checklist/item/{item_id}/toggle", response_model=ChecklistItemResponse)
def toggle_checklist_item(
    item_id: int,
    dados: ChecklistItemToggle,
    current_user: Usuario = Depends(get_current_approved_user),
    db: Session = Depends(get_db),
):
    """Toggle cumprido de um item do checklist (+ vincular documento)."""
    item = checklist_repository.get_item_for_user(db, item_id, current_user.id)
    if not item:
        raise HTTPException(status_code=404, detail=Messages.CHECKLIST_ITEM_NOT_FOUND)
    item.cumprido = dados.cumprido
    if dados.documento_id is not None:
        item.documento_id = dados.documento_id
    db.commit()
    db.refresh(item)
    return item


@router.delete("/checklist/item/{item_id}", response_model=Mensagem)
def delete_checklist_item(
    item_id: int,
    current_user: Usuario = Depends(get_current_approved_user),
    db: Session = Depends(get_db),
):
    """Exclui um item do checklist."""
    item = checklist_repository.get_item_for_user(db, item_id, current_user.id)
    if not item:
        raise HTTPException(status_code=404, detail=Messages.CHECKLIST_ITEM_NOT_FOUND)
    db.delete(item)
    db.commit()
    return Mensagem(mensagem=Messages.CHECKLIST_ITEM_DELETED, sucesso=True)


# ===================== CRUD Documentos =====================

@router.get("/", response_model=PaginatedDocumentoResponse)
def list_documentos(
    pagination: PaginationParams = Depends(),
    tipo_documento: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    licitacao_id: Optional[int] = Query(None),
    busca: Optional[str] = Query(None),
    current_user: Usuario = Depends(get_current_approved_user),
    db: Session = Depends(get_db),
):
    """Lista documentos do usuario com filtros e paginacao."""
    query = documento_repository.get_filtered(
        db, current_user.id,
        tipo_documento=tipo_documento,
        status=status_filter,
        licitacao_id=licitacao_id,
        busca=busca,
    )
    return paginate_query(query, pagination, PaginatedDocumentoResponse)


@router.post("/upload", response_model=DocumentoResponse, status_code=201)
async def upload_documento(
    nome: str = Query(..., max_length=255),
    tipo_documento: str = Query(..., max_length=100),
    licitacao_id: Optional[int] = Query(None),
    data_emissao: Optional[str] = Query(None),
    data_validade: Optional[str] = Query(None),
    file: UploadFile = File(...),
    current_user: Usuario = Depends(get_current_approved_user),
    db: Session = Depends(get_db),
):
    """Upload de documento com arquivo."""
    # 1. Validar arquivo
    file_ext = await validate_upload_complete_or_raise(file)

    # 2. Validar tipo_documento
    if tipo_documento not in DocumentoTipo.ALL:
        raise HTTPException(
            status_code=400,
            detail=f"Tipo de documento invalido: {tipo_documento}",
        )

    # 3. Upload para storage
    filename = f"{uuid.uuid4()}{file_ext}"
    storage_path = f"users/{current_user.id}/documentos/{filename}"
    storage = get_storage()

    try:
        await file.seek(0)
        storage.upload(file.file, storage_path, file.content_type or "application/octet-stream")
    except Exception as e:
        logger.error(f"Erro no upload: {e}")
        raise HTTPException(status_code=500, detail=Messages.INTERNAL_ERROR)

    # 4. Determinar status inicial
    status_inicial = DocumentoStatus.NAO_APLICAVEL
    parsed_validade = None
    if data_validade:
        from datetime import datetime as dt, timezone as tz
        try:
            parsed_validade = dt.fromisoformat(data_validade)
            # Calcula status baseado na validade
            from config.base import DOCUMENT_EXPIRY_WARNING_DAYS
            agora = dt.now(tz.utc)
            if parsed_validade <= agora:
                status_inicial = DocumentoStatus.VENCIDO
            elif parsed_validade <= agora + __import__('datetime').timedelta(
                days=DOCUMENT_EXPIRY_WARNING_DAYS
            ):
                status_inicial = DocumentoStatus.VENCENDO
            else:
                status_inicial = DocumentoStatus.VALIDO
        except ValueError:
            pass  # Ignora data invalida, usa NAO_APLICAVEL
    elif tipo_documento in [
        DocumentoTipo.EDITAL, DocumentoTipo.PLANILHA, DocumentoTipo.OUTRO
    ]:
        status_inicial = DocumentoStatus.NAO_APLICAVEL
    else:
        status_inicial = DocumentoStatus.VALIDO

    # 5. Criar registro
    parsed_emissao = None
    if data_emissao:
        try:
            parsed_emissao = dt.fromisoformat(data_emissao)
        except (ValueError, NameError):
            pass

    documento = DocumentoLicitacao(
        user_id=current_user.id,
        licitacao_id=licitacao_id,
        nome=nome,
        tipo_documento=tipo_documento,
        arquivo_path=storage_path,
        tamanho_bytes=file.size,
        data_emissao=parsed_emissao,
        data_validade=parsed_validade,
        status=status_inicial,
    )
    documento = documento_repository.create(db, documento)

    log_action(
        logger, "documento_uploaded",
        user_id=current_user.id, resource_type="documento", resource_id=documento.id,
    )
    return documento


@router.post("/", response_model=DocumentoResponse, status_code=201)
def create_documento(
    dados: DocumentoCreate,
    current_user: Usuario = Depends(get_current_approved_user),
    db: Session = Depends(get_db),
):
    """Cria documento sem arquivo (metadados apenas)."""
    documento = DocumentoLicitacao(
        user_id=current_user.id,
        **dados.model_dump(),
    )
    documento = documento_repository.create(db, documento)
    log_action(
        logger, "documento_created",
        user_id=current_user.id, resource_type="documento", resource_id=documento.id,
    )
    return documento


@router.get("/{documento_id}", response_model=DocumentoResponse)
def get_documento(
    documento_id: int,
    current_user: Usuario = Depends(get_current_approved_user),
    db: Session = Depends(get_db),
):
    """Retorna detalhe de um documento."""
    doc = documento_repository.get_by_id_for_user(db, documento_id, current_user.id)
    if not doc:
        raise HTTPException(status_code=404, detail=Messages.DOCUMENTO_NOT_FOUND)
    return doc


@router.put("/{documento_id}", response_model=DocumentoResponse)
def update_documento(
    documento_id: int,
    dados: DocumentoUpdate,
    current_user: Usuario = Depends(get_current_approved_user),
    db: Session = Depends(get_db),
):
    """Atualiza metadados de um documento."""
    doc = documento_repository.get_by_id_for_user(db, documento_id, current_user.id)
    if not doc:
        raise HTTPException(status_code=404, detail=Messages.DOCUMENTO_NOT_FOUND)
    update_data = dados.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(doc, field, value)
    db.commit()
    db.refresh(doc)
    return doc


@router.delete("/{documento_id}", response_model=Mensagem)
def delete_documento(
    documento_id: int,
    current_user: Usuario = Depends(get_current_approved_user),
    db: Session = Depends(get_db),
):
    """Exclui um documento e seu arquivo."""
    doc = documento_repository.get_by_id_for_user(db, documento_id, current_user.id)
    if not doc:
        raise HTTPException(status_code=404, detail=Messages.DOCUMENTO_NOT_FOUND)

    # Excluir arquivo do storage se existir
    if doc.arquivo_path:
        safe_delete_file(doc.arquivo_path)

    db.delete(doc)
    db.commit()
    log_action(
        logger, "documento_deleted",
        user_id=current_user.id, resource_type="documento", resource_id=documento_id,
    )
    return Mensagem(mensagem=Messages.DOCUMENTO_DELETED, sucesso=True)


# ===================== Helpers =====================

def _validate_licitacao_ownership(db: Session, licitacao_id: int, user_id: int):
    """Valida que a licitacao pertence ao usuario."""
    licitacao = db.query(Licitacao).filter(
        Licitacao.id == licitacao_id,
        Licitacao.user_id == user_id,
    ).first()
    if not licitacao:
        raise HTTPException(status_code=404, detail=Messages.LICITACAO_NOT_FOUND)
```

**NOTA**: Rotas fixas (`/vencendo`, `/resumo`, `/licitacao/{id}`, `/checklist/{id}`, `/checklist/item/{id}`) devem vir ANTES de `/{documento_id}` no router para evitar conflito de path.

---

## Passo 8: main.py - Registrar router + rota HTML

### Modificar: `backend/main.py`

```python
# Adicionar import:
from routers import documentos

# Registrar router (apos lembretes e notificacoes):
app.include_router(documentos.router, prefix=API_PREFIX)

# Adicionar rota HTML:
@app.get("/documentos.html")
def serve_documentos():
    return FileResponse(os.path.join(frontend_path, "documentos.html"))
```

---

## Passo 9: Migracao Alembic

### Arquivo: `backend/alembic/versions/k1f5n46984mm_add_documentos_checklist.py`

```python
"""Adiciona tabelas documentos_licitacao e checklist_edital.

Revision ID: k1f5n46984mm
Revises: j0e4m35873ll
Create Date: 2026-02-11
"""
from alembic import op
import sqlalchemy as sa

revision = 'k1f5n46984mm'
down_revision = 'j0e4m35873ll'
branch_labels = None
depends_on = None


def _table_exists(table_name: str) -> bool:
    conn = op.get_bind()
    result = conn.execute(
        sa.text("SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = :t)"),
        {"t": table_name},
    )
    return bool(result.scalar())


def _index_exists(index_name: str) -> bool:
    conn = op.get_bind()
    result = conn.execute(
        sa.text("SELECT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = :i)"),
        {"i": index_name},
    )
    return bool(result.scalar())


def upgrade():
    # === documentos_licitacao ===
    if not _table_exists("documentos_licitacao"):
        op.create_table(
            "documentos_licitacao",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False),
            sa.Column("licitacao_id", sa.Integer(), sa.ForeignKey("licitacoes.id", ondelete="SET NULL"), nullable=True),
            sa.Column("nome", sa.String(255), nullable=False),
            sa.Column("tipo_documento", sa.String(100), nullable=False),
            sa.Column("arquivo_path", sa.String(500), nullable=True),
            sa.Column("tamanho_bytes", sa.Integer(), nullable=True),
            sa.Column("data_emissao", sa.DateTime(timezone=True), nullable=True),
            sa.Column("data_validade", sa.DateTime(timezone=True), nullable=True),
            sa.Column("status", sa.String(20), nullable=False, server_default="valido"),
            sa.Column("obrigatorio", sa.Boolean(), server_default="false"),
            sa.Column("observacoes", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        )

    # Indexes individuais
    for idx_name, columns in [
        ("ix_documentos_licitacao_id", ["id"]),
        ("ix_documentos_licitacao_user_id", ["user_id"]),
        ("ix_documentos_licitacao_licitacao_id", ["licitacao_id"]),
        ("ix_documentos_licitacao_data_validade", ["data_validade"]),
    ]:
        if not _index_exists(idx_name):
            op.create_index(idx_name, "documentos_licitacao", columns)

    # Indexes compostos
    for idx_name, columns in [
        ("ix_documentos_user_tipo", ["user_id", "tipo_documento"]),
        ("ix_documentos_user_status", ["user_id", "status"]),
        ("ix_documentos_user_licitacao", ["user_id", "licitacao_id"]),
        ("ix_documentos_validade_status", ["data_validade", "status"]),
    ]:
        if not _index_exists(idx_name):
            op.create_index(idx_name, "documentos_licitacao", columns)

    # === checklist_edital ===
    if not _table_exists("checklist_edital"):
        op.create_table(
            "checklist_edital",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("licitacao_id", sa.Integer(), sa.ForeignKey("licitacoes.id", ondelete="CASCADE"), nullable=False),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False),
            sa.Column("descricao", sa.Text(), nullable=False),
            sa.Column("tipo_documento", sa.String(100), nullable=True),
            sa.Column("obrigatorio", sa.Boolean(), server_default="true"),
            sa.Column("cumprido", sa.Boolean(), server_default="false"),
            sa.Column("documento_id", sa.Integer(), sa.ForeignKey("documentos_licitacao.id", ondelete="SET NULL"), nullable=True),
            sa.Column("observacao", sa.Text(), nullable=True),
            sa.Column("ordem", sa.Integer(), server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )

    for idx_name, columns in [
        ("ix_checklist_edital_id", ["id"]),
        ("ix_checklist_edital_licitacao_id", ["licitacao_id"]),
        ("ix_checklist_licitacao_ordem", ["licitacao_id", "ordem"]),
    ]:
        if not _index_exists(idx_name):
            op.create_index(idx_name, "checklist_edital", columns)


def downgrade():
    op.drop_table("checklist_edital")
    op.drop_table("documentos_licitacao")
```

---

## Passo 10: Frontend - Pagina de Documentos

### 10.1 `frontend/documentos.html`

Estrutura:
- Header nav (com todos os links existentes + "Documentos" ativo)
- alertContainer
- Header: "Gestao Documental" + resumo rapido (cards: validos/vencendo/vencidos)
- Filtros: tipo_documento (select), status (select), busca (input), licitacao (select)
- Tabela de documentos (nome, tipo, licitacao, validade, status, acoes)
- Botao "+ Novo Documento" (abre modal upload)
- Modal upload (file + metadados)
- Modal editar metadados

### 10.2 `frontend/js/documentos.js`

```javascript
const DocumentosModule = {
    documentos: [],
    filtros: { tipo: '', status: '', busca: '', licitacao_id: '' },
    paginaAtual: 1,

    async init() {
        await loadAuthConfig();
        this.setupEvents();
        this.carregarResumo();
        this.carregarDocumentos();
        this.carregarLicitacoesSelect();
    },

    setupEvents() {
        // Event delegation via data-action:
        // - 'upload-documento': abre modal upload
        // - 'salvar-upload': envia FormData via api.upload()
        // - 'editar-documento': abre modal edicao
        // - 'salvar-edicao': PUT metadados
        // - 'excluir-documento': confirmAction() + DELETE
        // - 'filtrar': debounce nos inputs
        // - 'ver-checklist': navega para checklist da licitacao
        // - 'paginar': muda pagina
    },

    async carregarResumo() {
        // GET /documentos/resumo
        // Renderiza cards: total, validos, vencendo (amarelo), vencidos (vermelho)
    },

    async carregarDocumentos() {
        // GET /documentos/?page={}&page_size=20&tipo_documento=...&status=...&busca=...
        // Renderiza tabela com Sanitize.escapeHtml()
    },

    async uploadDocumento(formData) {
        // POST /documentos/upload com FormData (multipart)
        // Usa fetch direto (nao api.post) para enviar arquivo
    },

    async editarDocumento(id, dados) {
        // PUT /documentos/{id}
    },

    async excluirDocumento(id) {
        // DELETE /documentos/{id}
    },

    renderTabela(items) {
        // Cada linha: nome, tipo (badge), licitacao (link), validade, status (badge colorido), acoes
        // Status badges:
        //   valido -> verde
        //   vencendo -> amarelo
        //   vencido -> vermelho
        //   nao_aplicavel -> cinza
    },

    renderResumoCards(resumo) {
        // 4 cards compactos no topo
    },
};

// === Checklist (mesma pagina, secao colapsavel por licitacao) ===

const ChecklistModule = {
    async carregarChecklist(licitacaoId) {
        // GET /documentos/checklist/{id}
    },

    async carregarResumo(licitacaoId) {
        // GET /documentos/checklist/{id}/resumo
        // Barra de progresso visual
    },

    async adicionarItens(licitacaoId, itens) {
        // POST /documentos/checklist/{id}
    },

    async toggleItem(itemId, cumprido, documentoId) {
        // PATCH /documentos/checklist/item/{id}/toggle
    },

    async editarItem(itemId, dados) {
        // PUT /documentos/checklist/item/{id}
    },

    async excluirItem(itemId) {
        // DELETE /documentos/checklist/item/{id}
    },

    renderChecklist(itens, resumo) {
        // Lista de itens com checkbox, descricao, tipo, documento vinculado
        // Barra de progresso: cumpridos/total (%)
        // Highlight obrigatorios pendentes em vermelho
    },
};

document.addEventListener('DOMContentLoaded', () => {
    DocumentosModule.init();
});
```

### 10.3 `frontend/css/documentos.css`

```css
/* Resumo cards */
.doc-resumo { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 1rem; margin-bottom: 1.5rem; }
.doc-resumo-card { padding: 1rem; border-radius: var(--radius-md); text-align: center; background: var(--bg-card); border: 1px solid var(--border); }
.doc-resumo-card .count { font-size: 1.5rem; font-weight: 700; }
.doc-resumo-card.vencendo { border-left: 3px solid var(--warning); }
.doc-resumo-card.vencido { border-left: 3px solid var(--error); }

/* Status badges */
.badge-valido { background: var(--success-bg); color: var(--success); }
.badge-vencendo { background: var(--warning-bg); color: var(--warning); }
.badge-vencido { background: var(--error-bg); color: var(--error); }
.badge-nao-aplicavel { background: var(--bg-secondary); color: var(--text-secondary); }

/* Tabela documentos */
.doc-table { width: 100%; border-collapse: collapse; }
.doc-table th, .doc-table td { padding: 0.75rem; text-align: left; border-bottom: 1px solid var(--border); }
.doc-table tr:hover { background: var(--bg-secondary); }
.doc-validade-proxima { color: var(--warning); font-weight: 500; }
.doc-validade-vencida { color: var(--error); font-weight: 500; }

/* Checklist */
.checklist-progress { width: 100%; height: 8px; background: var(--bg-secondary); border-radius: 4px; overflow: hidden; margin-bottom: 1rem; }
.checklist-progress-bar { height: 100%; background: var(--success); transition: width 0.3s; }
.checklist-item { display: flex; align-items: flex-start; gap: 0.75rem; padding: 0.75rem; border-bottom: 1px solid var(--border); }
.checklist-item.pendente-obrigatorio { background: rgba(239, 68, 68, 0.05); }
.checklist-item input[type="checkbox"] { margin-top: 0.25rem; }
.checklist-item .doc-link { font-size: 0.85rem; color: var(--primary); }

/* Upload area */
.upload-area { border: 2px dashed var(--border); border-radius: var(--radius-md); padding: 2rem; text-align: center; cursor: pointer; transition: border-color 0.2s; }
.upload-area:hover, .upload-area.dragover { border-color: var(--primary); background: rgba(245, 158, 11, 0.05); }
```

### 10.4 Atualizar HTMLs existentes

Adicionar link "Documentos" na nav de todas as paginas (entre "Calendario" e "Admin"):
```html
<a href="documentos.html" class="nav-link">Documentos</a>
```

Paginas a atualizar:
- `dashboard.html`
- `atestados.html`
- `analises.html`
- `licitacoes.html`
- `calendario.html`
- `admin.html`
- `perfil.html`

---

## Passo 11: Testes

### 11.1 `tests/test_schemas_documento.py`

Testes de validacao dos schemas:
- DocumentoCreate com tipo valido/invalido
- DocumentoUpdate com campos opcionais
- ChecklistItemCreate com validacoes
- ChecklistItemToggle
- Testar que tipos invalidos geram ValueError
- Testar campos obrigatorios (nome, tipo_documento, descricao)

**Estimativa**: ~25 testes

### 11.2 `tests/test_documento_repository.py`

Testes do repositorio:
- CRUD basico: create, get_by_id_for_user, delete
- get_filtered com cada combinacao de filtros (tipo, status, licitacao, busca)
- get_by_licitacao
- get_vencendo (com documentos dentro e fora do range)
- get_vencidos
- get_resumo (contagens corretas)
- atualizar_status_validade (transicoes: valido->vencendo, vencendo->vencido, vencido->valido)
- ChecklistRepository: get_by_licitacao, get_item_for_user, get_resumo, bulk_create

**Estimativa**: ~20 testes

### 11.3 `tests/test_documentos_router.py`

Testes dos endpoints:
- GET / (listagem paginada, filtros)
- GET /vencendo (com e sem documentos vencendo)
- GET /resumo
- GET /{id} (sucesso + 404)
- POST /upload (multipart upload com arquivo)
- POST / (sem arquivo)
- PUT /{id} (update parcial)
- DELETE /{id} (sucesso + 404 + verificar exclusao arquivo)
- GET /licitacao/{id} (documentos de licitacao)
- GET /checklist/{id} (checklist de licitacao)
- GET /checklist/{id}/resumo
- POST /checklist/{id} (bulk create)
- PUT /checklist/item/{id}
- PATCH /checklist/item/{id}/toggle
- DELETE /checklist/item/{id}
- Testar autenticacao (401 sem token)
- Testar ownership (404 para recurso de outro usuario)

**Estimativa**: ~25 testes

### 11.4 `tests/test_document_checker.py`

Testes do servico de verificacao:
- Documentos valido->vencendo quando data_validade <= 30 dias
- Documentos vencendo->vencido quando data_validade <= agora
- Documentos vencido->valido quando data_validade atualizada para futuro
- Notificacao criada para documento vencendo (sem duplicata)
- Sem notificacao duplicada se ja notificado

**Estimativa**: ~8 testes

**Total estimado de novos testes**: ~78

---

## Resumo de Arquivos

### Novos arquivos (criar):
| # | Arquivo | Descricao |
|---|---------|-----------|
| 1 | `backend/models/documento.py` | DocumentoLicitacao, ChecklistEdital, DocumentoTipo, DocumentoStatus |
| 2 | `backend/schemas/documento.py` | Todos os schemas de documentos e checklist |
| 3 | `backend/repositories/documento_repository.py` | DocumentoLicitacaoRepository, ChecklistRepository |
| 4 | `backend/services/notification/document_checker.py` | DocumentExpiryChecker |
| 5 | `backend/routers/documentos.py` | 15 endpoints |
| 6 | `backend/alembic/versions/k1f5n46984mm_add_documentos_checklist.py` | Migracao 2 tabelas |
| 7 | `frontend/documentos.html` | Pagina de gestao documental |
| 8 | `frontend/js/documentos.js` | Logica de documentos + checklist |
| 9 | `frontend/css/documentos.css` | Estilos da pagina |
| 10 | `tests/test_schemas_documento.py` | Testes de schema (~25) |
| 11 | `tests/test_documento_repository.py` | Testes de repository (~20) |
| 12 | `tests/test_documentos_router.py` | Testes de router (~25) |
| 13 | `tests/test_document_checker.py` | Testes do servico (~8) |

### Arquivos existentes a modificar:
| # | Arquivo | Mudanca |
|---|---------|---------|
| 1 | `backend/models/__init__.py` | Re-exportar DocumentoLicitacao, ChecklistEdital, DocumentoTipo, DocumentoStatus |
| 2 | `backend/schemas/__init__.py` | Re-exportar todos os novos schemas |
| 3 | `backend/config/base.py` | Adicionar DOCUMENT_EXPIRY_CHECK_INTERVAL, DOCUMENT_EXPIRY_WARNING_DAYS |
| 4 | `backend/config/__init__.py` | Re-exportar novas constantes |
| 5 | `backend/config/messages.py` | Adicionar 7 novas constantes (documento + checklist) |
| 6 | `backend/main.py` | Registrar router documentos + rota HTML |
| 7 | `backend/services/notification/reminder_scheduler.py` | Integrar document_checker no loop |
| 8 | `frontend/dashboard.html` | + link Documentos na nav |
| 9 | `frontend/atestados.html` | + link Documentos na nav |
| 10 | `frontend/analises.html` | + link Documentos na nav |
| 11 | `frontend/licitacoes.html` | + link Documentos na nav |
| 12 | `frontend/calendario.html` | + link Documentos na nav |
| 13 | `frontend/admin.html` | + link Documentos na nav |
| 14 | `frontend/perfil.html` | + link Documentos na nav |

---

## Decisoes Tecnicas

| Decisao | Escolha | Justificativa |
|---------|---------|---------------|
| Upload endpoint | Separado do CRUD (POST /upload) | Multipart precisa de UploadFile, metadados via query params; CRUD normal usa JSON body |
| Storage path | `users/{user_id}/documentos/{uuid}` | Mesmo padrao de atestados, isola por usuario |
| Status automatico | DocumentExpiryChecker no ReminderScheduler | Reutiliza infra existente de M2, sem novo worker |
| Notificacao anti-spam | Verifica referencia_tipo+referencia_id | Evita notificar sobre mesmo documento repetidamente |
| Checklist por licitacao | Tabela separada com FK documento | Permite vincular documento ao item e rastrear progresso |
| Checklist bulk create | POST recebe lista de itens | Pratico para importar checklist completo de edital |
| Tipos de documento | 15 tipos pre-definidos + "outro" | Cobre documentos mais comuns em licitacoes brasileiras |
| Documento sem licitacao | licitacao_id nullable | Permite acervo geral de documentos (certidoes recorrentes) |

---

## Verificacao Final

1. **Testes unitarios**: `python -m pytest tests/ -x -q --ignore=tests/integration` - todos passam (~1187 = 1109 + ~78 novos)
2. **Migracao**: `alembic upgrade head` sem erros (4 migracoes: base + M1 + M2 + M4)
3. **Backend**: `uvicorn main:app --reload` inicia sem erros
4. **Swagger**: Abrir `/docs` e verificar 15 novos endpoints (/documentos)
5. **Frontend**: Abrir `/documentos.html`, upload documento, verificar validade, checklist
6. **Notificacoes**: Verificar que documentos vencendo geram notificacao automatica
7. **Backward compat**: Todas as paginas existentes continuam funcionando
8. **CI**: `ruff check . && mypy . && python -m pytest tests/ -x -q --ignore=tests/integration`
