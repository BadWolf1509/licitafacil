"""
Utilitários para manipulação de arquivos.

Funções auxiliares para operações comuns com arquivos.
"""
import os
import tempfile
from contextlib import contextmanager

from logging_config import get_logger

logger = get_logger('utils.file_helpers')


def cleanup_temp_file(temp_path: str) -> bool:
    """
    Remove arquivo temporário com tratamento de erros detalhado.

    Args:
        temp_path: Caminho do arquivo temporário a remover

    Returns:
        True se removido ou não existia, False em caso de erro.
    """
    if not temp_path or not os.path.exists(temp_path):
        return True

    try:
        os.unlink(temp_path)
        logger.debug(f"Temp file removido: {temp_path}")
        return True
    except FileNotFoundError:
        logger.debug(f"Temp file ja removido: {temp_path}")
        return True
    except PermissionError as e:
        logger.warning(f"Sem permissao para remover temp file: {e}")
        return False
    except OSError as e:
        logger.error(f"Erro ao limpar temp file {temp_path}: {e}")
        return False


@contextmanager
def temp_file_from_storage(storage_path: str, save_func, suffix: str = ".pdf"):
    """
    Context manager que baixa arquivo do storage para temp file e garante cleanup.

    Args:
        storage_path: Caminho do arquivo no storage
        save_func: Funcao que salva do storage para path local (storage_path, local_path) -> bool
        suffix: Extensao do arquivo temporario

    Yields:
        str: Caminho do arquivo temporario

    Raises:
        IOError: Se falhar ao baixar arquivo do storage
    """
    temp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    temp_path = temp.name
    temp.close()

    try:
        if not save_func(storage_path, temp_path):
            raise IOError(f"Falha ao baixar arquivo do storage: {storage_path}")
        yield temp_path
    finally:
        cleanup_temp_file(temp_path)
