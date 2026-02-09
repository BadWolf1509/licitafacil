"""
Extrator principal de serviços de tabelas.

Contém a lógica central para extrair serviços de uma tabela normalizada,
identificando colunas, processando linhas e gerando serviços.
"""

from typing import Any, Dict, List, Optional, Tuple

from services.extraction import (
    compute_column_stats,
    detect_header_row,
    dominant_item_length,
    filter_servicos_by_item_length,
    filter_servicos_by_item_prefix,
    guess_columns_by_content,
    guess_columns_by_header,
    repair_missing_prefix,
    validate_column_mapping,
)
from services.extraction.quality_assessor import compute_servicos_stats

from ..filters import (
    strip_section_header_prefix,
)
from .column_detector import column_detector
from .confidence_calculator import confidence_calculator
from .row_processor import row_processor


class TableExtractor:
    """
    Extrator de serviços de uma tabela.

    Processa uma tabela (lista de linhas) e extrai serviços
    com item, descrição, unidade e quantidade.
    """

    def extract(
        self,
        table: List[List[Any]],
        preferred_item_col: Optional[int] = None,
        allow_itemless: bool = False,
        ignore_item_numbers: bool = False
    ) -> Tuple[List[Dict[str, Any]], float, Dict[str, Any]]:
        """
        Extrai serviços de uma única tabela.

        Args:
            table: Lista de linhas da tabela (cada linha é lista de células)
            preferred_item_col: Índice preferido para coluna de item
            allow_itemless: Permite extrair itens sem código
            ignore_item_numbers: Ignora números de item

        Returns:
            Tupla (servicos, confidence, debug)
        """
        if not table:
            return [], 0.0, {}

        # Normalizar linhas
        rows = [
            row for row in table
            if row and any(str(cell or "").strip() for cell in row)
        ]
        if not rows:
            return [], 0.0, {}

        max_cols = max(len(row) for row in rows)
        normalized_rows = []
        for row in rows:
            padded = list(row) + [""] * (max_cols - len(row))
            normalized_rows.append(padded)

        # Detectar header e mapear colunas
        header_index = detect_header_row(normalized_rows)
        header_map: Dict[str, Optional[int]] = {
            "item": None,
            "descricao": None,
            "unidade": None,
            "quantidade": None,
            "valor": None
        }
        data_rows = normalized_rows

        if header_index is not None:
            header_map = guess_columns_by_header(normalized_rows[header_index])
            data_rows = normalized_rows[header_index + 1:]

        # Detectar coluna de item
        item_col, item_score_data, preferred_used = column_detector.detect_item_column(
            data_rows, max_cols, header_map,
            preferred_item_col, ignore_item_numbers
        )

        if not ignore_item_numbers and header_map.get("item") is None and item_col is not None:
            header_map["item"] = item_col

        if ignore_item_numbers:
            item_col = None
            header_map["item"] = None

        # Mapear outras colunas por conteúdo
        col_stats = compute_column_stats(data_rows, max_cols)
        header_map = guess_columns_by_content(data_rows, max_cols, header_map, col_stats)
        header_map = validate_column_mapping(header_map, col_stats)
        header_map = guess_columns_by_content(data_rows, max_cols, header_map, col_stats)

        desc_col = header_map.get("descricao")
        unit_col = header_map.get("unidade")
        qty_col = header_map.get("quantidade")

        # Processar linhas
        servicos, item_tuples = row_processor.process_rows(
            data_rows, item_col, desc_col, unit_col, qty_col,
            allow_itemless, ignore_item_numbers
        )

        # Pós-processamento
        servicos = [s for s in servicos if s.get("descricao")]
        servicos, prefix_info = filter_servicos_by_item_prefix(servicos)
        dominant_len, dominant_len_ratio = dominant_item_length(servicos)

        repair_info = {"applied": False, "repaired": 0}
        if dominant_len == 3 and prefix_info.get("dominant_prefix") is not None:
            servicos, repair_info = repair_missing_prefix(
                servicos, prefix_info.get("dominant_prefix")
            )

        servicos, dominant_info = filter_servicos_by_item_length(servicos)

        # Calcular confiança
        stats = compute_servicos_stats(servicos)
        confidence = confidence_calculator.calculate(
            servicos, item_tuples, item_score_data,
            stats, prefix_info, dominant_info
        )

        # Limpar prefixos de header das descrições
        for servico in servicos:
            desc = servico.get("descricao")
            if desc:
                cleaned = strip_section_header_prefix(desc)
                if cleaned != desc:
                    servico["descricao"] = cleaned

        debug = {
            "header_index": header_index,
            "columns": header_map,
            "item_col_score": item_score_data,
            "preferred_item_col": preferred_item_col,
            "preferred_item_used": preferred_used,
            "prefix_item": prefix_info,
            "dominant_item": dominant_info,
            "prefix_repair": repair_info,
            "stats": stats,
            "confidence": confidence
        }

        return servicos, confidence, debug
