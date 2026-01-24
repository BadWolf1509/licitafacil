"""
Parsers para extração de unidade e quantidade de texto.

Funções para extrair pares unidade/quantidade de strings de texto,
usadas na extração de serviços de tabelas.
"""

import re
from typing import List, Optional, Tuple

from services.extraction import normalize_unit, parse_quantity, UNIT_TOKENS


# Unidades de parada (preposições que podem parecer unidades)
STOP_UNITS = {"DE", "DA", "DO", "EM", "COM", "PARA", "POR", "QUE"}

# Unidades permitidas
ALLOWED_UNITS = set(UNIT_TOKENS) | {"MES"}

# Unidades dimensionais (não são unidades de quantidade)
DIMENSIONAL_UNITS = {"MM", "CM"}


def parse_unit_qty_from_text(text: str) -> Optional[Tuple[str, float]]:
    """
    Extrai par unidade/quantidade do final do texto.

    Procura de trás para frente por padrão UNIT QTY.

    Args:
        text: Texto para extrair unidade e quantidade

    Returns:
        Tupla (unidade, quantidade) ou None se não encontrar

    Examples:
        >>> parse_unit_qty_from_text("Serviço de pintura UN 10,5")
        ('UN', 10.5)
        >>> parse_unit_qty_from_text("Texto sem unidade")
        None
    """
    if not text:
        return None

    tokens = re.findall(r'[\w\u00ba\u00b0/%\u00b2\u00b3\.]+', text)
    if len(tokens) < 2:
        return None

    # Procurar de trás para frente
    for idx in range(len(tokens) - 2, -1, -1):
        unit_raw = tokens[idx]
        qty_raw = tokens[idx + 1]

        # Quantidade deve ser numérica
        if not re.fullmatch(r'[\d.,]+', qty_raw):
            continue

        qty = parse_quantity(qty_raw)
        if qty is None or qty == 0:
            continue

        unit_norm = normalize_unit(unit_raw)
        if not unit_norm or unit_norm in DIMENSIONAL_UNITS:
            continue

        if unit_norm in STOP_UNITS:
            continue

        if unit_norm not in ALLOWED_UNITS:
            continue

        return unit_norm, qty

    return None


def find_unit_qty_pairs(text: str) -> List[Tuple[str, float, int, int]]:
    """
    Encontra todos os pares unidade/quantidade no texto.

    Args:
        text: Texto para buscar pares

    Returns:
        Lista de tuplas (unidade, quantidade, start, end)
        onde start/end são posições no texto

    Examples:
        >>> find_unit_qty_pairs("Item UN 10 descrição M2 25,5")
        [('UN', 10.0, 5, 10), ('M2', 25.5, 22, 29)]
    """
    if not text:
        return []

    pattern = re.compile(r'([\w\u00ba\u00b0/%\u00b2\u00b3\.]+)\s+([\d.,]+)')
    pairs = []

    for match in pattern.finditer(text):
        unit_raw = match.group(1)
        qty_raw = match.group(2)

        qty = parse_quantity(qty_raw)
        if qty is None or qty == 0:
            continue

        unit_norm = normalize_unit(unit_raw)
        if not unit_norm or unit_norm in DIMENSIONAL_UNITS:
            continue

        if unit_norm in STOP_UNITS:
            continue

        if unit_norm not in ALLOWED_UNITS:
            continue

        pairs.append((unit_norm, qty, match.start(), match.end()))

    return pairs
