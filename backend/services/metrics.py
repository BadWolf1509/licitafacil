"""
Metricas Prometheus para observabilidade do LicitaFacil.

Expoe metricas de processamento, fila e requisicoes HTTP.
"""
from prometheus_client import REGISTRY, Counter, Gauge, Histogram, Info
from prometheus_client.exposition import CONTENT_TYPE_LATEST, generate_latest

from logging_config import get_logger

logger = get_logger('services.metrics')


# === Metricas de Processamento de Jobs ===

jobs_total = Counter(
    'licitafacil_jobs_total',
    'Total de jobs processados',
    ['type', 'status']  # labels: type=atestado/edital, status=completed/failed/cancelled
)

jobs_duration_seconds = Histogram(
    'licitafacil_job_duration_seconds',
    'Duracao do processamento de jobs em segundos',
    ['type', 'pipeline'],  # labels: atestado/edital, pipeline: NATIVE_TEXT/LOCAL_OCR/VISION_AI
    buckets=[1, 5, 10, 30, 60, 120, 300, 600]  # ate 10 min
)

queue_size = Gauge(
    'licitafacil_queue_size',
    'Tamanho atual da fila de processamento'
)

processing_count = Gauge(
    'licitafacil_processing_count',
    'Quantidade de jobs em processamento'
)


# === Metricas HTTP ===

http_requests_total = Counter(
    'licitafacil_http_requests_total',
    'Total de requisicoes HTTP',
    ['method', 'endpoint', 'status']
)

http_request_duration_seconds = Histogram(
    'licitafacil_http_request_duration_seconds',
    'Duracao das requisicoes HTTP em segundos',
    ['method', 'endpoint'],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10]
)


# === Metricas de Upload ===

uploads_total = Counter(
    'licitafacil_uploads_total',
    'Total de uploads',
    ['type', 'status']  # labels: atestado/edital, status: success/failed
)

upload_size_bytes = Histogram(
    'licitafacil_upload_size_bytes',
    'Tamanho dos uploads em bytes',
    ['type'],
    buckets=[10240, 102400, 1048576, 5242880, 10485760, 52428800]  # 10KB a 50MB
)


# === Metricas de Sistema ===

app_info = Info(
    'licitafacil_app',
    'Informacoes da aplicacao'
)


# === Funcoes Auxiliares ===

def set_app_info(version: str, environment: str):
    """Define informacoes da aplicacao."""
    app_info.info({
        'version': version,
        'environment': environment
    })


def record_job_completed(job_type: str, pipeline: str, duration_seconds: float):
    """Registra um job completado."""
    jobs_total.labels(type=job_type, status='completed').inc()
    jobs_duration_seconds.labels(type=job_type, pipeline=pipeline or 'unknown').observe(duration_seconds)


def record_job_failed(job_type: str):
    """Registra um job que falhou."""
    jobs_total.labels(type=job_type, status='failed').inc()


def record_job_cancelled(job_type: str):
    """Registra um job cancelado."""
    jobs_total.labels(type=job_type, status='cancelled').inc()


def update_queue_metrics(queue_len: int, processing_len: int):
    """Atualiza metricas da fila."""
    queue_size.set(queue_len)
    processing_count.set(processing_len)


def record_upload(upload_type: str, success: bool, size_bytes: int = 0):
    """Registra um upload."""
    status = 'success' if success else 'failed'
    uploads_total.labels(type=upload_type, status=status).inc()
    if success and size_bytes > 0:
        upload_size_bytes.labels(type=upload_type).observe(size_bytes)


def record_http_request(method: str, endpoint: str, status_code: int, duration_seconds: float):
    """Registra uma requisicao HTTP."""
    # Normalizar endpoint para evitar alta cardinalidade
    normalized_endpoint = _normalize_endpoint(endpoint)
    status_class = f"{status_code // 100}xx"

    http_requests_total.labels(
        method=method,
        endpoint=normalized_endpoint,
        status=status_class
    ).inc()

    http_request_duration_seconds.labels(
        method=method,
        endpoint=normalized_endpoint
    ).observe(duration_seconds)


def _normalize_endpoint(path: str) -> str:
    """Normaliza endpoint removendo IDs para evitar alta cardinalidade."""
    import re
    # Substituir IDs numericos por {id}
    normalized = re.sub(r'/\d+', '/{id}', path)
    # Substituir UUIDs por {uuid}
    normalized = re.sub(
        r'/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}',
        '/{uuid}',
        normalized
    )
    return normalized


def get_metrics() -> bytes:
    """Retorna metricas no formato Prometheus."""
    return generate_latest(REGISTRY)


def get_metrics_content_type() -> str:
    """Retorna content-type para metricas Prometheus."""
    return CONTENT_TYPE_LATEST
