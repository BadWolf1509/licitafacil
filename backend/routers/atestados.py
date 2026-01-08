import os
import shutil
import uuid
from datetime import datetime, date
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Query
from sqlalchemy.orm import Session

from database import get_db, get_db_session
from models import Usuario, Atestado
from schemas import (
    AtestadoCreate, AtestadoUpdate, AtestadoServicosUpdate, AtestadoResponse,
    Mensagem, JobResponse, PaginatedAtestadoResponse
)
from auth import get_current_approved_user
from services.processing_queue import processing_queue, JobStatus
from config import (
    UPLOAD_DIR, Messages, validate_upload_file,
    ALLOWED_DOCUMENT_EXTENSIONS, DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE
)

from logging_config import get_logger
logger = get_logger('routers.atestados')


def parse_date(date_str: Optional[str]) -> Optional[date]:
    """Converte string de data para objeto date do Python."""
    if not date_str:
        return None
    try:
        # Tentar formato ISO (YYYY-MM-DD)
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        try:
            # Tentar formato brasileiro (DD/MM/YYYY)
            return datetime.strptime(date_str, "%d/%m/%Y").date()
        except ValueError:
            return None


def _salvar_atestado_processado(job):
    """Salva o resultado do processamento no banco."""
    if job.status != JobStatus.COMPLETED:
        return

    result = job.result or {}
    data_emissao = parse_date(result.get("data_emissao"))
    servicos = result.get("servicos") or []

    try:
        with get_db_session() as db:
            existente = db.query(Atestado).filter(
                Atestado.user_id == job.user_id,
                Atestado.arquivo_path == job.file_path
            ).first()

            if existente:
                existente.descricao_servico = result.get("descricao_servico") or "Descricao nao identificada"
                existente.quantidade = result.get("quantidade") or 0
                existente.unidade = result.get("unidade") or ""
                existente.contratante = result.get("contratante")
                existente.data_emissao = data_emissao
                existente.texto_extraido = result.get("texto_extraido")
                existente.servicos_json = servicos if servicos else None
                db.commit()
                return

            novo_atestado = Atestado(
                user_id=job.user_id,
                descricao_servico=result.get("descricao_servico") or "Descricao nao identificada",
                quantidade=result.get("quantidade") or 0,
                unidade=result.get("unidade") or "",
                contratante=result.get("contratante"),
                data_emissao=data_emissao,
                arquivo_path=job.file_path,
                texto_extraido=result.get("texto_extraido"),
                servicos_json=servicos if servicos else None
            )
            db.add(novo_atestado)
            db.commit()
    except Exception as e:
        logger.error(f"Erro ao salvar atestado do job {job.id}: {e}")


processing_queue.register_callback("atestado", _salvar_atestado_processado)

router = APIRouter(prefix="/atestados", tags=["Atestados"])


@router.get("/", response_model=PaginatedAtestadoResponse)
def listar_atestados(
    page: int = Query(1, ge=1, description="Número da página"),
    page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE, description="Itens por página"),
    current_user: Usuario = Depends(get_current_approved_user),
    db: Session = Depends(get_db)
):
    """Lista todos os atestados do usuário logado com paginação."""
    # Contar total
    total = db.query(Atestado).filter(
        Atestado.user_id == current_user.id
    ).count()

    # Buscar página
    offset = (page - 1) * page_size
    atestados = db.query(Atestado).filter(
        Atestado.user_id == current_user.id
    ).order_by(Atestado.created_at.desc()).offset(offset).limit(page_size).all()

    return PaginatedAtestadoResponse.create(
        items=atestados,
        total=total,
        page=page,
        page_size=page_size
    )


@router.get("/{atestado_id}", response_model=AtestadoResponse)
def obter_atestado(
    atestado_id: int,
    current_user: Usuario = Depends(get_current_approved_user),
    db: Session = Depends(get_db)
):
    """Obtém um atestado específico."""
    atestado = db.query(Atestado).filter(
        Atestado.id == atestado_id,
        Atestado.user_id == current_user.id
    ).first()

    if not atestado:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Atestado não encontrado"
        )
    return atestado


