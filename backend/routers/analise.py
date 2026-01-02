import os
import shutil
import uuid
from typing import List
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session

from database import get_db
from models import Usuario, Atestado, Analise
from schemas import AnaliseCreate, AnaliseResponse, Mensagem, ResultadoExigencia, ExigenciaEdital, AtestadoMatch
from auth import get_current_approved_user
from services import document_processor

router = APIRouter(prefix="/analises", tags=["Análises"])

UPLOAD_DIR = "uploads"


@router.get("/status/servicos")
def status_servicos():
    """Retorna o status dos serviços de processamento de documentos."""
    return document_processor.get_status()


@router.get("/", response_model=List[AnaliseResponse])
def listar_analises(
    current_user: Usuario = Depends(get_current_approved_user),
    db: Session = Depends(get_db)
):
    """Lista todas as análises do usuário logado."""
    analises = db.query(Analise).filter(
        Analise.user_id == current_user.id
    ).order_by(Analise.created_at.desc()).all()
    return analises


@router.get("/{analise_id}", response_model=AnaliseResponse)
def obter_analise(
    analise_id: int,
    current_user: Usuario = Depends(get_current_approved_user),
    db: Session = Depends(get_db)
):
    """Obtém uma análise específica."""
    analise = db.query(Analise).filter(
        Analise.id == analise_id,
        Analise.user_id == current_user.id
    ).first()

    if not analise:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Análise não encontrada"
        )
    return analise


@router.post("/", response_model=AnaliseResponse)
async def criar_analise(
    nome_licitacao: str = Form(...),
    file: UploadFile = File(...),
    current_user: Usuario = Depends(get_current_approved_user),
    db: Session = Depends(get_db)
):
    """
    Cria uma nova análise de licitação.
    Faz upload do PDF do edital, extrai exigências e faz matching com atestados.
    """
    # Verificar extensão
    allowed_extensions = [".pdf"]
    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Apenas arquivos PDF são aceitos para análise de edital"
        )

    # Criar diretório do usuário
    user_upload_dir = os.path.join(UPLOAD_DIR, str(current_user.id), "editais")
    os.makedirs(user_upload_dir, exist_ok=True)

    # Salvar arquivo
    filename = f"{uuid.uuid4()}{file_ext}"
    filepath = os.path.join(user_upload_dir, filename)

    with open(filepath, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

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
                "unidade": at.unidade or ""
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
        # Remover arquivo se falhar
        if os.path.exists(filepath):
            os.remove(filepath)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao processar edital: {str(e)}"
        )


@router.post("/{analise_id}/processar", response_model=AnaliseResponse)
async def processar_analise(
    analise_id: int,
    current_user: Usuario = Depends(get_current_approved_user),
    db: Session = Depends(get_db)
):
    """
    Reprocessa uma análise existente: extrai exigências do edital e faz matching com atestados.
    Útil quando novos atestados são adicionados ou para reprocessar com IA atualizada.
    """
    analise = db.query(Analise).filter(
        Analise.id == analise_id,
        Analise.user_id == current_user.id
    ).first()

    if not analise:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Análise não encontrada"
        )

    if not analise.arquivo_path or not os.path.exists(analise.arquivo_path):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Arquivo do edital não encontrado"
        )

    # Buscar atestados do usuário
    atestados = db.query(Atestado).filter(
        Atestado.user_id == current_user.id
    ).all()

    if not atestados:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Você não possui atestados cadastrados. Cadastre atestados antes de analisar uma licitação."
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
                "unidade": at.unidade or ""
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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao reprocessar análise: {str(e)}"
        )


@router.delete("/{analise_id}", response_model=Mensagem)
def excluir_analise(
    analise_id: int,
    current_user: Usuario = Depends(get_current_approved_user),
    db: Session = Depends(get_db)
):
    """Exclui uma análise."""
    analise = db.query(Analise).filter(
        Analise.id == analise_id,
        Analise.user_id == current_user.id
    ).first()

    if not analise:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Análise não encontrada"
        )

    # Remover arquivo se existir
    if analise.arquivo_path and os.path.exists(analise.arquivo_path):
        os.remove(analise.arquivo_path)

    db.delete(analise)
    db.commit()

    return Mensagem(
        mensagem="Análise excluída com sucesso!",
        sucesso=True
    )
