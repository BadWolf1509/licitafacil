"""
Calculador de confiança para extração de tabelas.

Avalia a qualidade da extração baseado em múltiplas métricas
como sequência de itens, presença de quantidade/unidade, etc.
"""

from typing import Any, Dict, List

from services.extraction import parse_item_tuple


class ConfidenceCalculator:
    """
    Calcula a confiança da extração de serviços de uma tabela.

    Combina múltiplas métricas para gerar um score de 0.0 a 1.0.
    """

    def calculate(
        self,
        servicos: List[Dict[str, Any]],
        item_tuples: List[tuple],
        item_score_data: Dict[str, Any],
        stats: Dict[str, Any],
        prefix_info: Dict[str, Any],
        dominant_info: Dict[str, Any]
    ) -> float:
        """
        Calcula a confiança da extração.

        Args:
            servicos: Lista de serviços extraídos
            item_tuples: Tuplas de códigos de item
            item_score_data: Dados de score da coluna de item
            stats: Estatísticas dos serviços
            prefix_info: Informações sobre prefixos
            dominant_info: Informações sobre tamanho dominante

        Returns:
            Score de confiança entre 0.0 e 1.0
        """
        # Calcular ratio de sequência ordenada
        seq_ratio = self._calculate_sequence_ratio(servicos)

        # Extrair métricas
        total = max(1, stats.get("total", 0))
        with_qty_ratio = stats.get("with_qty", 0) / total
        with_unit_ratio = stats.get("with_unit", 0) / total
        dominant_ratio = dominant_info.get("ratio", 0.0)
        prefix_ratio = prefix_info.get("ratio", 0.0)

        # Combinar métricas com pesos
        confidence = (
            0.4 * item_score_data.get("score", 0.0) +
            0.2 * seq_ratio +
            0.2 * with_qty_ratio +
            0.1 * with_unit_ratio +
            0.05 * dominant_ratio +
            0.05 * prefix_ratio
        )

        return max(0.0, min(1.0, round(confidence, 3)))

    def _calculate_sequence_ratio(self, servicos: List[Dict[str, Any]]) -> float:
        """
        Calcula o ratio de itens em sequência ordenada.

        Args:
            servicos: Lista de serviços

        Returns:
            Ratio de pares ordenados (0.0 a 1.0)
        """
        filtered_tuples = []
        for servico in servicos:
            item_value = servico.get("item")
            item_tuple = parse_item_tuple(str(item_value)) if item_value else None
            if item_tuple:
                filtered_tuples.append(item_tuple)

        if len(filtered_tuples) <= 1:
            return 0.0

        ordered = 0
        total_pairs = 0
        prev = None

        for item_tuple in filtered_tuples:
            if prev is not None:
                total_pairs += 1
                if item_tuple >= prev:
                    ordered += 1
            prev = item_tuple

        return ordered / total_pairs if total_pairs else 0.0


# Instância singleton
confidence_calculator = ConfidenceCalculator()
