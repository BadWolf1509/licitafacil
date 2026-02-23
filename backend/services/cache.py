"""
Sistema de cache com fallback.

Usa Redis se disponível, senão fallback para cache em memória com TTL.
Decorator @cached() para facilitar uso em funções.
"""

import hashlib
import json
import os
import time
from collections import OrderedDict
from functools import wraps
from threading import Lock
from typing import Any, Callable, Optional, TypeVar

from logging_config import get_logger

logger = get_logger('services.cache')

# Tipo genérico para retorno de funções
T = TypeVar('T')


class MemoryCache:
    """Cache em memória com suporte a TTL e evição LRU."""

    def __init__(self, max_size: int = 1000):
        self._cache: OrderedDict[str, tuple[Any, Optional[float]]] = OrderedDict()
        self._lock = Lock()
        self._max_size = max_size

    def get(self, key: str) -> Optional[Any]:
        """Obtém valor do cache se existir e não expirou."""
        with self._lock:
            if key not in self._cache:
                return None

            value, expires_at = self._cache[key]
            if expires_at and time.time() > expires_at:
                del self._cache[key]
                return None

            # Move para o final (LRU: marca como recentemente usado)
            self._cache.move_to_end(key)
            return value

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Define valor no cache com TTL opcional e evição LRU."""
        with self._lock:
            # Limpar entradas expiradas se cache cheio
            if len(self._cache) >= self._max_size:
                self._cleanup_expired()

            # Se ainda cheio, remover entrada menos recentemente usada (LRU)
            if len(self._cache) >= self._max_size:
                self._cache.popitem(last=False)  # Remove o primeiro (mais antigo)

            # Se a chave já existe, remover para atualizar a ordem
            if key in self._cache:
                del self._cache[key]

            expires_at = time.time() + ttl if ttl else None
            self._cache[key] = (value, expires_at)

    def delete(self, key: str) -> bool:
        """Remove valor do cache."""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    def clear(self) -> None:
        """Limpa todo o cache."""
        with self._lock:
            self._cache.clear()

    def _cleanup_expired(self) -> None:
        """Remove entradas expiradas."""
        now = time.time()
        expired = [
            k for k, (_, expires_at) in self._cache.items()
            if expires_at and now > expires_at
        ]
        for key in expired:
            del self._cache[key]

    def delete_by_prefix(self, prefix: str) -> int:
        """
        Remove todas as chaves que começam com o prefixo.

        Args:
            prefix: Prefixo das chaves a remover

        Returns:
            Número de chaves removidas
        """
        with self._lock:
            keys_to_delete = [
                k for k in self._cache.keys()
                if k.startswith(prefix)
            ]
            for key in keys_to_delete:
                del self._cache[key]
            return len(keys_to_delete)

    def stats(self) -> dict:
        """Retorna estatísticas do cache."""
        with self._lock:
            now = time.time()
            valid = sum(
                1 for _, (_, expires_at) in self._cache.items()
                if not expires_at or now <= expires_at
            )
            return {
                "backend": "memory",
                "total_keys": len(self._cache),
                "valid_keys": valid,
                "max_size": self._max_size
            }


class RedisCache:
    """Cache usando Redis."""

    def __init__(self, redis_url: str):
        try:
            import redis
            self._client = redis.from_url(redis_url, decode_responses=True)
            # Testar conexão
            self._client.ping()
            self._available = True
            logger.info("Redis cache conectado com sucesso")
        except Exception as e:
            logger.warning(f"Redis não disponível, usando fallback: {e}")
            self._client = None
            self._available = False

    @property
    def available(self) -> bool:
        return self._available

    def get(self, key: str) -> Optional[Any]:
        """Obtém valor do cache."""
        if not self._available:
            return None
        try:
            value = self._client.get(key)
            if value is None:
                return None
            return json.loads(value)
        except Exception as e:
            logger.error(f"Erro ao ler do Redis: {e}")
            return None

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Define valor no cache."""
        if not self._available:
            return
        try:
            serialized = json.dumps(value, default=str)
            if ttl:
                self._client.setex(key, ttl, serialized)
            else:
                self._client.set(key, serialized)
        except Exception as e:
            logger.error(f"Erro ao escrever no Redis: {e}")

    def delete(self, key: str) -> bool:
        """Remove valor do cache."""
        if not self._available:
            return False
        try:
            return self._client.delete(key) > 0
        except Exception as e:
            logger.error(f"Erro ao deletar do Redis: {e}")
            return False

    def clear(self) -> None:
        """Limpa todo o cache (CUIDADO em produção)."""
        if not self._available:
            return
        try:
            self._client.flushdb()
        except Exception as e:
            logger.error(f"Erro ao limpar Redis: {e}")

    def delete_by_prefix(self, prefix: str) -> int:
        """
        Remove todas as chaves que começam com o prefixo usando SCAN.

        Args:
            prefix: Prefixo das chaves a remover

        Returns:
            Número de chaves removidas
        """
        if not self._available:
            return 0
        try:
            count = 0
            cursor = 0
            pattern = f"{prefix}*"
            while True:
                cursor, keys = self._client.scan(cursor, match=pattern, count=100)
                if keys:
                    self._client.delete(*keys)
                    count += len(keys)
                if cursor == 0:
                    break
            return count
        except Exception as e:
            logger.error(f"Erro ao deletar por prefixo do Redis: {e}")
            return 0

    def stats(self) -> dict:
        """Retorna estatísticas do cache."""
        if not self._available:
            return {"backend": "redis", "available": False}
        try:
            info = self._client.info("keyspace")
            db_info = info.get("db0", {})
            return {
                "backend": "redis",
                "available": True,
                "keys": db_info.get("keys", 0) if isinstance(db_info, dict) else 0
            }
        except Exception as e:
            logger.debug(f"Erro ao obter estatísticas do Redis: {e}")
            return {"backend": "redis", "available": False}


