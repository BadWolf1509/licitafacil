"""
Serviço para operações de atestados.
Contém lógica de negócio extraída dos routers.
"""
import re
from datetime import date, datetime
from typing import Optional, List

from database import get_db_session
from models import Atestado
from config import Messages
from logging_config import get_logger

logger = get_logger('services.atestado')


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

    Trata itens como "1.1", "2.10", "3.1.2" e aditivos "AD1-1.1" corretamente.
    Itens de aditivo (AD1-, AD2-, etc.) vêm depois dos itens originais.

    Args:
        servico: Dicionário do serviço com campo 'item'

    Returns:
        Tupla para ordenação
    """
    item = servico.get("item", "") or ""
    if not item:
        return (float('inf'), 0)  # Itens sem número vão para o final

    try:
        # Verificar se é item de aditivo (AD1-1.1, AD2-2.3, etc.)
        aditivo_num = 0
        aditivo_match = re.match(r'^AD(\d+)-(.+)$', item)
        if aditivo_match:
            aditivo_num = int(aditivo_match.group(1))
            item = aditivo_match.group(2)  # Pegar apenas a parte do item

        # Divide o item em partes numéricas (ex: "2.10.1" -> [2, 10, 1])
        parts = []
        for part in item.split('.'):
            # Remove caracteres não numéricos e converte
            num_str = ''.join(c for c in part if c.isdigit())
            if num_str:
                parts.append(int(num_str))
            else:
                parts.append(0)

        # Retorna tupla: (numero_aditivo, partes_do_item...)
        # Assim itens originais (aditivo=0) vêm antes dos aditivos (aditivo=1, 2, ...)
        return (aditivo_num,) + tuple(parts) if parts else (float('inf'), 0)
    except (ValueError, AttributeError):
        return (float('inf'), 0)


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


def salvar_atestado_processado(job) -> None:
    """
    Salva o resultado do processamento de um atestado no banco.

    Chamado como callback após processamento OCR/AI.
    Atualiza registro existente ou cria novo.

    Args:
        job: Job de processamento com resultado
    """
    from services.processing_queue import JobStatus

    if job.status != JobStatus.COMPLETED:
        return

    result = job.result or {}
    data_emissao = parse_date(result.get("data_emissao"))
    servicos = ordenar_servicos(result.get("servicos") or [])

    try:
        with get_db_session() as db:
            existente = db.query(Atestado).filter(
                Atestado.user_id == job.user_id,
                Atestado.arquivo_path == job.file_path
            ).first()

            if existente:
                existente.descricao_servico = result.get("descricao_servico") or Messages.DESCRICAO_NAO_IDENTIFICADA
                existente.quantidade = result.get("quantidade") or 0
                existente.unidade = result.get("unidade") or ""
                existente.contratante = result.get("contratante")
                existente.data_emissao = data_emissao
                existente.texto_extraido = result.get("texto_extraido")
                existente.servicos_json = servicos if servicos else None
                db.commit()
                return

            novo_atestado = Atestado(
                user_id=job.user_id,
                descricao_servico=result.get("descricao_servico") or Messages.DESCRICAO_NAO_IDENTIFICADA,
                quantidade=result.get("quantidade") or 0,
                unidade=result.get("unidade") or "",
                contratante=result.get("contratante"),
                data_emissao=data_emissao,
                arquivo_path=job.file_path,
                texto_extraido=result.get("texto_extraido"),
                servicos_json=servicos if servicos else None
            )
            db.add(novo_atestado)
            db.commit()
    except Exception as e:
        logger.error(f"Erro ao salvar atestado do job {job.id}: {e}")
