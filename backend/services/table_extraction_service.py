"""
Serviço de Extração de Tabelas.

Responsável por:
- Extração de serviços de tabelas em PDFs
- Processamento com pdfplumber e Document AI
- Extração baseada em layout OCR
- Cascata de extração com thresholds de qualidade
"""

from typing import Optional, Callable


# Importar módulos extraídos do pacote table_extraction
from .table_extraction.parsers import (
    parse_row_text_to_servicos as _parse_row_text_to_servicos,
)
from .table_extraction.extractors import (
    TableExtractor,
    infer_missing_units,
    extract_servicos_from_tables as _extract_servicos_from_tables,
    extract_servicos_from_document_ai as _extract_servicos_from_document_ai,
    extract_servicos_from_grid_ocr as _extract_servicos_from_grid_ocr,
    extract_servicos_from_ocr_layout as _extract_servicos_from_ocr_layout,
    build_table_from_ocr_words as _build_table_from_ocr_words,
    infer_item_column_from_words as _infer_item_column_from_words,
    assign_itemless_items as _assign_itemless_items,
    is_retry_result_better as _is_retry_result_better,
    extract_from_ocr_words as _extract_from_ocr_words,
)
from .table_extraction.utils import (
    calc_qty_ratio as _calc_qty_ratio,
    calc_complete_ratio as _calc_complete_ratio,
    calc_quality_metrics as _calc_quality_metrics,
    merge_table_sources as _merge_table_sources,
    render_pdf_page as _render_pdf_page,
    crop_page_image as _crop_page_image,
    detect_grid_rows as _detect_grid_rows,
    first_last_item_tuple as _first_last_item_tuple,
    build_table_signature as _build_table_signature,
    should_start_new_planilha as _should_start_new_planilha,
    collect_item_codes as _collect_item_codes,
    should_restart_prefix as _should_restart_prefix,
    apply_restart_prefix as _apply_restart_prefix,
    summarize_table_debug as _summarize_table_debug_fn,
)
from .table_extraction.analyzers import analyze_document_type as _analyze_document_type
from .table_extraction.cascade import CascadeStrategy


from logging_config import get_logger
logger = get_logger('services.table_extraction_service')


# Type aliases para callbacks
ProgressCallback = Optional[Callable[[int, int, str, str], None]]
CancelCheck = Optional[Callable[[], bool]]


