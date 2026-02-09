"""
Document AI service for table extraction.

NOTA: Google Document AI foi DESABILITADO permanentemente.
O sistema usa apenas processamento local.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from logging_config import get_logger

logger = get_logger('services.document_ai_service')

# DOCUMENT AI PERMANENTEMENTE DESABILITADO
_DOC_AI_AVAILABLE = False
_DOC_AI_ENABLED = False


class DocumentAIService:
    """
    Wrapper around Google Document AI to extract tables.

    NOTA: DESABILITADO permanentemente - usa apenas processamento local.
    """

    def __init__(self) -> None:
        self._client: Optional[Any] = None

    @property
    def is_available(self) -> bool:
        """Sempre retorna False - Document AI desabilitado."""
        return False

    @property
    def is_configured(self) -> bool:
        """Sempre retorna False - Document AI desabilitado."""
        return False

    def extract_tables(
        self,
        file_path: str,
        mime_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Document AI desabilitado - retorna lista vazia."""
        logger.debug("Document AI desabilitado - extract_tables retorna vazio")
        return []

    def extract_items_from_pdf(
        self,
        file_path: str,
    ) -> List[Dict[str, Any]]:
        """Document AI desabilitado - retorna lista vazia."""
        logger.debug("Document AI desabilitado - extract_items_from_pdf retorna vazio")
        return []


# Singleton
document_ai_service = DocumentAIService()
