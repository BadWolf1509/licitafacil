"""
Testes para validação de upload de arquivos.

Testa as funções de validação em config/validation.py e utils/validation.py.
"""
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from config import ALLOWED_DOCUMENT_EXTENSIONS, MAX_UPLOAD_SIZE_BYTES
from config.validation import (
    detect_mime_type,
    validate_file_size,
    validate_mime_type,
    validate_upload_complete,
    validate_upload_file,
)
from utils.validation import (
    validate_file_size_or_raise,
    validate_upload_complete_or_raise,
    validate_upload_or_raise,
)


class TestDetectMimeType:
    """Testes para detecção de MIME type via magic bytes."""

    def test_detect_pdf(self):
        """Detecta PDF corretamente."""
        content = b'%PDF-1.4 rest of file'
        assert detect_mime_type(content) == 'application/pdf'

    def test_detect_png(self):
        """Detecta PNG corretamente."""
        content = b'\x89PNG\r\n\x1a\n rest of file'
        assert detect_mime_type(content) == 'image/png'

    def test_detect_jpeg(self):
        """Detecta JPEG corretamente."""
        content = b'\xff\xd8\xff rest of file'
        assert detect_mime_type(content) == 'image/jpeg'

    def test_detect_tiff_little_endian(self):
        """Detecta TIFF little-endian corretamente."""
        content = b'II*\x00 rest of file'
        assert detect_mime_type(content) == 'image/tiff'

    def test_detect_tiff_big_endian(self):
        """Detecta TIFF big-endian corretamente."""
        content = b'MM\x00* rest of file'
        assert detect_mime_type(content) == 'image/tiff'

    def test_detect_bmp(self):
        """Detecta BMP corretamente."""
        content = b'BM rest of file'
        assert detect_mime_type(content) == 'image/bmp'

    def test_detect_gif(self):
        """Detecta GIF corretamente."""
        content = b'GIF89a rest of file'
        assert detect_mime_type(content) == 'image/gif'

    def test_detect_webp(self):
        """Detecta WEBP corretamente."""
        content = b'RIFF\x00\x00\x00\x00WEBPVP8 '
        assert detect_mime_type(content) == 'image/webp'

    def test_unknown_type_returns_none(self):
        """Tipo desconhecido retorna None."""
        content = b'random content here'
        assert detect_mime_type(content) is None

    def test_empty_content_returns_none(self):
        """Conteúdo vazio retorna None."""
        content = b''
        assert detect_mime_type(content) is None


class TestValidateUploadFile:
    """Testes para validação de nome de arquivo."""

    def test_valid_pdf_extension(self):
        """PDF com extensão válida passa."""
        ext = validate_upload_file('documento.pdf')
        assert ext == '.pdf'

    def test_valid_png_extension(self):
        """PNG com extensão válida passa."""
        ext = validate_upload_file('imagem.png')
        assert ext == '.png'

    def test_valid_jpeg_extension(self):
        """JPEG com extensão válida passa."""
        ext = validate_upload_file('foto.jpg')
        assert ext == '.jpg'

    def test_case_insensitive(self):
        """Extensão é case-insensitive."""
        ext = validate_upload_file('documento.PDF')
        assert ext == '.pdf'

    def test_invalid_extension_raises(self):
        """Extensão inválida levanta ValueError."""
        with pytest.raises(ValueError) as exc_info:
            validate_upload_file('arquivo.exe')
        assert "extensao" in str(exc_info.value).lower() or "extension" in str(exc_info.value).lower()

    def test_no_filename_raises(self):
        """Arquivo sem nome levanta ValueError."""
        with pytest.raises(ValueError):
            validate_upload_file(None)

    def test_empty_filename_raises(self):
        """Arquivo com nome vazio levanta ValueError."""
        with pytest.raises(ValueError):
            validate_upload_file('')

    def test_custom_allowed_extensions(self):
        """Permite especificar extensões customizadas."""
        ext = validate_upload_file('arquivo.txt', allowed_extensions=['.txt', '.md'])
        assert ext == '.txt'

    def test_custom_extension_not_in_list_raises(self):
        """Extensão não na lista customizada levanta ValueError."""
        with pytest.raises(ValueError):
            validate_upload_file('arquivo.pdf', allowed_extensions=['.txt', '.md'])


