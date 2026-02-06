import os
import uuid
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
from utils.file_helpers import cleanup_temp_file, temp_file_from_storage
from routers.base import AuthenticatedRouter

from logging_config import get_logger, log_action
from utils import handle_exception

logger = get_logger('routers.atestados')


# Registrar callback apenas em modo assíncrono
if not is_serverless():
    from services.processing_queue import processing_queue
    processing_queue.register_callback("atestado", salvar_atestado_processado)

router = AuthenticatedRouter(prefix="/atestados", tags=["Atestados"])


@router.get(
    "/",
    response_model=PaginatedAtestadoResponse,
    summary="Listar atestados",
    responses={
        200: {"description": "Lista de atestados retornada"},
        401: {"description": "Não autenticado"},
        403: {"description": "Usuário não aprovado"},
    }
)
def list_atestados(
    pagination: PaginationParams = Depends(),
    current_user: Usuario = Depends(get_current_approved_user),
    db: Session = Depends(get_db)
) -> PaginatedAtestadoResponse:
    """
    Lista todos os atestados do usuário logado com paginação.

    Ordenados do mais recente para o mais antigo.

    **Parâmetros de paginação:**
    - `page`: Número da página (padrão: 1)
    - `per_page`: Itens por página (padrão: 10, máximo: 100)
    """
    query = db.query(Atestado).filter(
        Atestado.user_id == current_user.id
    ).order_by(Atestado.created_at.desc())

    return paginate_query(query, pagination, PaginatedAtestadoResponse)


@router.get(
    "/{atestado_id}",
    response_model=AtestadoResponse,
    summary="Obter um atestado",
    responses={
        200: {"description": "Atestado retornado"},
        401: {"description": "Não autenticado"},
        403: {"description": "Usuário não aprovado"},
        404: {"description": "Atestado não encontrado"},
    }
)
def get_atestado(
    atestado_id: int,
    current_user: Usuario = Depends(get_current_approved_user),
    db: Session = Depends(get_db)
) -> AtestadoResponse:
    """
    Obtém um atestado específico pelo ID.

    Retorna todos os dados do atestado incluindo serviços extraídos.
    """
    atestado = get_user_resource_or_404(
        db, Atestado, atestado_id, current_user.id, Messages.ATESTADO_NOT_FOUND
    )
    return atestado


@router.post(
    "/",
    response_model=AtestadoResponse,
    summary="Criar atestado manual",
    responses={
        200: {"description": "Atestado criado com sucesso"},
        401: {"description": "Não autenticado"},
        403: {"description": "Usuário não aprovado"},
        422: {"description": "Dados inválidos"},
    }
)
def create_atestado(
    atestado: AtestadoCreate,
    current_user: Usuario = Depends(get_current_approved_user),
    db: Session = Depends(get_db)
) -> AtestadoResponse:
    """
    Cria um novo atestado manualmente (sem upload de arquivo).

    Use quando quiser cadastrar um atestado sem processar documento.
    Os serviços podem ser adicionados posteriormente via PATCH.
    """
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

    log_action(
        logger, "atestado_created",
        user_id=current_user.id,
        resource_type="atestado",
        resource_id=novo_atestado.id,
        method="manual"
    )
    return novo_atestado


@router.post(
    "/upload",
    response_model=Union[JobResponse, AtestadoResponse],
    summary="Upload de atestado",
    responses={
        200: {"description": "Atestado processado (modo síncrono)"},
        202: {"description": "Job criado para processamento (modo assíncrono)"},
        400: {"description": "Arquivo inválido (extensão, tamanho ou formato)"},
        401: {"description": "Não autenticado"},
        403: {"description": "Usuário não aprovado"},
        413: {"description": "Arquivo muito grande (máx 50MB)"},
        422: {"description": "Erro ao processar documento"},
    }
)
async def upload_atestado(
    file: UploadFile = File(...),
    current_user: Usuario = Depends(get_current_approved_user),
    db: Session = Depends(get_db)
) -> Union[JobResponse, AtestadoResponse]:
    """
    Faz upload de um PDF/imagem de atestado para processamento.

    O documento é analisado automaticamente usando OCR e IA para
    extrair informações de serviços executados.

    **Formatos aceitos:** PDF, PNG, JPG, JPEG, TIFF, BMP, GIF, WEBP

    **Tamanho máximo:** 50MB

    **Comportamento:**
    - Serverless (Vercel): Processa síncronamente e retorna AtestadoResponse
    - Tradicional: Enfileira e retorna JobResponse com job_id
    """
    # Validar arquivo (extensão, tamanho e MIME type)
    file_ext = await validate_upload_complete_or_raise(file, ALLOWED_DOCUMENT_EXTENSIONS)

    # Gerar nome único para o arquivo
    filename = f"{uuid.uuid4()}{file_ext}"
    original_filename = file.filename or "documento"

    # Determinar content type
    content_type = file.content_type or "application/octet-stream"

    log_action(
        logger, "upload_start",
        user_id=current_user.id,
        resource_type="atestado",
        filename=original_filename,
        size_bytes=file.size
    )

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
            sync_result = await _process_sync(db, current_user, storage_path, original_filename, file_ext)
            log_action(
                logger, "upload_complete",
                user_id=current_user.id,
                resource_type="atestado",
                resource_id=sync_result.id,
                mode="sync"
            )
            return sync_result
        else:
            # Modo tradicional: enfileirar
            async_result = _enqueue_processing(current_user, storage_path, original_filename)
            log_action(
                logger, "upload_queued",
                user_id=current_user.id,
                resource_type="atestado",
                job_id=async_result.job_id,
                mode="async"
            )
            return async_result

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

    with temp_file_from_storage(storage_path, save_temp_file_from_storage, suffix=file_ext) as temp_path:
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


