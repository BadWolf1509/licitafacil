"""
Helpers para extração de itens de tabela.

Funções auxiliares para extração de informações de serviços:
- Itens ocultos em texto concatenado
- Unidades no final de descrições
- Inferência de unidades faltantes
"""

import re
from typing import Any, Dict, List, Optional, Tuple

from services.extraction import (
    parse_item_tuple,
    parse_quantity,
    is_valid_item_context,
)
from utils.text_utils import sanitize_description


def extract_hidden_item_from_text(text: str) -> Optional[Dict[str, Any]]:
    """
    Extrai item oculto de texto concatenado.

    Detecta se o texto contém um código de item no meio
    (ex: "JUNTA 6.14 ELÁSTICA...") e extrai esse item como serviço separado.

    Args:
        text: Texto a verificar

    Returns:
        Dict com item/descricao se encontrou item oculto, None caso contrário
    """
    if not text or len(text) < 10:
        return None

    # Padrão: código de item (X.Y ou X.Y.Z) no meio do texto
    pattern = re.compile(
        r'(.{5,}?)\s+(\d{1,2}\.\d{1,2}(?:\.\d{1,2})?)\s+([A-ZÀ-ÚÇ].{10,})',
        re.IGNORECASE
    )
    match = pattern.search(text)

    if not match:
        return None

    prefix = match.group(1).strip()
    item_code = match.group(2)
    suffix = match.group(3).strip()

    # Verificar contexto - não extrair se precedido por palavra de contexto
    if not is_valid_item_context(text, match.start(2)):
        return None

    # Verificar se o código é válido
    item_tuple = parse_item_tuple(item_code)
    if not item_tuple:
        return None

    # A descrição do item oculto é o suffix
    return {
        "item": item_code,
        "descricao": sanitize_description(suffix),
        "prefix_for_last": prefix  # Texto que deve ir para o item anterior
    }


def extract_trailing_unit(
    desc: str,
    expected_qty: Optional[float] = None
) -> Tuple[str, Optional[str]]:
    """
    Extrai unidade do final da descrição se presente.

    Args:
        desc: Descrição a verificar
        expected_qty: Quantidade esperada (para validar extração de UNIT QTY)

    Returns:
        Tupla (desc_limpa, unidade) ou (desc, None)
    """
    if not desc:
        return desc, None

    # Padrão 1: unidade sozinha no final (ex: "...DESCRIÇÃO M")
    pattern_unit_only = r'\s+(UN|M|M2|M3|M²|M³|KG|L|CJ|VB|PC|PÇ|JG|CONJ)\s*$'
    match = re.search(pattern_unit_only, desc, re.IGNORECASE)
    if match:
        return desc[:match.start()].strip(), match.group(1).upper()

    # Padrão 2: UNIT QTY no meio da descrição (ex: "...COMPRIMENTO. M 29,3 AF_03/2016")
    pattern_unit_qty = r'\.\s+(UN|M|M2|M3|M²|M³|KG|L|CJ|VB|PC|PÇ|JG|CONJ)\s+([\d.,]+)\s+[A-Z]'
    match = re.search(pattern_unit_qty, desc, re.IGNORECASE)
    if match:
        unit = match.group(1).upper()
        qty_str = match.group(2)
        qty = parse_quantity(qty_str)
        # Validar se a quantidade encontrada corresponde à esperada
        if qty is not None and (expected_qty is None or abs(qty - expected_qty) < 0.01):
            clean_desc = desc[:match.start() + 1].strip()  # Manter o ponto
            return clean_desc, unit

    return desc, None


def infer_missing_units(servicos: List[Dict[str, Any]]) -> int:
    """
    Infere unidades faltantes a partir de itens similares.

    Estratégias:
    1. Se um item pai (ex: 3.1) tem unidade, itens filhos (3.2, 3.3...)
       sem unidade herdam a unidade mais comum do prefixo.

    Modifica os serviços in-place.

    Args:
        servicos: Lista de serviços

    Returns:
        Número de unidades inferidas
    """
    if not servicos:
        return 0

    # Construir mapa de prefixo -> unidades conhecidas
    prefix_units: Dict[str, Dict[str, int]] = {}  # prefix -> {unit: count}

    for s in servicos:
        item = s.get("item") or ""
        unit = s.get("unidade") or ""
        if not item or not unit:
            continue
        # Extrair prefixo (ex: "3" de "3.5", "8" de "8.17")
        parts = item.split(".")
        if len(parts) >= 1:
            prefix = parts[0]
            if prefix not in prefix_units:
                prefix_units[prefix] = {}
            prefix_units[prefix][unit] = prefix_units[prefix].get(unit, 0) + 1

    # Inferir unidades faltantes
    inferred = 0
    for s in servicos:
        if s.get("unidade"):
            continue  # Já tem unidade

        item = s.get("item") or ""
        if not item:
            continue

        parts = item.split(".")
        if len(parts) < 1:
            continue

        prefix = parts[0]
        if prefix not in prefix_units:
            continue

        # Encontrar unidade mais comum para este prefixo
        unit_counts = prefix_units[prefix]
        if not unit_counts:
            continue

        most_common_unit = max(unit_counts.keys(), key=lambda u: unit_counts[u])

        # Só inferir se a unidade é dominante (>= 50% dos itens do prefixo)
        total = sum(unit_counts.values())
        if unit_counts[most_common_unit] / total >= 0.5:
            s["unidade"] = most_common_unit
            s["_unit_inferred"] = True
            inferred += 1

    return inferred
