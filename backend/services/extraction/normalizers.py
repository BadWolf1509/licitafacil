"""
Estratégias de normalização de descrição centralizadas.

Fornece diferentes níveis de normalização para diferentes casos de uso:
- for_comparison: Normalização agressiva para deduplicação
- for_display: Normalização leve mantendo legibilidade
- for_matching: Otimizado para cálculo de similaridade
"""

import re
from functools import lru_cache

from .text_normalizer import (
    extract_keywords,
    normalize_desc_for_match,
    normalize_description,
)


class DescriptionNormalizer:
    """
    Estratégias de normalização de descrição.

    Centraliza diferentes abordagens de normalização para
    diferentes casos de uso no sistema.
    """

    @staticmethod
    @lru_cache(maxsize=2048)
    def for_comparison(desc: str) -> str:
        """
        Normalização agressiva para comparação/deduplicação.

        Remove acentos, pontuação, espaços extras.
        Converte para maiúsculas. Corrige erros de OCR.

        Usado em: ServiceDeduplicator, comparações de igualdade.

        Args:
            desc: Descrição original

        Returns:
            Descrição normalizada agressivamente
        """
        return normalize_description(desc)

    @staticmethod
    def for_display(desc: str) -> str:
        """
        Normalização leve para exibição.

        Mantém legibilidade enquanto limpa espaços e
        caracteres problemáticos.

        Usado em: Exibição para usuário, relatórios.

        Args:
            desc: Descrição original

        Returns:
            Descrição limpa mas legível
        """
        if not desc:
            return ""

        # Normalizar espaços (sem remover acentos)
        text = ' '.join(desc.split())

        # Remover caracteres de controle
        text = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', text)

        # Normalizar aspas e travessões
        text = text.replace('"', '"').replace('"', '"')
        text = text.replace(''', "'").replace(''', "'")
        text = text.replace('–', '-').replace('—', '-')

        return text.strip()

    @staticmethod
    @lru_cache(maxsize=2048)
    def for_matching(desc: str) -> str:
        """
        Normalização otimizada para cálculo de similaridade.

        Remove prefixos de código de item e normaliza
        para comparação de similaridade.

        Usado em: Cálculo de similaridade, matching.

        Args:
            desc: Descrição original

        Returns:
            Descrição normalizada para matching
        """
        return normalize_desc_for_match(desc)

    @staticmethod
    def similarity_score(desc1: str, desc2: str) -> float:
        """
        Calcula score de similaridade entre duas descrições.

        Usa Jaccard similarity baseado em keywords.

        Args:
            desc1: Primeira descrição
            desc2: Segunda descrição

        Returns:
            Score entre 0.0 e 1.0
        """
        kw1 = extract_keywords(desc1)
        kw2 = extract_keywords(desc2)

        if not kw1 or not kw2:
            return 0.0

        intersection = len(kw1 & kw2)
        union = len(kw1 | kw2)

        return intersection / union if union > 0 else 0.0
