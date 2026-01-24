"""
Corretor de descrições para garantir 100% de fidelidade ao PDF original.
Usa texto_extraido como fonte da verdade.
"""
import re
from typing import Dict, List, Optional, Tuple


def fix_descriptions(servicos: List[Dict], texto_extraido: str) -> List[Dict]:
    """
    Corrige as descrições de todos os itens usando o texto original.

    Args:
        servicos: Lista de serviços extraídos (pode conter descrições erradas)
        texto_extraido: Texto bruto extraído do PDF (fonte da verdade)

    Returns:
        Lista de serviços com descrições corrigidas
    """
    if not texto_extraido or not servicos:
        return servicos

    # Construir índice de TODAS as linhas por item (não só primeira)
    item_lines = _build_item_line_index(texto_extraido)

    # Corrigir cada serviço
    for servico in servicos:
        item = _normalize_item_code(servico.get('item', ''))
        if not item:
            continue

        # Buscar todas as linhas candidatas para este item
        candidates = item_lines.get(item, [])
        if not candidates:
            continue

        # Encontrar a melhor correspondência baseado em quantidade/unidade
        best_match = _find_best_match(
            candidates,
            item,
            servico.get('unidade'),
            servico.get('quantidade')
        )

        if best_match:
            servico['descricao'] = best_match['descricao']
            servico['_desc_source'] = 'texto_original'
            servico['_linha_original'] = best_match['linha']

    return servicos


def _build_item_line_index(texto: str) -> Dict[str, List[Dict]]:
    """
    Constrói índice de TODAS as linhas que contêm cada item.

    Returns:
        {
            '1.2': [
                {'linha': 45, 'texto_linha': '1.2 Descrição A UN 10', 'unit': 'UN', 'qty': 10.0},
                {'linha': 200, 'texto_linha': '1.2 Descrição B M² 5', 'unit': 'M2', 'qty': 5.0}
            ]
        }
    """
    index: Dict[str, List[Dict]] = {}
    lines = texto.split('\n')

    # Padrão para detectar item no início da linha
    item_pattern = re.compile(r'^(\d{1,2}\.\d{1,2}(?:\.\d{1,2})?)\s+(.+)', re.IGNORECASE)

    for i, line in enumerate(lines, 1):
        line_stripped = line.strip()
        if not line_stripped:
            continue

        match = item_pattern.match(line_stripped)
        if match:
            item_code = match.group(1)
            resto = match.group(2)

            # Extrair unidade e quantidade do final
            unit, qty = _extract_unit_qty(resto)

            entry = {
                'linha': i,
                'texto_linha': line_stripped,
                'unit': unit,
                'qty': qty
            }

            if item_code not in index:
                index[item_code] = []
            index[item_code].append(entry)

    return index


def _extract_unit_qty(texto: str) -> Tuple[Optional[str], Optional[float]]:
    """Extrai unidade e quantidade do final do texto."""
    pattern = r'\b(UN|M|M2|M3|M²|M³|KG|L|VB|CJ|PC|GL|PAR|JG|SC)\s+([\d.,]+)\s*$'
    match = re.search(pattern, texto, re.IGNORECASE)

    if match:
        unit = match.group(1).upper()
        # Normalizar unidade
        unit = unit.replace('²', '2').replace('³', '3')
        qty_str = match.group(2).replace('.', '').replace(',', '.')
        try:
            qty = float(qty_str)
            return unit, qty
        except ValueError:
            return unit, None

    return None, None


def _normalize_unit(unit: Optional[str]) -> Optional[str]:
    """Normaliza unidade para comparação."""
    if not unit:
        return None
    unit = unit.upper().strip()
    unit = unit.replace('²', '2').replace('³', '3')
    # Mapeamentos comuns
    mappings = {
        'UND': 'UN',
        'UNID': 'UN',
        'UNIDADE': 'UN',
        'METRO': 'M',
        'METROS': 'M',
    }
    return mappings.get(unit, unit)


def _find_best_match(
    candidates: List[Dict],
    item: str,
    expected_unit: Optional[str],
    expected_qty: Optional[float]
) -> Optional[Dict]:
    """
    Encontra a melhor correspondência entre as linhas candidatas.

    Prioriza correspondência por:
    1. Quantidade exata + unidade
    2. Quantidade similar (±5%) + unidade
    3. Apenas unidade
    4. Primeira linha com descrição válida
    """
    if not candidates:
        return None

    expected_unit_norm = _normalize_unit(expected_unit)

    best = None
    best_score = -1

    for candidate in candidates:
        # Extrair descrição
        desc = _extract_description_from_line(candidate['texto_linha'], item)
        if not desc or len(desc) < 10:
            continue

        score = 0
        cand_unit = _normalize_unit(candidate.get('unit'))
        cand_qty = candidate.get('qty')

        # Pontuação por unidade
        if expected_unit_norm and cand_unit:
            if expected_unit_norm == cand_unit:
                score += 100

        # Pontuação por quantidade
        if expected_qty and cand_qty:
            if expected_qty == cand_qty:
                score += 200  # Quantidade exata
            elif abs(expected_qty - cand_qty) / max(expected_qty, 0.01) < 0.05:
                score += 150  # Quantidade similar (±5%)

        # Se não tem critério de match, usar primeira ocorrência válida
        if score == 0:
            score = 1

        if score > best_score:
            best_score = score
            best = {
                'linha': candidate['linha'],
                'descricao': desc
            }

    return best


def _normalize_item_code(item: str) -> str:
    """Remove prefixos S1-, S2-, AD1- e sufixos -A, -B do código do item."""
    if not item:
        return ''
    # Remover prefixos
    clean = re.sub(r'^(S\d+|AD\d*)-', '', item)
    # Remover sufixos
    clean = re.sub(r'-[A-Z]$', '', clean)
    return clean


def _extract_description_from_line(line: str, item: str) -> Optional[str]:
    """
    Extrai a descrição exata de uma linha de texto.

    Formato esperado:
        "1.2 Descrição do serviço completa UN 10,50"
             ^---------------------------------^
                    parte a extrair
    """
    if not line:
        return None

    # Remover o item do início
    pattern_start = rf'^{re.escape(item)}\s+'
    desc = re.sub(pattern_start, '', line.strip())

    if not desc:
        return None

    # Remover unidade e quantidade do final
    pattern_end = r'\s+([A-Za-z²³0-9/]+)\s+([\d.,]+)\s*$'
    match_end = re.search(pattern_end, desc)

    if match_end:
        desc = desc[:match_end.start()].strip()

    # Validação: descrição não deve ser muito curta
    if len(desc) < 5:
        return None

    # Validação: descrição não deve ser só unidade/quantidade
    if re.match(r'^[A-Z]{1,3}\s*[\d.,]+$', desc):
        return None

    return desc
