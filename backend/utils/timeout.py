"""
Utilitarios de timeout para operacoes longas.

Fornece decorators e context managers para limitar tempo de execucao.
"""
import asyncio
import signal
import threading
from contextlib import contextmanager
from functools import wraps
from typing import Callable, TypeVar

from logging_config import get_logger

logger = get_logger(__name__)

T = TypeVar('T')


class TimeoutError(Exception):
    """Excecao levantada quando uma operacao excede o timeout."""

    def __init__(self, message: str, timeout_seconds: int, operation: str = "Operation"):
        self.timeout_seconds = timeout_seconds
        self.operation = operation
        super().__init__(message)


class OCRTimeoutError(TimeoutError):
    """Excecao especifica para timeout de operacoes OCR."""
    pass


def with_timeout_sync(timeout_seconds: int, operation_name: str = "Operation"):
    """
    Decorator para adicionar timeout a funcoes sincronas.

    Usa threading para implementar timeout em funcoes bloqueantes.

    Args:
        timeout_seconds: Tempo maximo de execucao em segundos
        operation_name: Nome da operacao para logging

    Usage:
        @with_timeout_sync(30, "PDF extraction")
        def extract_text(file_path):
            ...
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            result = [None]
            exception = [None]

            def target():
                try:
                    result[0] = func(*args, **kwargs)
                except Exception as e:
                    exception[0] = e

            thread = threading.Thread(target=target)
            thread.daemon = True
            thread.start()
            thread.join(timeout=timeout_seconds)

            if thread.is_alive():
                logger.warning(
                    f"{operation_name} timeout after {timeout_seconds}s"
                )
                raise OCRTimeoutError(
                    f"{operation_name} excedeu o tempo limite de {timeout_seconds} segundos",
                    timeout_seconds=timeout_seconds,
                    operation=operation_name
                )

            if exception[0] is not None:
                raise exception[0]

            return result[0]  # type: ignore[return-value]
        return wrapper
    return decorator


def with_timeout_async(timeout_seconds: int, operation_name: str = "Operation"):
    """
    Decorator para adicionar timeout a funcoes assincronas.

    Args:
        timeout_seconds: Tempo maximo de execucao em segundos
        operation_name: Nome da operacao para logging

    Usage:
        @with_timeout_async(30, "API call")
        async def fetch_data(url):
            ...
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            try:
                return await asyncio.wait_for(
                    func(*args, **kwargs),  # type: ignore[arg-type]
                    timeout=timeout_seconds
                )
            except asyncio.TimeoutError:
                logger.warning(
                    f"{operation_name} timeout after {timeout_seconds}s"
                )
                raise OCRTimeoutError(
                    f"{operation_name} excedeu o tempo limite de {timeout_seconds} segundos",
                    timeout_seconds=timeout_seconds,
                    operation=operation_name
                )
        return wrapper  # type: ignore[return-value]
    return decorator


@contextmanager
def timeout_context(timeout_seconds: int, operation_name: str = "Operation"):
    """
    Context manager para timeout em bloco de codigo.

    Funciona apenas em sistemas Unix (usa SIGALRM).
    Em Windows, o timeout nao sera aplicado mas nao levantara erro.

    Args:
        timeout_seconds: Tempo maximo de execucao
        operation_name: Nome da operacao para logging

    Usage:
        with timeout_context(30, "Table extraction"):
            # codigo que pode demorar
            result = extract_tables(file_path)
    """
    def timeout_handler(signum, frame):
        raise OCRTimeoutError(
            f"{operation_name} excedeu o tempo limite de {timeout_seconds} segundos",
            timeout_seconds=timeout_seconds,
            operation=operation_name
        )

    # Signal so funciona em Unix
    if hasattr(signal, 'SIGALRM'):
        old_handler = signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(timeout_seconds)  # type: ignore[attr-defined]
        try:
            yield
        finally:
            signal.alarm(0)  # type: ignore[attr-defined]
            signal.signal(signal.SIGALRM, old_handler)
    else:
        # Windows: timeout via signal nao disponivel
        # Usar with_timeout_sync() ou run_with_timeout() para timeout cross-platform
        import os
        env = os.environ.get("ENVIRONMENT", "development")
        if env == "production":
            logger.warning(
                f"[TIMEOUT] SIGALRM nao disponivel em Windows para {operation_name}. "
                "Considere usar with_timeout_sync() para timeout cross-platform."
            )
        else:
            logger.debug(f"Timeout via signal nao disponivel neste sistema para {operation_name}")
        yield


def run_with_timeout(
    func: Callable[..., T],
    timeout_seconds: int,
    operation_name: str = "Operation",
    *args,
    **kwargs
) -> T:
    """
    Executa uma funcao com timeout usando threading.

    Funcao utilitaria para aplicar timeout sem usar decorator.

    Args:
        func: Funcao a executar
        timeout_seconds: Tempo maximo em segundos
        operation_name: Nome da operacao para logging
        *args, **kwargs: Argumentos para a funcao

    Returns:
        Resultado da funcao

    Raises:
        OCRTimeoutError: Se exceder o timeout
    """
    result = [None]
    exception = [None]

    def target():
        try:
            result[0] = func(*args, **kwargs)
        except Exception as e:
            exception[0] = e

    thread = threading.Thread(target=target)
    thread.daemon = True
    thread.start()
    thread.join(timeout=timeout_seconds)

    if thread.is_alive():
        logger.warning(
            f"{operation_name} timeout after {timeout_seconds}s"
        )
        raise OCRTimeoutError(
            f"{operation_name} excedeu o tempo limite de {timeout_seconds} segundos",
            timeout_seconds=timeout_seconds,
            operation=operation_name
        )

    if exception[0] is not None:
        raise exception[0]

    return result[0]  # type: ignore[return-value]
