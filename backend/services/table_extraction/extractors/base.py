"""
Interface base para estrategias de extracao.

Define o contrato que todas as estrategias de extracao devem implementar.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Tuple


class ExtractionStrategy(ABC):
    """Interface para estrategias de extracao de tabelas."""

    @abstractmethod
    def extract(
        self,
        file_path: str,
        **kwargs
    ) -> Tuple[List[Dict[str, Any]], float, Dict[str, Any]]:
        """
        Extrai servicos do arquivo.

        Args:
            file_path: Caminho do arquivo a processar
            **kwargs: Argumentos adicionais especificos da estrategia

        Returns:
            Tupla contendo:
            - Lista de servicos extraidos
            - Confianca da extracao (0.0 a 1.0)
            - Dicionario com informacoes de debug
        """
        pass

    @abstractmethod
    def can_handle(self, file_path: str, file_ext: str) -> bool:
        """
        Verifica se esta estrategia pode processar o arquivo.

        Args:
            file_path: Caminho do arquivo
            file_ext: Extensao do arquivo (ex: '.pdf', '.xlsx')

        Returns:
            True se a estrategia pode processar o arquivo
        """
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Nome da estrategia para logging e debug."""
        pass

    @property
    def priority(self) -> int:
        """
        Prioridade da estrategia (menor = maior prioridade).

        Estrategias com menor prioridade sao tentadas primeiro.
        Default: 100
        """
        return 100


class ExtractionResult:
    """Resultado de uma extracao."""

    def __init__(
        self,
        servicos: List[Dict[str, Any]],
        confidence: float,
        debug: Dict[str, Any],
        strategy_name: str
    ):
        self.servicos = servicos
        self.confidence = confidence
        self.debug = debug
        self.strategy_name = strategy_name

    @property
    def qty_ratio(self) -> float:
        """Proporcao de servicos com quantidade."""
        if not self.servicos:
            return 0.0
        from services.extraction import parse_quantity
        count = sum(
            1 for s in self.servicos
            if parse_quantity(s.get("quantidade")) not in (None, 0)
        )
        return count / len(self.servicos)

    @property
    def is_success(self) -> bool:
        """Verifica se a extracao foi bem sucedida."""
        return len(self.servicos) > 0 and self.confidence > 0.5

    def __repr__(self) -> str:
        return (
            f"ExtractionResult(strategy={self.strategy_name}, "
            f"servicos={len(self.servicos)}, "
            f"confidence={self.confidence:.2f}, "
            f"qty_ratio={self.qty_ratio:.2f})"
        )
