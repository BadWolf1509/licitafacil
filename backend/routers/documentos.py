"""
Router para gestão documental.

Endpoints:
    GET    /documentos/                          - Listar documentos (paginado, filtros)
    GET    /documentos/vencendo                  - Documentos vencendo em N dias
    GET    /documentos/resumo                    - Resumo de saúde documental
    GET    /documentos/licitacao/{id}            - Documentos de uma licitação
    GET    /documentos/checklist/{id}            - Checklist de uma licitação
    GET    /documentos/checklist/{id}/resumo     - Resumo do checklist
    POST   /documentos/checklist/{id}            - Criar itens de checklist
    PUT    /documentos/checklist/item/{id}       - Atualizar item do checklist
    PATCH  /documentos/checklist/item/{id}/toggle - Toggle cumprido
    DELETE /documentos/checklist/item/{id}       - Excluir item do checklist
    GET    /documentos/{id}                      - Detalhe do documento
    POST   /documentos/upload                    - Upload de documento
    POST   /documentos/                          - Criar documento (sem arquivo)
    PUT    /documentos/{id}                      - Atualizar metadados
    DELETE /documentos/{id}                      - Excluir documento
"""
import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session

from auth import get_current_approved_user
from config import Messages
from config.base import DOCUMENT_EXPIRY_WARNING_DAYS
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
    DocumentoResponse,
    DocumentoResumoResponse,
    DocumentoUpdate,
    Mensagem,
    PaginatedDocumentoResponse,
)
from services.storage_service import get_storage
from utils.pagination import PaginationParams, paginate_query
from utils.router_helpers import safe_delete_file
from utils.validation import validate_upload_complete_or_raise

logger = get_logger("routers.documentos")
router = AuthenticatedRouter(prefix="/documentos", tags=["Documentos"])


# ===================== Rotas fixas ANTES de /{id} =====================


@router.get("/vencendo", response_model=List[DocumentoResponse])
def get_vencendo(
    dias: int = Query(30, ge=1, le=365),
    current_user: Usuario = Depends(get_current_approved_user),
    db: Session = Depends(get_db),
):
    """Retorna documentos vencendo nos próximos N dias."""
    return documento_repository.get_vencendo(db, current_user.id, dias)


@router.get("/resumo", response_model=DocumentoResumoResponse)
def get_resumo(
    current_user: Usuario = Depends(get_current_approved_user),
    db: Session = Depends(get_db),
):
    """Retorna resumo de saúde documental do usuário."""
    resumo = documento_repository.get_resumo(db, current_user.id)
    return DocumentoResumoResponse(**resumo)


@router.get("/licitacao/{licitacao_id}", response_model=List[DocumentoResponse])
def get_by_licitacao(
    licitacao_id: int,
    current_user: Usuario = Depends(get_current_approved_user),
    db: Session = Depends(get_db),
):
    """Retorna documentos de uma licitação específica."""
    _validate_licitacao_ownership(db, licitacao_id, current_user.id)
    return documento_repository.get_by_licitacao(db, licitacao_id, current_user.id)


# ===================== Checklist (rotas fixas) =====================


@router.get("/checklist/{licitacao_id}", response_model=List[ChecklistItemResponse])
def get_checklist(
    licitacao_id: int,
    current_user: Usuario = Depends(get_current_approved_user),
    db: Session = Depends(get_db),
):
    """Retorna checklist de uma licitação."""
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
    """Cria múltiplos itens de checklist para uma licitação."""
    _validate_licitacao_ownership(db, licitacao_id, current_user.id)
    itens_data = [item.model_dump() for item in itens]
    return checklist_repository.bulk_create_items(
        db, licitacao_id, current_user.id, itens_data,
    )


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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=Messages.CHECKLIST_ITEM_NOT_FOUND,
        )
    update_data = dados.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(item, field, value)
    db.commit()
    db.refresh(item)
    return item


