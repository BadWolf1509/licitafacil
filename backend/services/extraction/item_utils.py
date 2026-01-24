"""
Utilitários unificados para códigos de item.

Este módulo contém funções canônicas para manipulação de códigos de item,
substituindo implementações duplicadas em outros módulos.
"""
from typing import Any, Optional, Tuple
import re

from .table_processor import parse_item_tuple, item_tuple_to_str


def normalize_item_code(item: Any) -> Optional[str]:
    """
    Normaliza código de item para formato padrão.

    Converte variações como "1.2.3", "1 2 3", "AD-1.2.3", "S1-1.2.3" para "1.2.3".

    Args:
        item: Código do item (string ou qualquer tipo)

    Returns:
        Código normalizado (ex: "1.2.3") ou None se inválido

    Examples:
        >>> normalize_item_code("1.2.3")
        '1.2.3'
        >>> normalize_item_code("AD-1.2.3")
        '1.2.3'
        >>> normalize_item_code("S1-1.2.3")
        '1.2.3'
        >>> normalize_item_code("1 2 3")
        '1.2.3'
        >>> normalize_item_code("invalid")
        None
    """
    if item is None:
        return None
    item_str = str(item).strip()
    if not item_str:
        return None

    # Remover prefixos de aditivo ou restart (AD-, Sx-)
    item_str = re.sub(r'^(AD-|S\d+-)', '', item_str, flags=re.IGNORECASE).strip()

    # Usar parse_item_tuple para normalização robusta
    item_tuple = parse_item_tuple(item_str)
    if not item_tuple:
        return None

    return item_tuple_to_str(item_tuple)


def strip_restart_prefix(item_value: str) -> str:
    """
    Remove prefixo de restart (S1-, S2-, AD-) do código de item.

    Args:
        item_value: Código do item possivelmente com prefixo

    Returns:
        Código sem prefixo

    Examples:
        >>> strip_restart_prefix("S1-1.2.3")
        '1.2.3'
        >>> strip_restart_prefix("AD-1.2.3")
        '1.2.3'
        >>> strip_restart_prefix("1.2.3")
        '1.2.3'
    """
    if not item_value:
        return ""
    return re.sub(r"^(S\d+-|AD-)", "", item_value, flags=re.IGNORECASE).strip()


def split_restart_prefix(item: Any) -> Tuple[Optional[str], str]:
    """
    Separa prefixo de restart do código base.

    Alguns documentos reiniciam a numeração com prefixos como S1, S2, etc.

    Args:
        item: Código do item

    Returns:
        Tupla (prefixo, código_base) onde prefixo é None se não houver

    Examples:
        >>> split_restart_prefix("S1-1.2.3")
        ('S1', '1.2.3')
        >>> split_restart_prefix("1.2.3")
        (None, '1.2.3')
        >>> split_restart_prefix("")
        (None, '')
    """
    item_str = str(item or "").strip()
    if not item_str:
        return None, ""

    match = re.match(r'^(S\d+)-(.+)$', item_str, re.IGNORECASE)
    if match:
        return match.group(1).upper(), match.group(2).strip()

    return None, item_str


def item_code_in_text(item_code: str, texto: str) -> bool:
    """
    Verifica se um código de item aparece no texto.

    Usa regex para encontrar o código com espaçamento flexível
    entre os componentes.

    Args:
        item_code: Código normalizado (ex: "1.2.3")
        texto: Texto para busca

    Returns:
        True se o código foi encontrado

    Examples:
        >>> item_code_in_text("1.2.3", "Item 1.2.3 descrição")
        True
        >>> item_code_in_text("1.2.3", "Item 1. 2. 3 descrição")
        True
    """
    if not item_code or not texto:
        return False
    escaped = re.escape(item_code)
    # Permitir espaços flexíveis ao redor dos pontos
    escaped = escaped.replace(r"\.", r"\s*\.\s*")
    # Garantir que não seja parte de um número maior
    pattern = rf"(?<!\d){escaped}(?!\d)"
    return re.search(pattern, texto) is not None


def max_restart_prefix_index(items: list) -> int:
    """
    Encontra o maior índice de prefixo de restart em uma lista de itens.

    Args:
        items: Lista de dicionários com campo 'item'

    Returns:
        Maior índice encontrado (0 se nenhum prefixo)

    Examples:
        >>> max_restart_prefix_index([{"item": "S2-1.1"}, {"item": "1.2"}])
        2
    """
    max_idx = 0
    for s in items:
        item_val = s.get("item", "")
        if isinstance(item_val, str):
            match = re.match(r'^S(\d+)-', item_val, re.IGNORECASE)
            if match:
                idx = int(match.group(1))
                if idx > max_idx:
                    max_idx = idx
    return max_idx
