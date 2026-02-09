"""
Filtros de classificação para serviços extraídos.

Contém funções para identificar e filtrar caminhos de classificação
que não são serviços reais.
"""

import re

from .table_processor import parse_item_tuple

_COMPARISON_PATTERN = re.compile(r"(>=|<=|>|<)\s*\d")


def _is_technical_comparison(desc_upper: str) -> bool:
    """Verifica se descrição contém comparação técnica (ex: FCK >= 25MPA)."""
    if not desc_upper:
        return False
    if "FCK" in desc_upper or "MPA" in desc_upper:
        return True
    return bool(_COMPARISON_PATTERN.search(desc_upper))


def _has_valid_item_and_quantity(servico: dict) -> bool:
    """
    Verifica se o serviço tem código de item válido e quantidade.

    Itens com código e quantidade válidos devem ser preservados
    mesmo que a descrição esteja incompleta (podem ser recuperados depois).

    Args:
        servico: Dicionário do serviço

    Returns:
        True se tem item válido e quantidade
    """
    item = servico.get("item")
    quantidade = servico.get("quantidade")

    # Verificar se tem código de item válido (ex: "1.1", "6.3.4")
    if not item:
        return False
    item_tuple = parse_item_tuple(str(item))
    if not item_tuple or len(item_tuple) < 2:
        return False

    # Verificar se tem quantidade válida
    if quantidade is None:
        return False
    try:
        qty = float(quantidade)
        return qty > 0
    except (TypeError, ValueError):
        return False


def is_classification_path(descricao: str) -> bool:
    """
    Verifica se uma descrição é um caminho de classificação.

    Args:
        descricao: Descrição a verificar

    Returns:
        True se for caminho de classificação
    """
    if not descricao:
        return False

    desc_upper = descricao.upper().strip()

    # Verificar padrão de classificação com ">"
    if ">" in descricao and not _is_technical_comparison(desc_upper):
        return True

    # Prefixos de classificação
    invalid_prefixes = [
        "DIRETA OBRAS", "1 - DIRETA",
        "2 - DIRETA", "ATIVIDADE TÉCNICA", "CLASSIFICAÇÃO",
    ]

    for prefix in invalid_prefixes:
        if desc_upper.startswith(prefix):
            return True

    if desc_upper.startswith("EXECUÇÃO") and ">" in desc_upper:
        return True

    return False


def filter_classification_paths(servicos: list) -> list:
    """
    Remove serviços que são caminhos de classificação (não serviços reais).

    Isso inclui itens que contêm ">" (caminho de classificação) ou
    começam com padrões de classificação de CAT.

    Preserva itens com código válido e quantidade mesmo se descrição curta.

    Args:
        servicos: Lista de serviços

    Returns:
        Lista filtrada
    """
    if not servicos:
        return []

    filtered = []
    for servico in servicos:
        descricao = servico.get("descricao", "") or ""

        # Preservar itens com código e quantidade válidos (descrição pode ser recuperada)
        has_valid_item_qty = _has_valid_item_and_quantity(servico)

        if not descricao.strip():
            # Só continuar se tiver item e quantidade válidos
            if has_valid_item_qty:
                filtered.append(servico)
            continue

        # Ignore classification paths but allow technical comparisons (e.g., FCK >= 25MPA).
        desc_upper = descricao.upper().strip()

        if ">" in descricao and not (has_valid_item_qty or _is_technical_comparison(desc_upper)):
            continue

        # Prefixos que SEMPRE são classificação (não serviços reais)
        invalid_prefixes = [
            "DIRETA OBRAS", "1 - DIRETA",
            "2 - DIRETA", "ATIVIDADE TÉCNICA", "CLASSIFICAÇÃO",
        ]

        is_invalid = False
        for prefix in invalid_prefixes:
            if desc_upper.startswith(prefix):
                is_invalid = True
                break

        # "EXECUÇÃO" é inválido APENAS se seguido de ">" (classificação)
        if desc_upper.startswith("EXECUÇÃO") and ">" in desc_upper:
            is_invalid = True

        if is_invalid:
            continue

        # Ignorar itens muito curtos, MAS preservar se tiver código e quantidade
        if len(descricao.strip()) < 5:
            if has_valid_item_qty:
                filtered.append(servico)
            continue

        filtered.append(servico)

    return filtered
