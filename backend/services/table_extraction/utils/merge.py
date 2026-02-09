"""
Utilitários para merge de fontes de tabela.

Combina resultados de diferentes extratores (pdfplumber, Document AI, OCR)
preservando a melhor informação de cada fonte.
"""

from typing import Any, Dict, List, Optional, Tuple

from services.extraction import (
    description_similarity,
    normalize_description,
    parse_quantity,
)


def _normalize_desc_key(desc: str) -> str:
    """Normaliza descrição para uso como chave de lookup."""
    if not desc:
        return ""
    return normalize_description(desc)[:80]


def merge_table_sources(
    primary: List[Dict[str, Any]],
    secondary: List[Dict[str, Any]]
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Merge de itens de tabela, preferindo primary mas preenchendo dados faltantes do secondary.

    Args:
        primary: Lista principal de serviços
        secondary: Lista secundária para complementar

    Returns:
        Tupla (merged_list, debug_info)
    """
    if not secondary:
        return primary, {
            "merged": False,
            "reason": "no_secondary",
            "primary_count": len(primary)
        }
    if not primary:
        return secondary, {
            "merged": False,
            "reason": "no_primary",
            "secondary_count": len(secondary)
        }

    result: List[Dict[str, Any]] = []
    by_item: Dict[str, List[Dict[str, Any]]] = {}
    by_item_desc: Dict[Tuple[str, str], Dict[str, Any]] = {}
    by_item_desc_keys: Dict[str, set] = {}
    by_desc: set = set()

    def add_servico(servico: Dict[str, Any]) -> None:
        result.append(servico)
        item = servico.get("item")
        if item:
            item_key = str(item)
            by_item.setdefault(item_key, []).append(servico)
            desc_key = _normalize_desc_key(servico.get("descricao") or "")
            if desc_key:
                by_item_desc[(item_key, desc_key)] = servico
                by_item_desc_keys.setdefault(item_key, set()).add(desc_key)
        else:
            key = _normalize_desc_key(servico.get("descricao") or "")
            if key:
                by_desc.add(key)

    # Adicionar todos os itens do primary
    for servico in primary:
        add_servico(servico)

    added = 0
    qty_filled = 0
    unit_filled = 0
    desc_updated = 0

    def find_similar_candidate(
        item_key: str,
        desc: str,
        threshold: float = 0.6
    ) -> Optional[Dict[str, Any]]:
        """Encontra candidato similar por descrição."""
        if not desc or item_key not in by_item:
            return None
        best = None
        best_score = 0.0
        for candidate in by_item[item_key]:
            cand_desc = candidate.get("descricao") or ""
            score = description_similarity(desc, cand_desc)
            if score > best_score:
                best_score = score
                best = candidate
        if best_score >= threshold:
            return best
        return None

    # Processar secondary
    for servico in secondary:
        item = servico.get("item")
        item = str(item) if item else ""

        if item:
            desc_key = _normalize_desc_key(servico.get("descricao") or "")
            target = None

            if desc_key:
                target = by_item_desc.get((item, desc_key))
                if target is None and item in by_item_desc_keys:
                    for existing_key in by_item_desc_keys[item]:
                        if desc_key in existing_key or existing_key in desc_key:
                            target = by_item_desc.get((item, existing_key))
                            break

            if target is None:
                target = find_similar_candidate(item, servico.get("descricao") or "")

            if target is None and not desc_key and item in by_item:
                target = by_item[item][0]

            if target is not None:
                # Preencher quantidade faltante
                primary_qty = parse_quantity(target.get("quantidade"))
                secondary_qty = parse_quantity(servico.get("quantidade"))
                if (primary_qty in (None, 0)) and (secondary_qty not in (None, 0)):
                    target["quantidade"] = secondary_qty
                    qty_filled += 1

                # Preencher unidade faltante
                if not (target.get("unidade") or "").strip() and (servico.get("unidade") or "").strip():
                    target["unidade"] = servico.get("unidade")
                    unit_filled += 1

                # Atualizar descrição se secondary for melhor
                primary_desc = str(target.get("descricao") or "").strip()
                secondary_desc = str(servico.get("descricao") or "").strip()
                if secondary_desc and (not primary_desc or len(secondary_desc) > len(primary_desc) + 5):
                    target["descricao"] = secondary_desc
                    desc_updated += 1
                    updated_key = _normalize_desc_key(secondary_desc)
                    if updated_key:
                        by_item_desc[(item, updated_key)] = target
                        by_item_desc_keys.setdefault(item, set()).add(updated_key)
                continue

            # Verificar duplicata
            if desc_key and item in by_item_desc_keys and desc_key in by_item_desc_keys[item]:
                continue

            # Adicionar como novo
            add_servico(servico)
            added += 1
            continue

        # Item sem código - verificar por descrição
        key = _normalize_desc_key(servico.get("descricao") or "")
        if key and key in by_desc:
            continue
        add_servico(servico)
        added += 1

    debug = {
        "merged": True,
        "primary_count": len(primary),
        "secondary_count": len(secondary),
        "added": added,
        "qty_filled": qty_filled,
        "unit_filled": unit_filled,
        "desc_updated": desc_updated,
    }

    return result, debug
