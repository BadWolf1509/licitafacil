"""Filtro client-side para resultados PNCP."""
from decimal import Decimal
from typing import Any, Dict, List, Optional

from logging_config import get_logger

logger = get_logger("services.pncp.matcher")


class PncpMatcher:
    """Aplica filtros client-side nos resultados da API PNCP."""

    @staticmethod
    def match_palavras_chave(texto: Optional[str], palavras: List[str]) -> bool:
        """Verifica se alguma palavra-chave está no texto."""
        if not palavras:
            return True
        if not texto:
            return False
        texto_lower = texto.lower()
        return any(p.lower() in texto_lower for p in palavras)

    @staticmethod
    def match_ufs(uf_item: Optional[str], ufs: List[str]) -> bool:
        """Verifica se a UF do item está na lista de UFs do monitor."""
        if not ufs:
            return True
        if not uf_item:
            return False
        return uf_item.upper() in [u.upper() for u in ufs]

    @staticmethod
    def match_valor(
        valor: Any,
        minimo: Optional[Decimal],
        maximo: Optional[Decimal],
    ) -> bool:
        """Verifica se o valor está dentro da faixa."""
        if minimo is None and maximo is None:
            return True
        if valor is None:
            return True  # Sem valor estimado, não filtrar

        try:
            valor_dec = Decimal(str(valor))
        except Exception:
            return True

        if minimo is not None and valor_dec < minimo:
            return False
        if maximo is not None and valor_dec > maximo:
            return False
        return True

    @staticmethod
    def filtrar_resultados(
        items: List[Dict[str, Any]],
        monitor: Any,
    ) -> List[Dict[str, Any]]:
        """Aplica todos os filtros do monitor sobre os resultados PNCP."""
        palavras = monitor.palavras_chave or []
        ufs = monitor.ufs or []
        valor_min = monitor.valor_minimo
        valor_max = monitor.valor_maximo

        filtrados = []
        for item in items:
            objeto = item.get("objetoCompra", "")
            unidade = item.get("unidadeOrgao", {}) or {}
            uf_item = unidade.get("ufSigla")
            valor = item.get("valorTotalEstimado")

            if not PncpMatcher.match_palavras_chave(objeto, palavras):
                continue
            if not PncpMatcher.match_ufs(uf_item, ufs):
                continue
            if not PncpMatcher.match_valor(valor, valor_min, valor_max):
                continue

            filtrados.append(item)

        return filtrados


pncp_matcher = PncpMatcher()
