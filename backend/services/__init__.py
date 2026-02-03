# Services do LicitaFácil
#
# IMPORTANTE: ai_analyzer e gemini_analyzer estao DEPRECADOS.
# Use services.ai.extraction_service.AIExtractionService com os providers:
#   - services.providers.openai_provider.OpenAIProvider
#   - services.providers.gemini_provider.GeminiProvider
# Ou use ai_provider que abstrai a escolha de provider automaticamente.
#
# NOTA: Imports pesados (OCR, numpy) sao lazy-loaded para compatibilidade
# com Vercel Serverless Functions (limite de 250MB).


def __getattr__(name):
    """Lazy loading de módulos pesados."""
    if name == "pdf_extractor":
        from .pdf_extractor import pdf_extractor
        return pdf_extractor
    elif name == "ocr_service":
        from .ocr_service import ocr_service
        return ocr_service
    elif name == "ai_provider":
        from .ai_provider import ai_provider
        return ai_provider
    elif name == "matching_service":
        from .matching_service import matching_service
        return matching_service
    elif name == "document_ai_service":
        from .document_ai_service import document_ai_service
        return document_ai_service
    elif name == "document_processor":
        from .document_processor import document_processor
        return document_processor
    elif name == "processing_queue":
        from .processing_queue import processing_queue
        return processing_queue
    elif name == "AIExtractionService":
        from .ai.extraction_service import AIExtractionService
        return AIExtractionService
    elif name == "extraction_service":
        from .ai.extraction_service import extraction_service
        return extraction_service
    raise AttributeError(f"module 'services' has no attribute '{name}'")


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