class TestValidateFileSize:
    """Testes para validação de tamanho de arquivo."""

    def test_small_file_passes(self):
        """Arquivo pequeno passa."""
        validate_file_size(1024)  # 1KB

    def test_max_size_passes(self):
        """Arquivo no limite máximo passa."""
        validate_file_size(MAX_UPLOAD_SIZE_BYTES)

    def test_oversized_file_raises(self):
        """Arquivo maior que limite levanta ValueError."""
        with pytest.raises(ValueError) as exc_info:
            validate_file_size(MAX_UPLOAD_SIZE_BYTES + 1)
        assert "grande" in str(exc_info.value).lower() or "size" in str(exc_info.value).lower()

    def test_zero_size_passes(self):
        """Arquivo vazio (0 bytes) passa validação de tamanho."""
        validate_file_size(0)


class TestValidateMimeType:
    """Testes para validação de MIME type."""

    def test_pdf_content_with_pdf_extension_passes(self):
        """PDF real com extensão .pdf passa."""
        content = b'%PDF-1.4 rest of file'
        validate_mime_type(content, '.pdf')  # Não deve levantar exceção

    def test_png_content_with_png_extension_passes(self):
        """PNG real com extensão .png passa."""
        content = b'\x89PNG\r\n\x1a\n rest of file'
        validate_mime_type(content, '.png')

    def test_jpeg_content_with_jpeg_extension_passes(self):
        """JPEG real com extensão .jpg passa."""
        content = b'\xff\xd8\xff rest of file'
        validate_mime_type(content, '.jpg')

    def test_mismatch_content_raises(self):
        """Conteúdo não corresponde à extensão levanta ValueError."""
        content = b'%PDF-1.4 rest of file'  # É PDF
        with pytest.raises(ValueError) as exc_info:
            validate_mime_type(content, '.png')  # Mas diz ser PNG
        assert "corresponde" in str(exc_info.value).lower() or "correspond" in str(exc_info.value).lower()

    def test_unknown_content_raises(self):
        """Conteúdo desconhecido levanta ValueError."""
        content = b'random content'
        with pytest.raises(ValueError):
            validate_mime_type(content, '.pdf')


class TestValidateUploadComplete:
    """Testes para validação completa de upload."""

    @pytest.fixture
    def mock_pdf_file(self):
        """Cria mock de arquivo PDF válido."""
        file = MagicMock()
        file.filename = 'documento.pdf'
        file.size = 1024
        file.read = AsyncMock(return_value=b'%PDF-1.4 test content here')
        file.seek = AsyncMock()
        return file

    @pytest.fixture
    def mock_png_file(self):
        """Cria mock de arquivo PNG válido."""
        file = MagicMock()
        file.filename = 'imagem.png'
        file.size = 2048
        file.read = AsyncMock(return_value=b'\x89PNG\r\n\x1a\n test content')
        file.seek = AsyncMock()
        return file

    @pytest.mark.asyncio
    async def test_valid_pdf_passes(self, mock_pdf_file):
        """PDF válido passa todas as validações."""
        ext = await validate_upload_complete(mock_pdf_file)
        assert ext == '.pdf'

    @pytest.mark.asyncio
    async def test_valid_png_passes(self, mock_png_file):
        """PNG válido passa todas as validações."""
        ext = await validate_upload_complete(mock_png_file)
        assert ext == '.png'

    @pytest.mark.asyncio
    async def test_invalid_extension_raises(self):
        """Extensão inválida levanta ValueError."""
        file = MagicMock()
        file.filename = 'virus.exe'
        file.size = 1024

        with pytest.raises(ValueError):
            await validate_upload_complete(file)

    @pytest.mark.asyncio
    async def test_oversized_file_raises(self):
        """Arquivo muito grande levanta ValueError."""
        file = MagicMock()
        file.filename = 'grande.pdf'
        file.size = MAX_UPLOAD_SIZE_BYTES + 1

        with pytest.raises(ValueError):
            await validate_upload_complete(file)

    @pytest.mark.asyncio
    async def test_mime_mismatch_raises(self):
        """MIME type incompatível levanta ValueError."""
        file = MagicMock()
        file.filename = 'fake.pdf'  # Diz ser PDF
        file.size = 1024
        file.read = AsyncMock(return_value=b'\x89PNG\r\n\x1a\n test')  # Mas é PNG
        file.seek = AsyncMock()

        with pytest.raises(ValueError):
            await validate_upload_complete(file, validate_content=True)

    @pytest.mark.asyncio
    async def test_skip_content_validation(self):
        """Permite pular validação de conteúdo."""
        file = MagicMock()
        file.filename = 'documento.pdf'
        file.size = 1024
        # Conteúdo não é validado

        ext = await validate_upload_complete(file, validate_content=False)
        assert ext == '.pdf'

    @pytest.mark.asyncio
    async def test_empty_file_raises(self):
        """Arquivo vazio levanta ValueError."""
        file = MagicMock()
        file.filename = 'vazio.pdf'
        file.size = 0
        file.read = AsyncMock(return_value=b'')
        file.seek = AsyncMock()

        with pytest.raises(ValueError):
            await validate_upload_complete(file, validate_content=True)


