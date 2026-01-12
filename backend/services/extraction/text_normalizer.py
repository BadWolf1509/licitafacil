"""
Utilitários de normalização de texto para extração de documentos.

Este módulo contém funções para normalizar descrições, unidades,
extrair palavras-chave e calcular similaridade entre textos.

Usa lru_cache para melhorar performance em chamadas repetidas.
"""

import unicodedata
import re
from functools import lru_cache
from typing import Set, FrozenSet


# Unidades comuns de medida
UNIT_TOKENS: Set[str] = {
    "M", "M2", "M3", "M3XKM", "M2XKM", "UN", "UND", "VB", "KG", "TON", "T", "KM", "L", "MODULOS"
}

# Stopwords para extração de palavras-chave
STOPWORDS: Set[str] = {
    'DE', 'DO', 'DA', 'EM', 'PARA', 'COM', 'E', 'A', 'O', 'AS', 'OS',
    'UN', 'M2', 'M3', 'ML', 'M', 'VB', 'KG', 'INCLUSIVE', 'INCLUSIV',
    'TIPO', 'MODELO', 'TRACO'
}


@lru_cache(maxsize=2048)
def normalize_description(desc: str) -> str:
    """
    Normaliza descrição para comparação.

    Remove acentos, espaços extras, pontuação e converte para maiúsculas.
    Também corrige erros comuns de OCR.

    Args:
        desc: Descrição a normalizar

    Returns:
        Descrição normalizada
    """
    if not desc:
        return ""

    # Remover acentos
    nfkd = unicodedata.normalize('NFKD', desc)
    ascii_text = nfkd.encode('ASCII', 'ignore').decode('ASCII')

    # Converter para maiúsculas
    text = ascii_text.upper()

    # Normalizar pontuação (OCR pode confundir ; com , ou .)
    text = text.replace(';', ',').replace(':', ',')

    # Remover toda pontuação para comparação mais robusta
    text = re.sub(r'[^\w\s]', ' ', text)

    # Corrigir erros comuns de OCR em números/letras
    # I no meio de números geralmente é 1
    # Exemplo: 9X19XI9CM -> 9X19X19CM
    text = re.sub(r'(\d)I(\d)', r'\g<1>1', text)
    text = re.sub(r'(\d)l(\d)', r'\g<1>1', text)  # l minúsculo
    text = re.sub(r'(\d)O(\d)', r'\g<1>0', text)  # O -> 0

    # Remover espaços extras
    return ' '.join(text.split())


@lru_cache(maxsize=1024)
def normalize_unit(unit: str) -> str:
    """
    Normaliza unidade para comparação.

    Converte expoentes e padroniza caixa.

    Args:
        unit: Unidade a normalizar

    Returns:
        Unidade normalizada
    """
    if not unit:
        return ""
    normalized = unit.strip().upper()
    normalized = normalized.translate({ord("\u00b2"): '2', ord("\u00b3"): '3'})
    normalized = normalized.replace("M^2", "M2").replace("M^3", "M3")
    normalized = normalized.replace("M\u00b2", "M2").replace("M\u00b3", "M3")
    normalized = normalized.replace(" ", "")
    return normalized


def normalize_header(value: str) -> str:
    """
    Normaliza valor de cabeçalho de tabela.

    Args:
        value: Valor do cabeçalho

    Returns:
        Cabeçalho normalizado
    """
    return normalize_description(value or "")


def normalize_desc_for_match(desc: str) -> str:
    """
    Normaliza descrição para matching.

    Remove prefixos de item e normaliza para comparação.

    Args:
        desc: Descrição a normalizar

    Returns:
        Descrição normalizada para matching
    """
    if not desc:
        return ""
    # Remove leading item codes like "1.1" or "1.1.1"
    cleaned = re.sub(r'^\d+(\.\d+)*\s*[-–—]?\s*', '', desc)
    return normalize_description(cleaned)


@lru_cache(maxsize=2048)
def _extract_keywords_cached(desc: str) -> FrozenSet[str]:
    """Versão cacheada de extract_keywords usando stopwords padrão."""
    normalized = normalize_description(desc)
    words = frozenset(normalized.split())
    return words - STOPWORDS


def extract_keywords(desc: str, stopwords: Set[str] = STOPWORDS) -> Set[str]:
    """
    Extrai palavras-chave significativas da descrição.

    Args:
        desc: Descrição original
        stopwords: Conjunto de palavras a ignorar

    Returns:
        Conjunto de palavras-chave
    """
    # Se usando stopwords padrão, usar versão cacheada
    if stopwords is STOPWORDS:
        return set(_extract_keywords_cached(desc))

    normalized = normalize_description(desc)
    words = set(normalized.split())
    return words - stopwords


def description_similarity(left: str, right: str) -> float:
    """
    Calcula similaridade entre duas descrições.

    Usa interseção de palavras-chave dividido pelo máximo de palavras.

    Args:
        left: Primeira descrição
        right: Segunda descrição

    Returns:
        Similaridade entre 0.0 e 1.0
    """
    left_kw = extract_keywords(left)
    right_kw = extract_keywords(right)
    if not left_kw or not right_kw:
        return 0.0
    intersection = len(left_kw & right_kw)
    return intersection / max(len(left_kw), len(right_kw))
