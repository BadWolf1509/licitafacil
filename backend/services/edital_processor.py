"""
Processador de editais de licitacao.
Extrai exigencias tecnicas de documentos de edital.
"""
from typing import Dict, Any, List
from pathlib import Path

from .pdf_extractor import pdf_extractor
from .pdf_extraction_service import pdf_extraction_service
from .ai_provider import ai_provider
from .matching_service import matching_service
from exceptions import UnsupportedFileError, TextExtractionError, PDFError, OCRError
from logging_config import get_logger

logger = get_logger('services.edital_processor')


class EditalProcessor:
    """Processador de editais de licitacao."""

    def process(
        self,
        file_path: str,
        progress_callback=None,
        cancel_check=None
    ) -> Dict[str, Any]:
        """
        Processa uma pagina de edital com quantitativos minimos.

        Args:
            file_path: Caminho para o arquivo PDF
            progress_callback: Callback para progresso
            cancel_check: Funcao para verificar cancelamento

        Returns:
            Dicionario com exigencias extraidas
        """
        pdf_extraction_service._check_cancel(cancel_check)
        pdf_extraction_service._notify_progress(
            progress_callback, 0, 0, "texto", "Extraindo texto do edital"
        )
        file_ext = Path(file_path).suffix.lower()
        texto = ""
        tabelas = []

        if file_ext != ".pdf":
            raise UnsupportedFileError("nao-PDF", ["PDF"])

        # Extrair conteudo do PDF
        resultado = pdf_extractor.extract_all(file_path)

        if resultado["tem_texto"]:
            texto = resultado["texto"]
            tabelas = resultado["tabelas"]
        else:
            # PDF escaneado - usar OCR
            try:
                images = pdf_extractor.pdf_to_images(file_path)
                texto = pdf_extraction_service.ocr_image_list(
                    images,
                    progress_callback=progress_callback,
                    cancel_check=cancel_check
                )
            except (PDFError, OCRError, IOError) as e:
                raise OCRError(str(e))

        if not texto.strip():
            raise TextExtractionError("edital")

        # Combinar texto e tabelas para analise
        texto_completo = texto
        if tabelas:
            texto_completo += "\n\nTABELAS ENCONTRADAS:\n"
            for i, tabela in enumerate(tabelas):
                texto_completo += f"\nTabela {i + 1}:\n"
                for linha in tabela:
                    texto_completo += " | ".join(linha) + "\n"

        # Extrair exigencias com IA
        if ai_provider.is_configured:
            pdf_extraction_service._notify_progress(
                progress_callback, 0, 0, "ia", "Analisando exigencias"
            )
            pdf_extraction_service._check_cancel(cancel_check)
            # Usar provider configurado via ai_provider
            provider = ai_provider.get_provider_instance()
            from .ai.extraction_service import AIExtractionService
            service = AIExtractionService()
            exigencias = service.extract_edital_requirements(texto_completo, provider=provider)
        else:
            exigencias = []

        pdf_extraction_service._notify_progress(
            progress_callback, 0, 0, "final", "Finalizando processamento"
        )
        return {
            "texto_extraido": texto,
            "tabelas": tabelas,
            "exigencias": exigencias,
            "paginas": resultado.get("paginas", 1)
        }

    def analyze_qualification(
        self,
        exigencias: List[Dict[str, Any]],
        atestados: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Analisa a qualificacao tecnica comparando exigencias e atestados.

        Args:
            exigencias: Lista de exigencias do edital
            atestados: Lista de atestados do usuario

        Returns:
            Resultado da analise com status de atendimento
        """
        return matching_service.match_exigencias(exigencias, atestados)


# Singleton
edital_processor = EditalProcessor()
