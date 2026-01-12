"""
Serviço integrado de processamento de documentos.
Combina extração de PDF, OCR e análise com IA.
Suporta GPT-4o Vision para análise direta de imagens.
Inclui processamento paralelo opcional para melhor performance.
"""

from typing import Dict, Any, List, Optional
from pathlib import Path
import io
import re
import pdfplumber
import fitz  # PyMuPDF
from PIL import Image
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

from .pdf_extractor import pdf_extractor
from .ocr_service import ocr_service
from .ai_provider import ai_provider
from .document_ai_service import document_ai_service
# Módulos extraídos para migração gradual - noqa: F401
from .pdf_converter import pdf_converter  # noqa: F401
from .extraction import (  # noqa: F401
    # text_normalizer
    normalize_description,
    normalize_unit,
    normalize_header,
    normalize_desc_for_match,
    extract_keywords,
    description_similarity,
    UNIT_TOKENS,
    # table_processor
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
    # service_filter
    filter_classification_paths,
    remove_duplicate_services,
    filter_servicos_by_item_length,
    filter_servicos_by_item_prefix,
    repair_missing_prefix,
    is_summary_row,
    filter_summary_rows,
    deduplicate_by_description,
    quantities_similar,
    descriptions_similar,
    items_similar,
    servico_key,
    merge_servicos_prefer_primary,
    dominant_item_length,
    # quality_assessor
    compute_servicos_stats,
    compute_description_quality,
    is_ocr_noisy,
    compute_quality_score,
)
from .aditivo_processor import prefix_aditivo_items
from exceptions import (
    PDFError,
    OCRError,
    UnsupportedFileError,
    TextExtractionError,
    AzureAPIError,
    OpenAIError,
)
from .text_utils import is_garbage_text
from config import (
    OCR_PARALLEL_ENABLED,
    OCR_MAX_WORKERS,
    AtestadoProcessingConfig as APC,
)

from logging_config import get_logger
logger = get_logger('services.document_processor')


class ProcessingCancelled(Exception):
    """Processamento cancelado pelo usuario."""


