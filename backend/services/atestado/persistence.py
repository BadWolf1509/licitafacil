"""
Persistência de atestados no banco de dados.

Fornece funções para salvar e atualizar atestados processados.
"""
from database import get_db_session
from models import Atestado
from config import Messages
from logging_config import get_logger

from .service import parse_date, ordenar_servicos

logger = get_logger('services.atestado.persistence')


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
