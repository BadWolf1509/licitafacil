"""
Decorator de retry para operações que podem falhar.

Implementa retry com backoff exponencial para operações
que podem ter falhas transientes (rede, banco, APIs externas).
"""

import time
from functools import wraps
from typing import Tuple, Type, Union

from logging_config import get_logger

logger = get_logger('utils.retry')


def retry(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: Union[Type[Exception], Tuple[Type[Exception], ...]] = (Exception,),
    on_retry: callable = None
):
    """
    Decorator que adiciona retry com backoff exponencial.

    Args:
        max_attempts: Número máximo de tentativas (default: 3)
        delay: Delay inicial em segundos entre tentativas (default: 1.0)
        backoff: Multiplicador do delay a cada tentativa (default: 2.0)
        exceptions: Exceção ou tupla de exceções para capturar (default: Exception)
        on_retry: Callback chamado antes de cada retry (recebe attempt, exception, delay)

    Exemplo:
        @retry(max_attempts=3, delay=1.0, exceptions=(ConnectionError, TimeoutError))
        def fetch_data():
            return requests.get(url)

        @retry(max_attempts=5, backoff=1.5, on_retry=lambda a, e, d: logger.warning(f"Retry {a}"))
        def save_to_database(data):
            db.save(data)
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            attempts = 0
            current_delay = delay
            last_exception = None

            while attempts < max_attempts:
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    attempts += 1
                    last_exception = e

                    if attempts >= max_attempts:
                        logger.error(
                            f"[retry] {func.__name__} falhou após {max_attempts} tentativas: {e}"
                        )
                        raise

                    logger.warning(
                        f"[retry] {func.__name__} tentativa {attempts}/{max_attempts} "
                        f"falhou: {e}. Tentando novamente em {current_delay:.1f}s..."
                    )

                    if on_retry:
                        on_retry(attempts, e, current_delay)

                    time.sleep(current_delay)
                    current_delay *= backoff

            # Não deveria chegar aqui, mas por segurança
            if last_exception:
                raise last_exception

        return wrapper
    return decorator


async def async_retry(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: Union[Type[Exception], Tuple[Type[Exception], ...]] = (Exception,),
    on_retry: callable = None
):
    """
    Decorator que adiciona retry com backoff exponencial para funções async.

    Args:
        max_attempts: Número máximo de tentativas (default: 3)
        delay: Delay inicial em segundos entre tentativas (default: 1.0)
        backoff: Multiplicador do delay a cada tentativa (default: 2.0)
        exceptions: Exceção ou tupla de exceções para capturar (default: Exception)
        on_retry: Callback chamado antes de cada retry (recebe attempt, exception, delay)

    Exemplo:
        @async_retry(max_attempts=3, exceptions=(aiohttp.ClientError,))
        async def fetch_data():
            async with aiohttp.ClientSession() as session:
                return await session.get(url)
    """
    import asyncio

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            attempts = 0
            current_delay = delay
            last_exception = None

            while attempts < max_attempts:
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    attempts += 1
                    last_exception = e

                    if attempts >= max_attempts:
                        logger.error(
                            f"[async_retry] {func.__name__} falhou após {max_attempts} tentativas: {e}"
                        )
                        raise

                    logger.warning(
                        f"[async_retry] {func.__name__} tentativa {attempts}/{max_attempts} "
                        f"falhou: {e}. Tentando novamente em {current_delay:.1f}s..."
                    )

                    if on_retry:
                        on_retry(attempts, e, current_delay)

                    await asyncio.sleep(current_delay)
                    current_delay *= backoff

            if last_exception:
                raise last_exception

        return wrapper
    return decorator
