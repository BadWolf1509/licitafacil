import os
import uuid
import tempfile
from decimal import Decimal
from typing import Dict, Any
from fastapi import Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session

from database import get_db
from models import Usuario, Analise
from repositories.atestado_repository import atestado_repository
from schemas import AnaliseResponse, Mensagem, PaginatedAnaliseResponse, AnaliseManualCreate
from auth import get_current_approved_user
from dependencies import ServiceContainer, get_services
from services.atestado import atestados_to_dict
from config import Messages, ALLOWED_PDF_EXTENSIONS
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

logger = get_logger('routers.analise')

router = AuthenticatedRouter(prefix="/analises", tags=["Análises"])


def _serialize_for_json(obj):
    """Converte Decimal para float para serialização JSON."""
    if isinstance(obj, dict):
        return {k: _serialize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_serialize_for_json(item) for item in obj]
    elif isinstance(obj, Decimal):
        return float(obj)
    return obj


@router.get("/status/servicos")
def status_servicos(
    current_user: Usuario = Depends(get_current_approved_user),
    services: ServiceContainer = Depends(get_services)
) -> Dict[str, Any]:
    """Retorna o status dos serviços de processamento de documentos."""
    return services.document_processor.get_status()


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
    db: Session = Depends(get_db),
    services: ServiceContainer = Depends(get_services)
) -> AnaliseResponse:
    """
    Cria uma nova análise de licitação.
    Faz upload do PDF do edital, extrai exigências e faz matching com atestados.
    """
    # Validar arquivo (extensão, tamanho e MIME type)
    file_ext = await validate_upload_complete_or_raise(file, ALLOWED_PDF_EXTENSIONS)

    # Gerar nome único para o arquivo
    filename = f"{uuid.uuid4()}{file_ext}"

    # Salvar arquivo no Storage (Supabase ou local)
    storage_path = save_upload_file_to_storage(
        file=file,
        user_id=current_user.id,
        subfolder="editais",
        filename=filename,
        content_type="application/pdf"
    )

    # Criar arquivo temporário para processamento
    temp_file = None
    try:
        # Baixar arquivo do storage para arquivo temporário
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=file_ext)
        temp_path = temp_file.name
        temp_file.close()

        if not save_temp_file_from_storage(storage_path, temp_path):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Erro ao preparar arquivo para processamento"
            )

        # Processar edital (extrair texto e exigências)
        resultado_edital = services.document_processor.process_edital(temp_path)
        exigencias = resultado_edital.get("exigencias", [])

        # Buscar atestados do usuário usando repository
        atestados = atestado_repository.get_all_with_services(db, current_user.id)

        # Converter atestados para formato de análise
        atestados_dict = atestados_to_dict(atestados)

        # Fazer matching se houver exigências e atestados
        resultado_matching = []
        if exigencias and atestados_dict:
            resultado_matching = services.document_processor.analyze_qualification(
                exigencias, atestados_dict
            )

        # Criar análise (salva o path do storage, não o path local)
        nova_analise = Analise(
            user_id=current_user.id,
            nome_licitacao=nome_licitacao,
            arquivo_path=storage_path,  # Caminho no storage
            exigencias_json=exigencias,
            resultado_json=resultado_matching
        )
        db.add(nova_analise)
        db.commit()
        db.refresh(nova_analise)

        return nova_analise

    except Exception as e:
        # Em caso de erro, remover arquivo do storage
        safe_delete_file(storage_path)
        raise handle_exception(e, logger, "ao processar edital")

    finally:
        # Limpar arquivo temporário
        if temp_file and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except OSError:
                pass


