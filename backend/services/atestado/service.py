"""
Funções de utilidade para atestados.

Inclui parsing de datas, ordenação de serviços e conversão de dados.
"""
import re
from datetime import date, datetime
from typing import List, Optional


def parse_date(date_str: Optional[str]) -> Optional[date]:
    """
    Converte string de data para objeto date do Python.

    Suporta formatos:
    - ISO: YYYY-MM-DD
    - Brasileiro: DD/MM/YYYY

    Args:
        date_str: String de data para converter

    Returns:
        Objeto date ou None se inválido
    """
    if not date_str:
        return None
    try:
        # Tentar formato ISO (YYYY-MM-DD)
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        try:
            # Tentar formato brasileiro (DD/MM/YYYY)
            return datetime.strptime(date_str, "%d/%m/%Y").date()
        except ValueError:
            return None


def sort_key_item(servico: dict) -> tuple:
    """
    Gera uma chave de ordenação para um serviço baseado no número do item.

    Trata itens como "1.1", "2.10", "3.1.2" e reinícios "S2-1.1" corretamente.
    Também trata sufixos de duplicata (-A, -B, etc.) para ordenação correta.
    Itens com prefixo Sx vêm depois dos itens originais.

    Args:
        servico: Dicionário do serviço com campo 'item'

    Returns:
        Tupla para ordenação
    """
    item = servico.get("item", "") or ""
    if not item:
        return (float('inf'), 0, 0)  # Itens sem número vão para o final

    try:
        # Verificar prefixo de reinício (S2-1.1, S3-2.4, etc.)
        segment_num = 0
        segment_match = re.match(r'^S(\d+)-(.+)$', item, re.IGNORECASE)
        if segment_match:
            segment_num = int(segment_match.group(1))
            item = segment_match.group(2)
        else:
            # Legacy: aditivo (AD-1.1, AD1-1.1, AD2-2.3, etc.)
            aditivo_match = re.match(r'^AD(\d*)-(.+)$', item, re.IGNORECASE)
            if aditivo_match:
                aditivo_num = int(aditivo_match.group(1)) if aditivo_match.group(1) else 1
                segment_num = 100 + aditivo_num
                item = aditivo_match.group(2)  # Pegar apenas a parte do item

        # Extrair sufixo de duplicata (-A, -B, etc.) do final
        suffix_num = 0
        suffix_match = re.match(r'^(.+)-([A-Z])$', item)
        if suffix_match:
            item = suffix_match.group(1)  # Item sem sufixo
            suffix_num = ord(suffix_match.group(2)) - ord('A') + 1  # A=1, B=2, C=3

        # Divide o item em partes numéricas (ex: "2.10.1" -> [2, 10, 1])
        parts = []
        for part in item.split('.'):
            # Remove caracteres não numéricos e converte
            num_str = ''.join(c for c in part if c.isdigit())
            if num_str:
                parts.append(int(num_str))
            else:
                parts.append(0)

        # Retorna tupla: (segmento, partes_do_item..., sufixo_duplicata)
        # Assim: originais (segmento=0) < S2 < S3 < ... < AD (segmento>=101)
        # E: sem sufixo (0) < -A (1) < -B (2) ...
        if parts:
            return (segment_num,) + tuple(parts) + (suffix_num,)
        return (float('inf'), 0, 0)
    except (ValueError, AttributeError):
        return (float('inf'), 0, 0)


def ordenar_servicos(servicos: List[dict]) -> List[dict]:
    """
    Ordena lista de serviços pelo número do item.

    Args:
        servicos: Lista de dicionários de serviços

    Returns:
        Lista ordenada
    """
    if not servicos:
        return servicos
    return sorted(servicos, key=sort_key_item)


def atestados_to_dict(atestados: list) -> List[dict]:
    """
    Converte lista de atestados ORM para dicionários de análise.

    Usado para preparar atestados para matching com exigências de edital.

    Args:
        atestados: Lista de objetos Atestado (ORM)

    Returns:
        Lista de dicionários com campos necessários para análise
    """
    return [
        {
            "id": at.id,
            "descricao_servico": at.descricao_servico,
            "quantidade": float(at.quantidade) if at.quantidade else 0,
            "unidade": at.unidade or "",
            "servicos_json": at.servicos_json
        }
        for at in atestados
    ]