class TestHTTPExceptionWrappers:
    """Testes para wrappers que levantam HTTPException."""

    def test_validate_upload_or_raise_valid(self):
        """Arquivo válido retorna extensão."""
        ext = validate_upload_or_raise('doc.pdf')
        assert ext == '.pdf'

    def test_validate_upload_or_raise_invalid_raises_400(self):
        """Arquivo inválido levanta HTTPException 400."""
        with pytest.raises(HTTPException) as exc_info:
            validate_upload_or_raise('virus.exe')
        assert exc_info.value.status_code == 400

    def test_validate_file_size_or_raise_valid(self):
        """Tamanho válido não levanta exceção."""
        validate_file_size_or_raise(1024)  # Não deve levantar

    def test_validate_file_size_or_raise_oversized_raises_413(self):
        """Arquivo grande levanta HTTPException 413."""
        with pytest.raises(HTTPException) as exc_info:
            validate_file_size_or_raise(MAX_UPLOAD_SIZE_BYTES + 1)
        assert exc_info.value.status_code == 413

    @pytest.mark.asyncio
    async def test_validate_upload_complete_or_raise_valid(self):
        """Upload completo válido retorna extensão."""
        file = MagicMock()
        file.filename = 'doc.pdf'
        file.size = 1024
        file.read = AsyncMock(return_value=b'%PDF-1.4 content')
        file.seek = AsyncMock()

        ext = await validate_upload_complete_or_raise(file)
        assert ext == '.pdf'

    @pytest.mark.asyncio
    async def test_validate_upload_complete_or_raise_invalid_raises_400(self):
        """Upload inválido levanta HTTPException 400."""
        file = MagicMock()
        file.filename = 'virus.exe'
        file.size = 1024

        with pytest.raises(HTTPException) as exc_info:
            await validate_upload_complete_or_raise(file)
        assert exc_info.value.status_code == 400


class TestAllowedExtensions:
    """Testes para extensões permitidas."""

    def test_pdf_in_allowed_extensions(self):
        """PDF está nas extensões permitidas."""
        assert '.pdf' in ALLOWED_DOCUMENT_EXTENSIONS

    def test_common_image_formats_allowed(self):
        """Formatos de imagem comuns estão permitidos."""
        assert '.png' in ALLOWED_DOCUMENT_EXTENSIONS
        assert '.jpg' in ALLOWED_DOCUMENT_EXTENSIONS
        assert '.jpeg' in ALLOWED_DOCUMENT_EXTENSIONS
        assert '.gif' in ALLOWED_DOCUMENT_EXTENSIONS
        assert '.webp' in ALLOWED_DOCUMENT_EXTENSIONS

    def test_dangerous_extensions_not_allowed(self):
        """Extensões perigosas não estão permitidas."""
        dangerous = ['.exe', '.bat', '.cmd', '.ps1', '.sh', '.js', '.vbs']
        for ext in dangerous:
            assert ext not in ALLOWED_DOCUMENT_EXTENSIONS
