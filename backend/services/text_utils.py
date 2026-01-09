"""
Utilitários para processamento de texto.

Funções extraídas do document_processor.py para melhor organização.
"""
import re
import unicodedata
from typing import Set


def normalize_description(desc: str) -> str:
    """
    Normaliza uma descrição para comparação.
    Remove acentos, converte para maiúsculas, remove caracteres especiais.
    """
    if not desc:
        return ""
    # Remover acentos
    desc = unicodedata.normalize('NFKD', desc)
    desc = desc.encode('ASCII', 'ignore').decode('ASCII')
    # Converter para maiúsculas e remover caracteres especiais
    desc = desc.upper()
    desc = re.sub(r'[^A-Z0-9\s]', ' ', desc)
    desc = re.sub(r'\s+', ' ', desc)
    return desc.strip()


def normalize_unit(unit: str) -> str:
    """
    Normaliza uma unidade de medida para comparação.
    """
    if not unit:
        return ""
    unit = unit.upper().strip()
    # Mapeamento de variações comuns
    mappings = {
        'M²': 'M2', 'M2': 'M2', 'M 2': 'M2',
        'M³': 'M3', 'M3': 'M3', 'M 3': 'M3',
        'UN': 'UN', 'UND': 'UN', 'UNID': 'UN', 'UNIDADE': 'UN',
        'KG': 'KG', 'KILO': 'KG', 'QUILOGRAMA': 'KG',
        'L': 'L', 'LT': 'L', 'LITRO': 'L', 'LITROS': 'L',
        'ML': 'ML', 'MILILITRO': 'ML',
        'VB': 'VB', 'VERBA': 'VB',
        'CJ': 'CJ', 'CONJ': 'CJ', 'CONJUNTO': 'CJ',
        'PAR': 'PAR', 'PARES': 'PAR',
        'PC': 'PC', 'PÇ': 'PC', 'PECA': 'PC', 'PEÇA': 'PC',
        'GL': 'GL', 'GLOBAL': 'GL',
    }
    # Normalizar caracteres especiais da unidade
    unit = unicodedata.normalize('NFKD', unit)
    unit = unit.encode('ASCII', 'ignore').decode('ASCII')
    unit = re.sub(r'[^A-Z0-9]', '', unit)
    return mappings.get(unit, unit)


def extract_keywords(text: str, min_length: int = 3) -> Set[str]:
    """
    Extrai palavras-chave de um texto para comparação.

    Args:
        text: Texto de entrada
        min_length: Comprimento mínimo das palavras (default: 3)

    Returns:
        Conjunto de palavras-chave normalizadas
    """
    if not text:
        return set()
    normalized = normalize_description(text)
    words = normalized.split()
    # Filtrar palavras muito curtas e stopwords comuns
    stopwords = {'DE', 'DA', 'DO', 'DAS', 'DOS', 'EM', 'COM', 'PARA', 'POR', 'SEM', 'SOB', 'ATE'}
    return {w for w in words if len(w) >= min_length and w not in stopwords}


def is_garbage_text(text: str, threshold: float = 0.4) -> bool:
    """
    Verifica se um texto parece ser lixo de OCR.

    Args:
        text: Texto a verificar
        threshold: Proporção máxima de caracteres não-alfanuméricos (default: 0.4)

    Returns:
        True se o texto parece ser lixo
    """
    if not text or len(text) < 10:
        return True

    # Contar caracteres alfanuméricos
    alnum_count = sum(1 for c in text if c.isalnum() or c.isspace())
    total_count = len(text)

    ratio = alnum_count / total_count if total_count > 0 else 0
    return ratio < (1 - threshold)
