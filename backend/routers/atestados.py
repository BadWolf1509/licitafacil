import os
import uuid
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session

from database import get_db
from models import Usuario, Atestado
from schemas import (
    AtestadoCreate, AtestadoUpdate, AtestadoServicosUpdate, AtestadoResponse,
    Mensagem, JobResponse, PaginatedAtestadoResponse
)
from auth import get_current_approved_user
from services.processing_queue import processing_queue
from services.atestado_service import ordenar_servicos, salvar_atestado_processado
from config import Messages, ALLOWED_DOCUMENT_EXTENSIONS
from utils.pagination import PaginationParams, paginate_query
from utils.validation import validate_upload_or_raise
from utils.router_helpers import get_user_upload_dir, safe_delete_file, save_upload_file

from logging_config import get_logger
logger = get_logger('routers.atestados')


# Registrar callback para processamento de atestados
processing_queue.register_callback("atestado", salvar_atestado_processado)

router = APIRouter(prefix="/atestados", tags=["Atestados"])


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
    atestado = db.query(Atestado).filter(
        Atestado.id == atestado_id,
        Atestado.user_id == current_user.id
    ).first()

    if not atestado:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=Messages.ATESTADO_NOT_FOUND
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


@router.post("/upload", response_model=JobResponse)
async def upload_atestado(
    file: UploadFile = File(...),
    current_user: Usuario = Depends(get_current_approved_user),
    db: Session = Depends(get_db)
) -> JobResponse:
    """
    Faz upload de um PDF/imagem de atestado para processamento.
    O arquivo sera processado em background e o status pode ser consultado na fila.
    """
    # Validar arquivo
    file_ext = validate_upload_or_raise(file.filename, ALLOWED_DOCUMENT_EXTENSIONS)

    # Criar diretorio do usuario e salvar arquivo
    user_upload_dir = get_user_upload_dir(current_user.id, "atestados")
    filename = f"{uuid.uuid4()}{file_ext}"
    filepath = str(user_upload_dir / filename)
    save_upload_file(file, filepath)

    try:
        job_id = str(uuid.uuid4())
        processing_queue.add_job(
            job_id=job_id,
            user_id=current_user.id,
            file_path=filepath,
            job_type="atestado",
            original_filename=file.filename,
            callback=salvar_atestado_processado
        )
        return JobResponse(
            mensagem=Messages.UPLOAD_SUCCESS,
            sucesso=True,
            job_id=job_id
        )
    except Exception as e:
        logger.error(f"Erro ao enfileirar processamento de atestado: {e}")
        safe_delete_file(filepath)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=Messages.QUEUE_ERROR
        )


@router.post("/{atestado_id}/reprocess", response_model=JobResponse)
async def reprocessar_atestado(
    atestado_id: int,
    current_user: Usuario = Depends(get_current_approved_user),
    db: Session = Depends(get_db)
) -> JobResponse:
    """Reprocessa um atestado existente usando o arquivo salvo."""
    atestado = db.query(Atestado).filter(
        Atestado.id == atestado_id,
        Atestado.user_id == current_user.id
    ).first()

    if not atestado:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=Messages.ATESTADO_NOT_FOUND
        )

    if not atestado.arquivo_path or not os.path.exists(atestado.arquivo_path):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=Messages.ATESTADO_FILE_NOT_FOUND
        )

    try:
        job_id = str(uuid.uuid4())
        # Usar basename do arquivo como nome original (já é UUID no reprocessamento)
        original_name = os.path.basename(atestado.arquivo_path)
        processing_queue.add_job(
            job_id=job_id,
            user_id=current_user.id,
            file_path=atestado.arquivo_path,
            job_type="atestado",
            original_filename=original_name,
            callback=salvar_atestado_processado
        )
        return JobResponse(
            mensagem="Reprocessamento iniciado.",
            sucesso=True,
            job_id=job_id
        )
    except Exception as e:
        logger.error(f"Erro ao enfileirar reprocessamento de atestado {atestado_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=Messages.QUEUE_ERROR
        )


@router.put("/{atestado_id}", response_model=AtestadoResponse)
def atualizar_atestado(
    atestado_id: int,
    dados: AtestadoUpdate,
    current_user: Usuario = Depends(get_current_approved_user),
    db: Session = Depends(get_db)
) -> AtestadoResponse:
    """Atualiza um atestado existente."""
    atestado = db.query(Atestado).filter(
        Atestado.id == atestado_id,
        Atestado.user_id == current_user.id
    ).first()

    if not atestado:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=Messages.ATESTADO_NOT_FOUND
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
    atestado = db.query(Atestado).filter(
        Atestado.id == atestado_id,
        Atestado.user_id == current_user.id
    ).first()

    if not atestado:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=Messages.ATESTADO_NOT_FOUND
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
    atestado = db.query(Atestado).filter(
        Atestado.id == atestado_id,
        Atestado.user_id == current_user.id
    ).first()

    if not atestado:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=Messages.ATESTADO_NOT_FOUND
        )

    # Remover arquivo se existir
    if atestado.arquivo_path:
        safe_delete_file(atestado.arquivo_path)

    db.delete(atestado)
    db.commit()

    return Mensagem(
        mensagem=Messages.ATESTADO_DELETED,
        sucesso=True
    )
