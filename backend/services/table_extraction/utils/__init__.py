"""Utilitários para extração de tabelas."""

from .planilha import (
    build_table_signature,
    should_start_new_planilha,
    collect_item_codes,
    should_restart_prefix,
    apply_restart_prefix,
    first_last_item_tuple,
)

from .merge import merge_table_sources

from .quality import (
    calc_qty_ratio,
    calc_complete_ratio,
    calc_quality_metrics,
)

from .pdf_render import (
    render_pdf_page,
    crop_page_image,
)

from .grid_detect import detect_grid_rows

from .debug_utils import summarize_table_debug

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
