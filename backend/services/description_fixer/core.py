"""
Função principal do corretor de descrições.
"""
from typing import Dict, List

from logging_config import get_logger
from services.extraction import normalize_item_code
from .indexing import build_item_line_index, build_line_to_page_map
from .matching import find_best_match

logger = get_logger('services.description_fixer.core')


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
        logger.debug(f"[FIXER] Entrada vazia: servicos={len(servicos) if servicos else 0}, texto={len(texto_extraido) if texto_extraido else 0}")
        return servicos

    logger.debug(f"[FIXER] Iniciando correção de {len(servicos)} serviços com {len(texto_extraido)} chars de texto")

    # Construir índice de linhas por item
    item_lines = build_item_line_index(texto_extraido)
    logger.debug(f"[FIXER] Índice construído com {len(item_lines)} itens únicos")

    # Construir mapeamento linha -> página
    line_to_page = build_line_to_page_map(texto_extraido)

    # Corrigir cada serviço
    for servico in servicos:
        original_item = servico.get('item', '')
        item = normalize_item_code(original_item, strip_suffixes=True)
        if not item:
            continue

        # Buscar candidatas para este item
        candidates = item_lines.get(item, [])
        if not candidates:
            continue

        # Descrição atual
        current_desc = servico.get('descricao', '')

        # Página do serviço (se disponível)
        servico_page = servico.get('_page')

        # Encontrar melhor correspondência
        best_match = find_best_match(
            candidates,
            item,
            servico.get('unidade'),
            servico.get('quantidade'),
            current_desc,
            original_item,
            servico_page,
            line_to_page
        )

        if best_match:
            old_desc = (servico.get('descricao') or '')[:50]
            new_desc = best_match['descricao'][:50]
            logger.debug(f"[FIXER] Item {item}: match encontrado, score={best_match.get('score', 0):.2f}")
            logger.debug(f"[FIXER]   Antes: {old_desc}...")
            logger.debug(f"[FIXER]   Depois: {new_desc}...")
            servico['descricao'] = best_match['descricao']
            servico['_desc_source'] = 'texto_original'
            servico['_linha_original'] = best_match['linha']
            if best_match.get('desc_corrupted'):
                servico['_desc_corrupted'] = True
        else:
            logger.debug(f"[FIXER] Item {item}: nenhum match adequado entre {len(candidates)} candidatos")
            servico.pop('_desc_source', None)
            servico.pop('_linha_original', None)
            servico.pop('_desc_corrupted', None)

    fixed_count = sum(1 for s in servicos if s.get('_desc_source') == 'texto_original')
    logger.debug(f"[FIXER] Correção finalizada: {fixed_count}/{len(servicos)} descrições corrigidas")
    return servicos
