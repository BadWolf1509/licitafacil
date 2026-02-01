"""
Processador síncrono para ambientes serverless.

Processa documentos de forma síncrona, sem fila.
Ideal para Vercel, AWS Lambda, Google Cloud Functions.
"""
import os
import uuid
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from logging_config import get_logger
from models import Atestado
from services.atestado import AtestadoProcessor

logger = get_logger('services.sync_processor')


class SyncProcessor:
    """
    Processador síncrono de documentos.

    Processa atestados imediatamente, sem usar fila.
    Retorna o resultado diretamente.
    """

    def __init__(self):
        self._processor = AtestadoProcessor()

    def process_atestado(
        self,
        db: Session,
        user_id: int,
        file_path: str,
        original_filename: str,
        use_vision: bool = True
    ) -> Dict[str, Any]:
        """
        Processa um atestado de forma síncrona.

        Args:
            db: Sessão do banco de dados
            user_id: ID do usuário
            file_path: Caminho do arquivo
            original_filename: Nome original do arquivo
            use_vision: Se deve usar OCR/Vision

        Returns:
            Dicionário com dados extraídos e ID do atestado criado
        """
        logger.info(f"[SYNC] Processando atestado: {original_filename}")

        try:
            # Processar documento
            resultado = self._processor.process(file_path, use_vision=use_vision)

            # Criar atestado no banco
            atestado = self._save_atestado(
                db=db,
                user_id=user_id,
                file_path=file_path,
                original_filename=original_filename,
                resultado=resultado
            )

            logger.info(f"[SYNC] Atestado {atestado.id} criado com sucesso")

            return {
                "success": True,
                "atestado_id": atestado.id,
                "servicos_count": len(resultado.get("servicos", [])),
                "dados": resultado
            }

        except Exception as e:
            logger.error(f"[SYNC] Erro ao processar atestado: {e}")
            return {
                "success": False,
                "error": str(e),
                "atestado_id": None
            }

    def _save_atestado(
        self,
        db: Session,
        user_id: int,
        file_path: str,
        original_filename: str,
        resultado: Dict[str, Any]
    ) -> Atestado:
        """Salva atestado processado no banco."""
        from services.atestado import salvar_atestado_processado

        # Criar contexto similar ao usado pela fila
        job_context = {
            "user_id": user_id,
            "file_path": file_path,
            "original_filename": original_filename
        }

        return salvar_atestado_processado(db, resultado, job_context)


# Singleton
_sync_processor: Optional[SyncProcessor] = None


def get_sync_processor() -> SyncProcessor:
    """Retorna instância do processador síncrono."""
    global _sync_processor
    if _sync_processor is None:
        _sync_processor = SyncProcessor()
    return _sync_processor
