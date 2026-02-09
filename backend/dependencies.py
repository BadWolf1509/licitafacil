"""
Container de Dependencias para LicitaFacil.
Centraliza instanciacao e acesso aos servicos.
Permite injecao de dependencia nos routers via FastAPI Depends.
"""
from functools import lru_cache
from typing import Optional

from services.protocols import (
    AtestadoServiceProtocol,
    DocumentProcessorProtocol,
    OCRServiceProtocol,
    ProcessingQueueProtocol,
)


class ServiceContainer:
    """
    Container singleton para servicos da aplicacao.
    Lazy-loading: servicos sao instanciados apenas quando necessarios.
    """
    _instance: Optional['ServiceContainer'] = None

    def __init__(self):
        self._document_processor = None
        self._processing_queue = None
        self._ocr_service = None
        self._atestado_service = None

    @classmethod
    def get(cls) -> 'ServiceContainer':
        """Retorna instancia singleton do container."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Reseta o container (util para testes)."""
        cls._instance = None

    @property
    def document_processor(self) -> DocumentProcessorProtocol:
        """Retorna instancia do processador de documentos."""
        if self._document_processor is None:
            from services.document_processor import document_processor
            self._document_processor = document_processor
        return self._document_processor

    @property
    def processing_queue(self) -> ProcessingQueueProtocol:
        """Retorna instancia da fila de processamento."""
        if self._processing_queue is None:
            from services.processing_queue import processing_queue
            self._processing_queue = processing_queue
        return self._processing_queue

    @property
    def ocr_service(self) -> OCRServiceProtocol:
        """Retorna instancia do servico de OCR."""
        if self._ocr_service is None:
            from services.ocr_service import ocr_service
            self._ocr_service = ocr_service
        return self._ocr_service

    @property
    def atestado_service(self) -> AtestadoServiceProtocol:
        """Retorna modulo de servico de atestados."""
        if self._atestado_service is None:
            from services.atestado import service as atestado_service
            self._atestado_service = atestado_service
        return self._atestado_service

    def set_document_processor(self, processor: DocumentProcessorProtocol) -> None:
        """Injeta processador de documentos (util para testes)."""
        self._document_processor = processor

    def set_processing_queue(self, queue: ProcessingQueueProtocol) -> None:
        """Injeta fila de processamento (util para testes)."""
        self._processing_queue = queue

    def set_ocr_service(self, service: OCRServiceProtocol) -> None:
        """Injeta servico de OCR (util para testes)."""
        self._ocr_service = service


@lru_cache()
def get_services() -> ServiceContainer:
    """
    Dependency injection para FastAPI.
    Uso: services: ServiceContainer = Depends(get_services)
    """
    return ServiceContainer.get()


# Shortcuts para acesso direto (compatibilidade)
def get_document_processor() -> DocumentProcessorProtocol:
    """Retorna processador de documentos."""
    return ServiceContainer.get().document_processor


def get_processing_queue() -> ProcessingQueueProtocol:
    """Retorna fila de processamento."""
    return ServiceContainer.get().processing_queue


def get_ocr_service() -> OCRServiceProtocol:
    """Retorna servico de OCR."""
    return ServiceContainer.get().ocr_service
