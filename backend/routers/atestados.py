import os
import uuid
import tempfile
from fastapi import Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
from typing import Union

from database import get_db
from models import Usuario, Atestado
from repositories.atestado_repository import atestado_repository
from schemas import (
    AtestadoCreate, AtestadoUpdate, AtestadoServicosUpdate, AtestadoResponse,
    Mensagem, JobResponse, PaginatedAtestadoResponse
)
from auth import get_current_approved_user
from services.atestado import ordenar_servicos, salvar_atestado_processado
from services.processing_mode import is_serverless
from config import Messages, ALLOWED_DOCUMENT_EXTENSIONS
from utils.pagination import PaginationParams, paginate_query
from utils.validation import validate_upload_complete_or_raise
from utils.router_helpers import (
    safe_delete_file,
    save_upload_file_to_storage,
    file_exists_in_storage,
    save_temp_file_from_storage
)
from utils.http_helpers import get_user_resource_or_404
from routers.base import AuthenticatedRouter

from logging_config import get_logger
from utils import handle_exception

logger = get_logger('routers.atestados')


# Registrar callback apenas em modo assíncrono
if not is_serverless():
    from services.processing_queue import processing_queue
    processing_queue.register_callback("atestado", salvar_atestado_processado)

router = AuthenticatedRouter(prefix="/atestados", tags=["Atestados"])


@router.get("/", response_model=PaginatedAtestadoResponse)
def listar_atestados(
    pagination: PaginationParams = Depends(),
    current_user: Usuario = Depends(get_current_approved_user),
    db: Session = Depends(get_db)
) -> PaginatedAtestadoResponse:
    """Lista todos os atestados do usuário logado com paginação."""
    query = db.query(Atestado).filter(
        Atestado.user_id == current_user.id
    ).order_by(Atestado.created_at.desc())

    return paginate_query(query, pagination, PaginatedAtestadoResponse)


@router.get("/{atestado_id}", response_model=AtestadoResponse)
def obter_atestado(
    atestado_id: int,
    current_user: Usuario = Depends(get_current_approved_user),
    db: Session = Depends(get_db)
) -> AtestadoResponse:
    """Obtém um atestado específico."""
    atestado = get_user_resource_or_404(
        db, Atestado, atestado_id, current_user.id, Messages.ATESTADO_NOT_FOUND
    )
    return atestado


@router.post("/", response_model=AtestadoResponse)
def criar_atestado(
    atestado: AtestadoCreate,
    current_user: Usuario = Depends(get_current_approved_user),
    db: Session = Depends(get_db)
) -> AtestadoResponse:
    """Cria um novo atestado manualmente (sem upload de arquivo)."""
    novo_atestado = Atestado(
        user_id=current_user.id,
        descricao_servico=atestado.descricao_servico,
        quantidade=atestado.quantidade,
        unidade=atestado.unidade,
        contratante=atestado.contratante,
        data_emissao=atestado.data_emissao
    )
    db.add(novo_atestado)
    db.commit()
    db.refresh(novo_atestado)
    return novo_atestado


@router.post("/upload", response_model=Union[JobResponse, AtestadoResponse])
async def upload_atestado(
    file: UploadFile = File(...),
    current_user: Usuario = Depends(get_current_approved_user),
    db: Session = Depends(get_db)
) -> Union[JobResponse, AtestadoResponse]:
    """
    Faz upload de um PDF/imagem de atestado para processamento.

    Em ambiente serverless (Vercel): processa síncronamente e retorna AtestadoResponse.
    Em ambiente tradicional: enfileira e retorna JobResponse com job_id.
    """
    # Validar arquivo (extensão, tamanho e MIME type)
    file_ext = await validate_upload_complete_or_raise(file, ALLOWED_DOCUMENT_EXTENSIONS)

    # Gerar nome único para o arquivo
    filename = f"{uuid.uuid4()}{file_ext}"
    original_filename = file.filename or "documento"

    # Determinar content type
    content_type = file.content_type or "application/octet-stream"

    # Salvar arquivo no Storage (Supabase ou local)
    storage_path = save_upload_file_to_storage(
        file=file,
        user_id=current_user.id,
        subfolder="atestados",
        filename=filename,
        content_type=content_type
    )

    try:
        if is_serverless():
            # Modo serverless: processar síncronamente
            return await _process_sync(db, current_user, storage_path, original_filename, file_ext)
        else:
            # Modo tradicional: enfileirar
            return _enqueue_processing(current_user, storage_path, original_filename)

    except Exception as e:
        safe_delete_file(storage_path)
        raise handle_exception(e, logger, "ao processar atestado")


