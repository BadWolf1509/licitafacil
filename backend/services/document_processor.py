"""
Serviço integrado de processamento de documentos.
Fachada que delega para sub-processadores especializados.

Pós-processamento de serviços extraído para postprocessor.py.
"""

from typing import Dict, Any, List

from .pdf_extractor import pdf_extractor  # noqa: F401
from .ocr_service import ocr_service  # noqa: F401
from .ai_provider import ai_provider  # noqa: F401
from .document_ai_service import document_ai_service  # noqa: F401
from .pdf_extraction_service import pdf_extraction_service, ProcessingCancelled  # noqa: F401 (re-export)
from .table_extraction_service import table_extraction_service  # noqa: F401
from .document_analysis_service import document_analysis_service  # noqa: F401
from .pdf_converter import pdf_converter  # noqa: F401
from .extraction import (  # noqa: F401 (re-exports)
    normalize_unit,
    normalize_desc_for_match,
    description_similarity,
    parse_item_tuple,
    item_tuple_to_str,
    parse_quantity,
    filter_classification_paths,
    remove_duplicate_services,
    filter_summary_rows,
    UNIT_TOKENS,
    extract_item_code,
    split_item_description,
)
from .edital_processor import edital_processor
from .processing_helpers import (  # noqa: F401 (re-exports)
    normalize_item_code as helpers_normalize_item_code,
    is_section_header_desc,
    is_narrative_desc,
    is_contaminated_desc,
    split_restart_prefix,
    item_key as helpers_item_key,
)
from .processors.text_processor import text_processor  # noqa: F401
from .processors.text_cleanup import strip_trailing_unit_qty  # noqa: F401
from .processors.deduplication import ServiceDeduplicator  # noqa: F401
from .processors.service_merger import ServiceMerger  # noqa: F401
from .processors.validation_filter import ServiceFilter  # noqa: F401
from config import AtestadoProcessingConfig as APC, PAID_SERVICES_ENABLED

# Pós-processamento extraído para módulo dedicado
from . import postprocessor

from logging_config import get_logger
logger = get_logger('services.document_processor')


class DocumentProcessor:
    """Processador integrado de documentos - fachada para sub-processadores."""

    # Delegação para postprocessor (mantém interface para pipeline/processor)
    def _filter_items_without_code(self, servicos: list, min_items_with_code: int = 5) -> list:
        return postprocessor.filter_items_without_code(servicos, min_items_with_code)

    def _build_restart_prefix_maps(self, servicos: list) -> tuple[Dict[tuple, str], Dict[str, str]]:
        return postprocessor.build_restart_prefix_maps(servicos)

    def _should_replace_desc(self, current_desc: str, candidate_desc: str) -> bool:
        return postprocessor.should_replace_desc(current_desc, candidate_desc)

    def _build_text_item_map(self, items: list) -> dict:
        return postprocessor.build_text_item_map(items)

    def _apply_text_descriptions(self, servicos: list, text_map: dict) -> int:
        return postprocessor.apply_text_descriptions(servicos, text_map)

    def _postprocess_servicos(
        self, servicos: list, use_ai: bool, table_used: bool,
        servicos_table: list, texto: str,
        strict_item_gate: bool = False, skip_no_code_dedupe: bool = False
    ) -> list:
        return postprocessor.postprocess_servicos(
            servicos, use_ai, table_used, servicos_table, texto,
            strict_item_gate, skip_no_code_dedupe
        )

    def process_atestado(
        self,
        file_path: str,
        use_vision: bool = True,
        progress_callback=None,
        cancel_check=None
    ) -> Dict[str, Any]:
        """Processa um atestado de capacidade técnica usando abordagem híbrida."""
        from .atestado.pipeline import AtestadoPipeline
        return AtestadoPipeline(self, file_path, use_vision, progress_callback, cancel_check).run()

    def process_edital(self, file_path: str, progress_callback=None, cancel_check=None) -> Dict[str, Any]:
        """Processa uma pagina de edital com quantitativos minimos."""
        return edital_processor.process(file_path, progress_callback, cancel_check)

    def analyze_qualification(
        self,
        exigencias: List[Dict[str, Any]],
        atestados: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Analisa a qualificacao tecnica comparando exigencias e atestados."""
        return edital_processor.analyze_qualification(exigencias, atestados)

    def get_status(self) -> Dict[str, Any]:
        """Retorna o status dos serviços de processamento."""
        provider_status = ai_provider.get_status()
        return {
            "pdf_extractor": True,
            "ocr_service": True,
            "ai_provider": provider_status,
            "document_ai": {
                "available": document_ai_service.is_available,
                "configured": document_ai_service.is_configured,
                "enabled": APC.DOCUMENT_AI_ENABLED,
                "paid_services_enabled": PAID_SERVICES_ENABLED
            },
            "is_configured": ai_provider.is_configured,
            "mensagem": (
                "Serviços pagos desativados (PAID_SERVICES_ENABLED=false)."
                if not PAID_SERVICES_ENABLED
                else (
                    f"IA configurada ({', '.join(ai_provider.available_providers)})"
                    if ai_provider.is_configured
                    else "Configure OPENAI_API_KEY ou GOOGLE_API_KEY para análise inteligente"
                )
            )
        }


# Instancia singleton para uso global
document_processor = DocumentProcessor()

# Configurar AtestadoProcessor com referencia ao DocumentProcessor
# Importação tardia necessária para evitar dependência circular
from .atestado.processor import atestado_processor  # noqa: E402
atestado_processor.set_document_processor(document_processor)
