"""
Detector de colunas para tabelas de serviços.

Identifica colunas de item, descrição, unidade e quantidade
em tabelas extraídas de documentos.
"""

from typing import Any, Dict, List, Optional, Tuple

from config import AtestadoProcessingConfig as APC
from services.extraction import score_item_column


class ColumnDetector:
    """
    Detecta a coluna de código de item em uma tabela.

    Analisa as células de cada coluna para identificar
    qual contém códigos de item válidos.
    """

    def detect_item_column(
        self,
        data_rows: List[List[Any]],
        max_cols: int,
        header_map: Dict[str, Any],
        preferred_item_col: Optional[int],
        ignore_item_numbers: bool
    ) -> Tuple[Optional[int], Dict[str, Any], bool]:
        """
        Detecta a coluna de item na tabela.

        Args:
            data_rows: Linhas de dados da tabela
            max_cols: Número máximo de colunas
            header_map: Mapeamento de colunas do header
            preferred_item_col: Coluna preferida para item
            ignore_item_numbers: Se deve ignorar números de item

        Returns:
            Tupla (item_col, score_data, preferred_used)
        """
        item_col = header_map.get("item")
        item_score_data = {"score": 0.0}
        preferred_used = False

        if ignore_item_numbers:
            return None, item_score_data, False

        # Tentar usar coluna preferida
        if item_col is None and preferred_item_col is not None and preferred_item_col < max_cols:
            col_cells = [
                row[preferred_item_col]
                for row in data_rows
                if preferred_item_col < len(row)
            ]
            preferred_score_data = score_item_column(col_cells, preferred_item_col, max_cols)
            if preferred_score_data["score"] >= APC.ITEM_COL_MIN_SCORE:
                item_col = preferred_item_col
                item_score_data = preferred_score_data
                preferred_used = True

        # Buscar melhor coluna se não encontrada
        if item_col is None:
            best_score = 0.0
            best_col = None
            for col in range(max_cols):
                col_cells = [row[col] for row in data_rows if col < len(row)]
                score_data = score_item_column(col_cells, col, max_cols)
                if score_data["score"] > best_score:
                    best_score = score_data["score"]
                    best_col = col
                    item_score_data = score_data
            item_col = best_col
        else:
            # Calcular score da coluna encontrada
            col_cells = [row[item_col] for row in data_rows if item_col < len(row)]
            item_score_data = score_item_column(col_cells, item_col, max_cols)

        return item_col, item_score_data, preferred_used


# Instância singleton
column_detector = ColumnDetector()
