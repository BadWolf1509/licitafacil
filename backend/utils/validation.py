"""
Utilitários de validação para uploads e outros dados.
"""
from typing import List, Optional

from fastapi import HTTPException, status

from config import validate_upload_file, ALLOWED_DOCUMENT_EXTENSIONS


def validate_upload_or_raise(
    filename: Optional[str],
    allowed_extensions: Optional[List[str]] = None
) -> str:
    """
    Valida arquivo de upload e levanta HTTPException em caso de erro.

    Args:
        filename: Nome do arquivo
        allowed_extensions: Lista de extensões permitidas

    Returns:
        Extensão do arquivo em minúsculas

    Raises:
        HTTPException: Se o arquivo for inválido (400 Bad Request)
    """
    if allowed_extensions is None:
        allowed_extensions = ALLOWED_DOCUMENT_EXTENSIONS

    try:
        return validate_upload_file(filename, allowed_extensions)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
