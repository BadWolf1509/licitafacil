"""
Serviço de integração com Azure Document Intelligence.
Usa o modelo Read para OCR de alta qualidade em documentos difíceis.
"""

import os
import time
from typing import Dict, Any, List
from dataclasses import dataclass
from dotenv import load_dotenv

from logging_config import get_logger
logger = get_logger('services.azure_document_service')

load_dotenv()


@dataclass
class AzureExtractionResult:
    """Resultado da extração pelo Azure."""
    text: str
    pages: List[Dict[str, Any]]
    tables: List[Dict[str, Any]]
    confidence: float
    processing_time: float


class AzureDocumentService:
    """Serviço de OCR usando Azure Document Intelligence."""

    def __init__(self):
        self._endpoint = os.getenv("AZURE_DOCUMENT_ENDPOINT")
        self._key = os.getenv("AZURE_DOCUMENT_KEY")
        self._client = None
        self._initialized = False

    def _initialize(self):
        """Inicializa o cliente Azure sob demanda."""
        if self._initialized:
            return

        if not self._endpoint or not self._key:
            self._initialized = True
            return

        try:
            from azure.ai.documentintelligence import DocumentIntelligenceClient
            from azure.core.credentials import AzureKeyCredential

            self._client = DocumentIntelligenceClient(
                endpoint=self._endpoint,
                credential=AzureKeyCredential(self._key)
            )
            self._initialized = True
        except ImportError:
            logger.warning("Pacote azure-ai-documentintelligence não instalado")
            self._initialized = True
        except Exception as e:
            logger.error(f"Erro ao inicializar Azure Document Intelligence: {e}")
            self._initialized = True

    @property
    def is_configured(self) -> bool:
        """Verifica se o serviço está configurado."""
        self._initialize()
        return self._client is not None

    def extract_text_from_file(self, file_path: str) -> AzureExtractionResult:
        """
        Extrai texto de um arquivo usando Azure Document Intelligence.

        Args:
            file_path: Caminho para o arquivo (PDF ou imagem)

        Returns:
            AzureExtractionResult com texto e metadados
        """
        if not self.is_configured:
            raise Exception(
                "Azure Document Intelligence não configurado. "
                "Defina AZURE_DOCUMENT_ENDPOINT e AZURE_DOCUMENT_KEY no .env"
            )

        try:
            with open(file_path, "rb") as f:
                file_content = f.read()

            return self.extract_text_from_bytes(file_content)

        except Exception as e:
            raise Exception(f"Erro ao processar arquivo com Azure: {str(e)}")

    def extract_text_from_bytes(self, content: bytes) -> AzureExtractionResult:
        """
        Extrai texto de bytes usando Azure Document Intelligence.

        Args:
            content: Conteúdo do arquivo em bytes

        Returns:
            AzureExtractionResult com texto e metadados
        """
        if not self.is_configured:
            raise Exception(
                "Azure Document Intelligence não configurado. "
                "Defina AZURE_DOCUMENT_ENDPOINT e AZURE_DOCUMENT_KEY no .env"
            )

        start_time = time.time()

        try:
            # Usar modelo "prebuilt-read" para OCR
            poller = self._client.begin_analyze_document(
                model_id="prebuilt-read",
                analyze_request=content,
                content_type="application/octet-stream"
            )

            result = poller.result()

            # Extrair texto de todas as páginas
            full_text = []
            pages_data = []
            total_confidence = 0
            word_count = 0

            for page in result.pages:
                page_text = []
                page_words = []

                for line in page.lines or []:
                    page_text.append(line.content)

                for word in page.words or []:
                    page_words.append({
                        'content': word.content,
                        'confidence': word.confidence
                    })
                    total_confidence += word.confidence
                    word_count += 1

                pages_data.append({
                    'page_number': page.page_number,
                    'width': page.width,
                    'height': page.height,
                    'text': '\n'.join(page_text),
                    'word_count': len(page_words),
                    'words': page_words
                })

                full_text.append(f"--- Página {page.page_number} ---")
                full_text.append('\n'.join(page_text))

            # Extrair tabelas se houver
            tables_data = []
            for table in result.tables or []:
                table_info = {
                    'row_count': table.row_count,
                    'column_count': table.column_count,
                    'cells': []
                }
                for cell in table.cells or []:
                    table_info['cells'].append({
                        'row': cell.row_index,
                        'column': cell.column_index,
                        'content': cell.content,
                        'row_span': cell.row_span,
                        'column_span': cell.column_span
                    })
                tables_data.append(table_info)

            avg_confidence = total_confidence / word_count if word_count > 0 else 0
            processing_time = time.time() - start_time

            return AzureExtractionResult(
                text='\n\n'.join(full_text),
                pages=pages_data,
                tables=tables_data,
                confidence=avg_confidence,
                processing_time=processing_time
            )

        except Exception as e:
            raise Exception(f"Erro na API Azure: {str(e)}")

    def get_status(self) -> Dict[str, Any]:
        """Retorna status do serviço."""
        self._initialize()
        return {
            'configured': self.is_configured,
            'endpoint': self._endpoint[:30] + '...' if self._endpoint else None,
            'model': 'prebuilt-read',
            'cost_per_page': 0.001,  # $0.001/página para Read
            'free_tier': '500 páginas/mês'
        }


# Instância singleton
azure_document_service = AzureDocumentService()