@router.post("/", response_model=AtestadoResponse)
def criar_atestado(
    atestado: AtestadoCreate,
    current_user: Usuario = Depends(get_current_approved_user),
    db: Session = Depends(get_db)
):
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
):
    """
    Faz upload de um PDF/imagem de atestado para processamento.
    O arquivo sera processado em background e o status pode ser consultado na fila.
    """
    # Validar arquivo
    try:
        file_ext = validate_upload_file(file.filename, ALLOWED_DOCUMENT_EXTENSIONS)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

    # Criar diretorio do usuario
    user_upload_dir = os.path.join(UPLOAD_DIR, str(current_user.id), "atestados")
    os.makedirs(user_upload_dir, exist_ok=True)

    # Salvar arquivo
    filename = f"{uuid.uuid4()}{file_ext}"
    filepath = os.path.join(user_upload_dir, filename)

    with open(filepath, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        job_id = str(uuid.uuid4())
        processing_queue.add_job(
            job_id=job_id,
            user_id=current_user.id,
            file_path=filepath,
            job_type="atestado",
            callback=_salvar_atestado_processado
        )
        return JobResponse(
            mensagem="Arquivo enviado. Processamento iniciado.",
            sucesso=True,
            job_id=job_id
        )
    except Exception as e:
        logger.error(f"Erro ao enfileirar processamento de atestado: {e}")
        if os.path.exists(filepath):
            os.remove(filepath)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=Messages.QUEUE_ERROR
        )


@router.post("/{atestado_id}/reprocess", response_model=JobResponse)
async def reprocessar_atestado(
    atestado_id: int,
    current_user: Usuario = Depends(get_current_approved_user),
    db: Session = Depends(get_db)
):
    """Reprocessa um atestado existente usando o arquivo salvo."""
    atestado = db.query(Atestado).filter(
        Atestado.id == atestado_id,
        Atestado.user_id == current_user.id
    ).first()

    if not atestado:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Atestado nao encontrado"
        )

    if not atestado.arquivo_path or not os.path.exists(atestado.arquivo_path):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Arquivo do atestado nao encontrado"
        )

    try:
        job_id = str(uuid.uuid4())
        processing_queue.add_job(
            job_id=job_id,
            user_id=current_user.id,
            file_path=atestado.arquivo_path,
            job_type="atestado",
            callback=_salvar_atestado_processado
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
):
    """Atualiza um atestado existente."""
    atestado = db.query(Atestado).filter(
        Atestado.id == atestado_id,
        Atestado.user_id == current_user.id
    ).first()

    if not atestado:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Atestado não encontrado"
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
):
    """Atualiza apenas os serviços de um atestado (usado para excluir itens individuais)."""
    atestado = db.query(Atestado).filter(
        Atestado.id == atestado_id,
        Atestado.user_id == current_user.id
    ).first()

    if not atestado:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Atestado não encontrado"
        )

    # Converter ServicoAtestado para dict para salvar no JSON
    atestado.servicos_json = [s.model_dump() for s in dados.servicos_json]

    db.commit()
    db.refresh(atestado)
    return atestado


@router.delete("/{atestado_id}", response_model=Mensagem)
def excluir_atestado(
    atestado_id: int,
    current_user: Usuario = Depends(get_current_approved_user),
    db: Session = Depends(get_db)
):
    """Exclui um atestado."""
    atestado = db.query(Atestado).filter(
        Atestado.id == atestado_id,
        Atestado.user_id == current_user.id
    ).first()

    if not atestado:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Atestado não encontrado"
        )

    # Remover arquivo se existir
    if atestado.arquivo_path and os.path.exists(atestado.arquivo_path):
        os.remove(atestado.arquivo_path)

    db.delete(atestado)
    db.commit()

    return Mensagem(
        mensagem="Atestado excluído com sucesso!",
        sucesso=True
    )
