"""
Modo de processamento adaptativo para ambientes serverless e tradicionais.

Em ambiente serverless (Vercel), o processamento é feito de forma síncrona.
Em ambiente tradicional (VPS/Docker), usa fila assíncrona.
"""
import os
from enum import Enum
from typing import Optional

from logging_config import get_logger

logger = get_logger('services.processing_mode')


class ProcessingMode(Enum):
    """Modos de processamento disponíveis."""
    SYNC = "sync"           # Síncrono - para serverless
    ASYNC_QUEUE = "queue"   # Fila assíncrona - para VPS/Docker


def detect_processing_mode() -> ProcessingMode:
    """
    Detecta automaticamente o modo de processamento baseado no ambiente.

    Returns:
        ProcessingMode apropriado para o ambiente
    """
    # Vercel define estas variáveis
    is_vercel = bool(os.getenv("VERCEL") or os.getenv("VERCEL_ENV"))

    # AWS Lambda
    is_lambda = bool(os.getenv("AWS_LAMBDA_FUNCTION_NAME"))

    # Google Cloud Functions
    is_gcf = bool(os.getenv("FUNCTION_TARGET"))

    # Forçar modo via variável de ambiente
    forced_mode = os.getenv("PROCESSING_MODE", "").lower()
    if forced_mode == "sync":
        return ProcessingMode.SYNC
    elif forced_mode == "queue":
        return ProcessingMode.ASYNC_QUEUE

    # Auto-detectar
    if is_vercel or is_lambda or is_gcf:
        logger.info("[PROCESSING] Ambiente serverless detectado - usando modo síncrono")
        return ProcessingMode.SYNC

    logger.info("[PROCESSING] Ambiente tradicional - usando fila assíncrona")
    return ProcessingMode.ASYNC_QUEUE


# Singleton para modo de processamento
_processing_mode: Optional[ProcessingMode] = None


def get_processing_mode() -> ProcessingMode:
    """Retorna o modo de processamento atual."""
    global _processing_mode
    if _processing_mode is None:
        _processing_mode = detect_processing_mode()
    return _processing_mode


def is_serverless() -> bool:
    """Verifica se está rodando em ambiente serverless."""
    return get_processing_mode() == ProcessingMode.SYNC
