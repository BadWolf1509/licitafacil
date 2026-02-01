"""
Configuração de logging para o LicitaFacil.

Uso:
    from logging_config import get_logger
    logger = get_logger(__name__)
    logger.info("Mensagem de info")
    logger.error("Mensagem de erro")

Para logging estruturado (JSON):
    export LOG_FORMAT=json

Para logging com contexto de requisição:
    from logging_config import get_request_logger, set_correlation_id
    set_correlation_id("req-123")
    logger = get_request_logger(__name__)
    logger.info("Processando")  # Inclui correlation_id automaticamente

Para medir tempo de operações:
    from logging_config import log_timing
    with log_timing(logger, "operacao_lenta"):
        # código lento
"""
import json
import logging
import time
import uuid
from contextvars import ContextVar
from contextlib import contextmanager
from datetime import datetime
from functools import wraps
from typing import Optional, List, Any, Dict, Callable, TypeVar

import os
import sys
from pathlib import Path

# Context var para correlation ID (thread-safe)
_correlation_id: ContextVar[Optional[str]] = ContextVar('correlation_id', default=None)

T = TypeVar('T')

DEFAULT_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
CORRELATION_FORMAT = "%(asctime)s | %(levelname)-8s | [%(correlation_id)s] %(name)s | %(message)s"


class StructuredFormatter(logging.Formatter):
    """
    Formatter que produz logs em formato JSON estruturado.

    Útil para integração com ferramentas de análise de logs
    como ELK Stack, Datadog, CloudWatch, etc.
    """

    def format(self, record: logging.LogRecord) -> str:
        """Formata o registro de log como JSON."""
        log_data: Dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Adicionar correlation_id se disponível
        correlation_id = getattr(record, 'correlation_id', None) or _correlation_id.get()
        if correlation_id:
            log_data['correlation_id'] = correlation_id

        # Adicionar contexto extra se disponível
        if hasattr(record, 'context'):
            log_data['context'] = record.context

        # Adicionar informações de exceção se houver
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)

        # Adicionar campos extras do record
        for key, value in record.__dict__.items():
            if key not in ('name', 'msg', 'args', 'created', 'filename',
                           'funcName', 'levelname', 'levelno', 'lineno',
                           'module', 'msecs', 'pathname', 'process',
                           'processName', 'relativeCreated', 'stack_info',
                           'exc_info', 'exc_text', 'message', 'context'):
                if not key.startswith('_'):
                    log_data[key] = value

        return json.dumps(log_data, ensure_ascii=False, default=str)


class ContextLogger(logging.LoggerAdapter):
    """
    Logger adapter que permite adicionar contexto a todas as mensagens.

    Uso:
        logger = get_context_logger(__name__, user_id=123, job_id="abc")
        logger.info("Processando...")  # Inclui user_id e job_id automaticamente
    """

    def process(self, msg, kwargs):
        """Adiciona contexto extra ao log."""
        extra = kwargs.get('extra', {})
        extra.update(self.extra)
        kwargs['extra'] = extra
        return msg, kwargs


def setup_logging(
    level: Optional[str] = None,
    log_file: Optional[str] = None,
    format_string: Optional[str] = None,
    use_json: Optional[bool] = None
) -> None:
    """
    Configura o logging para toda a aplicação.

    Args:
        level: Nível de logging (DEBUG, INFO, WARNING, ERROR)
        log_file: Caminho para arquivo de log (opcional)
        format_string: Formato das mensagens de log
        use_json: Se True, usa formato JSON estruturado (útil para produção)

    Environment Variables:
        LOG_LEVEL: Nível de logging (default: INFO)
        LOG_FILE: Caminho para arquivo de log
        LOG_FORMAT: "json" para formato JSON, ou string de formato customizado
    """
    effective_level: str = level or os.getenv("LOG_LEVEL", "INFO") or "INFO"
    log_level = getattr(logging, effective_level.upper(), logging.INFO)

    # Determinar se deve usar JSON
    log_format_env = os.getenv("LOG_FORMAT", "")
    if use_json is None:
        use_json = log_format_env.lower() == "json"

    effective_format: str = format_string or DEFAULT_FORMAT

    # Criar formatter apropriado
    formatter: logging.Formatter
    if use_json:
        formatter = StructuredFormatter()
    else:
        formatter = logging.Formatter(effective_format)

    # Configuração básica
    handlers: List[Any] = []

    # Handler para console
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    handlers.append(console_handler)

    # Handler para arquivo (opcional)
    log_file_path = log_file or os.getenv("LOG_FILE")
    if log_file_path:
        log_path = Path(log_file_path)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_path, encoding='utf-8')
        file_handler.setLevel(log_level)
        # Arquivo sempre usa JSON para facilitar parsing
        file_handler.setFormatter(StructuredFormatter() if use_json else formatter)
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


def get_context_logger(name: str, **context) -> ContextLogger:
    """
    Obtém um logger com contexto adicional.

    O contexto é incluído automaticamente em todas as mensagens.
    Útil para rastrear requisições, jobs, ou usuários.

    Args:
        name: Nome do módulo (geralmente __name__)
        **context: Contexto a incluir em todas as mensagens

    Returns:
        ContextLogger configurado

    Example:
        logger = get_context_logger(__name__, user_id=123, job_id="abc-123")
        logger.info("Iniciando processamento")
        # Output: ... user_id=123, job_id=abc-123, message="Iniciando processamento"
    """
    base_logger = logging.getLogger(name)
    return ContextLogger(base_logger, context)


