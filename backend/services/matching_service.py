"""
Deterministic matching between edital requirements and atestado services.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Dict, List, Optional, Set

from logging_config import get_logger
from config import MatchingConfig as MC
from .extraction import normalize_unit, normalize_desc_for_match, extract_keywords, parse_quantity


logger = get_logger("services.matching_service")

SIMILARITY_THRESHOLD = MC.SIMILARITY_THRESHOLD
MIN_COMMON_WORDS = MC.MIN_COMMON_WORDS
MIN_COMMON_WORDS_SHORT = MC.MIN_COMMON_WORDS_SHORT


@dataclass(frozen=True)
class ServiceEntry:
    atestado_id: Optional[int]
    atestado_desc: str
    item: Optional[str]
    descricao: str
    norm_desc: str
    unidade: str
    quantidade: float
    unit_norm: str
    keywords: Set[str]


@dataclass(frozen=True)
class AtestadoEntry:
    id: Optional[int]
    descricao_servico: str
    servicos: List[ServiceEntry]


def _coerce_quantity(value: Any) -> float:
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return 0.0
        if re.match(r"^\d+\.\d+$", text):
            return float(text)
    parsed = parse_quantity(value)
    return float(parsed) if parsed is not None else 0.0


def _load_servicos(raw: Any) -> List[Dict[str, Any]]:
    if isinstance(raw, list):
        return raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                return parsed
        except json.JSONDecodeError:
            return []
    return []


def _build_atestado_entries(atestados: List[Dict[str, Any]]) -> List[AtestadoEntry]:
    entries: List[AtestadoEntry] = []

    for at in atestados:
        at_id = at.get("id")
        at_desc = (at.get("descricao_servico") or "").strip()
        servicos_raw = _load_servicos(at.get("servicos_json"))

        if not servicos_raw:
            servicos_raw = [{
                "item": None,
                "descricao": at_desc,
                "quantidade": at.get("quantidade"),
                "unidade": at.get("unidade"),
            }]

        servicos: List[ServiceEntry] = []
        for serv in servicos_raw:
            desc = (serv.get("descricao") or "").strip()
            unidade = serv.get("unidade") or ""
            quantidade = _coerce_quantity(serv.get("quantidade"))
            servicos.append(
                ServiceEntry(
                    atestado_id=at_id,
                    atestado_desc=at_desc,
                    item=serv.get("item"),
                    descricao=desc,
                    norm_desc=normalize_desc_for_match(desc),
                    unidade=unidade,
                    quantidade=quantidade,
                    unit_norm=normalize_unit(unidade),
                    keywords=extract_keywords(desc),
                )
            )

        entries.append(
            AtestadoEntry(
                id=at_id,
                descricao_servico=at_desc,
                servicos=servicos
            )
        )

    return entries


def _keyword_similarity(left: Set[str], right: Set[str]) -> float:
    if not left or not right:
        return 0.0
    intersection = len(left & right)
    return intersection / len(left)


ACTIVITY_TOKENS = [
    ("DEMOLICAO", {"DEMOLICAO", "REMOCAO", "RETIRADA"}),
    ("LIMPEZA", {"LIMPEZA", "HIGIENIZACAO"}),
    ("MANUTENCAO", {"MANUTENCAO", "CONSERVACAO", "RECUPERACAO"}),
    ("SUPPLY_INSTALL", {"FORNECIMENTO", "INSTALACAO", "MONTAGEM"}),
    ("REVESTIMENTO", {"REVESTIMENTO", "ASSENTAMENTO", "APLICACAO"}),
    ("PINTURA", {"PINTURA", "PINTAR"}),
    ("EXECUCAO", {"EXECUCAO", "CONSTRUCAO", "IMPLANTACAO"}),
]

MANDATORY_PATTERNS = [
    "MDF",
    "LAMINAD",
    "PORCELANAT",
    "CANALETA",
    "COBRE",
    "VIDRO",
    "GESSO",
    "CERAMIC",
    "ANTI CHAMA",
    "ANTICHAMA",
]


def _detect_activity(keywords: Set[str]) -> Optional[str]:
    for name, tokens in ACTIVITY_TOKENS:
        if keywords & tokens:
            return name
    return None


def _resolve_allow_sum(exigencia: Dict[str, Any]) -> bool:
    if "exige_unico" in exigencia:
        return not bool(exigencia.get("exige_unico"))
    if "permitir_soma" in exigencia:
        return bool(exigencia.get("permitir_soma"))
    return True


class MatchingService:
    def match_exigencias(
        self,
        exigencias: List[Dict[str, Any]],
        atestados: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        if not exigencias or not atestados:
            return []

        atestados_prepared = _build_atestado_entries(atestados)
        results: List[Dict[str, Any]] = []

        for exig in exigencias:
            req_desc_raw = (exig.get("descricao") or exig.get("exigencia") or "").strip()
            req_desc_norm = normalize_desc_for_match(req_desc_raw)
            req_keywords = extract_keywords(req_desc_norm)
            req_activity = _detect_activity(req_keywords)
            req_mandatory = [pat for pat in MANDATORY_PATTERNS if pat in req_desc_norm]
            req_qty = _coerce_quantity(
                exig.get("quantidade_minima")
                or exig.get("quantidade")
                or exig.get("quantidade_exigida")
                or exig.get("qtd")
            )
            req_unit_raw = (exig.get("unidade") or "").strip()
            req_unit = normalize_unit(req_unit_raw)
            allow_sum = _resolve_allow_sum(exig)

            matches: List[Dict[str, Any]] = []
            candidates_total = 0
            rejected = {
                "common": 0,
                "mandatory": 0,
                "activity": 0,
                "similarity": 0,
            }

            for at in atestados_prepared:
                at_qty = 0.0
                at_items: List[Dict[str, Any]] = []
                best_item_desc = ""
                best_item_unit = ""
                best_score = 0.0

                for serv in at.servicos:
                    if req_unit and serv.unit_norm != req_unit:
                        continue
                    if serv.quantidade <= 0:
                        continue
                    if not req_keywords or not serv.keywords:
                        continue

                    candidates_total += 1

                    common = req_keywords & serv.keywords
                    min_common = MIN_COMMON_WORDS_SHORT if len(req_keywords) <= 2 else MIN_COMMON_WORDS
                    if len(common) < min_common:
                        rejected["common"] += 1
                        continue

                    if req_mandatory and not all(pat in serv.norm_desc for pat in req_mandatory):
                        rejected["mandatory"] += 1
                        continue

                    serv_activity = _detect_activity(serv.keywords)
                    if req_activity and serv_activity and req_activity != serv_activity:
                        rejected["activity"] += 1
                        continue

                    sim = _keyword_similarity(req_keywords, serv.keywords)
                    if sim < SIMILARITY_THRESHOLD:
                        rejected["similarity"] += 1
                        continue

                    at_qty += serv.quantidade
                    at_items.append({
                        "item": serv.item,
                        "descricao": serv.descricao,
                        "quantidade": serv.quantidade,
                        "unidade": serv.unit_norm or serv.unidade,
                    })

                    if sim > best_score:
                        best_score = sim
                        best_item_desc = serv.descricao
                        best_item_unit = serv.unit_norm or serv.unidade

                if at_qty > 0:
                    matches.append({
                        "atestado_id": at.id,
                        "descricao_servico": at.descricao_servico or best_item_desc or f"Atestado {at.id}",
                        "quantidade": at_qty,
                        "unidade": req_unit or best_item_unit or req_unit_raw,
                        "percentual_cobertura": (at_qty / req_qty * 100) if req_qty > 0 else 0.0,
                        "itens": at_items,
                    })

            matches.sort(key=lambda m: m["quantidade"], reverse=True)

            if allow_sum:
                recomendados: List[Dict[str, Any]] = []
                soma = 0.0
                for match in matches:
                    recomendados.append(match)
                    soma += match["quantidade"]
                    if req_qty > 0 and soma >= req_qty:
                        break
            else:
                recomendados = matches[:1]
                soma = recomendados[0]["quantidade"] if recomendados else 0.0

            if req_qty > 0:
                percentual_total = (soma / req_qty * 100)
                status = "atende" if soma >= req_qty else ("parcial" if soma > 0 else "nao_atende")
            else:
                percentual_total = 0.0
                status = "parcial" if soma > 0 else "nao_atende"

            results.append({
                "exigencia": {
                    "descricao": req_desc_raw,
                    "quantidade_minima": req_qty,
                    "unidade": req_unit or req_unit_raw,
                    "permitir_soma": allow_sum,
                    "exige_unico": not allow_sum,
                },
                "status": status,
                "atestados_recomendados": recomendados,
                "soma_quantidades": soma,
                "percentual_total": percentual_total,
            })

            audit_payload = {
                "event": "matching_exigencia",
                "descricao": req_desc_raw,
                "unidade": req_unit or req_unit_raw,
                "quantidade_minima": req_qty,
                "allow_sum": allow_sum,
                "activity": req_activity,
                "mandatory": req_mandatory,
                "threshold": SIMILARITY_THRESHOLD,
                "candidates_total": candidates_total,
                "rejected": rejected,
                "matches": len(matches),
                "selected": len(recomendados),
                "soma": soma,
                "status": status,
                "selected_atestados": [
                    {
                        "id": m.get("atestado_id"),
                        "quantidade": m.get("quantidade"),
                        "itens": len(m.get("itens") or []),
                    }
                    for m in recomendados
                ],
            }
            logger.info(json.dumps(audit_payload, ensure_ascii=True))

        return results


matching_service = MatchingService()
