"""
Funções de matching e scoring para o corretor de descrições.
"""
import re
from typing import Dict, List, Optional, Tuple

from services.extraction import is_corrupted_text
from services.extraction.patterns import Patterns


def extract_unit_qty(texto: str) -> Tuple[Optional[str], Optional[float]]:
    """Extrai unidade e quantidade do texto."""
    match = Patterns.UNIT_QTY_EXTRACT_END.search(texto)
    if not match:
        match = Patterns.UNIT_QTY_EXTRACT_MID.search(texto)

    if match:
        unit = match.group(1).upper()
        unit = unit.replace('²', '2').replace('³', '3')
        qty_str = match.group(2).replace('.', '').replace(',', '.')
        try:
            qty = float(qty_str)
            return unit, qty
        except ValueError:
            return unit, None

    return None, None


def normalize_unit(unit: Optional[str]) -> Optional[str]:
    """Normaliza unidade para comparação."""
    if not unit:
        return None
    unit = unit.upper().strip()
    unit = unit.replace('²', '2').replace('³', '3')
    mappings = {
        'UND': 'UN',
        'UNID': 'UN',
        'UNIDADE': 'UN',
        'METRO': 'M',
        'METROS': 'M',
    }
    return mappings.get(unit, unit)


def group_candidates_by_proximity(candidates: List[Dict]) -> List[List[Dict]]:
    """
    Agrupa candidatos por proximidade de linhas.

    Returns:
        Lista de grupos de candidatos.
    """
    if len(candidates) <= 1:
        return [candidates] if candidates else []

    sorted_candidates = sorted(candidates, key=lambda c: c['linha'])

    groups = []
    current_group = [sorted_candidates[0]]

    for i in range(1, len(sorted_candidates)):
        prev_line = sorted_candidates[i - 1]['linha']
        curr_line = sorted_candidates[i]['linha']

        if curr_line - prev_line <= 200:
            current_group.append(sorted_candidates[i])
        else:
            groups.append(current_group)
            current_group = [sorted_candidates[i]]

    groups.append(current_group)

    return groups


def get_segment_index(item_code: str) -> int:
    """Extrai o índice do segmento do código do item."""
    match = Patterns.SEGMENT_PREFIX.match(item_code)
    if match:
        return int(match.group(1)) - 1
    return 0


def filter_candidates_by_page(
    candidates: List[Dict],
    servico_page: Optional[int],
    line_to_page: Optional[Dict[int, int]],
    max_page_distance: int = 2
) -> List[Dict]:
    """
    Filtra candidatos por proximidade de página.

    Returns:
        Lista filtrada de candidatos.
    """
    if not servico_page or not line_to_page:
        return candidates

    same_page = [
        c for c in candidates
        if line_to_page.get(c['linha']) == servico_page
    ]
    if same_page:
        return same_page

    nearby = [
        c for c in candidates
        if abs(line_to_page.get(c['linha'], 0) - servico_page) <= max_page_distance
    ]
    if nearby:
        return nearby

    return []


def select_candidate_group(
    candidates: List[Dict],
    original_item: str,
    item: str
) -> Tuple[List[Dict], bool]:
    """
    Seleciona grupo de candidatos apropriado.

    Returns:
        Tuple (candidatos_selecionados, grupo_explicitamente_selecionado)
    """
    has_segment_prefix = bool(Patterns.SEGMENT_PREFIX.match(original_item)) if original_item else False
    group_explicitly_selected = has_segment_prefix

    if len(candidates) <= 1:
        return candidates, group_explicitly_selected

    groups = group_candidates_by_proximity(candidates)
    if len(groups) > 1:
        segment_idx = get_segment_index(original_item or item)
        segment_idx = min(segment_idx, len(groups) - 1)
        return groups[segment_idx], True

    return groups[0] if groups else [], group_explicitly_selected


def find_quantity_match(
    candidates: List[Dict],
    expected_unit_norm: Optional[str],
    expected_qty: Optional[float]
) -> Optional[Dict]:
    """Encontra candidato com quantidade e unidade exatas."""
    if not expected_qty or not expected_unit_norm:
        return None

    for candidate in candidates:
        cand_qty = candidate.get('qty')
        cand_unit = normalize_unit(candidate.get('unit'))

        if (cand_qty and cand_qty == expected_qty and
                cand_unit and cand_unit == expected_unit_norm):
            return candidate

    return None


def score_candidate(
    candidate: Dict,
    desc: str,
    expected_unit_norm: Optional[str],
    expected_qty: Optional[float]
) -> int:
    """
    Calcula pontuação de um candidato.

    Returns:
        Pontuação (maior = melhor)
    """
    score = 0
    cand_unit = normalize_unit(candidate.get('unit'))
    cand_qty = candidate.get('qty')

    if len(desc) >= 50:
        score += 50
    elif len(desc) >= 30:
        score += 25

    if expected_unit_norm and cand_unit and expected_unit_norm == cand_unit:
        score += 100

    if expected_qty is not None and cand_qty is not None:
        try:
            exp_qty = float(str(expected_qty).replace('.', '').replace(',', '.')) if isinstance(expected_qty, str) else float(expected_qty)
            cnd_qty = float(cand_qty) if isinstance(cand_qty, (int, float)) else float(str(cand_qty).replace('.', '').replace(',', '.'))
            if exp_qty == cnd_qty:
                score += 200
            elif abs(exp_qty - cnd_qty) / max(exp_qty, 0.01) < 0.05:
                score += 150
        except (ValueError, TypeError):
            pass

    if score == 0:
        score = len(desc)

    return score