def log_with_context(
    logger: logging.Logger,
    level: int,
    message: str,
    **context
) -> None:
    """
    Loga uma mensagem com contexto adicional.

    Args:
        logger: Logger a usar
        level: Nível de log (logging.INFO, etc.)
        message: Mensagem de log
        **context: Contexto adicional a incluir

    Example:
        log_with_context(logger, logging.INFO, "Processando arquivo",
                        file_path="/tmp/doc.pdf", user_id=123)
    """
    logger.log(level, message, extra={'context': context})


# === Correlation ID (Request Tracking) ===

def set_correlation_id(correlation_id: Optional[str] = None) -> str:
    """
    Define o correlation ID para a requisição atual.

    Args:
        correlation_id: ID para usar (gera novo se None)

    Returns:
        O correlation ID definido
    """
    cid = correlation_id or str(uuid.uuid4())[:8]
    _correlation_id.set(cid)
    return cid


def get_correlation_id() -> Optional[str]:
    """Obtém o correlation ID da requisição atual."""
    return _correlation_id.get()


def clear_correlation_id() -> None:
    """Limpa o correlation ID (fim da requisição)."""
    _correlation_id.set(None)


class CorrelationFilter(logging.Filter):
    """Filter que adiciona correlation_id a todos os logs."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.correlation_id = get_correlation_id() or '-'
        return True


def get_request_logger(name: str) -> logging.Logger:
    """
    Obtém logger que inclui correlation_id automaticamente.

    Args:
        name: Nome do módulo

    Returns:
        Logger com correlation_id filter
    """
    logger = logging.getLogger(name)
    # Adicionar filter se não existir
    if not any(isinstance(f, CorrelationFilter) for f in logger.filters):
        logger.addFilter(CorrelationFilter())
    return logger


# === Timing Utilities ===

@contextmanager
def log_timing(
    logger: logging.Logger,
    operation: str,
    level: int = logging.DEBUG,
    threshold_ms: Optional[float] = None
):
    """
    Context manager para medir e logar tempo de operações.

    Args:
        logger: Logger a usar
        operation: Nome da operação
        level: Nível de log (default: DEBUG)
        threshold_ms: Se definido, só loga se tempo > threshold

    Example:
        with log_timing(logger, "query_database"):
            db.execute(query)
        # Output: [timing] query_database completed in 123.45ms
    """
    start = time.perf_counter()
    try:
        yield
    finally:
        elapsed_ms = (time.perf_counter() - start) * 1000
        if threshold_ms is None or elapsed_ms > threshold_ms:
            logger.log(
                level,
                f"[timing] {operation} completed in {elapsed_ms:.2f}ms"
            )


def timed(
    logger: Optional[logging.Logger] = None,
    operation: Optional[str] = None,
    level: int = logging.DEBUG,
    threshold_ms: Optional[float] = None
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Decorator para medir tempo de execução de funções.

    Args:
        logger: Logger a usar (usa nome do módulo se None)
        operation: Nome da operação (usa nome da função se None)
        level: Nível de log
        threshold_ms: Só loga se tempo > threshold

    Example:
        @timed(threshold_ms=100)
        def slow_function():
            time.sleep(0.2)
        # Loga porque demorou mais que 100ms
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        func_logger = logger or logging.getLogger(func.__module__)
        op_name = operation or func.__name__

        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            with log_timing(func_logger, op_name, level, threshold_ms):
                return func(*args, **kwargs)
        return wrapper
    return decorator


# === Sensitive Data Sanitization ===

SENSITIVE_KEYS = {
    'password', 'senha', 'secret', 'token', 'api_key', 'apikey',
    'authorization', 'auth', 'credential', 'private_key'
}


def sanitize_dict(data: Dict[str, Any], mask: str = '***') -> Dict[str, Any]:
    """
    Remove dados sensíveis de um dicionário para logging seguro.

    Args:
        data: Dicionário para sanitizar
        mask: String de substituição

    Returns:
        Dicionário com valores sensíveis mascarados
    """
    if not isinstance(data, dict):
        return data

    result = {}
    for key, value in data.items():
        key_lower = key.lower()
        if any(sensitive in key_lower for sensitive in SENSITIVE_KEYS):
            result[key] = mask
        elif isinstance(value, dict):
            result[key] = sanitize_dict(value, mask)  # type: ignore[assignment]
        elif isinstance(value, list):
            result[key] = [  # type: ignore[assignment]
                sanitize_dict(item, mask) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            result[key] = value
    return result


def log_sanitized(
    logger: logging.Logger,
    level: int,
    message: str,
    data: Dict[str, Any]
) -> None:
    """
    Loga dados com valores sensíveis mascarados.

    Args:
        logger: Logger a usar
        level: Nível de log
        message: Mensagem
        data: Dados a logar (serão sanitizados)
    """
    safe_data = sanitize_dict(data)
    logger.log(level, f"{message}: {safe_data}")


# Configurar logging na importação
setup_logging()