@router.post("/manual", response_model=AnaliseResponse)
async def criar_analise_manual(
    dados: AnaliseManualCreate,
    current_user: Usuario = Depends(get_current_approved_user),
    db: Session = Depends(get_db),
    services: ServiceContainer = Depends(get_services)
) -> AnaliseResponse:
    """
    Cria uma análise de licitação com exigências informadas manualmente.
    Não requer upload de PDF - as exigências são inseridas diretamente.
    """
    if not dados.exigencias or len(dados.exigencias) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Informe pelo menos uma exigência"
        )

    # Converter exigências para dict (Decimal -> float para JSON)
    exigencias = [_serialize_for_json(e.model_dump()) for e in dados.exigencias]

    # Buscar atestados do usuário usando repository
    atestados = atestado_repository.get_all_with_services(db, current_user.id)

    # Converter atestados para formato de análise
    atestados_dict = atestados_to_dict(atestados)

    # Fazer matching se houver atestados
    resultado_matching = []
    if atestados_dict:
        try:
            resultado_matching = services.document_processor.analyze_qualification(
                exigencias, atestados_dict
            )
            # Serializar resultado (Decimal -> float)
            resultado_matching = _serialize_for_json(resultado_matching)
        except Exception as e:
            logger.warning(f"Erro no matching: {e}")

    # Criar análise
    nova_analise = Analise(
        user_id=current_user.id,
        nome_licitacao=dados.nome_licitacao,
        arquivo_path=None,  # Sem arquivo
        exigencias_json=exigencias,
        resultado_json=resultado_matching
    )
    db.add(nova_analise)
    db.commit()
    db.refresh(nova_analise)

    return nova_analise


@router.post("/{analise_id}/processar", response_model=AnaliseResponse)
async def processar_analise(
    analise_id: int,
    current_user: Usuario = Depends(get_current_approved_user),
    db: Session = Depends(get_db),
    services: ServiceContainer = Depends(get_services)
) -> AnaliseResponse:
    """
    Reprocessa uma análise existente: extrai exigências do edital e faz matching com atestados.
    Útil quando novos atestados são adicionados ou para reprocessar com IA atualizada.
    """
    analise = get_user_resource_or_404(
        db, Analise, analise_id, current_user.id, Messages.ANALISE_NOT_FOUND
    )

    # Verificar se há arquivo associado
    if not analise.arquivo_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=Messages.EDITAL_FILE_NOT_FOUND
        )

    # Verificar se arquivo existe no storage
    if not file_exists_in_storage(analise.arquivo_path):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=Messages.EDITAL_FILE_NOT_FOUND
        )

    # Buscar atestados do usuário usando repository
    atestados = atestado_repository.get_all_with_services(db, current_user.id)

    if not atestados:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=Messages.NO_ATESTADOS
        )

    # Baixar arquivo do storage para arquivo temporário
    temp_file = None
    try:
        file_ext = os.path.splitext(analise.arquivo_path)[1] or ".pdf"
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=file_ext)
        temp_path = temp_file.name
        temp_file.close()

        if not save_temp_file_from_storage(analise.arquivo_path, temp_path):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Erro ao baixar arquivo do storage"
            )

        # Reprocessar edital
        resultado_edital = services.document_processor.process_edital(temp_path)
        exigencias = resultado_edital.get("exigencias", [])

        # Converter atestados para formato de análise
        atestados_dict = atestados_to_dict(atestados)

        # Fazer matching
        resultado_matching = []
        if exigencias and atestados_dict:
            resultado_matching = services.document_processor.analyze_qualification(
                exigencias, atestados_dict
            )

        # Atualizar análise
        analise.exigencias_json = exigencias
        analise.resultado_json = resultado_matching
        db.commit()
        db.refresh(analise)

        return analise

    except HTTPException:
        raise
    except Exception as e:
        raise handle_exception(e, logger, f"ao reprocessar análise {analise_id}")

    finally:
        # Limpar arquivo temporário
        if temp_file and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except OSError:
                pass


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

    # Remover arquivo do storage se existir
    if analise.arquivo_path:
        safe_delete_file(analise.arquivo_path)

    db.delete(analise)
    db.commit()

    return Mensagem(
        mensagem=Messages.ANALISE_DELETED,
        sucesso=True
    )
