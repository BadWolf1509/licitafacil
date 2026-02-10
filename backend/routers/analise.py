import os
import uuid
from decimal import Decimal
from typing import Any, Dict

from fastapi import Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from auth import get_current_approved_user
from config import ALLOWED_PDF_EXTENSIONS, Messages
from database import get_db
from dependencies import ServiceContainer, get_services
from logging_config import get_logger, log_action
from models import Analise, Usuario
from repositories.atestado_repository import atestado_repository
from routers.base import AuthenticatedRouter
from schemas import AnaliseManualCreate, AnaliseResponse, Mensagem, PaginatedAnaliseResponse
from services.atestado import atestados_to_dict
from services.matching_service import matching_service
from utils import handle_exception
from utils.file_helpers import temp_file_from_storage
from utils.http_helpers import get_user_resource_or_404
from utils.pagination import PaginationParams, paginate_query
from utils.router_helpers import (
    file_exists_in_storage,
    safe_delete_file,
    save_temp_file_from_storage,
    save_upload_file_to_storage,
)
from utils.validation import validate_upload_complete_or_raise

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


@router.get(
    "/status/servicos",
    summary="Status dos serviços de processamento",
    responses={
        200: {"description": "Status dos serviços retornado"},
        401: {"description": "Não autenticado"},
        403: {"description": "Usuário não aprovado"},
    }
)
def get_services_status(
    current_user: Usuario = Depends(get_current_approved_user),
    services: ServiceContainer = Depends(get_services)
) -> Dict[str, Any]:
    """
    Retorna o status dos serviços de processamento de documentos.

    Inclui disponibilidade de OCR, vision API e modo de processamento ativo.
    """
    return services.document_processor.get_status()


@router.get(
    "/",
    response_model=PaginatedAnaliseResponse,
    summary="Listar análises",
    responses={
        200: {"description": "Lista de análises retornada"},
        401: {"description": "Não autenticado"},
        403: {"description": "Usuário não aprovado"},
    }
)
def list_analyses(
    pagination: PaginationParams = Depends(),
    current_user: Usuario = Depends(get_current_approved_user),
    db: Session = Depends(get_db)
) -> PaginatedAnaliseResponse:
    """
    Lista todas as análises de licitação do usuário logado com paginação.

    Ordenadas da mais recente para a mais antiga.

    **Parâmetros de paginação:**
    - `page`: Número da página (padrão: 1)
    - `per_page`: Itens por página (padrão: 10, máximo: 100)
    """
    query = db.query(Analise).filter(
        Analise.user_id == current_user.id
    ).order_by(Analise.created_at.desc())

    return paginate_query(query, pagination, PaginatedAnaliseResponse)


@router.get(
    "/{analise_id}",
    response_model=AnaliseResponse,
    summary="Obter uma análise",
    responses={
        200: {"description": "Análise retornada"},
        401: {"description": "Não autenticado"},
        403: {"description": "Usuário não aprovado"},
        404: {"description": "Análise não encontrada"},
    }
)
def get_analysis(
    analise_id: int,
    current_user: Usuario = Depends(get_current_approved_user),
    db: Session = Depends(get_db)
) -> AnaliseResponse:
    """
    Obtém uma análise de licitação específica pelo ID.

    Retorna exigências extraídas do edital e resultado do matching
    com os atestados do usuário.
    """
    analise = get_user_resource_or_404(
        db, Analise, analise_id, current_user.id, Messages.ANALISE_NOT_FOUND
    )
    return analise


