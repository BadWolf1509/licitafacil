"""
Utilitários para processamento de texto.

Funções extraídas do document_processor.py para melhor organização.
"""
import re
import unicodedata
from typing import Set, Optional


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


def jaccard_similarity(set1: Set[str], set2: Set[str]) -> float:
    """
    Calcula a similaridade de Jaccard entre dois conjuntos.

    Returns:
        Valor entre 0.0 e 1.0
    """
    if not set1 or not set2:
        return 0.0
    intersection = len(set1 & set2)
    union = len(set1 | set2)
    return intersection / union if union > 0 else 0.0


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


def extract_item_code(text: str) -> Optional[str]:
    """
    Extrai código de item de uma descrição (ex: "4.2.1" de "4.2.1 DESCRIÇÃO...").

    Returns:
        Código do item ou None se não encontrado
    """
    if not text:
        return None

    # Padrões comuns de código de item
    patterns = [
        r'^(\d{1,3}(?:\.\d{1,3}){1,4})\s',  # 4.2.1 ou 4.2.1.3
        r'^(\d{1,3}(?:\s+\d{1,2}){1,3})\s',  # 4 2 1 (espaço separado)
    ]

    for pattern in patterns:
        match = re.match(pattern, text.strip())
        if match:
            code = match.group(1)
            # Normalizar formato (trocar espaços por pontos)
            code = re.sub(r'\s+', '.', code)
            return code

    return None


def clean_description(text: str, remove_item_code: bool = True) -> str:
    """
    Limpa uma descrição removendo código de item e caracteres extras.

    Args:
        text: Texto a limpar
        remove_item_code: Se True, remove código de item do início

    Returns:
        Descrição limpa
    """
    if not text:
        return ""

    text = text.strip()

    if remove_item_code:
        # Remover código de item do início
        text = re.sub(r'^(\d{1,3}(?:\.\d{1,3}){0,4})\s*', '', text)

    # Remover caracteres de controle
    text = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', text)

    # Normalizar espaços
    text = re.sub(r'\s+', ' ', text)

    return text.strip()
