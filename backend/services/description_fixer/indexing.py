"""
Funções de construção de índice para o corretor de descrições.
"""
from typing import Dict, List

from services.extraction import is_corrupted_text
from services.extraction.patterns import Patterns

from .collection import collect_continuation_lines, collect_previous_lines
from .matching import extract_unit_qty
from .validation import is_description_fragment, should_prefix_with_previous


def build_line_to_page_map(texto: str) -> Dict[int, int]:
    """
    Constrói mapeamento de número de linha para número de página.

    Args:
        texto: Texto extraído do PDF

    Returns:
        Dict mapeando linha (1-indexed) -> número da página
    """
    line_to_page: Dict[int, int] = {}
    lines = texto.split('\n')
    current_page = 1

    for i, line in enumerate(lines):
        line_num = i + 1
        line_stripped = line.strip()

        page_match = Patterns.PAGE_MARKER.search(line_stripped)
        if page_match:
            current_page = int(page_match.group(1))

        line_to_page[line_num] = current_page

    return line_to_page


def build_item_line_index(texto: str) -> Dict[str, List[Dict]]:
    """
    Constrói índice de TODAS as linhas que contêm cada item.

    Returns:
        Dict mapeando item -> lista de candidatos com linha, texto, unidade, quantidade
    """
    index: Dict[str, List[Dict]] = {}
    lines = texto.split('\n')

    i = 0
    while i < len(lines):
        line_stripped = lines[i].strip()
        if not line_stripped:
            i += 1
            continue

        match = Patterns.ITEM_PATTERN.match(line_stripped)
        if match:
            item_code = match.group(1)
            full_text = line_stripped
            line_is_corrupted = is_corrupted_text(line_stripped)

            # Verificar UNIT_FIRST
            unit_first_match = Patterns.UNIT_FIRST.match(line_stripped)
            if unit_first_match and i > 0:
                prev_text = collect_previous_lines(lines, i)
                if prev_text:
                    full_text = prev_text + " " + line_stripped

            # Verificar UNIT_LAST
            if not unit_first_match and i > 0:
                unit_last_match = Patterns.UNIT_LAST.match(line_stripped)
                if unit_last_match:
                    desc_in_line = unit_last_match.group(2).strip()
                    prev_line = lines[i - 1].strip()

                    if should_prefix_with_previous(desc_in_line, prev_line, lines, i):
                        full_text = prev_line + " " + line_stripped

            # Coletar continuação
            has_af_code = bool(Patterns.AF_CODE_ANYWHERE.search(line_stripped))
            if not has_af_code:
                continuation = collect_continuation_lines(lines, i + 1)
                if continuation:
                    full_text = full_text + " " + continuation

            unit, qty = extract_unit_qty(full_text)

            entry = {
                'linha': i + 1,
                'texto_linha': full_text,
                'unit': unit,
                'qty': qty,
                'corrupted': line_is_corrupted
            }

            if item_code not in index:
                index[item_code] = []
            index[item_code].append(entry)

        else:
            # Verificar código embutido no final
            embedded_match = Patterns.EMBEDDED_ITEM_END.search(line_stripped)
            if embedded_match:
                item_code = embedded_match.group(1)
                unit = embedded_match.group(2).upper()
                unit = unit.replace('²', '2').replace('³', '3')
                qty_str = embedded_match.group(3).replace('.', '').replace(',', '.')
                try:
                    qty = float(qty_str)
                except ValueError:
                    qty = None

                desc_end_pos = embedded_match.start()
                desc_part = line_stripped[:desc_end_pos].strip()

                if desc_part and len(desc_part) >= 20:
                    line_is_corrupted = is_corrupted_text(line_stripped)
                    full_text = line_stripped

                    if i > 0:
                        prev_line = lines[i - 1].strip()
                        if is_description_fragment(desc_part, prev_line) or len(desc_part) < 25:
                            prev_text = collect_previous_lines(lines, i)
                            if prev_text:
                                full_text = prev_text + " " + line_stripped

                    continuation = collect_continuation_lines(lines, i + 1)
                    if continuation:
                        full_text = full_text + " " + continuation

                    if i + 1 < len(lines):
                        next_line = lines[i + 1].strip()
                        if Patterns.AF_ONLY.match(next_line):
                            full_text = line_stripped + " " + next_line

                    entry = {
                        'linha': i + 1,
                        'texto_linha': full_text,
                        'unit': unit,
                        'qty': qty,
                        'corrupted': line_is_corrupted,
                        'embedded': True
                    }

                    if item_code not in index:
                        index[item_code] = []
                    index[item_code].append(entry)

        i += 1

    return index
