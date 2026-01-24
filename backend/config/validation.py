"""
Funcoes de validacao do LicitaFacil.
"""
from typing import List, Optional
from .base import ALLOWED_DOCUMENT_EXTENSIONS, get_file_extension
from .messages import Messages


def validate_upload_file(
    filename: Optional[str],
    allowed_extensions: Optional[List[str]] = None
) -> str:
    """
    Valida arquivo de upload e retorna a extensao.

    Args:
        filename: Nome do arquivo
        allowed_extensions: Lista de extensoes permitidas (usa ALLOWED_DOCUMENT_EXTENSIONS se None)

    Returns:
        Extensao do arquivo em minusculas

    Raises:
        ValueError: Se o arquivo for invalido
    """
    if not filename:
        raise ValueError(Messages.FILE_REQUIRED)

    if allowed_extensions is None:
        allowed_extensions = ALLOWED_DOCUMENT_EXTENSIONS

    ext = get_file_extension(filename)
    if ext not in allowed_extensions:
        raise ValueError(
            f"{Messages.INVALID_EXTENSION}. Use: {', '.join(allowed_extensions)}"
        )

    return ext
