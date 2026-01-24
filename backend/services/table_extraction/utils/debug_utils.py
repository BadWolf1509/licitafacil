"""
Utilitarios para debug de extracao de tabelas.

Funcoes para resumir e formatar informacoes de debug.
"""

from typing import Any, Dict


def summarize_table_debug(debug: Dict[str, Any]) -> Dict[str, Any]:
    """
    Resume informacoes de debug da tabela.

    Extrai apenas as chaves relevantes para evitar payloads grandes.

    Args:
        debug: Dicionario completo de debug

    Returns:
        Dicionario resumido com apenas chaves essenciais
    """
    if not isinstance(debug, dict):
        return {}

    summary: Dict[str, Any] = {}

    # Chaves essenciais de debug
    essential_keys = (
        "source",
        "tables",
        "pages",
        "pages_used",
        "error",
        "imageless",
    )

    for key in essential_keys:
        if key in debug:
            summary[key] = debug.get(key)

    # OCR noise separado (pode ser grande)
    if "ocr_noise" in debug:
        summary["ocr_noise"] = debug.get("ocr_noise")

    return summary
