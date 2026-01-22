"""
Funções auxiliares reutilizáveis para routers.

Centraliza operações comuns de arquivos e diretórios,
evitando duplicação de código entre routers.
"""
import os
import shutil
from pathlib import Path

from fastapi import UploadFile

from config import UPLOAD_DIR
from logging_config import get_logger

logger = get_logger('utils.router_helpers')


def get_user_upload_dir(user_id: int, subfolder: str = "") -> Path:
    """
    Retorna o diretório de upload do usuário, criando-o se necessário.

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

    Args:
        filepath: Caminho do arquivo a remover

    Returns:
        True se removido com sucesso ou arquivo não existia, False em caso de erro
    """
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
    Salva arquivo de upload no destino especificado.

    Args:
        file: Arquivo de upload do FastAPI
        destination: Caminho completo de destino

    Raises:
        IOError: Se falhar ao salvar o arquivo
    """
    with open(destination, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)


