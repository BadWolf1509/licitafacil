"""
Corretor de descrições para garantir 100% de fidelidade ao PDF original.

NOTA: Este módulo foi refatorado e dividido em submódulos.
Este arquivo mantém compatibilidade com imports existentes.

Para novos imports, use:
    from services.description_fixer import fix_descriptions
"""

# Re-exportar função principal do novo módulo
from services.description_fixer.core import fix_descriptions

# Re-exportar constantes para compatibilidade
from services.description_fixer.constants import (
    STOP_PREFIXES,
    REVERSED_FOOTER_TOKENS,
    FOOTER_DATE_PATTERN
)

# Re-exportar funções auxiliares para compatibilidade (uso interno)
from services.description_fixer.validation import (
    is_valid_prefix_line as _is_valid_prefix_line,
    is_description_fragment as _is_description_fragment,
    prev_line_is_continuation as _prev_line_is_continuation,
    should_prefix_with_previous as _should_prefix_with_previous,
    looks_like_reversed_footer_line as _looks_like_reversed_footer_line
)

from services.description_fixer.collection import (
    collect_continuation_lines as _collect_continuation_lines,
    collect_previous_lines as _collect_previous_lines
)

from services.description_fixer.indexing import (
    build_line_to_page_map as _build_line_to_page_map,
    build_item_line_index as _build_item_line_index
)

from services.description_fixer.matching import (
    extract_unit_qty as _extract_unit_qty,
    normalize_unit as _normalize_unit,
    group_candidates_by_proximity as _group_candidates_by_proximity,
    get_segment_index as _get_segment_index,
    filter_candidates_by_page as _filter_candidates_by_page,
    select_candidate_group as _select_candidate_group,
    find_quantity_match as _find_quantity_match,
    build_match_result as _build_match_result_from_qty_match,
    score_candidate as _score_candidate,
    find_best_match as _find_best_match,
    extract_description_from_line as _extract_description_from_line
)

__all__ = ['fix_descriptions']
