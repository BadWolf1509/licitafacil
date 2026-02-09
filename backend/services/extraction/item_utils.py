"""
Utilitários unificados para códigos de item.

Este módulo contém funções canônicas para manipulação de códigos de item,
substituindo implementações duplicadas em outros módulos.
"""
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from .table_processor import item_tuple_to_str, parse_item_tuple, parse_quantity

logger = logging.getLogger(__name__)


def normalize_item_code(item: Any, strip_suffixes: bool = False) -> Optional[str]:
    """
    Normaliza código de item para formato padrão.

    Converte variações como "1.2.3", "1 2 3", "AD-1.2.3", "S1-1.2.3" para "1.2.3".

    Args:
        item: Código do item (string ou qualquer tipo)
        strip_suffixes: Se True, também remove sufixos como -A, -B, -C

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
        >>> normalize_item_code("1.2.3-A", strip_suffixes=True)
        '1.2.3'
        >>> normalize_item_code("invalid")
        None
    """
    if item is None:
        return None
    item_str = str(item).strip()
    if not item_str:
        return None

    # Remover prefixos de aditivo ou restart (AD-, AD1-, Sx-)
    item_str = re.sub(r'^(AD\d*-|S\d+-)', '', item_str, flags=re.IGNORECASE).strip()

    # Remover sufixos -A, -B, -C se solicitado
    if strip_suffixes:
        item_str = re.sub(r'-[A-Z]$', '', item_str, flags=re.IGNORECASE).strip()

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


def extract_item_code(desc: str) -> str:
    """
    Extrai código do item da descrição.

    Reconhece formatos:
    - Numérico padrão: "1.1", "001.03.01", "10.4-A"
    - Prefixo Sx-: "S2-1.1"
    - Prefixo AD-: "AD-1.1", "AD-1.1-A"
    - Espaços como separador: "1 2 3"

    Args:
        desc: Descrição que pode começar com código de item

    Returns:
        Código extraído ou string vazia se não encontrado

    Examples:
        >>> extract_item_code("001.03.01 MOBILIZAÇÃO")
        '001.03.01'
        >>> extract_item_code("S2-1.1 Serviço")
        'S2-1.1'
        >>> extract_item_code("AD-1.1-A Item")
        'AD-1.1-A'
        >>> extract_item_code("Sem código aqui")
        ''
    """
    if not desc:
        return ""

    text = desc.strip()

    # Primeiro, tentar extrair formato com prefixo Sx- (ex: S2-1.1)
    restart_match = re.match(r'^(S\d+-\d{1,3}(?:\.\d{1,3})+(?:-[A-Z])?)\b', text, re.IGNORECASE)
    if restart_match:
        return restart_match.group(1).upper()

    # Tentar extrair formato com prefixo AD- (legacy: AD-1.1, AD-1.1-A)
    ad_match = re.match(r'^(AD-\d{1,3}(?:\.\d{1,3})+(?:-[A-Z])?)\b', text, re.IGNORECASE)
    if ad_match:
        return ad_match.group(1).upper()

    # Formato numérico padrão (ex: 1.1, 10.4, 10.4-A)
    match = re.match(r'^(\d{1,3}(?:\s*\.\s*\d{1,3}){1,4}(?:-[A-Z])?)\b', text)
    if not match:
        match = re.match(r'^(\d{1,3}(?:\s+\d{1,2}){1,3})\b', text)

    if match:
        code = re.sub(r'[\s]+', '.', match.group(1))
        code = re.sub(r'\.{2,}', '.', code).strip('.')
        return code
    return ""


def split_item_description(desc: str) -> Tuple[str, str]:
    """
    Separa o código do item da descrição, se presente.

    Args:
        desc: Texto com possível código no início

    Returns:
        Tupla (código, descrição_limpa). Código vazio se não encontrado.

    Examples:
        >>> split_item_description("1.2.3 Serviço de teste")
        ('1.2.3', 'Serviço de teste')
        >>> split_item_description("Sem código aqui")
        ('', 'Sem código aqui')
        >>> split_item_description("")
        ('', '')
    """
    if not desc:
        return "", ""

    code = extract_item_code(desc)
    if not code:
        return "", desc.strip()

    cleaned = re.sub(
        r"^(S\d+-)?(\d{1,3}(?:\s*\.\s*\d{1,3}){1,4}|\d{1,3}(?:\s+\d{1,2}){1,3})\s*[-.]?\s*",
        "",
        desc
    ).strip()
    return code, cleaned or desc.strip()


def item_qty_matches_code(item_code: str, qty: float) -> bool:
    """
    Verifica se a quantidade é na verdade o código do item (vazamento de coluna).

    Quando a extração de tabela falha, a coluna de código pode vazar
    para a coluna de quantidade, resultando em qty == float(código_numérico).

    Args:
        item_code: Código do item
        qty: Quantidade extraída

    Returns:
        True se a quantidade parece ser o código do item

    Examples:
        >>> item_qty_matches_code("1.2", 12.0)
        True
        >>> item_qty_matches_code("1.2", 50.0)
        False
    """
    if not item_code or qty is None:
        return False
    digits = re.sub(r'\D', '', item_code)
    if not digits:
        return False
    try:
        return float(digits) == float(qty)
    except (TypeError, ValueError):
        return False


def clear_item_code_quantities(
    servicos: List[Dict[str, Any]],
    min_ratio: float = 0.7,
    min_samples: int = 10
) -> int:
    """
    Remove quantidades que são na verdade códigos de item (vazamento de coluna).

    Quando >= min_ratio dos itens têm qty == float(código), limpa todas
    essas quantidades pois provavelmente houve vazamento de coluna na tabela.

    Args:
        servicos: Lista de serviços
        min_ratio: Proporção mínima de matches para ativar limpeza
        min_samples: Mínimo de amostras para ativar limpeza

    Returns:
        Número de quantidades limpas
    """
    if not servicos:
        return 0
    total = 0
    matches = 0
    for s in servicos:
        code = normalize_item_code(s.get("item"))
        qty = parse_quantity(s.get("quantidade"))
        if not code or qty is None:
            continue
        total += 1
        if item_qty_matches_code(code, qty):
            matches += 1
    ratio = (matches / total) if total else 0.0
    if total < min_samples or ratio < min_ratio:
        return 0

    cleared = 0
    for s in servicos:
        code = normalize_item_code(s.get("item"))
        qty = parse_quantity(s.get("quantidade"))
        if code and qty is not None and item_qty_matches_code(code, qty):
            s["quantidade"] = None
            cleared += 1
    if cleared:
        logger.info(f"[QTY] Quantidades removidas por vazamento de coluna: {cleared} (ratio={ratio:.0%})")
    return cleared