@router.post(
    "/",
    response_model=AnaliseResponse,
    summary="Criar análise de licitação",
    responses={
        200: {"description": "Análise criada com sucesso"},
        400: {"description": "Arquivo inválido"},
        401: {"description": "Não autenticado"},
        403: {"description": "Usuário não aprovado"},
        413: {"description": "Arquivo muito grande (máx 50MB)"},
        500: {"description": "Erro ao processar edital"},
    }
)
async def create_analysis(
    nome_licitacao: str = Form(...),
    file: UploadFile = File(...),
    current_user: Usuario = Depends(get_current_approved_user),
    db: Session = Depends(get_db),
    services: ServiceContainer = Depends(get_services)
) -> AnaliseResponse:
    """
    Cria uma nova análise de licitação com upload de edital.

    **Fluxo de processamento:**
    1. Upload e validação do PDF do edital
    2. Extração de texto e identificação de exigências técnicas
    3. Matching automático das exigências com os atestados cadastrados
    4. Geração de relatório de qualificação técnica

    **Formatos aceitos:** PDF

    **Tamanho máximo:** 50MB
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

    # Processar arquivo temporário
    try:
        with temp_file_from_storage(storage_path, save_temp_file_from_storage, suffix=file_ext) as temp_path:
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

            log_action(
                logger, "analise_created",
                user_id=current_user.id,
                resource_type="analise",
                resource_id=nova_analise.id,
                exigencias_count=len(exigencias),
                matches_count=len(resultado_matching)
            )

            return nova_analise

    except Exception as e:
        # Em caso de erro, remover arquivo do storage
        safe_delete_file(storage_path)
        raise handle_exception(e, logger, "ao processar edital")


@router.post(
    "/manual",
    response_model=AnaliseResponse,
    summary="Criar análise manual",
    responses={
        200: {"description": "Análise criada com sucesso"},
        400: {"description": "Nenhuma exigência informada"},
        401: {"description": "Não autenticado"},
        403: {"description": "Usuário não aprovado"},
    }
)
async def create_manual_analysis(
    dados: AnaliseManualCreate,
    current_user: Usuario = Depends(get_current_approved_user),
    db: Session = Depends(get_db),
) -> AnaliseResponse:
    """
    Cria uma análise de licitação com exigências informadas manualmente.

    Não requer upload de PDF. As exigências são inseridas diretamente
    pelo usuário e o matching com atestados é realizado automaticamente.

    Útil quando o edital não está em formato digital ou quando se deseja
    testar cenários específicos de qualificação.
    """
    if not dados.exigencias or len(dados.exigencias) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Informe pelo menos uma exigência"
        )

    # Converter exigências para dict (Decimal -> float para JSON)
    exigencias = [_serialize_for_json(e.model_dump()) for e in dados.exigencias]
    logger.info(f"[ANALISE_MANUAL] Exigencias recebidas: {len(exigencias)}")

    # Buscar atestados do usuário usando repository
    atestados = atestado_repository.get_all_with_services(db, current_user.id)
    logger.info(f"[ANALISE_MANUAL] Atestados encontrados: {len(atestados) if atestados else 0}")

    # Converter atestados para formato de análise
    atestados_dict = atestados_to_dict(atestados)
    logger.info(f"[ANALISE_MANUAL] Atestados com servicos: {len(atestados_dict) if atestados_dict else 0}")

    # Fazer matching se houver exigências e atestados
    resultado_matching = []
    try:
        if exigencias and atestados_dict:
            logger.info("[ANALISE_MANUAL] Iniciando matching...")
            resultado_matching = matching_service.match_exigencias(
                exigencias, atestados_dict
            )
            logger.info(f"[ANALISE_MANUAL] Matching concluido: {len(resultado_matching)} resultados")
        # Serializar resultado (Decimal -> float)
        resultado_matching = _serialize_for_json(resultado_matching)
    except Exception as e:
        raise handle_exception(e, logger, "ao processar análise manual")

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

    log_action(
        logger, "analise_created",
        user_id=current_user.id,
        resource_type="analise",
        resource_id=nova_analise.id,
        method="manual",
        exigencias_count=len(exigencias),
        matches_count=len(resultado_matching)
    )

    return nova_analise


@router.post(
    "/{analise_id}/processar",
    response_model=AnaliseResponse,
    summary="Reprocessar análise",
    responses={
        200: {"description": "Análise reprocessada com sucesso"},
        400: {"description": "Arquivo não encontrado ou sem atestados"},
        401: {"description": "Não autenticado"},
        403: {"description": "Usuário não aprovado"},
        404: {"description": "Análise não encontrada"},
        500: {"description": "Erro ao processar"},
    }
)
async def reprocess_analysis(
    analise_id: int,
    current_user: Usuario = Depends(get_current_approved_user),
    db: Session = Depends(get_db),
    services: ServiceContainer = Depends(get_services)
) -> AnaliseResponse:
    """
    Reprocessa uma análise existente.

    Para análises com PDF: extrai novamente as exigências e refaz o matching.
    Para análises manuais: usa as exigências armazenadas e refaz o matching
    com os atestados atuais do usuário.

    **Casos de uso:**
    - Novos atestados foram adicionados após a análise original
    - O modelo de IA foi atualizado
    - Correção de extrações que falharam parcialmente
    """
    analise = get_user_resource_or_404(
        db, Analise, analise_id, current_user.id, Messages.ANALISE_NOT_FOUND
    )

    # Buscar atestados do usuário
    atestados = atestado_repository.get_all_with_services(db, current_user.id)

    if not atestados:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=Messages.NO_ATESTADOS
        )

    atestados_dict = atestados_to_dict(atestados)

    try:
        if analise.arquivo_path:
            # Análise com PDF: re-extrair exigências do arquivo + re-fazer matching
            if not file_exists_in_storage(analise.arquivo_path):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=Messages.EDITAL_FILE_NOT_FOUND
                )

            file_ext = os.path.splitext(analise.arquivo_path)[1] or ".pdf"
            with temp_file_from_storage(analise.arquivo_path, save_temp_file_from_storage, suffix=file_ext) as temp_path:
                resultado_edital = services.document_processor.process_edital(temp_path)
                exigencias = resultado_edital.get("exigencias", [])

                resultado_matching = []
                if exigencias and atestados_dict:
                    resultado_matching = services.document_processor.analyze_qualification(
                        exigencias, atestados_dict
                    )

                analise.exigencias_json = exigencias
                analise.resultado_json = resultado_matching
        else:
            # Análise manual: usar exigências armazenadas, apenas re-fazer matching
            # Usa matching_service diretamente (não precisa importar document_processor pesado)
            exigencias = analise.exigencias_json or []
            if not exigencias:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Análise manual sem exigências para reprocessar"
                )

            resultado_matching = []
            if atestados_dict:
                resultado_matching = matching_service.match_exigencias(
                    exigencias, atestados_dict
                )
            analise.resultado_json = _serialize_for_json(resultado_matching)

        db.commit()
        db.refresh(analise)
        return analise

    except HTTPException:
        raise
    except Exception as e:
        raise handle_exception(e, logger, f"ao reprocessar análise {analise_id}")


@router.delete(
    "/{analise_id}",
    response_model=Mensagem,
    summary="Excluir análise",
    responses={
        200: {"description": "Análise excluída com sucesso"},
        401: {"description": "Não autenticado"},
        403: {"description": "Usuário não aprovado"},
        404: {"description": "Análise não encontrada"},
    }
)
def delete_analysis(
    analise_id: int,
    current_user: Usuario = Depends(get_current_approved_user),
    db: Session = Depends(get_db)
) -> Mensagem:
    """
    Exclui uma análise de licitação e seu arquivo associado.

    Esta ação é irreversível. O PDF do edital no storage também será removido.
    """
    analise = get_user_resource_or_404(
        db, Analise, analise_id, current_user.id, Messages.ANALISE_NOT_FOUND
    )

    # Remover arquivo do storage se existir
    if analise.arquivo_path:
        safe_delete_file(analise.arquivo_path)

    db.delete(analise)
    db.commit()

    log_action(
        logger, "analise_deleted",
        user_id=current_user.id,
        resource_type="analise",
        resource_id=analise_id
    )

    return Mensagem(
        mensagem=Messages.ANALISE_DELETED,
        sucesso=True
    )
