"""
Servico de negocios para gerenciamento de atestados.

Este modulo contem a logica de negocio separada dos routers,
facilitando testes e manutencao.
"""
import os
import uuid
import shutil
from typing import List, Optional
from sqlalchemy.orm import Session
from fastapi import UploadFile

from models import Atestado
from schemas import AtestadoCreate, AtestadoUpdate, AtestadoServicosUpdate
from config import UPLOAD_DIR, ALLOWED_DOCUMENT_EXTENSIONS, get_file_extension
from exceptions import RecordNotFoundError, ValidationError
from services.processing_queue import processing_queue

from logging_config import get_logger
logger = get_logger('services.atestados')


class AtestadosService:
    """Servico para operacoes de atestados."""

    def __init__(self, db: Session):
        self.db = db

    def listar_por_usuario(self, user_id: int) -> List[Atestado]:
        """Lista todos os atestados de um usuario."""
        return self.db.query(Atestado).filter(
            Atestado.user_id == user_id
        ).order_by(Atestado.created_at.desc()).all()

    def obter_por_id(self, atestado_id: int, user_id: int) -> Atestado:
        """
        Obtem um atestado por ID, verificando ownership.

        Raises:
            RecordNotFoundError: Se atestado nao existe ou nao pertence ao usuario
        """
        atestado = self.db.query(Atestado).filter(
            Atestado.id == atestado_id,
            Atestado.user_id == user_id
        ).first()

        if not atestado:
            raise RecordNotFoundError("Atestado", atestado_id)

        return atestado

    def criar(self, user_id: int, dados: AtestadoCreate) -> Atestado:
        """Cria um novo atestado manualmente."""
        novo_atestado = Atestado(
            user_id=user_id,
            descricao_servico=dados.descricao_servico,
            quantidade=dados.quantidade,
            unidade=dados.unidade,
            contratante=dados.contratante,
            data_emissao=dados.data_emissao
        )
        self.db.add(novo_atestado)
        self.db.commit()
        self.db.refresh(novo_atestado)
        logger.info(f"Atestado {novo_atestado.id} criado para usuario {user_id}")
        return novo_atestado

    def atualizar(self, atestado_id: int, user_id: int, dados: AtestadoUpdate) -> Atestado:
        """
        Atualiza um atestado existente.

        Raises:
            RecordNotFoundError: Se atestado nao existe ou nao pertence ao usuario
        """
        atestado = self.obter_por_id(atestado_id, user_id)

        # Atualiza apenas campos fornecidos
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

        self.db.commit()
        self.db.refresh(atestado)
        logger.info(f"Atestado {atestado_id} atualizado")
        return atestado

    def atualizar_servicos(self, atestado_id: int, user_id: int, dados: AtestadoServicosUpdate) -> Atestado:
        """
        Atualiza a lista de servicos de um atestado.

        Raises:
            RecordNotFoundError: Se atestado nao existe ou nao pertence ao usuario
        """
        atestado = self.obter_por_id(atestado_id, user_id)
        atestado.servicos_json = [s.model_dump() for s in dados.servicos_json]
        self.db.commit()
        self.db.refresh(atestado)
        logger.info(f"Servicos do atestado {atestado_id} atualizados ({len(dados.servicos_json)} servicos)")
        return atestado

    def excluir(self, atestado_id: int, user_id: int) -> bool:
        """
        Exclui um atestado e seu arquivo associado.

        Raises:
            RecordNotFoundError: Se atestado nao existe ou nao pertence ao usuario
        """
        atestado = self.obter_por_id(atestado_id, user_id)

        # Remover arquivo se existir
        if atestado.arquivo_path and os.path.exists(atestado.arquivo_path):
            try:
                os.remove(atestado.arquivo_path)
                logger.info(f"Arquivo removido: {atestado.arquivo_path}")
            except OSError as e:
                logger.warning(f"Erro ao remover arquivo: {e}")

        self.db.delete(atestado)
        self.db.commit()
        logger.info(f"Atestado {atestado_id} excluido")
        return True


