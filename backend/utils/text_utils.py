"""
Text processing utilities for document extraction.

Contains functions for sanitizing and processing text extracted from documents,
particularly handling OCR artifacts and Unicode issues.
"""


def sanitize_description(desc: str) -> str:
    """
    Remove caracteres Unicode especiais nao esperados de uma descricao.

    Mantem apenas: ASCII + acentos latinos (Latin-1 Supplement: A-y)
    Isso remove caracteres como U+2796 (HEAVY MINUS SIGN) que podem aparecer
    em extracoes OCR mal-sucedidas.

    Args:
        desc: Descricao a ser sanitizada

    Returns:
        Descricao sanitizada com apenas caracteres permitidos
    """
    if not desc:
        return ""
    result = []
    for char in desc:
        code = ord(char)
        # Permitir ASCII (< 128) e Latin-1 Supplement (A-y = 0x00C0 a 0x00FF)
        if code < 128 or (0x00C0 <= code <= 0x00FF):
            result.append(char)
        else:
            result.append(' ')  # Substituir Unicode especial por espaco
    # Normalizar espacos multiplos
    return ' '.join(''.join(result).split())