def extract_description_from_line(line: str, item: str) -> Optional[str]:
    """
    Extrai a descrição exata de uma linha de texto.

    Returns:
        Descrição extraída ou None.
    """
    if not line:
        return None

    desc = line.strip()

    # Verificar código embutido no meio
    if not desc.startswith(item):
        embedded_pattern = re.compile(
            rf'{re.escape(item)}\s+'
            r'(UN|M|M2|M3|M²|M³|KG|L|VB|CJ|PC|GL)\s+'
            r'[\d.,]+',
            re.IGNORECASE
        )
        embedded_match = embedded_pattern.search(desc)
        if embedded_match and embedded_match.start() > 0:
            desc_before = desc[:embedded_match.start()].strip()
            desc_after = desc[embedded_match.end():].strip()

            af_match = Patterns.AF_CODE_ANYWHERE.search(desc_after)
            if af_match:
                continuation = desc_after[:af_match.start()].strip()
                af_code = af_match.group(0)
            else:
                continuation = desc_after
                af_code = ""

            if desc_before:
                result = desc_before
                if continuation:
                    result = result + " " + continuation
                if af_code:
                    result = result + " " + af_code
                result = ' '.join(result.split())
                if len(result) >= 5:
                    return result

    # Remover item do início
    pattern_start = rf'^{re.escape(item)}\s+'
    desc = re.sub(pattern_start, '', desc)

    # Remover item do meio
    pattern_mid = rf'\s+{re.escape(item)}\s+'
    desc = re.sub(pattern_mid, ' ', desc)

    if not desc:
        return None

    # Remover unidade/quantidade
    desc = Patterns.UNIT_QTY_DESC_START.sub('', desc)
    desc = Patterns.UNIT_QTY_DESC_MID.sub(' ', desc)
    desc = ' '.join(desc.split())

    if len(desc) < 5:
        return None

    if Patterns.DESC_ONLY_UNIT_QTY.match(desc):
        return None

    return desc


def build_match_result(
    qty_match_candidate: Dict,
    item: str,
    current_desc: str
) -> Dict:
    """
    Constrói resultado de match a partir de candidato com quantidade correta.

    Returns:
        Dict com linha, descrição e flag de corrompido.
    """
    desc = extract_description_from_line(qty_match_candidate['texto_linha'], item)
    is_corrupted = (
        qty_match_candidate.get('corrupted', False) or
        is_corrupted_text(qty_match_candidate['texto_linha'])
    )

    if desc and len(desc) >= 10 and not is_corrupted:
        return {
            'linha': qty_match_candidate['linha'],
            'descricao': desc
        }

    if current_desc and len(current_desc) >= 20 and not is_corrupted_text(current_desc):
        return {
            'linha': qty_match_candidate['linha'],
            'descricao': current_desc,
            'desc_corrupted': True
        }

    return {
        'linha': qty_match_candidate['linha'],
        'descricao': desc if desc else current_desc,
        'desc_corrupted': True
    }


def find_best_match(
    candidates: List[Dict],
    item: str,
    expected_unit: Optional[str],
    expected_qty: Optional[float],
    current_desc: str = "",
    original_item: str = "",
    servico_page: Optional[int] = None,
    line_to_page: Optional[Dict[int, int]] = None
) -> Optional[Dict]:
    """
    Encontra a melhor correspondência entre as linhas candidatas.

    Returns:
        Dict com linha e descrição ou None.
    """
    if not candidates:
        return None

    expected_unit_norm = normalize_unit(expected_unit)

    has_segment_prefix = bool(
        original_item and Patterns.SEGMENT_PREFIX.match(original_item)
    )

    # Filtrar por página
    max_distance = 1 if has_segment_prefix else 2
    page_filtered = filter_candidates_by_page(
        candidates, servico_page, line_to_page, max_page_distance=max_distance
    )

    if not page_filtered:
        return None

    # Selecionar grupo
    group_selected_by_page = bool(servico_page and line_to_page)
    working_candidates, group_selected = select_candidate_group(
        page_filtered, original_item, item
    )
    group_explicitly_selected = group_selected_by_page or group_selected

    # Match por quantidade exata
    qty_match = find_quantity_match(working_candidates, expected_unit_norm, expected_qty)
    if qty_match:
        return build_match_result(qty_match, item, current_desc)

    # Para itens com prefixo S-, exigir match de quantidade
    if has_segment_prefix and expected_qty:
        has_qty_match = any(
            c.get('qty') and abs(c['qty'] - expected_qty) / max(expected_qty, 0.01) < 0.1
            for c in working_candidates
        )
        if not has_qty_match:
            return None

    # Scoring de candidatos
    best = None
    best_score = -1
    current_starts_with_unit = bool(Patterns.DESC_STARTS_WITH_UNIT.match(current_desc))

    for candidate in working_candidates:
        desc = extract_description_from_line(candidate['texto_linha'], item)
        if not desc or len(desc) < 10:
            continue

        if candidate.get('corrupted', False) or is_corrupted_text(candidate['texto_linha']):
            continue

        if Patterns.DESC_STARTS_WITH_UNIT.match(desc):
            continue

        if not group_explicitly_selected and not current_starts_with_unit:
            if len(current_desc) >= 50 and len(desc) < len(current_desc):
                continue

        score = score_candidate(candidate, desc, expected_unit_norm, expected_qty)

        if score > best_score:
            best_score = score
            best = {
                'linha': candidate['linha'],
                'descricao': desc
            }

    return best