class AtestadoUploadService:
    """Servico para upload e processamento de atestados."""

    ALLOWED_EXTENSIONS = ALLOWED_DOCUMENT_EXTENSIONS

    def __init__(self, db: Optional[Session] = None):
        self.db = db

    def validar_arquivo(self, file: UploadFile) -> str:
        """
        Valida o arquivo de upload.

        Args:
            file: Arquivo enviado

        Returns:
            Extensao do arquivo validada

        Raises:
            ValidationError: Se arquivo invalido
        """
        if not file.filename:
            raise ValidationError("Arquivo sem nome. Envie novamente.")

        file_ext = get_file_extension(file.filename)
        if file_ext not in self.ALLOWED_EXTENSIONS:
            raise ValidationError(
                f"Formato nao suportado. Use: {', '.join(self.ALLOWED_EXTENSIONS)}"
            )

        return file_ext

    def salvar_arquivo(self, file: UploadFile, user_id: int) -> str:
        """
        Salva o arquivo de upload no diretorio do usuario.

        Args:
            file: Arquivo enviado
            user_id: ID do usuario

        Returns:
            Caminho completo do arquivo salvo
        """
        file_ext = self.validar_arquivo(file)

        # Criar diretorio do usuario
        user_upload_dir = os.path.join(UPLOAD_DIR, str(user_id), "atestados")
        os.makedirs(user_upload_dir, exist_ok=True)

        # Gerar nome unico
        filename = f"{uuid.uuid4()}{file_ext}"
        filepath = os.path.join(user_upload_dir, filename)

        # Salvar arquivo
        with open(filepath, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        logger.info(f"Arquivo salvo: {filepath}")
        return filepath

    def enfileirar_processamento(
        self,
        user_id: int,
        filepath: str,
        callback=None
    ) -> str:
        """
        Enfileira um arquivo para processamento.

        Args:
            user_id: ID do usuario
            filepath: Caminho do arquivo
            callback: Funcao de callback ao finalizar

        Returns:
            ID do job criado
        """
        job_id = str(uuid.uuid4())

        processing_queue.add_job(
            job_id=job_id,
            user_id=user_id,
            file_path=filepath,
            job_type="atestado",
            callback=callback
        )

        logger.info(f"Job {job_id} enfileirado para usuario {user_id}")
        return job_id

    def processar_upload(
        self,
        file: UploadFile,
        user_id: int,
        callback=None
    ) -> str:
        """
        Processa upload completo: valida, salva e enfileira.

        Args:
            file: Arquivo enviado
            user_id: ID do usuario
            callback: Funcao de callback

        Returns:
            ID do job criado

        Raises:
            ValidationError: Se arquivo invalido
        """
        filepath = None
        try:
            filepath = self.salvar_arquivo(file, user_id)
            job_id = self.enfileirar_processamento(user_id, filepath, callback)
            return job_id
        except Exception as e:
            # Limpar arquivo em caso de erro
            if filepath and os.path.exists(filepath):
                os.remove(filepath)
            logger.error(f"Erro ao processar upload: {e}")
            raise

    def reprocessar_atestado(
        self,
        atestado: Atestado,
        callback=None
    ) -> str:
        """
        Reprocessa um atestado existente.

        Args:
            atestado: Atestado a reprocessar
            callback: Funcao de callback

        Returns:
            ID do novo job

        Raises:
            ValidationError: Se arquivo nao existe
        """
        if not atestado.arquivo_path or not os.path.exists(atestado.arquivo_path):
            raise ValidationError("Arquivo do atestado nao encontrado")

        job_id = self.enfileirar_processamento(
            atestado.user_id,
            atestado.arquivo_path,
            callback
        )
        logger.info(f"Reprocessamento do atestado {atestado.id} iniciado: job {job_id}")
        return job_id


# Instancia singleton para uso em callbacks
_upload_service = None


def get_upload_service() -> AtestadoUploadService:
    """Retorna instancia do servico de upload."""
    global _upload_service
    if _upload_service is None:
        _upload_service = AtestadoUploadService()
    return _upload_service
