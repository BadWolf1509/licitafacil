"""
Funções de validação do LicitaFacil.
"""
from typing import List, Optional

from .base import (
    ALLOWED_DOCUMENT_EXTENSIONS,
    ALLOWED_MIME_TYPES,
    MAX_UPLOAD_SIZE_BYTES,
    MAX_UPLOAD_SIZE_MB,
    get_file_extension,
)
from .messages import Messages

# Assinaturas de arquivo (magic bytes) para detecção de MIME type
FILE_SIGNATURES = {
    b'%PDF': 'application/pdf',
    b'\x89PNG\r\n\x1a\n': 'image/png',
    b'\xff\xd8\xff': 'image/jpeg',
    b'II*\x00': 'image/tiff',  # Little-endian TIFF
    b'MM\x00*': 'image/tiff',  # Big-endian TIFF
    b'BM': 'image/bmp',
    b'GIF87a': 'image/gif',
    b'GIF89a': 'image/gif',
}


def detect_mime_type(content: bytes) -> Optional[str]:
    """
    Detecta o MIME type real do arquivo baseado nos magic bytes.

    Args:
        content: Primeiros bytes do arquivo (mínimo 8 bytes)

    Returns:
        MIME type detectado ou None se desconhecido
    """
    # WEBP: RIFF....WEBP (assinatura distribuída em duas partes)
    if len(content) >= 12 and content.startswith(b'RIFF') and content[8:12] == b'WEBP':
        return 'image/webp'

    for signature, mime_type in FILE_SIGNATURES.items():
        if content.startswith(signature):
            return mime_type
    return None


def validate_upload_file(
    filename: Optional[str],
    allowed_extensions: Optional[List[str]] = None
) -> str:
    """
    Valida arquivo de upload e retorna a extensão.

    Args:
        filename: Nome do arquivo
        allowed_extensions: Lista de extensões permitidas (usa ALLOWED_DOCUMENT_EXTENSIONS se None)

    Returns:
        Extensão do arquivo em minúsculas

    Raises:
        ValueError: Se o arquivo for inválido
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


def validate_file_size(file_size: int) -> None:
    """
    Valida o tamanho do arquivo.

    Args:
        file_size: Tamanho do arquivo em bytes

    Raises:
        ValueError: Se o arquivo exceder o limite
    """
    if file_size > MAX_UPLOAD_SIZE_BYTES:
        raise ValueError(
            f"Arquivo muito grande. Tamanho máximo permitido: {MAX_UPLOAD_SIZE_MB}MB"
        )


def validate_mime_type(content: bytes, expected_extension: str) -> None:
    """
    Valida o MIME type real do arquivo comparando com a extensão esperada.

    Args:
        content: Primeiros bytes do arquivo (mínimo 8 bytes)
        expected_extension: Extensão declarada do arquivo

    Raises:
        ValueError: Se o MIME type não corresponder à extensão
    """
    detected_mime = detect_mime_type(content)

    if detected_mime is None:
        raise ValueError("Tipo de arquivo não reconhecido ou inválido")

    # Verificar se o MIME detectado corresponde à extensão declarada
    allowed_extensions_for_mime = ALLOWED_MIME_TYPES.get(detected_mime, [])
    if expected_extension not in allowed_extensions_for_mime:
        raise ValueError(
            f"O conteúdo do arquivo não corresponde à extensão {expected_extension}. "
            f"Tipo detectado: {detected_mime}"
        )


async def validate_upload_complete(
    file,
    allowed_extensions: Optional[List[str]] = None,
    validate_content: bool = True
) -> str:
    """
    Validação completa de arquivo de upload (extensão, tamanho e MIME type).

    Args:
        file: Objeto UploadFile do FastAPI
        allowed_extensions: Lista de extensões permitidas
        validate_content: Se True, valida MIME type real do arquivo

    Returns:
        Extensão do arquivo em minúsculas

    Raises:
        ValueError: Se alguma validação falhar
    """
    # 1. Validar extensão
    ext = validate_upload_file(file.filename, allowed_extensions)

    # 2. Validar tamanho (se disponível)
    if hasattr(file, 'size') and file.size is not None:
        validate_file_size(file.size)

    # 3. Validar MIME type real
    if validate_content:
        # Ler primeiros bytes para detectar tipo
        content = await file.read(1024)
        await file.seek(0)  # Voltar ao início

        if len(content) < 4:
            raise ValueError("Arquivo muito pequeno ou vazio")

        validate_mime_type(content, ext)

    return ext
