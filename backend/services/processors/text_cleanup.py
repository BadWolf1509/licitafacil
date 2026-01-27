"""
Utilitários de limpeza de texto para processamento de serviços.

Contém funções para remover unidades/quantidades de descrições,
limpar prefixos de rodapé, e outras operações de limpeza.
"""

import re
from typing import Optional

from services.extraction import (
    normalize_unit,
    parse_quantity,
    UNIT_TOKENS,
)


def parse_unit_qty_from_line(line: str) -> Optional[tuple]:
    """
    Extrai par (unidade, quantidade) de uma linha.

    Procura o último padrão válido de unidade seguida de quantidade.

    Args:
        line: Linha de texto

    Returns:
        Tupla (unidade, quantidade) ou None
    """
    tokens = line.split()
    if len(tokens) < 2:
        return None

    last_match = None
    for idx in range(len(tokens) - 1):
        unit_token = tokens[idx]
        raw_unit = re.sub(r'[^A-Za-z0-9]', '', unit_token).upper()
        if raw_unit in ("MM", "CM"):
            continue

        qty_token = tokens[idx + 1]
        if not re.fullmatch(r'[\d.,]+', qty_token):
            continue

        qty = parse_quantity(qty_token)
        if qty in (None, 0):
            continue

        unit_norm = normalize_unit(unit_token)
        if not unit_norm or unit_norm not in UNIT_TOKENS:
            continue

        last_match = (unit_norm, qty)

    return last_match


def find_unit_qty_in_line(line: str) -> Optional[tuple]:
    """
    Encontra unidade e quantidade em qualquer posição da linha.

    Args:
        line: Linha de texto

    Returns:
        Tupla (unidade, quantidade, start, end) ou None
    """
    if not line:
        return None

    pattern = re.compile(r'([\w\u00ba\u00b0/%\u00b2\u00b3\.]+)\s+([\d.,]+)')
    matches = list(pattern.finditer(line))
    if not matches:
        return None

    stop_units = {"DE", "DA", "DO", "EM", "COM", "PARA", "POR", "QUE"}
    allowed_units = UNIT_TOKENS
    last_valid = None

    for match in matches:
        unit_raw = match.group(1)
        qty_raw = match.group(2)
        qty = parse_quantity(qty_raw)
        if qty in (None, 0):
            continue
        unit_norm = normalize_unit(unit_raw)
        if not unit_norm or unit_norm in ("MM", "CM"):
            continue
        if unit_norm in stop_units:
            continue
        if unit_norm not in allowed_units:
            continue
        last_valid = (unit_norm, qty, match.start(), match.end())

    return last_valid


def strip_trailing_unit_qty(
    text: str,
    unit: Optional[str] = None,
    qty: Optional[float] = None
) -> str:
    """
    Remove unidade/quantidade do final do texto.

    Args:
        text: Texto para limpar
        unit: Unidade esperada (opcional, para validação)
        qty: Quantidade esperada (opcional, para validação)

    Returns:
        Texto sem unidade/quantidade no final
    """
    if not text:
        return text

    match = re.search(
        r'\b([\w\u00ba\u00b0/%\u00b2\u00b3\.]+)\s+([\d.,]+)\s*$',
        text
    )
    if not match:
        return text

    unit_raw = match.group(1)
    qty_raw = match.group(2)
    parsed_qty = parse_quantity(qty_raw)

    if parsed_qty is None:
        return text

    unit_norm = normalize_unit(unit_raw)
    if not unit_norm or unit_norm not in UNIT_TOKENS:
        return text

    if unit:
        unit_expected = normalize_unit(unit)
        if unit_expected and unit_norm != unit_expected:
            return text

    if qty is not None and abs(parsed_qty - qty) > 0.01:
        return text

    return text[:match.start()].strip()


def strip_footer_prefix_from_desc(desc: str) -> str:
    """
    Remove prefixo de rodapé que vazou para a descrição.

    Encontra o início real da descrição baseado em palavras-chave
    comuns de serviços de construção.

    Args:
        desc: Descrição a limpar

    Returns:
        Descrição sem prefixo de rodapé
    """
    if not desc:
        return desc

    upper = desc.upper()
    anchors = [
        "FORNEC", "LOCAÇÃO", "LOCACAO", "EXECUÇÃO", "EXECUCAO",
        "ESCAVAÇÃO", "ESCAVACAO", "REATERRO", "LASTRO",
        "FUNDAÇÃO", "FUNDACAO", "CONCRETO", "ADMINISTRAÇÃO",
        "ADMINISTRACAO", "MOBILIZAÇÃO", "MOBILIZACAO",
        "PLACA", "PERFURAÇÃO", "PERFURACAO"
    ]

    anchor_pos = None
    for anchor in anchors:
        pos = upper.find(anchor)
        if pos == -1:
            continue
        if anchor_pos is None or pos < anchor_pos:
            anchor_pos = pos

    if anchor_pos is not None and anchor_pos > 0:
        return desc[anchor_pos:].strip()

    return desc


def strip_unit_qty_prefix(desc: str) -> str:
    """
    Remove prefixo de unidade/quantidade da descrição.

    Exemplo: "UN 1,00 FORNECIMENTO..." -> "FORNECIMENTO..."

    Args:
        desc: Descrição a limpar

    Returns:
        Descrição sem prefixo de unidade/quantidade
    """
    if not desc:
        return desc

    pattern = r'^(UN|M|M2|M3|M²|M³|KG|L|CJ|VB|PC|PÇ|JG|CONJ)\s+[\d.,]+\s+'
    match = re.match(pattern, desc, re.IGNORECASE)
    if match:
        cleaned = desc[match.end():].strip()
        if len(cleaned) >= 5:
            return cleaned

    return desc
