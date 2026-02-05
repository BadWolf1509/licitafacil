"""
Utilitários para manipulação de arquivos.

Funções auxiliares para operações comuns com arquivos.
"""
import os
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
