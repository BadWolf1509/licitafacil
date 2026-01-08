"""
Configuração de logging para o LicitaFacil.

Uso:
    from logging_config import get_logger
    logger = get_logger(__name__)
    logger.info("Mensagem de info")
    logger.error("Mensagem de erro")
"""
import logging
from typing import Optional, List, Any

import os
import sys
from pathlib import Path

DEFAULT_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"


def setup_logging(
    level: Optional[str] = None,
    log_file: Optional[str] = None,
    format_string: Optional[str] = None
) -> None:
    """
    Configura o logging para toda a aplicação.

    Args:
        level: Nível de logging (DEBUG, INFO, WARNING, ERROR)
        log_file: Caminho para arquivo de log (opcional)
        format_string: Formato das mensagens de log
    """
    effective_level: str = level or os.getenv("LOG_LEVEL", "INFO") or "INFO"
    log_level = getattr(logging, effective_level.upper(), logging.INFO)

    effective_format: str = format_string or os.getenv("LOG_FORMAT", DEFAULT_FORMAT) or DEFAULT_FORMAT

    # Configuração básica
    handlers: List[Any] = []

    # Handler para console
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(logging.Formatter(effective_format))
    handlers.append(console_handler)

    # Handler para arquivo (opcional)
    log_file_path = log_file or os.getenv("LOG_FILE")
    if log_file_path:
        log_path = Path(log_file_path)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_path, encoding='utf-8')
        file_handler.setLevel(log_level)
        file_handler.setFormatter(logging.Formatter(effective_format))
        handlers.append(file_handler)

    # Configurar root logger
    logging.basicConfig(
        level=log_level,
        format=effective_format,
        handlers=handlers
    )

    # Reduzir verbosidade de bibliotecas externas
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)
    logging.getLogger("google").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """
    Obtém um logger configurado para um módulo.

    Args:
        name: Nome do módulo (geralmente __name__)

    Returns:
        Logger configurado
    """
    return logging.getLogger(name)


# Configurar logging na importação
setup_logging()
