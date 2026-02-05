"""
Servico centralizado de upload de arquivos.

Fornece uma interface unificada para validacao e upload,
combinando as funcionalidades de validation.py e router_helpers.py.
"""
import uuid
from typing import Tuple, Optional, List

from fastapi import UploadFile

from utils.validation import validate_upload_complete_or_raise
from utils.router_helpers import (
    save_upload_file_to_storage,
    safe_delete_file,
    file_exists_in_storage,
    get_file_from_storage
)
from logging_config import get_logger

logger = get_logger('services.file_upload')


class FileUploadService:
    """
    Servico para upload de arquivos com validacao.

    Centraliza a logica de:
    - Validacao de extensao, tamanho e MIME type
    - Upload para storage (Supabase ou local)
    - Geracao de nomes unicos
    - Cleanup em caso de erro
    """

    def __init__(self, allowed_extensions: Optional[List[str]] = None):
        """
        Inicializa o servico.

        Args:
            allowed_extensions: Lista de extensoes permitidas (ex: [".pdf", ".png"])
                              Se None, usa validacao padrao
        """
        self.allowed_extensions = allowed_extensions

    async def validate_and_upload(
        self,
        file: UploadFile,
        user_id: int,
        subfolder: str,
        custom_filename: Optional[str] = None
    ) -> Tuple[str, str]:
        """
        Valida e faz upload de arquivo.

        Args:
            file: Arquivo de upload do FastAPI
            user_id: ID do usuario
            subfolder: Subpasta no storage (ex: "atestados", "editais")
            custom_filename: Nome customizado (opcional, gera UUID se nao informado)

        Returns:
            Tupla (storage_path, original_filename)

        Raises:
            HTTPException: Se validacao falhar
        """
        # Validar arquivo (extensao, tamanho, MIME type)
        file_ext = await validate_upload_complete_or_raise(file, self.allowed_extensions)

        # Gerar nome unico
        if custom_filename:
            filename = custom_filename
        else:
            filename = f"{uuid.uuid4()}{file_ext}"

        # Capturar nome original antes do upload
        original_filename = file.filename or "documento"

        # Determinar content type
        content_type = file.content_type or "application/octet-stream"

        # Upload para storage
        storage_path = save_upload_file_to_storage(
            file=file,
            user_id=user_id,
            subfolder=subfolder,
            filename=filename,
            content_type=content_type
        )

        logger.info(f"[UPLOAD] Arquivo salvo: {storage_path} (original: {original_filename})")

        return storage_path, original_filename

    def delete(self, storage_path: str) -> bool:
        """
        Remove arquivo do storage.

        Args:
            storage_path: Caminho do arquivo no storage

        Returns:
            True se removido com sucesso
        """
        return safe_delete_file(storage_path)

    def exists(self, storage_path: str) -> bool:
        """
        Verifica se arquivo existe no storage.

        Args:
            storage_path: Caminho do arquivo no storage

        Returns:
            True se existe
        """
        return file_exists_in_storage(storage_path)

    def download(self, storage_path: str) -> Optional[bytes]:
        """
        Baixa conteudo do arquivo.

        Args:
            storage_path: Caminho do arquivo no storage

        Returns:
            Conteudo em bytes ou None se nao existir
        """
        return get_file_from_storage(storage_path)


# Instancia padrao para uso como dependency
_default_service: Optional[FileUploadService] = None


def get_upload_service() -> FileUploadService:
    """
    Retorna instancia do servico de upload.

    Uso como FastAPI dependency:
        @router.post("/upload")
        async def upload(
            file: UploadFile,
            upload_service: FileUploadService = Depends(get_upload_service)
        ):
            path, name = await upload_service.validate_and_upload(file, user_id, "docs")
    """
    global _default_service
    if _default_service is None:
        _default_service = FileUploadService()
    return _default_service


def get_document_upload_service() -> FileUploadService:
    """Servico pre-configurado para documentos (PDF, imagens)."""
    from config import ALLOWED_DOCUMENT_EXTENSIONS
    return FileUploadService(allowed_extensions=ALLOWED_DOCUMENT_EXTENSIONS)


def get_pdf_upload_service() -> FileUploadService:
    """Servico pre-configurado apenas para PDFs."""
    from config import ALLOWED_PDF_EXTENSIONS
    return FileUploadService(allowed_extensions=ALLOWED_PDF_EXTENSIONS)
