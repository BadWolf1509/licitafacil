"""
Utilitários de validação para uploads e outros dados.
"""
from typing import List, Optional

from fastapi import HTTPException, UploadFile, status

from config import (
    ALLOWED_DOCUMENT_EXTENSIONS,
    validate_file_size,
    validate_upload_complete,
    validate_upload_file,
)


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


async def validate_upload_complete_or_raise(
    file: UploadFile,
    allowed_extensions: Optional[List[str]] = None,
    validate_content: bool = True
) -> str:
    """
    Validação completa de arquivo de upload (extensão, tamanho e MIME type).
    Levanta HTTPException em caso de erro.

    Args:
        file: Objeto UploadFile do FastAPI
        allowed_extensions: Lista de extensões permitidas
        validate_content: Se True, valida MIME type real do arquivo

    Returns:
        Extensão do arquivo em minúsculas

    Raises:
        HTTPException: Se alguma validação falhar (400 Bad Request)
    """
    try:
        return await validate_upload_complete(file, allowed_extensions, validate_content)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


def validate_file_size_or_raise(file_size: int) -> None:
    """
    Valida o tamanho do arquivo e levanta HTTPException em caso de erro.

    Args:
        file_size: Tamanho do arquivo em bytes

    Raises:
        HTTPException: Se o arquivo exceder o limite (413 Request Entity Too Large)
    """
    try:
        validate_file_size(file_size)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=str(e)
        )
