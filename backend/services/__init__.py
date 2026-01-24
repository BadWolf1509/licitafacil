# Services do LicitaFácil
#
# IMPORTANTE: ai_analyzer e gemini_analyzer estao DEPRECADOS.
# Use services.ai.extraction_service.AIExtractionService com os providers:
#   - services.providers.openai_provider.OpenAIProvider
#   - services.providers.gemini_provider.GeminiProvider
# Ou use ai_provider que abstrai a escolha de provider automaticamente.

from .pdf_extractor import pdf_extractor
from .ocr_service import ocr_service
from .ai_provider import ai_provider
from .matching_service import matching_service
from .document_ai_service import document_ai_service
from .document_processor import document_processor
from .processing_queue import processing_queue
from .ai.extraction_service import AIExtractionService, extraction_service

__all__ = [
    "pdf_extractor",
    "ocr_service",
    "ai_provider",
    "matching_service",
    "document_ai_service",
    "document_processor",
    "processing_queue",
    "AIExtractionService",
    "extraction_service",
]
