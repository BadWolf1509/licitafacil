"""
Utilitários para calcular hash de arquivos.

Usado para identificar arquivos unicamente no cache de resultados OCR.
"""
import hashlib
from pathlib import Path
from typing import Union

from logging_config import get_logger

logger = get_logger(__name__)

# Tamanho do chunk para leitura de arquivos grandes
CHUNK_SIZE = 8192


def compute_file_hash(file_path: Union[str, Path], algorithm: str = "sha256") -> str:
    """
    Calcula o hash de um arquivo.

    Args:
        file_path: Caminho do arquivo
        algorithm: Algoritmo de hash (sha256, md5, sha1)

    Returns:
        Hash hexadecimal do arquivo

    Raises:
        FileNotFoundError: Se o arquivo não existir
        ValueError: Se o algoritmo não for suportado
    """
    file_path = Path(file_path)

    if not file_path.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {file_path}")

    if algorithm not in hashlib.algorithms_available:
        raise ValueError(f"Algoritmo não suportado: {algorithm}")

    hasher = hashlib.new(algorithm)

    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(CHUNK_SIZE), b''):
            hasher.update(chunk)

    return hasher.hexdigest()


def compute_content_hash(content: bytes, algorithm: str = "sha256") -> str:
    """
    Calcula o hash de um conteúdo em bytes.

    Args:
        content: Conteúdo em bytes
        algorithm: Algoritmo de hash

    Returns:
        Hash hexadecimal do conteúdo
    """
    if algorithm not in hashlib.algorithms_available:
        raise ValueError(f"Algoritmo não suportado: {algorithm}")

    hasher = hashlib.new(algorithm)
    hasher.update(content)
    return hasher.hexdigest()


def get_file_cache_key(file_path: Union[str, Path], prefix: str = "file") -> str:
    """
    Gera uma chave de cache única para um arquivo.

    Combina o hash do arquivo com o prefixo para criar uma chave.

    Args:
        file_path: Caminho do arquivo
        prefix: Prefixo para a chave de cache

    Returns:
        Chave de cache no formato "prefix:hash[:12]"
    """
    file_hash = compute_file_hash(file_path)
    # Usar apenas os primeiros 12 caracteres para chave mais curta
    return f"{prefix}:{file_hash[:12]}"


def get_ocr_cache_key(file_path: Union[str, Path], dpi: int = 300) -> str:
    """
    Gera uma chave de cache específica para resultados OCR.

    Inclui o DPI na chave pois diferentes DPIs produzem resultados diferentes.

    Args:
        file_path: Caminho do arquivo
        dpi: DPI usado no OCR

    Returns:
        Chave de cache no formato "ocr:hash:dpi"
    """
    file_hash = compute_file_hash(file_path)
    return f"ocr:{file_hash[:12]}:{dpi}"


def get_table_extraction_cache_key(file_path: Union[str, Path]) -> str:
    """
    Gera uma chave de cache para resultados de extração de tabela.

    Args:
        file_path: Caminho do arquivo

    Returns:
        Chave de cache no formato "table:hash"
    """
    file_hash = compute_file_hash(file_path)
    return f"table:{file_hash[:12]}"


def get_text_extraction_cache_key(file_path: Union[str, Path]) -> str:
    """
    Gera uma chave de cache para resultados de extração de texto.

    Args:
        file_path: Caminho do arquivo

    Returns:
        Chave de cache no formato "text:hash"
    """
    file_hash = compute_file_hash(file_path)
    return f"text:{file_hash[:12]}"