@router.patch(
    "/checklist/item/{item_id}/toggle", response_model=ChecklistItemResponse,
)
def toggle_checklist_item(
    item_id: int,
    dados: ChecklistItemToggle,
    current_user: Usuario = Depends(get_current_approved_user),
    db: Session = Depends(get_db),
):
    """Toggle cumprido de um item do checklist."""
    item = checklist_repository.get_item_for_user(db, item_id, current_user.id)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=Messages.CHECKLIST_ITEM_NOT_FOUND,
        )
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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=Messages.CHECKLIST_ITEM_NOT_FOUND,
        )
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
    """Lista documentos do usuário com filtros e paginação."""
    query = documento_repository.get_filtered(
        db,
        current_user.id,
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
    # Validar arquivo
    file_ext = await validate_upload_complete_or_raise(file)

    # Validar tipo_documento
    if tipo_documento not in DocumentoTipo.ALL:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Tipo de documento inválido: {tipo_documento}",
        )

    # Upload para storage
    filename = f"{uuid.uuid4()}{file_ext}"
    storage_path = f"users/{current_user.id}/documentos/{filename}"
    storage = get_storage()

    try:
        await file.seek(0)
        storage.upload(
            file.file, storage_path, file.content_type or "application/octet-stream",
        )
    except Exception as e:
        logger.error(f"Erro no upload: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=Messages.INTERNAL_ERROR,
        )

    # Determinar status inicial baseado na validade
    status_inicial = _calcular_status_inicial(tipo_documento, data_validade)

    # Parsear datas
    parsed_validade = _parse_datetime(data_validade)
    parsed_emissao = _parse_datetime(data_emissao)

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
        logger,
        "documento_uploaded",
        user_id=current_user.id,
        resource_type="documento",
        resource_id=documento.id,
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
        logger,
        "documento_created",
        user_id=current_user.id,
        resource_type="documento",
        resource_id=documento.id,
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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=Messages.DOCUMENTO_NOT_FOUND,
        )
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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=Messages.DOCUMENTO_NOT_FOUND,
        )
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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=Messages.DOCUMENTO_NOT_FOUND,
        )

    if doc.arquivo_path:
        safe_delete_file(doc.arquivo_path)

    db.delete(doc)
    db.commit()
    log_action(
        logger,
        "documento_deleted",
        user_id=current_user.id,
        resource_type="documento",
        resource_id=documento_id,
    )
    return Mensagem(mensagem=Messages.DOCUMENTO_DELETED, sucesso=True)


# ===================== Helpers =====================


def _validate_licitacao_ownership(
    db: Session, licitacao_id: int, user_id: int,
) -> None:
    """Valida que a licitação pertence ao usuário."""
    licitacao = (
        db.query(Licitacao)
        .filter(Licitacao.id == licitacao_id, Licitacao.user_id == user_id)
        .first()
    )
    if not licitacao:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=Messages.LICITACAO_NOT_FOUND,
        )


def _parse_datetime(value: Optional[str]) -> Optional[datetime]:
    """Parseia string ISO para datetime, retorna None se inválido."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _calcular_status_inicial(
    tipo_documento: str, data_validade_str: Optional[str],
) -> str:
    """Calcula status inicial baseado no tipo e na data de validade."""
    if not data_validade_str:
        # Documentos sem validade
        if tipo_documento in [DocumentoTipo.EDITAL, DocumentoTipo.PLANILHA, DocumentoTipo.OUTRO]:
            return DocumentoStatus.NAO_APLICAVEL
        return DocumentoStatus.VALIDO

    try:
        data_validade = datetime.fromisoformat(data_validade_str)
    except ValueError:
        return DocumentoStatus.VALIDO

    agora = datetime.now(timezone.utc)
    # Se data_validade é naive, assume UTC
    if data_validade.tzinfo is None:
        data_validade = data_validade.replace(tzinfo=timezone.utc)

    if data_validade <= agora:
        return DocumentoStatus.VENCIDO
    if data_validade <= agora + timedelta(days=DOCUMENT_EXPIRY_WARNING_DAYS):
        return DocumentoStatus.VENCENDO
    return DocumentoStatus.VALIDO
