"""
Extrator de servicos usando Google Document AI.

NOTA: Document AI foi DESABILITADO permanentemente.
O sistema usa apenas processamento local (pdfplumber, EasyOCR).
"""

from typing import Any, Dict, List, Tuple

from logging_config import get_logger

logger = get_logger('services.table_extraction.extractors.document_ai')


def extract_servicos_from_document_ai(
    service: Any,
    file_path: str,
    use_native_pdf_parsing: bool = False,
    allow_itemless: bool = False,
    ignore_item_numbers: bool = False
) -> Tuple[List[Dict[str, Any]], float, Dict[str, Any]]:
    """
    Extrai servicos usando Google Document AI.

    NOTA: Desabilitado permanentemente. Sempre retorna lista vazia.

    Args:
        service: Instancia do TableExtractionService (não utilizado)
        file_path: Caminho para o arquivo (não utilizado)
        use_native_pdf_parsing: Usar parsing nativo de PDF (não utilizado)
        allow_itemless: Permitir itens sem codigo (não utilizado)
        ignore_item_numbers: Ignorar numeros de item (não utilizado)

    Returns:
        Tupla (lista vazia, 0.0, debug info)
    """
    logger.debug("Document AI desabilitado - retornando vazio")
    return [], 0.0, {
        "enabled": False,
        "error": "not_configured",
        "imageless": use_native_pdf_parsing
    }