class CacheManager:
    """
    Gerenciador de cache com fallback automático.

    Tenta usar Redis se REDIS_URL estiver configurado,
    senão usa cache em memória.
    """

    def __init__(self):
        redis_url = os.getenv("REDIS_URL")
        self._redis: Optional[RedisCache] = None
        self._memory = MemoryCache()

        if redis_url:
            self._redis = RedisCache(redis_url)
            if not self._redis.available:
                self._redis = None

        backend = "redis" if self._redis else "memory"
        logger.info(f"Cache inicializado com backend: {backend}")

    @property
    def backend(self) -> str:
        """Retorna o backend atual."""
        return "redis" if self._redis else "memory"

    def get(self, key: str) -> Optional[Any]:
        """Obtém valor do cache."""
        if self._redis:
            return self._redis.get(key)
        return self._memory.get(key)

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Define valor no cache."""
        if self._redis:
            self._redis.set(key, value, ttl)
        else:
            self._memory.set(key, value, ttl)

    def delete(self, key: str) -> bool:
        """Remove valor do cache."""
        if self._redis:
            return self._redis.delete(key)
        return self._memory.delete(key)

    def clear(self) -> None:
        """Limpa todo o cache."""
        if self._redis:
            self._redis.clear()
        self._memory.clear()

    def delete_by_prefix(self, prefix: str) -> int:
        """
        Remove todas as chaves que começam com o prefixo.

        Args:
            prefix: Prefixo das chaves a remover

        Returns:
            Número de chaves removidas
        """
        if self._redis:
            return self._redis.delete_by_prefix(prefix)
        return self._memory.delete_by_prefix(prefix)

    def stats(self) -> dict:
        """Retorna estatísticas do cache."""
        if self._redis:
            return self._redis.stats()
        return self._memory.stats()


# Instância global do cache
_cache_manager: Optional[CacheManager] = None


def get_cache() -> CacheManager:
    """Obtém instância global do cache."""
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = CacheManager()
    return _cache_manager


def _make_cache_key(prefix: str, func_name: str, args: tuple, kwargs: dict) -> str:
    """Gera chave de cache única baseada nos argumentos."""
    # Serializar argumentos de forma determinística
    key_data = {
        "func": func_name,
        "args": [str(a) for a in args],
        "kwargs": {k: str(v) for k, v in sorted(kwargs.items())}
    }
    key_str = json.dumps(key_data, sort_keys=True)
    key_hash = hashlib.md5(key_str.encode()).hexdigest()[:12]
    return f"{prefix}:{func_name}:{key_hash}"


def cached(
    ttl: int = 300,
    prefix: str = "cache",
    key_func: Optional[Callable[..., str]] = None
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Decorator para cachear resultado de funções.

    Args:
        ttl: Tempo de vida em segundos (default: 5 minutos)
        prefix: Prefixo para chave do cache
        key_func: Função customizada para gerar chave (opcional)

    Exemplo:
        @cached(ttl=60, prefix="user")
        def get_user(user_id: int) -> dict:
            return db.query(User).get(user_id)

        @cached(ttl=3600, key_func=lambda desc, unit: f"match:{desc}:{unit}")
        def find_matches(descricao: str, unidade: str) -> list:
            return matching_service.search(descricao, unidade)
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            cache = get_cache()

            # Gerar chave
            if key_func:
                cache_key = f"{prefix}:{key_func(*args, **kwargs)}"
            else:
                cache_key = _make_cache_key(prefix, func.__name__, args, kwargs)

            # Tentar obter do cache
            cached_value = cache.get(cache_key)
            if cached_value is not None:
                logger.debug(f"Cache hit: {cache_key}")
                return cached_value

            # Executar função e cachear
            logger.debug(f"Cache miss: {cache_key}")
            result = func(*args, **kwargs)

            # Não cachear None
            if result is not None:
                cache.set(cache_key, result, ttl)

            return result

        # Adicionar metodo para invalidar cache
        def invalidate(*args, **kwargs) -> None:
            cache = get_cache()
            if key_func:
                cache_key = f"{prefix}:{key_func(*args, **kwargs)}"
            else:
                cache_key = _make_cache_key(prefix, func.__name__, args, kwargs)
            cache.delete(cache_key)

        wrapper.invalidate = invalidate  # type: ignore[attr-defined]
        wrapper.cache_prefix = prefix  # type: ignore[attr-defined]

        return wrapper
    return decorator


def invalidate_prefix(prefix: str) -> int:
    """
    Invalida todas as chaves com um prefixo.

    Funciona tanto com Redis (usando SCAN) quanto com cache em memória.

    Args:
        prefix: Prefixo das chaves a invalidar

    Returns:
        Número de chaves invalidadas
    """
    cache = get_cache()
    count = cache.delete_by_prefix(prefix)
    logger.info(f"Invalidate prefix '{prefix}': {count} chaves removidas")
    return count
