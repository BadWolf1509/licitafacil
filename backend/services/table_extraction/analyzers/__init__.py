"""
Analisadores para extracao de tabelas.

Contem funcoes de analise de qualidade e tipo de documento.
"""

from .quality import (
    calc_qty_ratio,
    calc_complete_ratio,
    calc_quality_metrics,
)

from .document import analyze_document_type

__all__ = [
    # Quality
    'calc_qty_ratio',
    'calc_complete_ratio',
    'calc_quality_metrics',
    # Document
    'analyze_document_type',
]
