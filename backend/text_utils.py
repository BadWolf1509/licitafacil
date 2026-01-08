"""
Utilitários para processamento e validação de texto.

Este módulo contém funções compartilhadas para análise de qualidade de texto
extraído de documentos.
"""

from typing import List


# Palavras comuns em português para validação de texto
PORTUGUESE_COMMON_WORDS: List[str] = [
    'de', 'do', 'da', 'em', 'para', 'que', 'com', 'os', 'as',
    'um', 'uma', 'no', 'na', 'ao', 'pela', 'pelo', 'este', 'esta',
    'esse', 'essa', 'são', 'ser', 'foi', 'como', 'mais', 'seu', 'sua'
]

# Configurações padrão
MIN_TEXT_LENGTH = 50
MIN_COMMON_WORDS = 5
MIN_LETTER_RATIO = 0.5


def is_garbage_text(
    text: str,
    min_length: int = MIN_TEXT_LENGTH,
    min_common_words: int = MIN_COMMON_WORDS,
    min_letter_ratio: float = MIN_LETTER_RATIO
) -> bool:
    """
    Verifica se o texto é lixo (marca d'água invertida, OCR mal feito, etc).

    Args:
        text: Texto a verificar
        min_length: Comprimento mínimo do texto para ser válido
        min_common_words: Número mínimo de palavras comuns portuguesas
        min_letter_ratio: Proporção mínima de letras vs caracteres especiais

    Returns:
        True se o texto parecer ser lixo/inválido, False se parecer válido
    """
    # Texto muito curto é considerado lixo
    if not text or len(text.strip()) < min_length:
        return True

    # Verificar se tem palavras comuns em português
    text_lower = text.lower()
    palavras_encontradas = sum(
        1 for p in PORTUGUESE_COMMON_WORDS
        if f' {p} ' in text_lower
    )

    # Se não encontrar palavras comuns suficientes, provavelmente é lixo
    if palavras_encontradas < min_common_words:
        return True

    # Verificar proporção de caracteres válidos vs especiais/números
    letras = sum(1 for c in text if c.isalpha())
    total = len(text.replace(' ', '').replace('\n', ''))

    if total > 0 and letras / total < min_letter_ratio:
        return True

    return False


def count_common_words(text: str, words: List[str] = PORTUGUESE_COMMON_WORDS) -> int:
    """
    Conta quantas palavras comuns aparecem no texto.

    Args:
        text: Texto para análise
        words: Lista de palavras comuns a procurar

    Returns:
        Número de palavras comuns encontradas
    """
    text_lower = text.lower()
    return sum(1 for word in words if f' {word} ' in text_lower)


def calculate_letter_ratio(text: str) -> float:
    """
    Calcula a proporção de letras no texto.

    Args:
        text: Texto para análise

    Returns:
        Proporção de letras (0.0 a 1.0)
    """
    letters = sum(1 for c in text if c.isalpha())
    total = len(text.replace(' ', '').replace('\n', ''))
    return letters / total if total > 0 else 0.0
