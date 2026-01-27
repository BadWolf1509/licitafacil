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
    "M", "M2", "M3", "M3XKM", "M2XKM", "UN", "UND", "VB", "KG", "TON", "T", "KM", "L",
    "MODULOS", "CONJ", "MES", "PT", "CENTO"
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

    Converte expoentes, corrige artefatos de OCR e padroniza caixa.

    Trata artefatos comuns de OCR:
    - Subscripts/superscripts Unicode (₁₂₃, ¹²³) → dígitos normais
    - Caracteres gregos similares (Σ→S, Έ→E) → removidos ou convertidos
    - Duplicações (UNN→UN, MMM→M)
    - Pontuação espúria (,M2→M2)

    Args:
        unit: Unidade a normalizar

    Returns:
        Unidade normalizada
    """
    if not unit:
        return ""

    normalized = unit.strip().upper()
    normalized = re.sub(r'M\s*[\?\u00b0\u00ba]', 'M2', normalized)
    normalized = normalized.replace("M²", "M2").replace("M³", "M3")

    # 1. Converter subscripts e superscripts Unicode para dígitos normais
    # 1. Converter subscripts e superscripts Unicode para digitos normais
    subscript_map = {
        '\u2080': '0', '\u2081': '1', '\u2082': '2', '\u2083': '3', '\u2084': '4',
        '\u2085': '5', '\u2086': '6', '\u2087': '7', '\u2088': '8', '\u2089': '9',
        '\u2070': '0', '\u00b9': '1', '\u00b2': '2', '\u00b3': '3', '\u2074': '4',
        '\u2075': '5', '\u2076': '6', '\u2077': '7', '\u2078': '8', '\u2079': '9',
    }
    for sub, digit in subscript_map.items():
        normalized = normalized.replace(sub, digit)

    # 2. Converter expoentes em formato texto
    normalized = normalized.replace("M^2", "M2").replace("M^3", "M3")
    normalized = normalized.replace("KG^2", "KG2").replace("KM^2", "KM2")

    # 3. Remover caracteres nao ASCII e ruidos (feito abaixo)

    # 3a. Remover caracteres nao ASCII e normalizar acentos
    normalized = unicodedata.normalize('NFKD', normalized)
    normalized = normalized.encode('ASCII', 'ignore').decode('ASCII')
    normalized = re.sub(r'[^A-Z0-9]', '', normalized)

    # 4. Remover pontuação e caracteres especiais do início/fim
    normalized = normalized.strip('.,;:!?()[]{}"\'-_/\\|<>@#$%^&*+=~`')

    # 5. Remover espaços
    normalized = normalized.replace(" ", "")

    # 6. Corrigir duplicações comuns de OCR
    # UNN → UN, MMM → M, etc.
    while 'NN' in normalized and normalized != 'UN':
        normalized = normalized.replace('NN', 'N')
    while 'MM' in normalized:
        normalized = normalized.replace('MM', 'M')
    while 'UU' in normalized:
        normalized = normalized.replace('UU', 'U')

    # 7. Remover dígitos espúrios no início (ex: "33" de "M233" mal parseado)
    # Mas preservar dígitos válidos no final (M2, M3, KG2)
    if normalized and normalized[0].isdigit() and len(normalized) > 1:
        # Se começa com dígito mas não é uma unidade válida conhecida
        if not normalized.startswith(('2', '3')) or len(normalized) > 2:
            # Remove dígitos do início até encontrar letra
            while normalized and normalized[0].isdigit():
                normalized = normalized[1:]

    # 8. Corrigir unidades de área/volume com dígitos extras
    # M231, M234, etc. → M2 (dígitos extras são ruído de OCR)
    # M312, M345, etc. → M3
    if re.match(r'^M2\d+$', normalized):
        normalized = 'M2'
    elif re.match(r'^M3\d+$', normalized):
        normalized = 'M3'
    elif re.match(r'^KM2\d+$', normalized):
        normalized = 'KM2'
    else:
        match = re.match(r'^(M2|M3)E\d{1,3}$', normalized)
        if match:
            normalized = match.group(1)

    # 8b. Corrigir unidades com números concatenados (erro comum de OCR do Document AI)
    # Padrões: "UN353375" → "UN", "UN333" → "UN", "UN3" → "UN"
    # O OCR às vezes junta a unidade com códigos SINAPI ou outros números adjacentes
    unit_with_garbage = re.match(r'^(UN|UND|VB|KG|L|CJ|PC|PT|HA|T|TON|KM|MES|GB)(\d{1,})$', normalized, re.IGNORECASE)
    if unit_with_garbage:
        base_unit = unit_with_garbage.group(1).upper()
        garbage_digits = unit_with_garbage.group(2)
        # Se tem mais de 2 dígitos, certamente é lixo (não é M2, M3)
        # Se tem 1-2 dígitos mas a unidade não aceita sufixo numérico, também é lixo
        if len(garbage_digits) >= 1 and base_unit not in ('M', 'KM'):
            normalized = base_unit

    # 9. Mapear unidades corrompidas conhecidas para unidades corretas
    unit_corrections = {
        'M23': 'M2',      # M2 + ruído "3"
        'M32': 'M3',      # M3 + ruído "2"
        'M22': 'M2',      # M2 duplicado
        'M33': 'M3',      # M3 duplicado
        'EM2': 'M2',      # E + M2 (OCR confundiu)
        'EM3': 'M3',      # E + M3 (OCR confundiu)
        'UNI': 'UN',      # UN + ruído "I"
        'UND': 'UN',      # Abreviação de UNIDADE
        'UNID': 'UN',     # Abreviação de UNIDADE
        'UNIDADE': 'UN',
        'METRO': 'M',
        'METROS': 'M',
        'KGS': 'KG',
        'MÊS': 'MES',
        'MES': 'MES',
        'MOS': 'MES',
        'VB': 'VB',       # Verba
        'GB': 'GB',       # Global
        'CJ': 'CJ',       # Conjunto
        'PC': 'PC',       # Peça
        'PT': 'PT',       # Ponto
        'L': 'L',         # Litro
        'LT': 'L',
        'KM': 'KM',
        'HA': 'HA',       # Hectare
        'T': 'T',         # Tonelada
        'TON': 'T',
    }

    if normalized in unit_corrections:
        normalized = unit_corrections[normalized]

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


def normalize_accents(text: str) -> str:
    """
    Remove acentos de texto para comparação normalizada.

    Usa unicodedata para normalização robusta de caracteres Unicode.

    Args:
        text: Texto a normalizar

    Returns:
        Texto sem acentos
    """
    if not text:
        return ""
    nfkd = unicodedata.normalize('NFKD', text)
    return nfkd.encode('ASCII', 'ignore').decode('ASCII')


def is_corrupted_text(text: str) -> bool:
    """
    Detecta texto corrompido por OCR (caracteres intercalados com espaços).

    Exemplo: "D M E A M N O U L A I L" ao invés de "DEMOLIÇÃO DE ALVENARIA"

    Args:
        text: Texto a verificar

    Returns:
        True se o texto parece corrompido por OCR
    """
    if not text or len(text) < 20:
        return False

    # Contar sequências de caracteres únicos separados por espaços
    parts = text.split()
    single_char_count = sum(1 for part in parts if len(part) == 1 and part.isalpha())

    # Se mais de 30% das "palavras" são caracteres únicos, é texto corrompido
    if len(parts) > 5 and single_char_count / len(parts) > 0.3:
        return True

    return False


