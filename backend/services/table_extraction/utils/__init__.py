"""Utilitários para extração de tabelas."""

from .debug_utils import summarize_table_debug
from .grid_detect import detect_grid_rows
from .merge import merge_table_sources
from .pdf_render import (
    crop_page_image,
    render_pdf_page,
)
from .planilha import (
    apply_restart_prefix,
    build_table_signature,
    collect_item_codes,
    first_last_item_tuple,
    should_restart_prefix,
    should_start_new_planilha,
)
from .quality import (
    calc_complete_ratio,
    calc_qty_ratio,
    calc_quality_metrics,
)

__all__ = [
    # planilha
    "build_table_signature",
    "should_start_new_planilha",
    "collect_item_codes",
    "should_restart_prefix",
    "apply_restart_prefix",
    "first_last_item_tuple",
    # merge
    "merge_table_sources",
    # quality
    "calc_qty_ratio",
    "calc_complete_ratio",
    "calc_quality_metrics",
    # pdf_render
    "render_pdf_page",
    "crop_page_image",
    # grid_detect
    "detect_grid_rows",
    # debug_utils
    "summarize_table_debug",
]