async def _process_sync(
    db: Session,
    user: Usuario,
    storage_path: str,
    original_filename: str,
    file_ext: str = ".pdf"
) -> AtestadoResponse:
    """Processa atestado de forma síncrona (serverless)."""
    from services.sync_processor import get_sync_processor

    # Baixar arquivo do storage para arquivo temporário
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=file_ext)
    temp_path = temp_file.name
    temp_file.close()

    try:
        if not save_temp_file_from_storage(storage_path, temp_path):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Erro ao baixar arquivo do storage"
            )

        processor = get_sync_processor()
        result = processor.process_atestado(
            db=db,
            user_id=user.id,
            file_path=temp_path,
            original_filename=original_filename,
            storage_path=storage_path  # Passar o path do storage para salvar no banco
        )

        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=result.get("error", "Erro ao processar documento")
            )

        # Buscar atestado criado usando repository
        atestado = atestado_repository.get_by_id(db, result["atestado_id"])
        if atestado is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Erro interno: atestado não encontrado após processamento"
            )
        return atestado

    finally:
        # Limpar arquivo temporário
        if os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except OSError:
                pass


def _enqueue_processing(
    user: Usuario,
    storage_path: str,
    original_filename: str
) -> JobResponse:
    """Enfileira processamento assíncrono (tradicional)."""
    from services.processing_queue import processing_queue

    job_id = str(uuid.uuid4())
    processing_queue.add_job(
        job_id=job_id,
        user_id=user.id,
        file_path=storage_path,
        job_type="atestado",
        original_filename=original_filename,
        callback=salvar_atestado_processado
    )
    return JobResponse(
        mensagem=Messages.UPLOAD_SUCCESS,
        sucesso=True,
        job_id=job_id
    )


@router.post("/{atestado_id}/reprocess", response_model=Union[JobResponse, AtestadoResponse])
async def reprocessar_atestado(
    atestado_id: int,
    current_user: Usuario = Depends(get_current_approved_user),
    db: Session = Depends(get_db)
) -> Union[JobResponse, AtestadoResponse]:
    """Reprocessa um atestado existente usando o arquivo salvo."""
    atestado = get_user_resource_or_404(
        db, Atestado, atestado_id, current_user.id, Messages.ATESTADO_NOT_FOUND
    )

    # Verificar se há arquivo associado
    if not atestado.arquivo_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=Messages.ATESTADO_FILE_NOT_FOUND
        )

    # Verificar se arquivo existe no storage
    if not file_exists_in_storage(atestado.arquivo_path):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=Messages.ATESTADO_FILE_NOT_FOUND
        )

    try:
        original_name = os.path.basename(atestado.arquivo_path)
        file_ext = os.path.splitext(atestado.arquivo_path)[1] or ".pdf"

        if is_serverless():
            return await _process_sync(db, current_user, atestado.arquivo_path, original_name, file_ext)
        else:
            return _enqueue_processing(current_user, atestado.arquivo_path, original_name)

    except HTTPException:
        raise
    except Exception as e:
        raise handle_exception(e, logger, f"ao reprocessar atestado {atestado_id}")


@router.put("/{atestado_id}", response_model=AtestadoResponse)
def atualizar_atestado(
    atestado_id: int,
    dados: AtestadoUpdate,
    current_user: Usuario = Depends(get_current_approved_user),
    db: Session = Depends(get_db)
) -> AtestadoResponse:
    """Atualiza um atestado existente."""
    atestado = get_user_resource_or_404(
        db, Atestado, atestado_id, current_user.id, Messages.ATESTADO_NOT_FOUND
    )

    # Atualizar campos fornecidos
    if dados.descricao_servico is not None:
        atestado.descricao_servico = dados.descricao_servico
    if dados.quantidade is not None:
        atestado.quantidade = dados.quantidade
    if dados.unidade is not None:
        atestado.unidade = dados.unidade
    if dados.contratante is not None:
        atestado.contratante = dados.contratante
    if dados.data_emissao is not None:
        atestado.data_emissao = dados.data_emissao

    db.commit()
    db.refresh(atestado)
    return atestado


@router.patch("/{atestado_id}/servicos", response_model=AtestadoResponse)
def atualizar_servicos(
    atestado_id: int,
    dados: AtestadoServicosUpdate,
    current_user: Usuario = Depends(get_current_approved_user),
    db: Session = Depends(get_db)
) -> AtestadoResponse:
    """Atualiza apenas os serviços de um atestado (usado para excluir itens individuais)."""
    atestado = get_user_resource_or_404(
        db, Atestado, atestado_id, current_user.id, Messages.ATESTADO_NOT_FOUND
    )

    # Converter ServicoAtestado para dict e ordenar por item
    servicos_dict = [s.model_dump() for s in dados.servicos_json]
    atestado.servicos_json = ordenar_servicos(servicos_dict)

    db.commit()
    db.refresh(atestado)
    return atestado


@router.delete("/{atestado_id}", response_model=Mensagem)
def excluir_atestado(
    atestado_id: int,
    current_user: Usuario = Depends(get_current_approved_user),
    db: Session = Depends(get_db)
) -> Mensagem:
    """Exclui um atestado."""
    atestado = get_user_resource_or_404(
        db, Atestado, atestado_id, current_user.id, Messages.ATESTADO_NOT_FOUND
    )

    # Remover arquivo do storage se existir
    if atestado.arquivo_path:
        safe_delete_file(atestado.arquivo_path)

    db.delete(atestado)
    db.commit()

    return Mensagem(
        mensagem=Messages.ATESTADO_DELETED,
        sucesso=True
    )
