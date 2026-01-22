import os
import uuid
from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session

from database import get_db
from models import Usuario, Atestado, Analise
from schemas import AnaliseResponse, Mensagem, PaginatedAnaliseResponse
from auth import get_current_approved_user
from services import document_processor
from config import Messages, ALLOWED_PDF_EXTENSIONS
from utils.pagination import PaginationParams, paginate_query
from utils.validation import validate_upload_or_raise
from utils.router_helpers import get_user_upload_dir, safe_delete_file, save_upload_file
from utils.http_helpers import get_user_resource_or_404
from logging_config import get_logger

logger = get_logger('routers.analise')

router = APIRouter(prefix="/analises", tags=["Análises"])


@router.get("/status/servicos")
def status_servicos(
    current_user: Usuario = Depends(get_current_approved_user)
) -> Dict[str, Any]:
    """Retorna o status dos serviços de processamento de documentos."""
    return document_processor.get_status()


@router.get("/", response_model=PaginatedAnaliseResponse)
def listar_analises(
    pagination: PaginationParams = Depends(),
    current_user: Usuario = Depends(get_current_approved_user),
    db: Session = Depends(get_db)
) -> PaginatedAnaliseResponse:
    """Lista todas as análises do usuário logado com paginação."""
    query = db.query(Analise).filter(
        Analise.user_id == current_user.id
    ).order_by(Analise.created_at.desc())

    return paginate_query(query, pagination, PaginatedAnaliseResponse)


@router.get("/{analise_id}", response_model=AnaliseResponse)
def obter_analise(
    analise_id: int,
    current_user: Usuario = Depends(get_current_approved_user),
    db: Session = Depends(get_db)
) -> AnaliseResponse:
    """Obtém uma análise específica."""
    analise = get_user_resource_or_404(
        db, Analise, analise_id, current_user.id, Messages.ANALISE_NOT_FOUND
    )
    return analise


@router.post("/", response_model=AnaliseResponse)
async def criar_analise(
    nome_licitacao: str = Form(...),
    file: UploadFile = File(...),
    current_user: Usuario = Depends(get_current_approved_user),
    db: Session = Depends(get_db)
) -> AnaliseResponse:
    """
    Cria uma nova análise de licitação.
    Faz upload do PDF do edital, extrai exigências e faz matching com atestados.
    """
    # Validar arquivo
    file_ext = validate_upload_or_raise(file.filename, ALLOWED_PDF_EXTENSIONS)

    # Criar diretório do usuário e salvar arquivo
    user_upload_dir = get_user_upload_dir(current_user.id, "editais")
    filename = f"{uuid.uuid4()}{file_ext}"
    filepath = str(user_upload_dir / filename)
    save_upload_file(file, filepath)

    try:
        # Processar edital (extrair texto e exigências)
        resultado_edital = document_processor.process_edital(filepath)
        exigencias = resultado_edital.get("exigencias", [])

        # Buscar atestados do usuário
        atestados = db.query(Atestado).filter(
            Atestado.user_id == current_user.id
        ).all()

        # Converter atestados para formato de análise
        atestados_dict = [
            {
                "id": at.id,
                "descricao_servico": at.descricao_servico,
                "quantidade": float(at.quantidade) if at.quantidade else 0,
                "unidade": at.unidade or "",
                "servicos_json": at.servicos_json
            }
            for at in atestados
        ]

        # Fazer matching se houver exigências e atestados
        resultado_matching = []
        if exigencias and atestados_dict:
            resultado_matching = document_processor.analyze_qualification(
                exigencias, atestados_dict
            )

        # Criar análise
        nova_analise = Analise(
            user_id=current_user.id,
            nome_licitacao=nome_licitacao,
            arquivo_path=filepath,
            exigencias_json=exigencias,
            resultado_json=resultado_matching
        )
        db.add(nova_analise)
        db.commit()
        db.refresh(nova_analise)

        return nova_analise

    except Exception as e:
        logger.error(f"Erro ao processar edital: {e}")
        safe_delete_file(filepath)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=Messages.PROCESSING_ERROR
        )


@router.post("/{analise_id}/processar", response_model=AnaliseResponse)
async def processar_analise(
    analise_id: int,
    current_user: Usuario = Depends(get_current_approved_user),
    db: Session = Depends(get_db)
) -> AnaliseResponse:
    """
    Reprocessa uma análise existente: extrai exigências do edital e faz matching com atestados.
    Útil quando novos atestados são adicionados ou para reprocessar com IA atualizada.
    """
    analise = get_user_resource_or_404(
        db, Analise, analise_id, current_user.id, Messages.ANALISE_NOT_FOUND
    )

    if not analise.arquivo_path or not os.path.exists(analise.arquivo_path):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=Messages.EDITAL_FILE_NOT_FOUND
        )

    # Buscar atestados do usuário
    atestados = db.query(Atestado).filter(
        Atestado.user_id == current_user.id
    ).all()

    if not atestados:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=Messages.NO_ATESTADOS
        )

    try:
        # Reprocessar edital
        resultado_edital = document_processor.process_edital(analise.arquivo_path)
        exigencias = resultado_edital.get("exigencias", [])

        # Converter atestados para formato de análise
        atestados_dict = [
            {
                "id": at.id,
                "descricao_servico": at.descricao_servico,
                "quantidade": float(at.quantidade) if at.quantidade else 0,
                "unidade": at.unidade or "",
                "servicos_json": at.servicos_json
            }
            for at in atestados
        ]

        # Fazer matching
        resultado_matching = []
        if exigencias and atestados_dict:
            resultado_matching = document_processor.analyze_qualification(
                exigencias, atestados_dict
            )

        # Atualizar análise
        analise.exigencias_json = exigencias
        analise.resultado_json = resultado_matching
        db.commit()
        db.refresh(analise)

        return analise

    except Exception as e:
        logger.error(f"Erro ao reprocessar análise {analise_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=Messages.PROCESSING_ERROR
        )


@router.delete("/{analise_id}", response_model=Mensagem)
def excluir_analise(
    analise_id: int,
    current_user: Usuario = Depends(get_current_approved_user),
    db: Session = Depends(get_db)
) -> Mensagem:
    """Exclui uma análise."""
    analise = get_user_resource_or_404(
        db, Analise, analise_id, current_user.id, Messages.ANALISE_NOT_FOUND
    )

    # Remover arquivo se existir
    if analise.arquivo_path:
        safe_delete_file(analise.arquivo_path)

    db.delete(analise)
    db.commit()

    return Mensagem(
        mensagem=Messages.ANALISE_DELETED,
        sucesso=True
    )