class DocumentProcessor:
    """Processador integrado de documentos."""

    def _pdf_to_images(
        self,
        file_path: str,
        dpi: int = 300,
        progress_callback=None,
        cancel_check=None,
        stage: str = "vision"
    ) -> List[bytes]:
        """
        Converte páginas de PDF em imagens PNG.

        Args:
            file_path: Caminho para o arquivo PDF
            dpi: Resolução em DPI (300 para melhor qualidade de OCR)

        Returns:
            Lista de imagens em bytes (PNG)
        """
        images = []
        doc = fitz.open(file_path)
        zoom = dpi / 72
        matrix = fitz.Matrix(zoom, zoom)

        total_pages = doc.page_count
        for page_index, page in enumerate(doc):
            self._check_cancel(cancel_check)
            self._notify_progress(
                progress_callback,
                page_index + 1,
                total_pages,
                stage,
                f"Convertendo pagina {page_index + 1} de {total_pages}"
            )
            pix = page.get_pixmap(matrix=matrix)
            img_bytes = pix.tobytes("png")
            images.append(img_bytes)

        doc.close()
        return images

    def _extract_pdf_with_ocr_fallback(
        self,
        file_path: str,
        progress_callback=None,
        cancel_check=None
    ) -> str:
        """
        Extrai texto de PDF, aplicando OCR em páginas que são imagens.

        Args:
            file_path: Caminho para o arquivo PDF

        Returns:
            Texto completo extraído (texto + OCR)
        """
        MIN_TEXT_PER_PAGE = 200  # Mínimo de caracteres para considerar página como texto
        text_parts = []
        pages_needing_ocr = []

        try:
            # Primeiro, tentar extrair texto de cada página
            with pdfplumber.open(file_path) as pdf:
                total_pages = len(pdf.pages)
                for i, page in enumerate(pdf.pages):
                    self._check_cancel(cancel_check)
                    self._notify_progress(
                        progress_callback,
                        i + 1,
                        total_pages,
                        "texto",
                        f"Extraindo texto da pagina {i + 1} de {total_pages}"
                    )
                    page_text = page.extract_text() or ""
                    text_stripped = page_text.strip()

                    # Se a página tem pouco texto OU texto é lixo/marca d'água, marcar para OCR
                    needs_ocr = len(text_stripped) < MIN_TEXT_PER_PAGE or is_garbage_text(text_stripped)

                    if needs_ocr:
                        pages_needing_ocr.append(i)
                        text_parts.append(f"[PÁGINA {i+1} - AGUARDANDO OCR]")
                    else:
                        text_parts.append(f"Página {i+1}/{len(pdf.pages)}\n{page_text}")

            # Se há páginas que precisam de OCR, processar
            if pages_needing_ocr:
                import fitz
                doc = fitz.open(file_path)
                zoom = 300 / 72  # 300 DPI para melhor qualidade de OCR
                matrix = fitz.Matrix(zoom, zoom)

                total_ocr = len(pages_needing_ocr)
                for ocr_index, page_idx in enumerate(pages_needing_ocr):
                    self._check_cancel(cancel_check)
                    self._notify_progress(
                        progress_callback,
                        ocr_index + 1,
                        total_ocr,
                        "ocr",
                        f"OCR na pagina {ocr_index + 1} de {total_ocr}"
                    )
                    try:
                        page = doc[page_idx]
                        pix = page.get_pixmap(matrix=matrix)
                        img_bytes = pix.tobytes("png")

                        # Aplicar OCR na página
                        ocr_text = ocr_service.extract_text_from_bytes(img_bytes)

                        if ocr_text and len(ocr_text.strip()) > 20:
                            # Substituir placeholder pelo texto do OCR
                            placeholder = f"[PÁGINA {page_idx+1} - AGUARDANDO OCR]"
                            text_parts = [
                                f"Página {page_idx+1}/{len(doc)}\n{ocr_text}" if part == placeholder else part
                                for part in text_parts
                            ]
                    except OCRError as e:
                        logger.warning(f"Erro no OCR da pagina {page_idx+1}: {e}")

                doc.close()

            return "\n\n".join(text_parts)

        except (IOError, ValueError, RuntimeError, PDFError, OCRError) as e:
            raise PDFError("processar", str(e))

    def _notify_progress(self, progress_callback, current: int, total: int, stage: str, message: str):
        if progress_callback:
            progress_callback(current, total, stage, message)

    def _check_cancel(self, cancel_check):
        if cancel_check and cancel_check():
            raise ProcessingCancelled("Processamento cancelado.")

    def _ocr_single_page(self, args) -> tuple:
        """Processa uma única página para OCR (usado em paralelo)."""
        page_index, image_bytes = args
        try:
            page_text = ocr_service.extract_text_from_bytes(image_bytes)
            if page_text.strip():
                return (page_index, f"--- Pagina {page_index + 1} ---\n{page_text}")
            return (page_index, "")
        except OCRError as e:
            logger.debug(f"Erro OCR na pagina {page_index + 1}: {e}")
            return (page_index, f"--- Pagina {page_index + 1} ---\n[Erro no OCR: {e}]")

    def _ocr_image_list(self, image_list, progress_callback=None, cancel_check=None) -> str:
        total = len(image_list)

        # Usar processamento paralelo se habilitado e houver múltiplas páginas
        if OCR_PARALLEL_ENABLED and total > 1:
            return self._ocr_image_list_parallel(image_list, progress_callback, cancel_check)

        # Processamento sequencial (padrão)
        all_texts = []
        for i, image_bytes in enumerate(image_list):
            self._check_cancel(cancel_check)
            self._notify_progress(
                progress_callback,
                i + 1,
                total,
                "ocr",
                f"OCR na pagina {i + 1} de {total}"
            )
            try:
                page_text = ocr_service.extract_text_from_bytes(image_bytes)
                if page_text.strip():
                    all_texts.append(f"--- Pagina {i + 1} ---\n{page_text}")
            except OCRError as e:
                logger.debug(f"Erro OCR na pagina {i + 1}: {e}")
                all_texts.append(f"--- Pagina {i + 1} ---\n[Erro no OCR: {e}]")

        return "\n\n".join(all_texts)

    def _ocr_image_list_parallel(self, image_list, progress_callback=None, cancel_check=None) -> str:
        """
        Processa múltiplas páginas em paralelo.
        Útil quando há muitas páginas e CPU com múltiplos núcleos.
        """
        total = len(image_list)
        results = {}
        completed_count = 0
        lock = threading.Lock()

        def update_progress():
            nonlocal completed_count
            with lock:
                completed_count += 1
                self._notify_progress(
                    progress_callback,
                    completed_count,
                    total,
                    "ocr",
                    f"OCR paralelo: {completed_count} de {total} paginas"
                )

        with ThreadPoolExecutor(max_workers=OCR_MAX_WORKERS) as executor:
            # Submeter todas as páginas para processamento
            futures = {
                executor.submit(self._ocr_single_page, (i, img)): i
                for i, img in enumerate(image_list)
            }

            # Coletar resultados conforme completam
            for future in as_completed(futures):
                self._check_cancel(cancel_check)
                page_index, text = future.result()
                results[page_index] = text
                update_progress()

        # Ordenar resultados por índice de página
        all_texts = [results[i] for i in sorted(results.keys()) if results[i]]
        return "\n\n".join(all_texts)

    def _remove_duplicate_pairs(self, servicos: list) -> list:
        """
        Remove duplicatas entre pares X.Y e X.Y.1 que representam o mesmo serviço.

        Quando ambos existem com quantidade igual e descrições similares:
        - Calcula similaridade baseada em keywords em comum
        - Se similaridade >= 50%, são considerados duplicados
        - Mantém apenas o item com código mais curto (X.Y) pois geralmente é o original
        - Exceto quando o pai é um header curto (< 20 chars), aí mantém o filho (X.Y.1)
        """
        if not servicos:
            return servicos

        # Indexar serviços por código de item
        by_item_code = {}
        for s in servicos:
            item = s.get("item")
            if item:
                by_item_code[str(item)] = s

        # Identificar itens a remover
        items_to_remove = set()

        for item_code, servico in by_item_code.items():
            # Verificar se existe item pai (X.Y para X.Y.1)
            parts = item_code.split(".")
            if len(parts) >= 2:
                parent_code = ".".join(parts[:-1])
                if parent_code in by_item_code:
                    parent = by_item_code[parent_code]

                    # Comparar quantidade
                    qty_filho = parse_quantity(servico.get("quantidade"))
                    qty_pai = parse_quantity(parent.get("quantidade"))

                    if not (qty_filho is not None and qty_pai is not None):
                        continue

                    # Verificar se quantidades são iguais ou similares
                    if not quantities_similar(qty_filho, qty_pai):
                        continue

                    # Calcular similaridade de descrições via keywords
                    desc_filho = servico.get("descricao") or ""
                    desc_pai = parent.get("descricao") or ""
                    kw_filho = extract_keywords(desc_filho)
                    kw_pai = extract_keywords(desc_pai)

                    if not kw_filho or not kw_pai:
                        continue

                    # Calcular Jaccard similarity
                    intersection = len(kw_filho & kw_pai)
                    union = len(kw_filho | kw_pai)
                    similarity = intersection / union if union > 0 else 0

                    # Se similaridade >= 50%, são duplicados
                    if similarity >= 0.5:
                        # Decidir qual remover baseado no contexto
                        desc_pai_norm = normalize_description(desc_pai)

                        # Caso 1: Pai é header curto - remover pai, manter filho
                        if len(desc_pai_norm) < 20:
                            items_to_remove.add(parent_code)
                        # Caso 2: Itens do aditivo (11.x) - manter filho (são os serviços reais)
                        elif parent_code.startswith("11"):
                            items_to_remove.add(parent_code)
                        # Caso 3: Itens do contrato - remover filho (provavelmente fantasma do OCR)
                        else:
                            items_to_remove.add(item_code)

        # Filtrar serviços removendo os duplicados
        return [s for s in servicos if s.get("item") not in items_to_remove]

    def _filter_items_without_quantity(self, servicos: list) -> list:
        """
        Remove itens que não têm quantidade definida.

        Itens sem quantidade geralmente são headers de seção ou linhas de título
        que foram erroneamente extraídos como serviços.

        Preserva itens do aditivo que foram prefixados (têm _section metadata),
        pois esses itens foram identificados como tendo quantidade no texto original
        mesmo que a extração não tenha capturado a quantidade corretamente.
        """
        if not servicos:
            return servicos

        return [
            s for s in servicos
            if parse_quantity(s.get("quantidade")) not in (None, 0)
            or s.get("_section")  # Preservar itens do aditivo prefixados
        ]

    def _filter_items_without_code(self, servicos: list, min_items_with_code: int = 5) -> list:
        """
        Remove itens sem código de item quando há itens suficientes com código.

        Itens sem código (item=None) geralmente são descrições gerais do documento
        (ex: "Execução de obra de SISTEMAS DE ILUMINAÇÃO") que foram erroneamente
        extraídos como serviços pela IA.

        Só remove itens sem código quando há pelo menos `min_items_with_code` itens
        com código, para não afetar documentos simples sem numeração.

        Args:
            servicos: Lista de serviços
            min_items_with_code: Mínimo de itens com código para ativar o filtro

        Returns:
            Lista filtrada de serviços
        """
        if not servicos:
            return servicos

        # Contar itens com e sem código
        com_codigo = [s for s in servicos if s.get("item")]
        sem_codigo = [s for s in servicos if not s.get("item")]

        # Se há poucos itens com código, manter todos (documento pode não ter numeração)
        if len(com_codigo) < min_items_with_code:
            return servicos

        # Se há itens suficientes com código, remover os sem código
        if sem_codigo:
            logger.info(f"[FILTRO] Removendo {len(sem_codigo)} itens sem código de item (há {len(com_codigo)} itens com código)")
            for s in sem_codigo:
                desc = (s.get("descricao") or "")[:50]
                logger.info(f"[FILTRO] Removido item sem código: {desc}...")

        return com_codigo

    def _extract_servicos_from_table(self, table: list, preferred_item_col: Optional[int] = None) -> tuple[list, float, dict]:
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

        header_index = detect_header_row(normalized_rows)
        header_map = {"item": None, "descricao": None, "unidade": None, "quantidade": None, "valor": None}
        data_rows = normalized_rows
        if header_index is not None:
            header_map = guess_columns_by_header(normalized_rows[header_index])
            data_rows = normalized_rows[header_index + 1:]

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

        col_stats = compute_column_stats(data_rows, max_cols)
        header_map = guess_columns_by_content(data_rows, max_cols, header_map, col_stats)
        header_map = validate_column_mapping(header_map, col_stats)
        header_map = guess_columns_by_content(data_rows, max_cols, header_map, col_stats)
        desc_col = header_map.get("descricao")
        unit_col = header_map.get("unidade")
        qty_col = header_map.get("quantidade")

        servicos = []
        last_item = None
        item_tuples = []
        for row in data_rows:
            cells = [str(cell or "").strip() for cell in row]
            item_val = cells[item_col] if item_col is not None and item_col < len(cells) else ""
            item_tuple = parse_item_tuple(item_val)
            item_col_effective = item_col
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
                if last_item:
                    if desc_val:
                        last_item["descricao"] = (str(last_item.get("descricao") or "") + " " + str(desc_val)).strip()
                    if not last_item.get("unidade") and unit_val:
                        last_item["unidade"] = unit_val.strip()
                    if (last_item.get("quantidade") in (None, 0)) and parse_quantity(qty_val) not in (None, 0):
                        last_item["quantidade"] = parse_quantity(qty_val)

        servicos = [s for s in servicos if s.get("descricao")]
        servicos, prefix_info = filter_servicos_by_item_prefix(servicos)
        dominant_len, dominant_len_ratio = dominant_item_length(servicos)
        repair_info = {"applied": False, "repaired": 0}
        if dominant_len == 3 and prefix_info.get("dominant_prefix") is not None:
            servicos, repair_info = repair_missing_prefix(servicos, prefix_info.get("dominant_prefix"))
        servicos, dominant_info = filter_servicos_by_item_length(servicos)
        stats = compute_servicos_stats(servicos)
        seq_ratio = 0.0
        filtered_tuples = []
        for servico in servicos:
            item_value: Any = servico.get("item")
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
            "preferred_item_score": preferred_score_data,
            "preferred_item_used": preferred_used,
            "seq_ratio": round(seq_ratio, 3),
            "prefix_item": prefix_info,
            "dominant_item": dominant_info,
            "prefix_repair": repair_info,
            "stats": stats,
            "confidence": confidence
        }
        return servicos, confidence, debug

    def _extract_servicos_from_tables(self, file_path: str) -> tuple[list, float, dict]:
        try:
            tables = pdf_extractor.extract_tables(file_path)
        except (PDFError, IOError, ValueError) as exc:
            logger.warning(f"Erro ao extrair tabelas: {exc}")
            return [], 0.0, {"error": str(exc)}
        if not tables:
            return [], 0.0, {"tables": 0}

        # Combinar servicos de TODAS as tabelas (não apenas a melhor)
        all_servicos: list = []
        all_confidences: list = []
        best_debug: dict = {}
        item_counts: dict[str, int] = {}  # Contador de ocorrências de cada item

        for table in tables:
            servicos, confidence, debug = self._extract_servicos_from_table(table)
            if servicos:
                all_confidences.append(confidence)
                if not best_debug or confidence > best_debug.get("confidence", 0):
                    best_debug = debug

                # Adicionar servicos - NÃO prefixar aqui, deixar para _prefix_aditivo_items
                # que usa detecção inteligente de reinício de numeração
                for s in servicos:
                    item = s.get("item", "")
                    if item:
                        count = item_counts.get(item, 0)
                        if count == 0:
                            # Primeira ocorrência - manter item original
                            item_counts[item] = 1
                            all_servicos.append(s)
                        else:
                            # Item duplicado - manter sem prefixo aqui
                            # O prefixo AD- será adicionado por _prefix_aditivo_items
                            item_counts[item] = count + 1
                            all_servicos.append(s)
                    else:
                        # Item sem número - adicionar diretamente
                        all_servicos.append(s)

        # Calcular confidence média
        avg_confidence = sum(all_confidences) / len(all_confidences) if all_confidences else 0.0
        best_debug["tables"] = len(tables)
        best_debug["combined_tables"] = len([c for c in all_confidences if c > 0])

        return all_servicos, avg_confidence, best_debug

    def _extract_servicos_from_document_ai(self, file_path: str) -> tuple[list, float, dict]:
        if not document_ai_service.is_configured:
            return [], 0.0, {"enabled": False, "error": "not_configured"}
        try:
            result = document_ai_service.extract_tables(file_path)
        except (AzureAPIError, IOError, ValueError) as exc:
            logger.warning(f"Erro no Document AI: {exc}")
            return [], 0.0, {"error": str(exc)}

        tables = result.get("tables") or []
        if not tables:
            return [], 0.0, {"tables": 0, "pages": result.get("pages", 0)}

        best: Dict[str, Any] = {"servicos": [], "confidence": 0.0, "debug": {}}
        for table in tables:
            rows = table.get("rows") or []
            servicos, confidence, debug = self._extract_servicos_from_table(rows)
            debug["page"] = table.get("page")
            if confidence > best["confidence"] or (
                confidence == best["confidence"] and len(servicos) > len(best["servicos"])
            ):
                best = {"servicos": servicos, "confidence": confidence, "debug": debug}

        best["debug"]["tables"] = len(tables)
        best["debug"]["pages"] = result.get("pages", 0)
        return best["servicos"], best["confidence"], best["debug"]

    def _choose_best_table(
        self,
        current_servicos: list,
        current_confidence: float,
        current_debug: dict,
        candidate_servicos: list,
        candidate_confidence: float,
        candidate_debug: dict
    ) -> tuple[list, float, dict]:
        if candidate_confidence > current_confidence:
            return candidate_servicos, candidate_confidence, candidate_debug
        if candidate_confidence == current_confidence and len(candidate_servicos) > len(current_servicos):
            return candidate_servicos, candidate_confidence, candidate_debug
        return current_servicos, current_confidence, current_debug

    def _summarize_table_debug(self, debug: dict) -> dict:
        if not isinstance(debug, dict):
            return {}
        summary = {}
        for key in ("source", "tables", "pages", "pages_used", "error"):
            if key in debug:
                summary[key] = debug.get(key)
        if "ocr_noise" in debug:
            summary["ocr_noise"] = debug.get("ocr_noise")
        return summary

    def _median(self, values: list) -> float:
        if not values:
            return 0.0
        sorted_vals = sorted(values)
        mid = len(sorted_vals) // 2
        if len(sorted_vals) % 2 == 1:
            return float(sorted_vals[mid])
        return float(sorted_vals[mid - 1] + sorted_vals[mid]) / 2

    def _build_table_from_ocr_words(self, words: list) -> tuple[list, list]:
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
        current = []
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

    def _infer_item_column_from_words(self, words: list, col_centers: list) -> tuple[Optional[int], dict]:
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

    def _extract_servicos_from_ocr_layout(
        self,
        file_path: str,
        progress_callback=None,
        cancel_check=None
    ) -> tuple[list, float, dict]:
        min_conf = APC.OCR_LAYOUT_CONFIDENCE
        dpi = APC.OCR_LAYOUT_DPI
        page_min_items = APC.OCR_LAYOUT_PAGE_MIN_ITEMS

        images = []
        file_ext = Path(file_path).suffix.lower()
        if file_ext == ".pdf":
            images = self._pdf_to_images(
                file_path,
                dpi=dpi,
                progress_callback=progress_callback,
                cancel_check=cancel_check,
                stage="ocr"
            )
        else:
            with open(file_path, "rb") as f:
                images = [f.read()]

        if not images:
            return [], 0.0, {"pages": 0}

        table_pages = self._detect_table_pages(images)
        if table_pages:
            page_queue = list(dict.fromkeys(table_pages))
            page_seen = set(page_queue)
        else:
            page_queue = list(range(len(images)))
            page_seen = set(page_queue)
        processed_pages = []

        total_items = 0
        weighted_conf = 0.0
        all_servicos = []
        page_debug = []

        while page_queue:
            page_index = page_queue.pop(0)
            self._check_cancel(cancel_check)
            image_bytes = images[page_index]
            cropped = self._crop_region(image_bytes, 0.05, 0.15, 0.95, 0.92)
            try:
                words = ocr_service.extract_words_from_bytes(cropped, min_confidence=min_conf)
            except OCRError as exc:
                logger.debug(f"Erro OCR na pagina {page_index + 1}: {exc}")
                page_debug.append({"page": page_index + 1, "error": str(exc)})
                continue

            table_rows, col_centers = self._build_table_from_ocr_words(words)
            preferred_item_col, item_col_debug = self._infer_item_column_from_words(words, col_centers)
            servicos, confidence, debug = self._extract_servicos_from_table(
                table_rows,
                preferred_item_col=preferred_item_col
            )
            stats = debug.get("stats") or {}
            dominant = debug.get("dominant_item") or {}
            total_page_items = stats.get("total", 0)
            item_ratio = stats.get("with_item", 0) / max(1, total_page_items)
            unit_ratio = stats.get("with_unit", 0) / max(1, total_page_items)
            dominant_len = dominant.get("dominant_len", 0) or 0

            primary_accept = (
                total_page_items > 0
                and dominant_len >= APC.OCR_PAGE_MIN_DOMINANT_LEN
                and item_ratio >= APC.OCR_PAGE_MIN_ITEM_RATIO
                and unit_ratio >= APC.OCR_PAGE_MIN_UNIT_RATIO
            )
            fallback_accept = (
                total_page_items >= APC.OCR_PAGE_MIN_ITEMS
                and dominant_len == 1
                and item_ratio >= APC.OCR_PAGE_FALLBACK_ITEM_RATIO
                and unit_ratio >= APC.OCR_PAGE_FALLBACK_UNIT_RATIO
            )
            page_accept = primary_accept or fallback_accept
            debug.update({
                "page": page_index + 1,
                "row_count": len(table_rows),
                "word_count": len(words),
                "item_col": item_col_debug,
                "page_accept": page_accept
            })
            page_debug.append(debug)
            processed_pages.append(page_index)
            if not page_accept:
                continue

            if servicos:
                all_servicos.extend(servicos)
                total_items += len(servicos)
                weighted_conf += confidence * len(servicos)
                if table_pages and len(servicos) >= page_min_items:
                    for neighbor in (page_index - 1, page_index + 1):
                        if 0 <= neighbor < len(images) and neighbor not in page_seen:
                            page_seen.add(neighbor)
                            page_queue.append(neighbor)

        overall_conf = (weighted_conf / total_items) if total_items else 0.0
        return all_servicos, round(overall_conf, 3), {
            "pages": len(processed_pages),
            "pages_used": sorted(set(processed_pages)),
            "page_debug": page_debug
        }

    def _select_primary_source(self, vision_stats: dict, ocr_stats: dict, vision_score: float, ocr_score: float) -> str:
        margin = APC.SCORE_MARGIN
        if vision_score >= ocr_score + margin:
            return "vision"
        if ocr_score >= vision_score + margin:
            return "ocr"

        def quality_tuple(stats: dict):
            total = max(1, stats.get("total", 0))
            return (
                stats.get("with_item", 0) / total,
                stats.get("with_qty", 0) / total,
                stats.get("with_unit", 0) / total,
                stats.get("total", 0)
            )

        vision_tuple = quality_tuple(vision_stats)
        ocr_tuple = quality_tuple(ocr_stats)
        if vision_tuple > ocr_tuple:
            return "vision"
        if ocr_tuple > vision_tuple:
            return "ocr"
        return "vision"

    def _crop_region(self, image_bytes: bytes, left: float, top: float, right: float, bottom: float) -> bytes:
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

    def _resize_image_bytes(self, image_bytes: bytes, scale: float = 0.5) -> bytes:
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

    def _detect_table_pages(self, images: List[bytes]) -> List[int]:
        keywords = {"RELATORIO", "SERVICOS", "EXECUTADOS", "ITEM", "DISCRIMINACAO", "UNID", "QUANTIDADE"}
        table_pages = []
        for index, image_bytes in enumerate(images):
            header = self._crop_region(image_bytes, 0.05, 0.0, 0.95, 0.35)
            header = self._resize_image_bytes(header, scale=0.5)
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
            if re.search(r"\b\d{3}\s*\d{2}\s*\d{2}\b", normalized):
                table_pages.append(index)

        # Se encontramos páginas de tabela mas não a última, incluir páginas consecutivas
        # pois tabelas frequentemente continuam em páginas seguintes sem cabeçalho
        if table_pages and len(images) > 1:
            max_detected = max(table_pages)
            # Se há páginas após a última detectada, incluí-las
            for i in range(max_detected + 1, len(images)):
                if i not in table_pages:
                    table_pages.append(i)
            table_pages.sort()

        return table_pages

    def _extract_servicos_pagewise(self, images: List[bytes], progress_callback=None, cancel_check=None) -> List[dict]:
        servicos: List[Dict[str, Any]] = []
        total_pages = len(images)
        if total_pages == 0:
            return servicos
        table_pages = self._detect_table_pages(images)
        page_indexes = table_pages if table_pages else list(range(total_pages))
        total = len(page_indexes)
        logger.info(f"Pagewise: processando {total} paginas de {total_pages} - indices: {page_indexes}")
        for idx, page_index in enumerate(page_indexes):
            self._check_cancel(cancel_check)
            self._notify_progress(progress_callback, idx + 1, total, "ia", f"Analisando pagina {page_index + 1} de {total_pages} com IA")
            image_bytes = images[page_index]
            cropped = self._crop_region(image_bytes, 0.05, 0.15, 0.95, 0.92)
            try:
                result = ai_provider.extract_atestado_from_images([cropped], provider="openai")
                page_servicos = result.get("servicos", []) if isinstance(result, dict) else []
                logger.info(f"Pagewise: pagina {page_index + 1} extraiu {len(page_servicos)} servicos")
                for s in page_servicos:
                    logger.debug(f"  Item: {s.get('item', '?')}: {s.get('descricao', '')[:50]}")
                servicos.extend(page_servicos)
            except (OpenAIError, ValueError, KeyError) as exc:
                logger.warning(f"Erro na IA por pagina {page_index + 1}: {exc}")
        logger.info(f"Pagewise: total extraido = {len(servicos)} servicos")
        return servicos

    def _extract_item_code(self, desc: str) -> str:
        """
        Extrai código do item da descrição (ex: "001.03.01" de "001.03.01 MOBILIZAÇÃO").
        Também reconhece formatos com prefixo AD- (ex: "AD-1.1", "AD-1.1-A").
        """
        if not desc:
            return ""

        text = desc.strip()

        # Primeiro, tentar extrair formato com prefixo AD- (ex: AD-1.1, AD-1.1-A)
        ad_match = re.match(r'^(AD-\d{1,3}(?:\.\d{1,3})+(?:-[A-Z])?)\b', text, re.IGNORECASE)
        if ad_match:
            return ad_match.group(1).upper()

        # Formato numérico padrão (ex: 1.1, 10.4, 10.4-A)
        match = re.match(r'^(\d{1,3}(?:\s*\.\s*\d{1,3}){1,3}(?:-[A-Z])?)\b', text)
        if not match:
            match = re.match(r'^(\d{1,3}(?:\s+\d{1,2}){1,3})\b', text)

        if match:
            code = re.sub(r'[\s]+', '.', match.group(1))
            code = re.sub(r'\.{2,}', '.', code).strip('.')
            return code
        return ""

    def _split_item_description(self, desc: str) -> tuple[str, str]:
        """
        Separa o codigo do item da descricao, se presente.
        """
        if not desc:
            return "", ""

        code = self._extract_item_code(desc)
        if not code:
            return "", desc.strip()

        cleaned = re.sub(
            r"^(\d{1,3}(?:\s*\.\s*\d{1,3}){1,3}|\d{1,3}(?:\s+\d{1,2}){1,3})\s*[-.]?\s*",
            "",
            desc
        ).strip()
        return code, cleaned or desc.strip()

    def _servico_match_key(self, servico: dict) -> str:
        desc = normalize_desc_for_match(servico.get("descricao") or "")
        unit = normalize_unit(servico.get("unidade") or "")
        if not desc:
            return ""
        return f"{desc}|||{unit}"

    def _servico_desc_key(self, servico: dict) -> str:
        return normalize_desc_for_match(servico.get("descricao") or "")

    def _dedupe_no_code_by_desc_unit(self, servicos: list) -> list:
        if not servicos:
            return servicos

        deduped: Dict[str, Any] = {}
        extras = []

        def score(item: dict) -> int:
            score_val = len((item.get("descricao") or "").strip())
            if parse_quantity(item.get("quantidade")) not in (None, 0):
                score_val += 50
            if item.get("unidade"):
                score_val += 10
            return score_val

        for servico in servicos:
            key = self._servico_match_key(servico)
            if not key:
                extras.append(servico)
                continue
            existing = deduped.get(key)
            if not existing or score(servico) > score(existing):
                deduped[key] = servico

        return list(deduped.values()) + extras

    def _prefer_items_with_code(self, servicos: list) -> list:
        if not servicos:
            return servicos if isinstance(servicos, list) else []

        if isinstance(servicos, dict):
            nested = servicos.get("servicos")
            if isinstance(nested, list):
                servicos = nested
            else:
                servicos = [servicos]

        if not isinstance(servicos, list):
            return []

        servicos = [servico for servico in servicos if isinstance(servico, dict)]
        if not servicos:
            return []

        coded = []
        no_code = []
        for servico in servicos:
            item = servico.get("item") or self._extract_item_code(servico.get("descricao") or "")
            if item:
                servico["item"] = item
                coded.append(servico)
            else:
                no_code.append(servico)

        if not coded:
            return self._dedupe_no_code_by_desc_unit(no_code)

        coded_keys = {self._servico_match_key(servico) for servico in coded}
        coded_desc_keys = {self._servico_desc_key(servico) for servico in coded if self._servico_desc_key(servico)}
        coded_entries = [
            {
                "descricao": servico.get("descricao") or "",
                "unidade": normalize_unit(servico.get("unidade") or ""),
                "quantidade": parse_quantity(servico.get("quantidade"))
            }
            for servico in coded
        ]
        similarity_threshold = APC.DESC_SIM_THRESHOLD

        filtered_no_code = [
            servico for servico in no_code
            if self._servico_match_key(servico) not in coded_keys
            and self._servico_desc_key(servico) not in coded_desc_keys
        ]
        refined_no_code = []
        for servico in filtered_no_code:
            desc = servico.get("descricao") or ""
            unit = normalize_unit(servico.get("unidade") or "")
            qty = parse_quantity(servico.get("quantidade"))
            drop = False
            for coded_entry in coded_entries:
                coded_desc = str(coded_entry.get("descricao") or "")
                if description_similarity(desc, coded_desc) < similarity_threshold:
                    continue
                unit_match = bool(unit and coded_entry["unidade"] and unit == coded_entry["unidade"])
                qty_match = False
                coded_qty = coded_entry.get("quantidade")
                if qty is not None and coded_qty is not None and isinstance(qty, (int, float)) and isinstance(coded_qty, (int, float)) and qty != 0 and coded_qty != 0:
                    diff = abs(qty - coded_qty)
                    denom = max(abs(qty), abs(coded_qty))
                    if denom > 0:
                        qty_match = (diff / denom) <= 0.02 or diff <= 0.01
                if unit_match or qty_match:
                    drop = True
                    break
            if not drop:
                refined_no_code.append(servico)

        refined_no_code = self._dedupe_no_code_by_desc_unit(refined_no_code)
        return coded + refined_no_code

    def _table_candidates_by_code(self, servicos_table: list) -> dict:
        if not servicos_table:
            return {}
        unit_tokens = UNIT_TOKENS
        candidates: Dict[str, Any] = {}
        for servico in servicos_table:
            item = servico.get("item") or self._extract_item_code(servico.get("descricao") or "")
            if not item:
                continue
            item_tuple = parse_item_tuple(item)
            if not item_tuple:
                continue
            desc = (servico.get("descricao") or "").strip()
            if len(desc) < 8:
                continue
            qty = parse_quantity(servico.get("quantidade"))
            if qty is None:
                continue
            unit = normalize_unit(servico.get("unidade") or "")
            if unit and unit not in unit_tokens:
                unit = ""
            normalized_item = item_tuple_to_str(item_tuple)
            candidate = {
                "item": normalized_item,
                "descricao": desc,
                "quantidade": qty,
                "unidade": unit
            }
            existing = candidates.get(normalized_item)
            if not existing or len(desc) > len(existing.get("descricao") or ""):
                candidates[normalized_item] = candidate
        return candidates

    def _attach_item_codes_from_table(self, servicos: list, servicos_table: list) -> list:
        if not servicos or not servicos_table:
            return servicos
        table_candidates = self._table_candidates_by_code(servicos_table)
        if not table_candidates:
            return servicos

        match_threshold = APC.CODE_MATCH_THRESHOLD

        used_codes = {s.get("item") for s in servicos if s.get("item")}
        used_codes.discard(None)
        for servico in servicos:
            if servico.get("item"):
                continue
            desc = servico.get("descricao") or ""
            unit = normalize_unit(servico.get("unidade") or "")
            qty = parse_quantity(servico.get("quantidade"))
            best_code = None
            best_score = 0.0
            best_candidate = None
            for code, candidate in table_candidates.items():
                if code in used_codes:
                    continue
                score = description_similarity(desc, candidate["descricao"])
                if score < match_threshold:
                    continue
                if unit and candidate["unidade"] and unit == candidate["unidade"]:
                    score += 0.1
                cand_qty = candidate.get("quantidade")
                if qty is not None and cand_qty is not None and isinstance(qty, (int, float)) and isinstance(cand_qty, (int, float)) and qty != 0 and cand_qty != 0:
                    diff = abs(qty - cand_qty)
                    denom = max(abs(qty), abs(cand_qty))
                    if denom > 0 and (diff / denom) <= 0.05:
                        score += 0.1
                if score > best_score:
                    best_score = score
                    best_code = code
                    best_candidate = candidate
            if best_code:
                servico["item"] = best_code
                used_codes.add(best_code)
                if best_candidate and not servico.get("unidade") and best_candidate.get("unidade"):
                    servico["unidade"] = best_candidate["unidade"]
                if best_candidate and parse_quantity(servico.get("quantidade")) in (None, 0) and best_candidate.get("quantidade") is not None:
                    servico["quantidade"] = best_candidate["quantidade"]

        return servicos

    def _is_short_description(self, desc: str) -> bool:
        desc = (desc or '').strip()
        if not desc:
            return True
        if len(desc) < 35:
            return True
        if len(desc.split()) < 4:
            return True
        return False

    # ========================================================================
    # Métodos auxiliares para process_atestado (divididos para legibilidade)
    # ========================================================================

    def _extract_texto_from_file(
        self,
        file_path: str,
        file_ext: str,
        progress_callback=None,
        cancel_check=None
    ) -> str:
        """
        Extrai texto do arquivo (PDF ou imagem) usando OCR quando necessário.

        Args:
            file_path: Caminho para o arquivo
            file_ext: Extensão do arquivo (ex: ".pdf", ".png")
            progress_callback: Callback para progresso
            cancel_check: Função para verificar cancelamento

        Returns:
            Texto extraído do documento

        Raises:
            PDFError, OCRError, UnsupportedFileError, TextExtractionError
        """
        texto = ""

        if file_ext == ".pdf":
            try:
                texto = self._extract_pdf_with_ocr_fallback(
                    file_path,
                    progress_callback=progress_callback,
                    cancel_check=cancel_check
                )
            except (PDFError, TextExtractionError) as e:
                logger.warning(f"Fallback para OCR apos erro: {e}")
                try:
                    images = pdf_extractor.pdf_to_images(file_path)
                    texto = self._ocr_image_list(
                        images,
                        progress_callback=progress_callback,
                        cancel_check=cancel_check
                    )
                except (PDFError, OCRError) as e2:
                    raise PDFError("processar", f"{e} / OCR: {e2}")
        elif file_ext in [".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif"]:
            try:
                self._check_cancel(cancel_check)
                self._notify_progress(progress_callback, 1, 1, "ocr", "OCR da imagem")
                texto = ocr_service.extract_text_from_image(file_path)
            except (OCRError, IOError) as e:
                raise OCRError(str(e))
        else:
            raise UnsupportedFileError(file_ext)

        if not texto.strip():
            raise TextExtractionError("documento")

        return texto

    def _extract_servicos_from_all_tables(
        self,
        file_path: str,
        file_ext: str,
        progress_callback=None,
        cancel_check=None
    ) -> tuple[list, float, dict, dict]:
        """
        Tenta extrair serviços de tabelas usando múltiplos métodos.

        Tenta: Document AI, pdfplumber, OCR layout (nessa ordem de prioridade).

        Args:
            file_path: Caminho para o arquivo
            file_ext: Extensão do arquivo
            progress_callback: Callback para progresso
            cancel_check: Função para verificar cancelamento

        Returns:
            Tupla (servicos, confidence, debug, attempts)
        """
        servicos_table: list = []
        table_confidence = 0.0
        table_debug: dict = {}
        table_attempts: dict = {}

        table_threshold = APC.TABLE_CONFIDENCE_THRESHOLD
        table_min_items = APC.TABLE_MIN_ITEMS
        document_ai_enabled = APC.DOCUMENT_AI_ENABLED
        document_ai_fallback_only = APC.DOCUMENT_AI_FALLBACK_ONLY
        document_ai_ready = document_ai_enabled and document_ai_service.is_configured

        if file_ext == ".pdf":
            # Tentar Document AI primeiro (se não for fallback-only)
            if document_ai_ready and not document_ai_fallback_only:
                doc_servicos, doc_conf, doc_debug = self._extract_servicos_from_document_ai(file_path)
                doc_debug["source"] = "document_ai"
                table_attempts["document_ai"] = {
                    "count": len(doc_servicos),
                    "confidence": doc_conf,
                    "debug": self._summarize_table_debug(doc_debug)
                }
                servicos_table, table_confidence, table_debug = self._choose_best_table(
                    servicos_table, table_confidence, table_debug,
                    doc_servicos, doc_conf, doc_debug
                )

            # Tentar pdfplumber
            pdf_servicos, pdf_conf, pdf_debug = self._extract_servicos_from_tables(file_path)
            pdf_debug["source"] = "pdfplumber"
            table_attempts["pdfplumber"] = {
                "count": len(pdf_servicos),
                "confidence": pdf_conf,
                "debug": self._summarize_table_debug(pdf_debug)
            }
            servicos_table, table_confidence, table_debug = self._choose_best_table(
                servicos_table, table_confidence, table_debug,
                pdf_servicos, pdf_conf, pdf_debug
            )

            # Tentar OCR layout se necessário
            needs_ocr_layout = (
                not servicos_table
                or table_confidence < table_threshold
                or len(servicos_table) < table_min_items
            )
            if needs_ocr_layout:
                ocr_servicos, ocr_conf, ocr_debug = self._extract_servicos_from_ocr_layout(
                    file_path,
                    progress_callback=progress_callback,
                    cancel_check=cancel_check
                )
                ocr_debug["source"] = "ocr_layout"
                table_attempts["ocr_layout"] = {
                    "count": len(ocr_servicos),
                    "confidence": ocr_conf,
                    "debug": self._summarize_table_debug(ocr_debug)
                }
                servicos_table, table_confidence, table_debug = self._choose_best_table(
                    servicos_table, table_confidence, table_debug,
                    ocr_servicos, ocr_conf, ocr_debug
                )

            # Verificar ruído do OCR
            ocr_noisy = False
            if table_debug.get("source") == "ocr_layout" and servicos_table:
                ocr_noisy, ocr_noise_debug = is_ocr_noisy(servicos_table)
                table_debug["ocr_noise"] = ocr_noise_debug

            # Document AI como fallback
            needs_document_ai = (
                document_ai_ready
                and document_ai_fallback_only
                and (
                    not servicos_table
                    or table_confidence < table_threshold
                    or len(servicos_table) < table_min_items
                    or ocr_noisy
                )
            )
            if needs_document_ai:
                doc_servicos, doc_conf, doc_debug = self._extract_servicos_from_document_ai(file_path)
                doc_debug["source"] = "document_ai"
                table_attempts["document_ai"] = {
                    "count": len(doc_servicos),
                    "confidence": doc_conf,
                    "debug": self._summarize_table_debug(doc_debug)
                }
                servicos_table, table_confidence, table_debug = self._choose_best_table(
                    servicos_table, table_confidence, table_debug,
                    doc_servicos, doc_conf, doc_debug
                )

        elif file_ext in [".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif"]:
            # Imagem: tentar Document AI e OCR layout
            if document_ai_ready and not document_ai_fallback_only:
                doc_servicos, doc_conf, doc_debug = self._extract_servicos_from_document_ai(file_path)
                doc_debug["source"] = "document_ai"
                table_attempts["document_ai"] = {
                    "count": len(doc_servicos),
                    "confidence": doc_conf,
                    "debug": self._summarize_table_debug(doc_debug)
                }
                servicos_table, table_confidence, table_debug = self._choose_best_table(
                    servicos_table, table_confidence, table_debug,
                    doc_servicos, doc_conf, doc_debug
                )

            ocr_servicos, ocr_conf, ocr_debug = self._extract_servicos_from_ocr_layout(
                file_path,
                progress_callback=progress_callback,
                cancel_check=cancel_check
            )
            ocr_debug["source"] = "ocr_layout"
            table_attempts["ocr_layout"] = {
                "count": len(ocr_servicos),
                "confidence": ocr_conf,
                "debug": self._summarize_table_debug(ocr_debug)
            }
            servicos_table, table_confidence, table_debug = self._choose_best_table(
                servicos_table, table_confidence, table_debug,
                ocr_servicos, ocr_conf, ocr_debug
            )

            ocr_noisy = False
            if table_debug.get("source") == "ocr_layout" and servicos_table:
                ocr_noisy, ocr_noise_debug = is_ocr_noisy(servicos_table)
                table_debug["ocr_noise"] = ocr_noise_debug

            needs_document_ai = (
                document_ai_ready
                and document_ai_fallback_only
                and (
                    not servicos_table
                    or table_confidence < table_threshold
                    or len(servicos_table) < table_min_items
                    or ocr_noisy
                )
            )
            if needs_document_ai:
                doc_servicos, doc_conf, doc_debug = self._extract_servicos_from_document_ai(file_path)
                doc_debug["source"] = "document_ai"
                table_attempts["document_ai"] = {
                    "count": len(doc_servicos),
                    "confidence": doc_conf,
                    "debug": self._summarize_table_debug(doc_debug)
                }
                servicos_table, table_confidence, table_debug = self._choose_best_table(
                    servicos_table, table_confidence, table_debug,
                    doc_servicos, doc_conf, doc_debug
                )

        return servicos_table, table_confidence, table_debug, table_attempts

    def _extract_dados_with_ai(
        self,
        file_path: str,
        file_ext: str,
        texto: str,
        use_vision: bool,
        servicos_table: list,
        table_used: bool,
        progress_callback=None,
        cancel_check=None
    ) -> tuple[dict, str, dict]:
        """
        Extrai dados do atestado usando IA (Vision e/ou OCR text).

        Args:
            file_path: Caminho para o arquivo
            file_ext: Extensão do arquivo
            texto: Texto extraído do documento
            use_vision: Se deve usar análise de imagem
            servicos_table: Serviços extraídos de tabelas
            table_used: Se tabela foi usada com alta confiança
            progress_callback: Callback para progresso
            cancel_check: Função para verificar cancelamento

        Returns:
            Tupla (dados, primary_source, debug_info)
        """
        images: list = []
        vision_reprocessed = False
        vision_score = 0.0
        ocr_score = 0.0
        vision_stats = {"total": 0, "with_item": 0, "with_unit": 0, "with_qty": 0, "duplicate_ratio": 0.0}
        ocr_stats = {"total": 0, "with_item": 0, "with_unit": 0, "with_qty": 0, "duplicate_ratio": 0.0}
        dados_vision = None
        dados_ocr = None
        primary_source = None

        llm_fallback_only = APC.LLM_FALLBACK_ONLY
        use_ai_for_services = not llm_fallback_only or not table_used

        # Método 1: OCR + análise de texto
        self._notify_progress(progress_callback, 0, 0, "ia", "Analisando texto com IA")
        self._check_cancel(cancel_check)
        dados_ocr = ai_provider.extract_atestado_info(texto)

        # Método 2: Vision (GPT-4o ou Gemini)
        if use_vision:
            try:
                if file_ext == ".pdf":
                    images = self._pdf_to_images(
                        file_path,
                        dpi=300,
                        progress_callback=progress_callback,
                        cancel_check=cancel_check,
                        stage="vision"
                    )
                else:
                    with open(file_path, "rb") as f:
                        self._check_cancel(cancel_check)
                        self._notify_progress(progress_callback, 1, 1, "vision", "Carregando imagem")
                        images = [f.read()]

                self._notify_progress(progress_callback, 0, 0, "ia", "Analisando imagens com IA")
                self._check_cancel(cancel_check)
                dados_vision = ai_provider.extract_atestado_from_images(images)
            except (OpenAIError, ValueError, KeyError) as e:
                logger.warning(f"Erro no Vision: {e}")
                dados_vision = None

        servicos_vision = filter_summary_rows(dados_vision.get("servicos", []) if dados_vision else [])
        servicos_ocr = filter_summary_rows(dados_ocr.get("servicos", []) if dados_ocr else [])
        vision_stats = compute_servicos_stats(servicos_vision)
        ocr_stats = compute_servicos_stats(servicos_ocr)
        vision_score = compute_quality_score(vision_stats)
        ocr_score = compute_quality_score(ocr_stats)

        # Fallback por página com OpenAI quando a qualidade estiver baixa
        pagewise_enabled = APC.PAGEWISE_VISION_ENABLED
        logger.info(f"Pagewise check: enabled={pagewise_enabled}, use_vision={use_vision}, images={len(images) if images else 0}, openai_available={'openai' in ai_provider.available_providers}")
        if pagewise_enabled and use_vision and images and "openai" in ai_provider.available_providers:
            quality_threshold = APC.VISION_QUALITY_THRESHOLD
            min_pages = APC.PAGEWISE_MIN_PAGES
            min_items = APC.PAGEWISE_MIN_ITEMS
            logger.info(f"Pagewise condition: vision_score={vision_score:.2f} < {quality_threshold} OR (pages={len(images)} >= {min_pages} AND items={vision_stats.get('total', 0)} < {min_items})")
            if vision_score < quality_threshold or (len(images) >= min_pages and vision_stats.get("total", 0) < min_items):
                page_servicos = self._extract_servicos_pagewise(images, progress_callback, cancel_check)
                if page_servicos:
                    if dados_vision is None:
                        dados_vision = {
                            "descricao_servico": dados_ocr.get("descricao_servico") if dados_ocr else None,
                            "contratante": dados_ocr.get("contratante") if dados_ocr else None,
                            "data_emissao": dados_ocr.get("data_emissao") if dados_ocr else None,
                            "quantidade": dados_ocr.get("quantidade") if dados_ocr else None,
                            "unidade": dados_ocr.get("unidade") if dados_ocr else None,
                        }
                    dados_vision["servicos"] = page_servicos
                    servicos_vision = filter_summary_rows(page_servicos)
                    vision_stats = compute_servicos_stats(servicos_vision)
                    vision_score = compute_quality_score(vision_stats)
                    vision_reprocessed = True
                    ocr_score = compute_quality_score(ocr_stats)

        # Combinar resultados
        self._notify_progress(progress_callback, 0, 0, "merge", "Consolidando dados extraidos")
        self._check_cancel(cancel_check)

        if dados_vision and dados_ocr:
            primary_source = self._select_primary_source(vision_stats, ocr_stats, vision_score, ocr_score)
            if primary_source == "vision":
                primary = dados_vision
                secondary = dados_ocr
                primary_servicos = servicos_vision
                secondary_servicos = servicos_ocr
            else:
                primary = dados_ocr
                secondary = dados_vision
                primary_servicos = servicos_ocr
                secondary_servicos = servicos_vision

            dados = {
                "descricao_servico": primary.get("descricao_servico") or secondary.get("descricao_servico"),
                "contratante": primary.get("contratante") or secondary.get("contratante"),
                "data_emissao": primary.get("data_emissao") or secondary.get("data_emissao"),
                "quantidade": primary.get("quantidade") or secondary.get("quantidade"),
                "unidade": primary.get("unidade") or secondary.get("unidade"),
            }

            # Prefixar itens do aditivo em cada fonte ANTES do merge
            primary_servicos = prefix_aditivo_items(primary_servicos, texto)
            secondary_servicos = prefix_aditivo_items(secondary_servicos, texto)
            dados["servicos"] = merge_servicos_prefer_primary(primary_servicos, secondary_servicos)

        else:
            primary_source = "ocr" if dados_ocr else "vision"
            dados = dados_ocr or {
                "descricao_servico": None,
                "quantidade": None,
                "unidade": None,
                "contratante": None,
                "data_emissao": None,
                "servicos": []
            }
            if dados.get("servicos"):
                dados["servicos"] = prefix_aditivo_items(dados["servicos"], texto)

        # Se tabela foi usada com alta confiança, comparar com IA
        if table_used and not use_ai_for_services:
            servicos_table_filtered = [
                s for s in servicos_table
                if s.get("quantidade") is not None
            ]
            servicos_table_filtered = prefix_aditivo_items(servicos_table_filtered, texto)

            ai_servicos = dados.get("servicos") or []
            ai_servicos_count = len(ai_servicos) if isinstance(ai_servicos, list) else 0
            table_servicos_count = len(servicos_table_filtered)

            if table_servicos_count >= ai_servicos_count:
                dados["servicos"] = servicos_table_filtered
                primary_source = "table_services"
            else:
                primary_source = primary_source + "_ai_preferred"

        debug_info = {
            "vision": {"count": len(servicos_vision), "score": vision_score, "reprocessed": vision_reprocessed},
            "ocr": {"count": len(servicos_ocr), "score": ocr_score},
            "vision_stats": vision_stats,
            "ocr_stats": ocr_stats,
            "page_count": len(images),
            "use_ai_for_services": use_ai_for_services,
        }

        return dados, primary_source, debug_info

    def _postprocess_servicos(
        self,
        servicos: list,
        use_ai: bool,
        table_used: bool,
        servicos_table: list
    ) -> list:
        """
        Aplica pós-processamento nos serviços extraídos.

        Inclui: normalização, filtros, deduplicação, limpeza de códigos.

        Args:
            servicos: Lista de serviços brutos
            use_ai: Se IA foi usada
            table_used: Se tabela foi usada com alta confiança
            servicos_table: Serviços da tabela (para enriquecimento)

        Returns:
            Lista de serviços processados
        """
        servicos = filter_summary_rows(servicos)

        # Enriquecer com dados da tabela se IA foi usada
        if use_ai and not table_used:
            servicos = self._attach_item_codes_from_table(servicos, servicos_table)
            servicos = self._prefer_items_with_code(servicos)

        # Normalizar cada serviço
        for servico in servicos:
            desc = servico.get("descricao", "")
            existing_item = servico.get("item")
            item, clean_desc = self._split_item_description(desc)
            if not item and existing_item:
                item = existing_item
            if item:
                servico["item"] = item
                if clean_desc:
                    servico["descricao"] = clean_desc
            else:
                servico["item"] = None
            qty = parse_quantity(servico.get("quantidade"))
            if qty is not None:
                servico["quantidade"] = qty
            unit = servico.get("unidade")
            if isinstance(unit, str):
                servico["unidade"] = unit.strip()

        # Aplicar filtros
        servicos = filter_classification_paths(servicos)
        servicos = remove_duplicate_services(servicos)
        servicos = self._remove_duplicate_pairs(servicos)
        servicos = self._filter_items_without_quantity(servicos)
        servicos = self._filter_items_without_code(servicos)

        return servicos

    def _find_better_description(self, item: dict, candidates: list) -> str:
        target_desc = (item.get('descricao') or '').strip()
        target_unit = normalize_unit(item.get('unidade') or '')
        try:
            target_qty = float(item.get('quantidade') or 0)
        except (TypeError, ValueError):
            target_qty = 0
        target_kw = extract_keywords(target_desc)

        best_desc = None
        best_len = len(target_desc)

        for cand in candidates:
            cand_desc = (cand.get('descricao') or '').strip()
            if not cand_desc or len(cand_desc) <= best_len:
                continue
            cand_unit = normalize_unit(cand.get('unidade') or '')
            if target_unit and cand_unit and cand_unit != target_unit:
                continue
            try:
                cand_qty = float(cand.get('quantidade') or 0)
            except (TypeError, ValueError):
                cand_qty = 0
            if target_qty and cand_qty and abs(target_qty - cand_qty) > 0.01:
                continue
            cand_kw = extract_keywords(cand_desc)
            if target_kw and cand_kw and len(target_kw & cand_kw) == 0:
                if not cand_desc.upper().startswith(target_desc.upper()):
                    continue
            best_desc = cand_desc
            best_len = len(cand_desc)

        return best_desc or ''

    def _improve_short_descriptions(self, items: list, candidates: list) -> list:
        if not items or not candidates:
            return items
        for item in items:
            desc = item.get('descricao', '')
            if not self._is_short_description(desc):
                continue
            better = self._find_better_description(item, candidates)
            if better:
                item['descricao'] = better
        return items

    def _recover_descriptions_from_text(
        self,
        servicos: list,
        texto: str
    ) -> list:
        """
        Recupera descrições ausentes do texto OCR para itens com descrição curta.

        Alguns PDFs têm formato onde a descrição aparece na linha anterior
        ao código do item. Este método tenta recuperar essas descrições.

        Args:
            servicos: Lista de serviços
            texto: Texto OCR extraído

        Returns:
            Lista de serviços com descrições recuperadas
        """

        if not servicos or not texto:
            return servicos

        lines = texto.split('\n')
        line_map = {}

        # Criar mapa de linhas que começam com código de item
        for i, line in enumerate(lines):
            match = re.match(r'^(\d+\.\d+(?:\.\d+)?)\s+', line.strip())
            if match:
                item_code = match.group(1)
                line_map[item_code] = i

        # Para cada serviço com descrição curta, tentar recuperar
        for servico in servicos:
            desc = (servico.get("descricao") or "").strip()
            item_code = servico.get("item")

            # Só processar se descrição muito curta e tem código válido
            if len(desc) >= 10 or not item_code:
                continue

            line_idx = line_map.get(str(item_code))
            if line_idx is None or line_idx == 0:
                continue

            # Verificar linha anterior
            prev_line = lines[line_idx - 1].strip()

            # A linha anterior deve ser texto (não um código de item)
            if re.match(r'^\d+\.\d+', prev_line):
                continue

            # Ignorar linhas muito curtas ou que são apenas números
            if len(prev_line) < 15:
                continue
            if re.match(r'^[\d\s,\.]+$', prev_line):
                continue

            # Ignorar linhas de cabeçalho/rodapé comuns
            skip_patterns = [
                r'^p[áa]gina\s+\d',
                r'^\d+/\d+$',
                r'^af_\d+/\d+$',
            ]
            should_skip = False
            for pattern in skip_patterns:
                if re.match(pattern, prev_line, re.I):
                    should_skip = True
                    break
            if should_skip:
                continue

            # Recuperar descrição da linha anterior
            servico["descricao"] = prev_line
            servico["_desc_recovered"] = True
            logger.debug(f"Recuperada descrição para {item_code}: {prev_line[:50]}...")

        return servicos

    def process_atestado(
        self,
        file_path: str,
        use_vision: bool = True,
        progress_callback=None,
        cancel_check=None
    ) -> Dict[str, Any]:
        """
        Processa um atestado de capacidade técnica usando abordagem híbrida.

        Combina GPT-4o Vision (para precisão) com OCR+texto (para completude).

        Args:
            file_path: Caminho para o arquivo (PDF ou imagem)
            use_vision: Se True, usa abordagem híbrida Vision+OCR; se False, apenas OCR+texto

        Returns:
            Dicionário com dados extraídos do atestado
        """
        self._check_cancel(cancel_check)
        file_ext = Path(file_path).suffix.lower()

        # 1. Extrair texto do documento
        texto = self._extract_texto_from_file(
            file_path, file_ext, progress_callback, cancel_check
        )

        # 2. Extrair serviços de tabelas (múltiplos métodos)
        servicos_table, table_confidence, table_debug, table_attempts = \
            self._extract_servicos_from_all_tables(
                file_path, file_ext, progress_callback, cancel_check
            )

        # Determinar se tabela será usada
        table_threshold = APC.TABLE_CONFIDENCE_THRESHOLD
        table_min_items = APC.TABLE_MIN_ITEMS
        table_used = (
            servicos_table
            and table_confidence >= table_threshold
            and len(servicos_table) >= table_min_items
        )

        if isinstance(table_debug, dict):
            table_debug.setdefault("attempts", table_attempts)

        # 3. Extrair dados com IA (se configurada)
        use_ai = ai_provider.is_configured

        if use_ai:
            dados, primary_source, ai_debug_info = self._extract_dados_with_ai(
                file_path, file_ext, texto, use_vision,
                servicos_table, table_used,
                progress_callback, cancel_check
            )

            dados["_debug"] = {
                **ai_debug_info,
                "table": {
                    "count": len(servicos_table),
                    "confidence": table_confidence,
                    "used": table_used,
                    "debug": table_debug
                },
                "primary_source": primary_source,
                "provider_config": ai_provider.current_provider,
            }
        else:
            # IA não configurada - usar apenas tabela
            servicos_table_filtered = [
                s for s in servicos_table
                if s.get("quantidade") is not None
            ] if table_used else []
            servicos_table_filtered = prefix_aditivo_items(servicos_table_filtered, texto)

            dados = {
                "descricao_servico": None,
                "quantidade": None,
                "unidade": None,
                "contratante": None,
                "data_emissao": None,
                "servicos": servicos_table_filtered
            }
            dados["_debug"] = {
                "table": {
                    "count": len(servicos_table),
                    "confidence": table_confidence,
                    "used": table_used,
                    "debug": table_debug
                },
                "primary_source": "table" if table_used else "none",
                "ai_configured": False,
            }

        # 4. Pós-processamento dos serviços
        self._notify_progress(progress_callback, 0, 0, "final", "Finalizando processamento")
        self._check_cancel(cancel_check)

        # Recuperar descrições ausentes do texto OCR
        servicos_raw = dados.get("servicos") or []
        servicos_raw = self._recover_descriptions_from_text(servicos_raw, texto)

        servicos = self._postprocess_servicos(
            servicos_raw,
            use_ai,
            table_used,
            servicos_table
        )

        dados["servicos"] = servicos
        dados["texto_extraido"] = texto
        return dados

    def process_edital(self, file_path: str, progress_callback=None, cancel_check=None) -> Dict[str, Any]:
        """
        Processa uma página de edital com quantitativos mínimos.

        Args:
            file_path: Caminho para o arquivo PDF

        Returns:
            Dicionário com exigências extraídas
        """
        self._check_cancel(cancel_check)
        self._notify_progress(progress_callback, 0, 0, "texto", "Extraindo texto do edital")
        file_ext = Path(file_path).suffix.lower()
        texto = ""
        tabelas = []

        if file_ext != ".pdf":
            raise UnsupportedFileError("não-PDF", ["PDF"])

        # Extrair conteúdo do PDF
        resultado = pdf_extractor.extract_all(file_path)

        if resultado["tem_texto"]:
            texto = resultado["texto"]
            tabelas = resultado["tabelas"]
        else:
            # PDF escaneado - usar OCR
            try:
                images = pdf_extractor.pdf_to_images(file_path)
                texto = self._ocr_image_list(
                images,
                progress_callback=progress_callback,
                cancel_check=cancel_check
            )
            except (PDFError, OCRError, IOError) as e:
                raise OCRError(str(e))

        if not texto.strip():
            raise TextExtractionError("edital")

        # Combinar texto e tabelas para análise
        texto_completo = texto
        if tabelas:
            texto_completo += "\n\nTABELAS ENCONTRADAS:\n"
            for i, tabela in enumerate(tabelas):
                texto_completo += f"\nTabela {i + 1}:\n"
                for linha in tabela:
                    texto_completo += " | ".join(linha) + "\n"

        # Extrair exigencias com IA
        if ai_provider.is_configured:
            self._notify_progress(progress_callback, 0, 0, "ia", "Analisando exigencias")
            self._check_cancel(cancel_check)
            # Usar OpenAI diretamente para exigências (mais maduro)
            from .ai_analyzer import ai_analyzer
            if ai_analyzer.is_configured:
                exigencias = ai_analyzer.extract_edital_requirements(texto_completo)
            else:
                # Tentar com Gemini
                from .gemini_analyzer import gemini_analyzer
                exigencias = gemini_analyzer.extract_edital_requirements(texto_completo) if gemini_analyzer.is_configured else []
        else:
            exigencias = []

        self._notify_progress(progress_callback, 0, 0, "final", "Finalizando processamento")
        return {
            "texto_extraido": texto,
            "tabelas": tabelas,
            "exigencias": exigencias,
            "paginas": resultado.get("paginas", 1)
        }

    def analyze_qualification(
        self,
        exigencias: List[Dict[str, Any]],
        atestados: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Analisa a qualificação técnica comparando exigências e atestados.

        Args:
            exigencias: Lista de exigências do edital
            atestados: Lista de atestados do usuário

        Returns:
            Resultado da análise com status de atendimento
        """
        return ai_provider.match_atestados(exigencias, atestados)

    def get_status(self) -> Dict[str, Any]:
        """
        Retorna o status dos serviços de processamento.

        Returns:
            Dicionário com status de cada serviço
        """
        provider_status = ai_provider.get_status()
        return {
            "pdf_extractor": True,
            "ocr_service": True,
            "ai_provider": provider_status,
            "document_ai": {
                "available": document_ai_service.is_available,
                "configured": document_ai_service.is_configured,
                "enabled": APC.DOCUMENT_AI_ENABLED
            },
            "is_configured": ai_provider.is_configured,
            "mensagem": f"IA configurada ({', '.join(ai_provider.available_providers)})" if ai_provider.is_configured else "Configure OPENAI_API_KEY ou GOOGLE_API_KEY para análise inteligente"
        }


# Instância singleton para uso global
document_processor = DocumentProcessor()