@router.post(
    "/{atestado_id}/reprocess",
    response_model=Union[JobResponse, AtestadoResponse],
    summary="Reprocessar atestado",
    responses={
        200: {"description": "Atestado reprocessado"},
        400: {"description": "Arquivo não encontrado"},
        401: {"description": "Não autenticado"},
        403: {"description": "Usuário não aprovado"},
        404: {"description": "Atestado não encontrado"},
    }
)
async def reprocess_atestado(
    atestado_id: int,
    current_user: Usuario = Depends(get_current_approved_user),
    db: Session = Depends(get_db)
) -> Union[JobResponse, AtestadoResponse]:
    """
    Reprocessa um atestado existente usando o arquivo salvo.

    Útil quando o modelo de IA foi atualizado ou para corrigir
    extrações que falharam parcialmente.
    """
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


@router.put(
    "/{atestado_id}",
    response_model=AtestadoResponse,
    summary="Atualizar atestado",
    responses={
        200: {"description": "Atestado atualizado"},
        401: {"description": "Não autenticado"},
        403: {"description": "Usuário não aprovado"},
        404: {"description": "Atestado não encontrado"},
    }
)
def update_atestado(
    atestado_id: int,
    dados: AtestadoUpdate,
    current_user: Usuario = Depends(get_current_approved_user),
    db: Session = Depends(get_db)
) -> AtestadoResponse:
    """
    Atualiza os dados de um atestado existente.

    Permite editar descrição, quantidade, unidade, contratante e data de emissão.
    """
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


@router.patch(
    "/{atestado_id}/servicos",
    response_model=AtestadoResponse,
    summary="Atualizar serviços do atestado",
    responses={
        200: {"description": "Serviços atualizados"},
        401: {"description": "Não autenticado"},
        403: {"description": "Usuário não aprovado"},
        404: {"description": "Atestado não encontrado"},
    }
)
def update_atestado_services(
    atestado_id: int,
    dados: AtestadoServicosUpdate,
    current_user: Usuario = Depends(get_current_approved_user),
    db: Session = Depends(get_db)
) -> AtestadoResponse:
    """
    Atualiza apenas os serviços de um atestado.

    Usado para editar, adicionar ou remover itens individuais da lista
    de serviços extraídos. Os serviços são reordenados automaticamente.
    """
    atestado = get_user_resource_or_404(
        db, Atestado, atestado_id, current_user.id, Messages.ATESTADO_NOT_FOUND
    )

    # Converter ServicoAtestado para dict e ordenar por item
    servicos_dict = [s.model_dump() for s in dados.servicos_json]
    atestado.servicos_json = ordenar_servicos(servicos_dict)

    db.commit()
    db.refresh(atestado)
    return atestado


@router.delete(
    "/{atestado_id}",
    response_model=Mensagem,
    summary="Excluir atestado",
    responses={
        200: {"description": "Atestado excluído com sucesso"},
        401: {"description": "Não autenticado"},
        403: {"description": "Usuário não aprovado"},
        404: {"description": "Atestado não encontrado"},
    }
)
def delete_atestado(
    atestado_id: int,
    current_user: Usuario = Depends(get_current_approved_user),
    db: Session = Depends(get_db)
) -> Mensagem:
    """
    Exclui um atestado e seu arquivo associado.

    Esta ação é irreversível. O arquivo no storage também será removido.
    """
    atestado = get_user_resource_or_404(
        db, Atestado, atestado_id, current_user.id, Messages.ATESTADO_NOT_FOUND
    )

    # Remover arquivo do storage se existir
    if atestado.arquivo_path:
        safe_delete_file(atestado.arquivo_path)

    db.delete(atestado)
    db.commit()

    log_action(
        logger, "atestado_deleted",
        user_id=current_user.id,
        resource_type="atestado",
        resource_id=atestado_id
    )

    return Mensagem(
        mensagem=Messages.ATESTADO_DELETED,
        sucesso=True
    )
