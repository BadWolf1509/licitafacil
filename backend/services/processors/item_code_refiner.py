"""
Refinador de códigos de item a partir de texto.

Melhora códigos de item em serviços extraídos usando informações
de texto OCR para corrigir itens com prefixos truncados.
"""

from typing import Any, Dict, List, Optional, Set

from services.extraction import (
    normalize_unit,
    parse_quantity,
    description_similarity,
)
from services.processing_helpers import normalize_item_code

from logging_config import get_logger

logger = get_logger("services.processors.item_code_refiner")


class ItemCodeRefiner:
    """
    Refina códigos de item usando informações extraídas do texto.

    Corrige itens com prefixos truncados (ex: "1.4" para "1.4.1")
    baseado em candidatos encontrados no texto OCR.
    """

    # Configurações de threshold para matching
    SCORE_THRESHOLD = 0.55
    SIMILARITY_FLOOR = 0.2

    def refine(
        self,
        servicos: List[Dict[str, Any]],
        text_items: List[Dict[str, Any]],
        text_codes: Optional[List[str]] = None
    ) -> int:
        """
        Refina códigos de item nos serviços usando dados do texto.

        Args:
            servicos: Lista de serviços (modificada in-place)
            text_items: Itens extraídos do texto com código, descrição, etc.
            text_codes: Lista ordenada de códigos encontrados no texto

        Returns:
            Número de códigos refinados
        """
        if not servicos or (not text_items and not text_codes):
            return 0

        # Construir índice de candidatos por prefixo
        candidates_by_prefix = self._build_candidates_index(text_items)

        # Rastrear códigos já usados
        used_codes = self._get_used_codes(servicos)

        updated = 0
        processed_prefixes: Set[str] = set()

        # Fase 1: Refinar usando lista ordenada de códigos (text_codes)
        if text_codes:
            updated += self._refine_from_ordered_codes(
                servicos, text_codes, used_codes, processed_prefixes
            )

        # Fase 2: Refinar usando candidatos com matching de similaridade
        updated += self._refine_from_candidates(
            servicos, candidates_by_prefix, used_codes, processed_prefixes
        )

        if updated:
            logger.info(f"[REFINE] {updated} códigos de item refinados")

        return updated

    def _build_candidates_index(
        self,
        text_items: List[Dict[str, Any]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Constrói índice de candidatos organizados por prefixo."""
        candidates_by_prefix: Dict[str, List[Dict[str, Any]]] = {}

        for item in text_items or []:
            code = normalize_item_code(item.get("item"))
            if not code:
                continue

            parts = code.split(".")
            if len(parts) < 3:
                continue

            prefix = ".".join(parts[:-1])
            desc = (item.get("descricao") or "").strip()
            unit = normalize_unit(item.get("unidade") or "")
            qty = parse_quantity(item.get("quantidade"))

            candidates_by_prefix.setdefault(prefix, []).append({
                "code": code,
                "desc": desc,
                "unit": unit,
                "qty": qty,
            })

        return candidates_by_prefix

    def _get_used_codes(self, servicos: List[Dict[str, Any]]) -> Set[str]:
        """Retorna conjunto de códigos já usados nos serviços."""
        codes: Set[str] = set()
        for s in servicos:
            code = normalize_item_code(s.get("item"))
            if code:
                codes.add(code)
        return codes

    def _refine_from_ordered_codes(
        self,
        servicos: List[Dict[str, Any]],
        text_codes: List[str],
        used_codes: Set[str],
        processed_prefixes: Set[str]
    ) -> int:
        """
        Refina usando lista ordenada de códigos do texto.

        Atribui códigos em ordem quando a contagem bate exatamente.
        """
        ordered_by_prefix: Dict[str, List[str]] = {}

        for code in text_codes:
            normalized = normalize_item_code(code)
            if not normalized:
                continue
            parts = normalized.split(".")
            if len(parts) < 3:
                continue
            prefix = ".".join(parts[:-1])
            ordered_by_prefix.setdefault(prefix, []).append(normalized)

        updated = 0

        for prefix, codes in ordered_by_prefix.items():
            prefix_indices = [
                idx for idx, s in enumerate(servicos)
                if normalize_item_code(s.get("item")) == prefix
            ]

            # Só atribuir se contagens batem exatamente
            if not prefix_indices or len(codes) < 2:
                continue
            if len(codes) != len(prefix_indices):
                continue
            if any(code in used_codes for code in codes):
                continue

            for idx, code in zip(prefix_indices, codes):
                servicos[idx]["item"] = code
                used_codes.add(code)
                updated += 1

            processed_prefixes.add(prefix)

        return updated

    def _refine_from_candidates(
        self,
        servicos: List[Dict[str, Any]],
        candidates_by_prefix: Dict[str, List[Dict[str, Any]]],
        used_codes: Set[str],
        processed_prefixes: Set[str]
    ) -> int:
        """
        Refina usando matching de similaridade com candidatos.

        Calcula score baseado em similaridade de descrição,
        unidade e quantidade.
        """
        updated = 0

        for prefix, candidates in candidates_by_prefix.items():
            if prefix in processed_prefixes:
                continue

            prefix_indices = [
                idx for idx, s in enumerate(servicos)
                if normalize_item_code(s.get("item")) == prefix
            ]

            if not prefix_indices:
                continue

            # Calcular scores para todos os pares possíveis
            pairs = self._calculate_match_pairs(
                servicos, prefix_indices, candidates, used_codes
            )

            if not pairs:
                continue

            # Ordenar por score decrescente e atribuir
            pairs.sort(key=lambda x: (-x[0], -x[1]))

            used_indices: Set[int] = set()
            for score, sim, idx, code in pairs:
                if idx in used_indices or code in used_codes:
                    continue
                servicos[idx]["item"] = code
                used_indices.add(idx)
                used_codes.add(code)
                updated += 1

        return updated

    def _calculate_match_pairs(
        self,
        servicos: List[Dict[str, Any]],
        prefix_indices: List[int],
        candidates: List[Dict[str, Any]],
        used_codes: Set[str]
    ) -> List[tuple]:
        """Calcula pares (score, sim, idx, code) para matching."""
        pairs = []

        for idx in prefix_indices:
            servico = servicos[idx]
            serv_desc = (servico.get("descricao") or "").strip()
            serv_unit = normalize_unit(servico.get("unidade") or "")
            serv_qty = parse_quantity(servico.get("quantidade"))

            for cand in candidates:
                if cand["code"] in used_codes:
                    continue

                # Calcular similaridade de descrição
                sim = description_similarity(serv_desc, cand["desc"])

                # Verificar match de unidade
                unit_match = bool(
                    serv_unit and cand["unit"] and serv_unit == cand["unit"]
                )

                # Verificar match de quantidade (tolerância de 2%)
                qty_match = self._quantities_match(serv_qty, cand["qty"])

                # Calcular score composto
                score = sim
                if unit_match:
                    score += 0.2
                if qty_match:
                    score += 0.2

                # Bonus por substring
                if serv_desc and cand["desc"]:
                    serv_upper = serv_desc.upper()
                    cand_upper = cand["desc"].upper()
                    if cand_upper in serv_upper or serv_upper in cand_upper:
                        score += 0.1

                # Filtrar por threshold
                if score < self.SCORE_THRESHOLD:
                    if sim < self.SIMILARITY_FLOOR and not (unit_match and qty_match):
                        continue

                pairs.append((score, sim, idx, cand["code"]))

        return pairs

    def _quantities_match(
        self,
        qty_a: Optional[float],
        qty_b: Optional[float]
    ) -> bool:
        """Verifica se quantidades são similares (2% tolerância)."""
        if qty_a is None or qty_b is None:
            return False
        if qty_a == 0 or qty_b == 0:
            return False

        diff = abs(qty_a - qty_b)
        denom = max(abs(qty_a), abs(qty_b))

        if denom > 0:
            return (diff / denom) <= 0.02 or diff <= 0.01

        return False


# Instância singleton
item_code_refiner = ItemCodeRefiner()
