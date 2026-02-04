"""
Funções auxiliares reutilizáveis para routers.

Centraliza operações comuns de arquivos e diretórios,
usando Supabase Storage em produção e filesystem local em desenvolvimento.
"""
import os
import io
from pathlib import Path
from typing import Optional

from fastapi import UploadFile

from config import UPLOAD_DIR
from services.storage_service import get_storage
from logging_config import get_logger

logger = get_logger('utils.router_helpers')


def get_storage_path(user_id: int, subfolder: str, filename: str) -> str:
    """
    Retorna o caminho de storage para um arquivo.

    Args:
        user_id: ID do usuário
        subfolder: Subpasta (ex: "atestados", "editais")
        filename: Nome do arquivo

    Returns:
        Caminho no formato "users/{user_id}/{subfolder}/{filename}"
    """
    return f"users/{user_id}/{subfolder}/{filename}"


def get_user_upload_dir(user_id: int, subfolder: str = "") -> Path:
    """
    Retorna o diretório de upload do usuário, criando-o se necessário.

    NOTA: Em ambiente serverless, usa /tmp que é efêmero.
    Prefira usar save_upload_file_to_storage() para persistência.

    Args:
        user_id: ID do usuário
        subfolder: Subpasta opcional (ex: "atestados", "editais")

    Returns:
        Path do diretório de upload do usuário
    """
    if subfolder:
        upload_dir = Path(UPLOAD_DIR) / str(user_id) / subfolder
    else:
        upload_dir = Path(UPLOAD_DIR) / str(user_id)

    upload_dir.mkdir(parents=True, exist_ok=True)
    return upload_dir


def safe_delete_file(filepath: str) -> bool:
    """
    Remove arquivo se existir, logando erros.
    Suporta tanto paths locais quanto paths de storage.

    Args:
        filepath: Caminho do arquivo a remover

    Returns:
        True se removido com sucesso ou arquivo não existia, False em caso de erro
    """
    storage = get_storage()

    # Se parece ser um path de storage (users/...)
    if filepath.startswith("users/"):
        return storage.delete(filepath)

    # Path local
    try:
        if os.path.exists(filepath):
            os.remove(filepath)
            logger.debug(f"Arquivo removido: {filepath}")
        return True
    except OSError as e:
        logger.warning(f"Erro ao remover arquivo {filepath}: {e}")
        return False


def save_upload_file(file: UploadFile, destination: str) -> None:
    """
    Salva arquivo de upload no destino especificado (filesystem local).

    NOTA: Em ambiente serverless, prefira usar save_upload_file_to_storage().

    Args:
        file: Arquivo de upload do FastAPI
        destination: Caminho completo de destino

    Raises:
        IOError: Se falhar ao salvar o arquivo
    """
    import shutil

    # Garantir que o diretório existe
    os.makedirs(os.path.dirname(destination), exist_ok=True)

    with open(destination, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)


def save_upload_file_to_storage(
    file: UploadFile,
    user_id: int,
    subfolder: str,
    filename: str,
    content_type: str = "application/pdf"
) -> str:
    """
    Salva arquivo de upload no storage (Supabase ou local).

    Args:
        file: Arquivo de upload do FastAPI
        user_id: ID do usuário
        subfolder: Subpasta (ex: "atestados", "editais")
        filename: Nome do arquivo
        content_type: Tipo MIME do arquivo

    Returns:
        Caminho do arquivo no storage (para salvar no banco)
    """
    storage = get_storage()
    storage_path = get_storage_path(user_id, subfolder, filename)

    # Ler conteúdo do arquivo
    file.file.seek(0)
    file_content = file.file.read()

    # Upload para storage
    storage.upload(io.BytesIO(file_content), storage_path, content_type)

    logger.info(f"[STORAGE] Arquivo salvo: {storage_path}")
    return storage_path


def get_file_from_storage(storage_path: str) -> Optional[bytes]:
    """
    Baixa arquivo do storage.

    Args:
        storage_path: Caminho do arquivo no storage

    Returns:
        Conteúdo do arquivo em bytes ou None se não existir
    """
    storage = get_storage()
    return storage.download(storage_path)


def file_exists_in_storage(storage_path: str) -> bool:
    """
    Verifica se arquivo existe no storage.

    Args:
        storage_path: Caminho do arquivo no storage

    Returns:
        True se existe, False caso contrário
    """
    storage = get_storage()
    return storage.exists(storage_path)


def validate_file_content(content: bytes, expected_extension: str) -> bool:
    """
    Valida se o conteúdo do arquivo corresponde à extensão esperada.

    Verifica os magic bytes do arquivo para garantir que não foi
    corrompido ou adulterado durante armazenamento/transmissão.

    Args:
        content: Conteúdo do arquivo em bytes
        expected_extension: Extensão esperada (ex: ".pdf", ".png")

    Returns:
        True se o conteúdo é válido, False caso contrário
    """
    if not content or len(content) < 4:
        logger.warning("[VALIDATION] Arquivo vazio ou muito pequeno")
        return False

    # Magic bytes por extensão
    MAGIC_BYTES = {
        ".pdf": [b'%PDF'],
        ".png": [b'\x89PNG\r\n\x1a\n'],
        ".jpg": [b'\xff\xd8\xff'],
        ".jpeg": [b'\xff\xd8\xff'],
        ".tiff": [b'II*\x00', b'MM\x00*'],
        ".tif": [b'II*\x00', b'MM\x00*'],
        ".bmp": [b'BM'],
    }

    ext = expected_extension.lower()
    signatures = MAGIC_BYTES.get(ext)

    if signatures is None:
        # Extensão desconhecida - aceitar (pode ser texto, etc)
        logger.debug(f"[VALIDATION] Extensão {ext} não tem validação de magic bytes")
        return True

    for sig in signatures:
        if content.startswith(sig):
            return True

    logger.warning(
        f"[VALIDATION] Conteúdo não corresponde à extensão {ext}. "
        f"Primeiros bytes: {content[:8].hex()}"
    )
    return False


def save_temp_file_from_storage(
    storage_path: str,
    local_path: str,
    validate_content: bool = True
) -> bool:
    """
    Baixa arquivo do storage para um arquivo local temporário.
    Útil para processar arquivos com bibliotecas que precisam de path local.

    Args:
        storage_path: Caminho do arquivo no storage
        local_path: Caminho local onde salvar
        validate_content: Se True, valida magic bytes do arquivo

    Returns:
        True se baixou com sucesso, False caso contrário
    """
    content = get_file_from_storage(storage_path)
    if content is None:
        logger.warning(f"[STORAGE] Arquivo não encontrado: {storage_path}")
        return False

    # Validar conteúdo se solicitado
    if validate_content:
        # Extrair extensão do path
        ext = os.path.splitext(storage_path)[1] or os.path.splitext(local_path)[1]
        if ext and not validate_file_content(content, ext):
            logger.error(
                f"[STORAGE] Validação falhou para {storage_path}. "
                "Arquivo pode estar corrompido ou adulterado."
            )
            return False

    os.makedirs(os.path.dirname(local_path), exist_ok=True)
    with open(local_path, 'wb') as f:
        f.write(content)

    return True