class TableExtractionService:
    """
    Serviço para extração de serviços de tabelas em documentos.

    Implementa um fluxo em cascata:
    1. pdfplumber (gratuito) - se qty_ratio >= 70%: SUCESSO
    2. Document AI (~R$0.008/pág) - se qty_ratio >= 60%: SUCESSO
    3. Fallback para melhor resultado disponível
    """

    def __init__(self):
        """Inicializa o serviço com a estratégia de cascata."""
        self._cascade = CascadeStrategy(self)

    # ==================== Métodos Delegados Utilizados ====================
    # Mantidos apenas os métodos chamados pelos extratores

    def _infer_missing_units(self, servicos: list) -> int:
        """Delega para função extraída do pacote table_extraction."""
        return infer_missing_units(servicos)

    def extract_servicos_from_table(
        self,
        table: list,
        preferred_item_col: Optional[int] = None,
        allow_itemless: bool = False,
        ignore_item_numbers: bool = False
    ) -> tuple[list, float, dict]:
        """Delega para TableExtractor do pacote table_extraction.extractors."""
        extractor = TableExtractor()
        return extractor.extract(
            table,
            preferred_item_col=preferred_item_col,
            allow_itemless=allow_itemless,
            ignore_item_numbers=ignore_item_numbers
        )

    def _first_last_item_tuple(self, servicos: list) -> tuple[Optional[tuple], Optional[tuple]]:
        """Delega para funcao extraida do pacote table_extraction.utils."""
        return _first_last_item_tuple(servicos)

    def _build_table_signature(self, table: list, debug: dict) -> dict:
        """Delega para funcao extraida do pacote table_extraction.utils."""
        return _build_table_signature(table, debug)

    def _should_start_new_planilha(
        self,
        current_planilha: Optional[dict],
        sig_info: dict,
        first_tuple: Optional[tuple]
    ) -> tuple[bool, str]:
        """Delega para funcao extraida do pacote table_extraction.utils."""
        return _should_start_new_planilha(current_planilha, sig_info, first_tuple)

    def _collect_item_codes(self, servicos: list) -> set:
        """Delega para funcao extraida do pacote table_extraction.utils."""
        return _collect_item_codes(servicos)

    def _should_restart_prefix(
        self,
        first_tuple: Optional[tuple],
        max_tuple: Optional[tuple],
        table_codes: set,
        seen_codes: set
    ) -> tuple[bool, dict]:
        """Delega para funcao extraida do pacote table_extraction.utils."""
        return _should_restart_prefix(first_tuple, max_tuple, table_codes, seen_codes)

    def _apply_restart_prefix(self, servicos: list, prefix: str) -> None:
        """Delega para funcao extraida do pacote table_extraction.utils."""
        return _apply_restart_prefix(servicos, prefix)

    def extract_servicos_from_tables(self, file_path: str) -> tuple[list, float, dict]:
        """Delega para funcao extraida do pacote table_extraction.extractors."""
        return _extract_servicos_from_tables(self, file_path)

    def extract_servicos_from_document_ai(
        self,
        file_path: str,
        use_native_pdf_parsing: bool = False,
        allow_itemless: bool = False,
        ignore_item_numbers: bool = False
    ) -> tuple[list, float, dict]:
        """Delega para funcao extraida do pacote table_extraction.extractors."""
        return _extract_servicos_from_document_ai(
            self, file_path, use_native_pdf_parsing, allow_itemless, ignore_item_numbers
        )

    def calc_qty_ratio(self, servicos: list) -> float:
        """Delega para função extraída do pacote table_extraction."""
        return _calc_qty_ratio(servicos)

    def calc_complete_ratio(self, servicos: list) -> float:
        """Delega para função extraída do pacote table_extraction."""
        return _calc_complete_ratio(servicos)

    def calc_quality_metrics(self, servicos: list) -> dict:
        """Delega para função extraída do pacote table_extraction."""
        return _calc_quality_metrics(servicos)

    def _merge_table_sources(self, primary: list, secondary: list) -> tuple[list, dict]:
        """Delega para funcao extraida do pacote table_extraction.utils."""
        return _merge_table_sources(primary, secondary)

    def analyze_document_type(self, file_path: str) -> dict:
        """Delega para funcao extraida do pacote table_extraction.analyzers."""
        return _analyze_document_type(file_path)

    def _render_pdf_page(self, file_path: str, page_index: int, dpi: int) -> Optional[bytes]:
        """Delega para funcao extraida do pacote table_extraction.utils."""
        return _render_pdf_page(file_path, page_index, dpi)

    def _crop_page_image(
        self,
        file_path: str,
        file_ext: str,
        page_index: int,
        image_bytes: bytes
    ) -> bytes:
        """Delega para funcao extraida do pacote table_extraction.utils."""
        return _crop_page_image(file_path, file_ext, page_index, image_bytes)

    def _build_table_from_ocr_words(
        self,
        words: list,
        row_tol_factor: float = 0.6,
        col_tol_factor: float = 0.7,
        min_row_tol: float = 6.0,
        min_col_tol: float = 18.0
    ) -> tuple[list, list]:
        """Delega para funcao extraida do pacote table_extraction.extractors."""
        return _build_table_from_ocr_words(words, row_tol_factor, col_tol_factor, min_row_tol, min_col_tol)

    def _infer_item_column_from_words(self, words: list, col_centers: list) -> tuple[Optional[int], dict]:
        """Delega para funcao extraida do pacote table_extraction.extractors."""
        return _infer_item_column_from_words(words, col_centers)

    def _extract_from_ocr_words(
        self,
        words: list,
        row_tol_factor: float = 0.6,
        col_tol_factor: float = 0.7,
        enable_refine: bool = True
    ) -> tuple[list, float, dict, dict]:
        """Delega para funcao extraida do pacote table_extraction.extractors."""
        return _extract_from_ocr_words(self, words, row_tol_factor, col_tol_factor, enable_refine)

    def _assign_itemless_items(self, servicos: list, page_number: int) -> None:
        """Delega para funcao extraida do pacote table_extraction.extractors."""
        return _assign_itemless_items(servicos, page_number)

    def _detect_grid_rows(self, image_bytes: bytes) -> tuple[list, dict]:
        """Delega para funcao extraida do pacote table_extraction.utils."""
        return _detect_grid_rows(image_bytes)

    def _parse_row_text_to_servicos(self, row_text: str) -> list:
        """Delega para funcao extraida do pacote table_extraction.parsers."""
        return _parse_row_text_to_servicos(row_text)

    def extract_servicos_from_grid_ocr(
        self,
        file_path: str,
        progress_callback: ProgressCallback = None,
        cancel_check: CancelCheck = None
    ) -> tuple[list, float, dict]:
        """Delega para funcao extraida do pacote table_extraction.extractors."""
        return _extract_servicos_from_grid_ocr(self, file_path, progress_callback, cancel_check)

    def _is_retry_result_better(
        self,
        servicos_retry: list,
        servicos_current: list,
        metrics_retry: dict,
        metrics_current: dict
    ) -> bool:
        """Delega para funcao extraida do pacote table_extraction.extractors."""
        return _is_retry_result_better(servicos_retry, servicos_current, metrics_retry, metrics_current)

    def extract_servicos_from_ocr_layout(
        self,
        file_path: str,
        progress_callback: ProgressCallback = None,
        cancel_check: CancelCheck = None
    ) -> tuple[list, float, dict]:
        """Delega para funcao extraida do pacote table_extraction.extractors."""
        return _extract_servicos_from_ocr_layout(self, file_path, progress_callback, cancel_check)

    def _summarize_table_debug(self, debug: dict) -> dict:
        """Delega para funcao extraida do pacote table_extraction.utils."""
        return _summarize_table_debug_fn(debug)

    def extract_cascade(
        self,
        file_path: str,
        file_ext: str,
        progress_callback: ProgressCallback = None,
        cancel_check: CancelCheck = None,
        doc_analysis: Optional[dict] = None
    ) -> tuple[list, float, dict, dict]:
        """
        Delega para CascadeStrategy.execute().

        Extrai serviços de tabelas usando fluxo em cascata otimizado.
        """
        return self._cascade.execute(
            file_path=file_path,
            file_ext=file_ext,
            progress_callback=progress_callback,
            cancel_check=cancel_check,
            doc_analysis=doc_analysis
        )


# Instância singleton para uso global
table_extraction_service = TableExtractionService()
