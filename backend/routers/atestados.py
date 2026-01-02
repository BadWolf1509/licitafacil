import os
import shutil
import uuid
from datetime import datetime, date
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session

from database import get_db
from models import Usuario, Atestado
from schemas import AtestadoCreate, AtestadoUpdate, AtestadoResponse, Mensagem
from auth import get_current_approved_user
from services import document_processor


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

router = APIRouter(prefix="/atestados", tags=["Atestados"])

UPLOAD_DIR = "uploads"


@router.get("/", response_model=List[AtestadoResponse])
def listar_atestados(
    current_user: Usuario = Depends(get_current_approved_user),
    db: Session = Depends(get_db)
):
    """Lista todos os atestados do usuário logado."""
    atestados = db.query(Atestado).filter(
        Atestado.user_id == current_user.id
    ).order_by(Atestado.created_at.desc()).all()
    return atestados


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


@router.post("/upload", response_model=AtestadoResponse)
async def upload_atestado(
    file: UploadFile = File(...),
    current_user: Usuario = Depends(get_current_approved_user),
    db: Session = Depends(get_db)
):
    """
    Faz upload de um PDF/imagem de atestado para processamento.
    O arquivo será processado automaticamente para extração dos dados.
    """
    # Verificar extensão
    allowed_extensions = [".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp"]
    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Formato não suportado. Use: {', '.join(allowed_extensions)}"
        )

    # Criar diretório do usuário
    user_upload_dir = os.path.join(UPLOAD_DIR, str(current_user.id), "atestados")
    os.makedirs(user_upload_dir, exist_ok=True)

    # Salvar arquivo
    filename = f"{uuid.uuid4()}{file_ext}"
    filepath = os.path.join(user_upload_dir, filename)

    with open(filepath, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        # Processar documento (PDF/imagem -> texto -> IA)
        dados = document_processor.process_atestado(filepath)

        # Converter data de string para objeto date
        data_emissao = parse_date(dados.get("data_emissao"))

        # Extrair lista de serviços detalhados
        servicos = dados.get("servicos") or []

        # Criar atestado com dados extraídos
        novo_atestado = Atestado(
            user_id=current_user.id,
            descricao_servico=dados.get("descricao_servico") or "Descrição não identificada",
            quantidade=dados.get("quantidade") or 0,
            unidade=dados.get("unidade") or "",
            contratante=dados.get("contratante"),
            data_emissao=data_emissao,
            arquivo_path=filepath,
            texto_extraido=dados.get("texto_extraido"),
            servicos_json=servicos if servicos else None
        )
        db.add(novo_atestado)
        db.commit()
        db.refresh(novo_atestado)

        return novo_atestado

    except Exception as e:
        # Remover arquivo se falhar
        if os.path.exists(filepath):
            os.remove(filepath)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao processar documento: {str(e)}"
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
