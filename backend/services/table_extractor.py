"""
Extrator de tabelas para documentos.

Contém funções para extrair e processar tabelas de PDFs e imagens,
incluindo OCR layout e detecção de colunas.
"""

from typing import Dict, Any, List, Optional, Tuple
import io
from PIL import Image

from .ocr_service import ocr_service
from .extraction import (
    parse_item_tuple,
    item_tuple_to_str,
    parse_quantity,
    score_item_column,
    detect_header_row,
    guess_columns_by_header,
    compute_column_stats,
    guess_columns_by_content,
    validate_column_mapping,
    build_description_from_cells,
    normalize_unit,
    normalize_description,
    filter_servicos_by_item_length,
    filter_servicos_by_item_prefix,
    repair_missing_prefix,
    dominant_item_length,
    compute_servicos_stats,
)
from exceptions import OCRError
from config import AtestadoProcessingConfig as APC

from logging_config import get_logger

logger = get_logger('services.table_extractor')


class TableExtractor:
    """Extrator de tabelas de documentos."""

    def extract_servicos_from_table(
        self,
        table: list,
        preferred_item_col: Optional[int] = None
    ) -> Tuple[list, float, dict]:
        """
        Extrai serviços de uma tabela.

        Args:
            table: Lista de linhas da tabela
            preferred_item_col: Coluna preferida para itens

        Returns:
            Tupla (servicos, confidence, debug_info)
        """
        if not table:
            return [], 0.0, {}

        rows = [row for row in table if row and any(str(cell or "").strip() for cell in row)]
        if not rows:
            return [], 0.0, {}

        max_cols = max(len(row) for row in rows)
        normalized_rows = []
        for row in rows:
            padded = list(row) + [""] * (max_cols - len(row))
            normalized_rows.append(padded)

        # Detectar cabeçalho e mapear colunas
        header_index = detect_header_row(normalized_rows)
        header_map = {"item": None, "descricao": None, "unidade": None, "quantidade": None, "valor": None}
        data_rows = normalized_rows

        if header_index is not None:
            header_map = guess_columns_by_header(normalized_rows[header_index])
            data_rows = normalized_rows[header_index + 1:]

        # Detectar coluna de item
        item_col, item_score_data, preferred_used = self._detect_item_column(
            header_map, data_rows, max_cols, preferred_item_col
        )

        # Adivinhar outras colunas por conteúdo
        col_stats = compute_column_stats(data_rows, max_cols)
        header_map = guess_columns_by_content(data_rows, max_cols, header_map, col_stats)
        header_map = validate_column_mapping(header_map, col_stats)
        header_map = guess_columns_by_content(data_rows, max_cols, header_map, col_stats)

        desc_col = header_map.get("descricao")
        unit_col = header_map.get("unidade")
        qty_col = header_map.get("quantidade")

        # Extrair serviços
        servicos, item_tuples = self._extract_servicos_from_rows(
            data_rows, item_col, desc_col, unit_col, qty_col
        )

        # Pós-processamento
        servicos = [s for s in servicos if s.get("descricao")]
        servicos, prefix_info = filter_servicos_by_item_prefix(servicos)
        dominant_len, dominant_len_ratio = dominant_item_length(servicos)
        repair_info = {"applied": False, "repaired": 0}

        if dominant_len == 3 and prefix_info.get("dominant_prefix") is not None:
            servicos, repair_info = repair_missing_prefix(servicos, prefix_info.get("dominant_prefix"))

        servicos, dominant_info = filter_servicos_by_item_length(servicos)

        # Calcular confiança
        confidence, debug = self._compute_table_confidence(
            servicos, item_tuples, item_score_data, prefix_info, dominant_info,
            header_index, header_map, preferred_item_col, preferred_used, repair_info
        )

        return servicos, confidence, debug

    def _detect_item_column(
        self,
        header_map: dict,
        data_rows: list,
        max_cols: int,
        preferred_item_col: Optional[int]
    ) -> Tuple[Optional[int], dict, bool]:
        """Detecta a coluna de item na tabela."""
        item_col = header_map.get("item")
        item_score_data = {"score": 0.0}
        preferred_score_data = None
        preferred_used = False

        if item_col is None and preferred_item_col is not None and preferred_item_col < max_cols:
            col_cells = [row[preferred_item_col] for row in data_rows if preferred_item_col < len(row)]
            preferred_score_data = score_item_column(col_cells, preferred_item_col, max_cols)
            if preferred_score_data["score"] >= APC.ITEM_COL_MIN_SCORE:
                item_col = preferred_item_col
                item_score_data = preferred_score_data
                preferred_used = True

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
            col_cells = [row[item_col] for row in data_rows if item_col < len(row)]
            item_score_data = score_item_column(col_cells, item_col, max_cols)

        return item_col, item_score_data, preferred_used

    def _extract_servicos_from_rows(
        self,
        data_rows: list,
        item_col: Optional[int],
        desc_col: Optional[int],
        unit_col: Optional[int],
        qty_col: Optional[int]
    ) -> Tuple[list, list]:
        """Extrai serviços das linhas de dados."""
        servicos = []
        last_item = None
        item_tuples = []

        for row in data_rows:
            cells = [str(cell or "").strip() for cell in row]
            item_val = cells[item_col] if item_col is not None and item_col < len(cells) else ""
            item_tuple = parse_item_tuple(item_val)
            item_col_effective = item_col

            # Tentar encontrar item em outra coluna se não encontrou
            if item_tuple is None:
                for idx, cell in enumerate(cells):
                    if idx == desc_col:
                        continue
                    candidate = parse_item_tuple(cell)
                    if candidate:
                        item_tuple = candidate
                        item_col_effective = idx
                        item_val = cell
                        break

            desc_val = cells[desc_col] if desc_col is not None and desc_col < len(cells) else ""
            unit_val = cells[unit_col] if unit_col is not None and unit_col < len(cells) else ""
            qty_val = cells[qty_col] if qty_col is not None and qty_col < len(cells) else ""

            # Construir descrição de múltiplas células se necessário
            exclude_cols = {c for c in (item_col_effective, unit_col, qty_col) if c is not None}
            if not desc_val or len(desc_val) < 6:
                desc_val = build_description_from_cells(cells, exclude_cols)

            if unit_val:
                unit_val = normalize_unit(unit_val).strip()

            if item_tuple:
                item_tuples.append(item_tuple)
                item_str = item_tuple_to_str(item_tuple)
                servico = {
                    "item": item_str,
                    "descricao": desc_val.strip(),
                    "unidade": unit_val.strip(),
                    "quantidade": parse_quantity(qty_val)
                }
                servicos.append(servico)
                last_item = servico
            else:
                # Concatenar com item anterior
                if last_item:
                    if desc_val:
                        last_item["descricao"] = (str(last_item.get("descricao") or "") + " " + str(desc_val)).strip()
                    if not last_item.get("unidade") and unit_val:
                        last_item["unidade"] = unit_val.strip()
                    if (last_item.get("quantidade") in (None, 0)) and parse_quantity(qty_val) not in (None, 0):
                        last_item["quantidade"] = parse_quantity(qty_val)

        return servicos, item_tuples

    def _compute_table_confidence(
        self,
        servicos: list,
        item_tuples: list,
        item_score_data: dict,
        prefix_info: dict,
        dominant_info: dict,
        header_index: Optional[int],
        header_map: dict,
        preferred_item_col: Optional[int],
        preferred_used: bool,
        repair_info: dict
    ) -> Tuple[float, dict]:
        """Calcula confiança da extração da tabela."""
        stats = compute_servicos_stats(servicos)

        # Calcular razão de sequência ordenada
        seq_ratio = 0.0
        filtered_tuples = []
        for servico in servicos:
            item_value = servico.get("item")
            item_tuple = parse_item_tuple(str(item_value)) if item_value else None
            if item_tuple:
                filtered_tuples.append(item_tuple)

        if len(filtered_tuples) > 1:
            ordered = 0
            total_pairs = 0
            prev = None
            for item_tuple in filtered_tuples:
                if prev is not None:
                    total_pairs += 1
                    if item_tuple >= prev:
                        ordered += 1
                prev = item_tuple
            seq_ratio = ordered / total_pairs if total_pairs else 0.0

        total = max(1, stats.get("total", 0))
        with_qty_ratio = stats.get("with_qty", 0) / total
        with_unit_ratio = stats.get("with_unit", 0) / total
        dominant_ratio = dominant_info.get("ratio", 0.0)
        prefix_ratio = prefix_info.get("ratio", 0.0)

        confidence = (
            0.4 * item_score_data.get("score", 0.0) +
            0.2 * seq_ratio +
            0.2 * with_qty_ratio +
            0.1 * with_unit_ratio +
            0.05 * dominant_ratio +
            0.05 * prefix_ratio
        )
        confidence = max(0.0, min(1.0, round(confidence, 3)))

        debug = {
            "header_index": header_index,
            "columns": header_map,
            "item_col_score": item_score_data,
            "preferred_item_col": preferred_item_col,
            "preferred_item_used": preferred_used,
            "seq_ratio": round(seq_ratio, 3),
            "prefix_item": prefix_info,
            "dominant_item": dominant_info,
            "prefix_repair": repair_info,
            "stats": stats,
            "confidence": confidence
        }

        return confidence, debug

    def build_table_from_ocr_words(self, words: list) -> Tuple[list, list]:
        """
        Constrói tabela a partir de palavras do OCR.

        Args:
            words: Lista de palavras com coordenadas

        Returns:
            Tupla (table_rows, col_centers)
        """
        if not words:
            return [], []

        heights = [w["height"] for w in words if w.get("height")]
        widths = [w["width"] for w in words if w.get("width")]
        median_height = self._median(heights) or 12.0
        median_width = self._median(widths) or 40.0
        row_tol = max(6.0, median_height * 0.6)
        col_tol = max(18.0, median_width * 0.7)

        words_sorted = sorted(words, key=lambda w: (w["y_center"], w["x_center"]))
        rows = []
        current: list = []
        current_y = None

        for word in words_sorted:
            if current_y is None:
                current_y = word["y_center"]
                current = [word]
                continue
            if abs(word["y_center"] - current_y) > row_tol:
                rows.append(current)
                current = [word]
                current_y = word["y_center"]
            else:
                current.append(word)
                current_y = (current_y + word["y_center"]) / 2
        if current:
            rows.append(current)

        # Clusterizar colunas
        centers = sorted(w["x_center"] for w in words)
        clusters: List[Dict[str, Any]] = []
        for center in centers:
            if not clusters:
                clusters.append({"center": center, "values": [center]})
                continue
            if abs(center - clusters[-1]["center"]) > col_tol:
                clusters.append({"center": center, "values": [center]})
            else:
                clusters[-1]["values"].append(center)
                clusters[-1]["center"] = sum(clusters[-1]["values"]) / len(clusters[-1]["values"])

        col_centers = [c["center"] for c in clusters]
        col_centers.sort()

        # Construir linhas da tabela
        table_rows = []
        for row in rows:
            cells = [""] * len(col_centers)
            for word in sorted(row, key=lambda w: w["x_center"]):
                distances = [abs(word["x_center"] - c) for c in col_centers]
                if not distances:
                    continue
                col_idx = distances.index(min(distances))
                if cells[col_idx]:
                    cells[col_idx] = f"{cells[col_idx]} {word['text']}".strip()
                else:
                    cells[col_idx] = word["text"]
            if any(cells):
                table_rows.append(cells)

        return table_rows, col_centers

    def infer_item_column_from_words(
        self,
        words: list,
        col_centers: list
    ) -> Tuple[Optional[int], dict]:
        """
        Infere coluna de item a partir das palavras do OCR.

        Args:
            words: Lista de palavras com coordenadas
            col_centers: Centros das colunas

        Returns:
            Tupla (item_col_index, debug_info)
        """
        if not words or not col_centers:
            return None, {}

        min_ratio = APC.ITEM_COL_RATIO
        max_x_ratio = APC.ITEM_COL_MAX_X_RATIO
        max_index = APC.ITEM_COL_MAX_INDEX
        min_count = APC.ITEM_COL_MIN_COUNT

        min_x = min(w["x0"] for w in words)
        max_x = max(w["x1"] for w in words)
        span = max(1.0, max_x - min_x)

        counts = [0] * len(col_centers)
        total_candidates = 0
        for word in words:
            item_tuple = parse_item_tuple(word.get("text"))
            if not item_tuple:
                continue
            total_candidates += 1
            distances = [abs(word["x_center"] - c) for c in col_centers]
            if not distances:
                continue
            col_idx = distances.index(min(distances))
            counts[col_idx] += 1

        if total_candidates == 0:
            return None, {"item_col_counts": counts}

        best_idx = counts.index(max(counts))
        ratio = counts[best_idx] / max(1, total_candidates)
        x_ratio = (col_centers[best_idx] - min_x) / span

        debug = {
            "item_col_counts": counts,
            "item_col_ratio": round(ratio, 3),
            "item_col_x_ratio": round(x_ratio, 3),
            "item_col_best": best_idx
        }

        if best_idx > max_index or x_ratio > max_x_ratio:
            return None, debug
        if ratio < min_ratio and counts[best_idx] < min_count:
            return None, debug

        return best_idx, debug

    def crop_region(
        self,
        image_bytes: bytes,
        left: float,
        top: float,
        right: float,
        bottom: float
    ) -> bytes:
        """
        Recorta região da imagem.

        Args:
            image_bytes: Bytes da imagem
            left, top, right, bottom: Coordenadas relativas (0.0-1.0)

        Returns:
            Bytes da imagem recortada
        """
        try:
            img = Image.open(io.BytesIO(image_bytes))
            width, height = img.size
            crop = img.crop((int(width * left), int(height * top), int(width * right), int(height * bottom)))
            buffer = io.BytesIO()
            crop.save(buffer, format="PNG")
            return buffer.getvalue()
        except (IOError, ValueError, OSError) as e:
            logger.debug(f"Erro ao recortar imagem: {e}")
            return image_bytes

    def resize_image_bytes(self, image_bytes: bytes, scale: float = 0.5) -> bytes:
        """
        Redimensiona imagem.

        Args:
            image_bytes: Bytes da imagem
            scale: Fator de escala

        Returns:
            Bytes da imagem redimensionada
        """
        try:
            img = Image.open(io.BytesIO(image_bytes))
            width, height = img.size
            resized = img.resize((max(1, int(width * scale)), max(1, int(height * scale))))
            buffer = io.BytesIO()
            resized.save(buffer, format="PNG")
            return buffer.getvalue()
        except (IOError, ValueError, OSError) as e:
            logger.debug(f"Erro ao redimensionar imagem: {e}")
            return image_bytes

    def detect_table_pages(self, images: List[bytes]) -> List[int]:
        """
        Detecta páginas que contêm tabelas.

        Args:
            images: Lista de imagens das páginas

        Returns:
            Lista de índices das páginas com tabelas
        """
        keywords = {"RELATORIO", "SERVICOS", "EXECUTADOS", "ITEM", "DISCRIMINACAO", "UNID", "QUANTIDADE"}
        table_pages = []

        for index, image_bytes in enumerate(images):
            header = self.crop_region(image_bytes, 0.05, 0.0, 0.95, 0.35)
            header = self.resize_image_bytes(header, scale=0.5)
            try:
                text = ocr_service.extract_text_from_bytes(header)
            except OCRError as e:
                logger.debug(f"Erro OCR na detecao de pagina de tabela: {e}")
                text = ""

            normalized = normalize_description(text)
            hits = sum(1 for k in keywords if k in normalized)
            if hits >= 2:
                table_pages.append(index)
                continue

            import re
            if re.search(r"\b\d{3}\s*\d{2}\s*\d{2}\b", normalized):
                table_pages.append(index)

        # Incluir páginas consecutivas após as detectadas
        if table_pages and len(images) > 1:
            max_detected = max(table_pages)
            for i in range(max_detected + 1, len(images)):
                if i not in table_pages:
                    table_pages.append(i)
            table_pages.sort()

        return table_pages

    def _median(self, values: list) -> float:
        """Calcula mediana de uma lista."""
        if not values:
            return 0.0
        sorted_vals = sorted(values)
        mid = len(sorted_vals) // 2
        if len(sorted_vals) % 2 == 1:
            return float(sorted_vals[mid])
        return float(sorted_vals[mid - 1] + sorted_vals[mid]) / 2


# Instância singleton
table_extractor = TableExtractor()
