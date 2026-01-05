"""
Serviço integrado de processamento de documentos.
Combina extração de PDF, OCR e análise com IA.
Suporta GPT-4o Vision para análise direta de imagens.
Inclui processamento paralelo opcional para melhor performance.
"""

from typing import Dict, Any, List, Optional
from pathlib import Path
import io
import os
import pdfplumber
import fitz  # PyMuPDF
from PIL import Image
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

from .pdf_extractor import pdf_extractor
from .ocr_service import ocr_service
from .ai_provider import ai_provider
from .document_ai_service import document_ai_service

# Configurações de paralelização
OCR_PARALLEL_ENABLED = os.getenv("OCR_PARALLEL", "0").lower() in {"1", "true", "yes"}
OCR_MAX_WORKERS = int(os.getenv("OCR_MAX_WORKERS", "2"))  # Número de threads para OCR


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

    def _is_garbage_text(self, text: str) -> bool:
        """
        Verifica se o texto é lixo (marca d'água invertida, etc).

        Args:
            text: Texto a verificar

        Returns:
            True se o texto parecer ser lixo/marca d'água
        """
        if not text or len(text.strip()) < 50:
            return True

        # Verificar se tem palavras comuns em português
        palavras_comuns = ['de', 'do', 'da', 'em', 'para', 'que', 'com', 'os', 'as', 'um', 'uma',
                          'no', 'na', 'ao', 'pela', 'pelo', 'este', 'esta', 'esse', 'essa']
        text_lower = text.lower()
        palavras_encontradas = sum(1 for p in palavras_comuns if f' {p} ' in text_lower)

        # Se não encontrar pelo menos 5 palavras comuns, provavelmente é lixo
        if palavras_encontradas < 5:
            return True

        # Verificar proporção de caracteres válidos vs especiais/números
        letras = sum(1 for c in text if c.isalpha())
        total = len(text.replace(' ', '').replace('\n', ''))

        if total > 0 and letras / total < 0.5:  # Menos de 50% letras = lixo
            return True

        return False

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
                    needs_ocr = len(text_stripped) < MIN_TEXT_PER_PAGE or self._is_garbage_text(text_stripped)

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
                    except Exception as e:
                        print(f"Erro no OCR da página {page_idx+1}: {str(e)}")

                doc.close()

            return "\n\n".join(text_parts)

        except Exception as e:
            raise Exception(f"Erro ao processar PDF: {str(e)}")

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
        except Exception as e:
            return (page_index, f"--- Pagina {page_index + 1} ---\n[Erro no OCR: {str(e)}]")

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
            except Exception as e:
                all_texts.append(f"--- Pagina {i + 1} ---\n[Erro no OCR: {str(e)}]")

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

    def _normalize_description(self, desc: str) -> str:
        """
        Normaliza descrição para comparação.
        Remove acentos, espaços extras e converte para maiúsculas.
        """
        import unicodedata
        # Remover acentos
        nfkd = unicodedata.normalize('NFKD', desc)
        ascii_text = nfkd.encode('ASCII', 'ignore').decode('ASCII')
        # Remover espaços extras e converter para maiúsculas
        return ' '.join(ascii_text.upper().split())

    def _normalize_unit(self, unit: str) -> str:
        """
        Normaliza unidade para compara‡Æo.
        Converte expoentes e padroniza caixa.
        """
        if not unit:
            return ""
        normalized = unit.strip().upper()
        normalized = normalized.translate({ord("\u00b2"): '2', ord("\u00b3"): '3'})
        normalized = normalized.replace("M^2", "M2").replace("M^3", "M3")
        normalized = normalized.replace("M\u00b2", "M2").replace("M\u00b3", "M3")
        normalized = normalized.replace(" ", "")
        return normalized

    def _extract_keywords(self, desc: str) -> set:
        """
        Extrai palavras-chave significativas da descrição.
        """
        normalized = self._normalize_description(desc)
        # Palavras a ignorar
        stopwords = {'DE', 'DO', 'DA', 'EM', 'PARA', 'COM', 'E', 'A', 'O', 'AS', 'OS',
                     'UN', 'M2', 'M3', 'ML', 'M', 'VB', 'KG', 'INCLUSIVE', 'INCLUSIV',
                     'TIPO', 'MODELO', 'TRACO'}
        words = set(normalized.split())
        return words - stopwords

    def _description_similarity(self, left: str, right: str) -> float:
        left_kw = self._extract_keywords(left)
        right_kw = self._extract_keywords(right)
        if not left_kw or not right_kw:
            return 0.0
        intersection = len(left_kw & right_kw)
        return intersection / max(len(left_kw), len(right_kw))

    def _unit_tokens(self) -> set:
        return {
            "M", "M2", "M3", "M3XKM", "M2XKM", "UN", "UND", "VB", "KG", "TON", "T", "KM", "L", "MODULOS"
        }

    def _normalize_header(self, value: str) -> str:
        return self._normalize_description(value or "")

    def _parse_item_tuple(self, value: str) -> Optional[tuple]:
        if value is None:
            return None
        text = str(value).strip()
        if not text:
            return None
        import re
        cleaned = re.sub(r"[^0-9. ]", "", text)
        cleaned = cleaned.strip().strip(".")
        if not cleaned:
            return None
        parts = [p for p in re.split(r"[ .]+", cleaned) if p]
        if not parts or len(parts) > 4:
            return None
        if any(len(p) > 3 for p in parts):
            return None
        try:
            return tuple(int(p) for p in parts)
        except ValueError:
            return None

    def _item_tuple_to_str(self, value: tuple) -> str:
        return ".".join(str(v) for v in value)

    def _score_item_column(self, cells: list, col_index: int, total_cols: int) -> dict:
        non_empty = 0
        matches = 0
        tuples = []
        lengths = []
        for cell in cells:
            text = str(cell or "").strip()
            if not text:
                continue
            non_empty += 1
            item_tuple = self._parse_item_tuple(text)
            if item_tuple:
                matches += 1
                tuples.append(item_tuple)
                lengths.append(len(text))
        if non_empty == 0:
            return {"score": 0.0, "pattern_ratio": 0.0, "seq_ratio": 0.0, "unique_ratio": 0.0}
        pattern_ratio = matches / non_empty
        unique_ratio = (len(set(tuples)) / matches) if matches else 0.0
        ordered = 0
        total_pairs = 0
        prev = None
        for item_tuple in tuples:
            if prev is not None:
                total_pairs += 1
                if item_tuple >= prev:
                    ordered += 1
            prev = item_tuple
        seq_ratio = (ordered / total_pairs) if total_pairs else 0.0
        avg_len = (sum(lengths) / len(lengths)) if lengths else 99
        if avg_len <= 6:
            length_bonus = 1.0
        elif avg_len <= 10:
            length_bonus = 0.5
        else:
            length_bonus = 0.0
        left_bias = 1.0 - (col_index / max(1, total_cols - 1))
        score = (
            0.45 * pattern_ratio +
            0.2 * seq_ratio +
            0.2 * unique_ratio +
            0.1 * left_bias +
            0.05 * length_bonus
        )
        return {
            "score": round(score, 3),
            "pattern_ratio": round(pattern_ratio, 3),
            "seq_ratio": round(seq_ratio, 3),
            "unique_ratio": round(unique_ratio, 3)
        }

    def _detect_header_row(self, rows: list) -> Optional[int]:
        if not rows:
            return None
        header_keywords = {
            "ITEM", "ITENS", "COD", "CODIGO", "DESCRICAO", "DISCRIMINACAO",
            "SERVICO", "SERVICOS", "UNID", "UNIDADE", "QTD", "QTE", "QUANT", "QUANTIDADE",
            "EXECUTADA", "EXECUTADO", "VALOR", "CUSTO", "PRECO"
        }
        best_score = 0
        best_index = None
        for idx, row in enumerate(rows[:5]):
            score = 0
            for cell in row:
                text = self._normalize_header(cell)
                if not text:
                    continue
                for kw in header_keywords:
                    if kw in text:
                        score += 1
                        break
            if score > best_score:
                best_score = score
                best_index = idx
        if best_score >= 2:
            return best_index
        return None

    def _guess_columns_by_header(self, header_row: list) -> dict:
        mapping: dict = {"item": None, "descricao": None, "unidade": None, "quantidade": None, "valor": None}
        for idx, cell in enumerate(header_row):
            text = self._normalize_header(cell)
            if not text:
                continue
            if mapping["item"] is None and ("ITEM" in text or "COD" in text):
                mapping["item"] = idx
            if mapping["descricao"] is None and ("DESCRICAO" in text or "DISCRIMINACAO" in text or "SERVICO" in text):
                mapping["descricao"] = idx
            if mapping["unidade"] is None and ("UNID" in text or "UNIDADE" in text):
                mapping["unidade"] = idx
            if mapping["quantidade"] is None and ("QUANT" in text or "QTD" in text or "QTE" in text or "EXECUTAD" in text):
                mapping["quantidade"] = idx
            if mapping["valor"] is None and ("VALOR" in text or "CUSTO" in text or "PRECO" in text):
                mapping["valor"] = idx
        return mapping

    def _compute_column_stats(self, rows: list, total_cols: int) -> list:
        unit_tokens = {
            "M", "M2", "M3", "M3XKM", "M2XKM", "UN", "UND", "VB", "KG", "TON", "T", "KM", "L", "MODULOS"
        }
        col_stats = []
        for col in range(total_cols):
            non_empty = 0
            numeric = 0
            unit_hits = 0
            text_len = 0
            for row in rows:
                if col >= len(row):
                    continue
                cell = str(row[col] or "").strip()
                if not cell:
                    continue
                non_empty += 1
                if self._parse_quantity(cell) is not None:
                    numeric += 1
                unit_norm = self._normalize_unit(cell)
                unit_norm = self._normalize_description(unit_norm).replace(" ", "")
                if unit_norm in unit_tokens:
                    unit_hits += 1
                text_len += len(cell)
            if non_empty == 0:
                col_stats.append({"non_empty": 0, "numeric_ratio": 0.0, "unit_ratio": 0.0, "avg_len": 0.0})
                continue
            col_stats.append({
                "non_empty": non_empty,
                "numeric_ratio": numeric / non_empty,
                "unit_ratio": unit_hits / non_empty,
                "avg_len": text_len / non_empty
            })
        return col_stats

    def _guess_columns_by_content(self, rows: list, total_cols: int, mapping: dict, col_stats: Optional[list] = None) -> dict:
        if col_stats is None:
            col_stats = self._compute_column_stats(rows, total_cols)

        if mapping.get("descricao") is None:
            best_col = None
            best_len = 0
            for col, stats in enumerate(col_stats):
                if col in (mapping.get("item"), mapping.get("unidade"), mapping.get("quantidade"), mapping.get("valor")):
                    continue
                if stats["avg_len"] > best_len and stats["numeric_ratio"] < 0.7:
                    best_len = stats["avg_len"]
                    best_col = col
            mapping["descricao"] = best_col

        if mapping.get("unidade") is None:
            best_col = None
            best_ratio = 0
            for col, stats in enumerate(col_stats):
                if col in (mapping.get("item"), mapping.get("descricao"), mapping.get("quantidade"), mapping.get("valor")):
                    continue
                if stats["unit_ratio"] > best_ratio:
                    best_ratio = stats["unit_ratio"]
                    best_col = col
            mapping["unidade"] = best_col

        if mapping.get("quantidade") is None:
            best_col = None
            best_ratio = 0
            for col, stats in enumerate(col_stats):
                if col in (mapping.get("item"), mapping.get("descricao"), mapping.get("unidade"), mapping.get("valor")):
                    continue
                if stats["numeric_ratio"] > best_ratio:
                    best_ratio = stats["numeric_ratio"]
                    best_col = col
            mapping["quantidade"] = best_col

        return mapping

    def _validate_column_mapping(self, mapping: dict, col_stats: list) -> dict:
        if not col_stats:
            return mapping

        def ratio(idx: Optional[int], key: str) -> float:
            if idx is None or idx >= len(col_stats):
                return 0.0
            return float(col_stats[idx].get(key, 0.0))

        def avg_len(idx: Optional[int]) -> float:
            if idx is None or idx >= len(col_stats):
                return 0.0
            return float(col_stats[idx].get("avg_len", 0.0))

        min_unit_ratio = 0.2
        min_qty_ratio = 0.35
        min_desc_len = 10.0
        max_desc_numeric = 0.6

        item_col = mapping.get("item")
        desc_col = mapping.get("descricao")
        unit_col = mapping.get("unidade")
        qty_col = mapping.get("quantidade")

        if desc_col in {item_col, unit_col, qty_col}:
            mapping["descricao"] = None

        if unit_col in {item_col, desc_col, qty_col}:
            mapping["unidade"] = None

        if qty_col in {item_col, desc_col, unit_col}:
            mapping["quantidade"] = None

        if unit_col is not None and ratio(unit_col, "unit_ratio") < min_unit_ratio:
            mapping["unidade"] = None

        if qty_col is not None and ratio(qty_col, "numeric_ratio") < min_qty_ratio:
            mapping["quantidade"] = None

        if desc_col is not None:
            if avg_len(desc_col) < min_desc_len or ratio(desc_col, "numeric_ratio") > max_desc_numeric:
                mapping["descricao"] = None

        unit_col = mapping.get("unidade")
        qty_col = mapping.get("quantidade")
        if unit_col is not None and qty_col is not None and qty_col < unit_col:
            best_col = None
            best_ratio = 0.0
            for col in range(unit_col + 1, len(col_stats)):
                if col in {mapping.get("item"), mapping.get("descricao")}:
                    continue
                col_ratio = ratio(col, "numeric_ratio")
                if col_ratio >= min_qty_ratio and col_ratio > best_ratio:
                    best_ratio = col_ratio
                    best_col = col
            if best_col is not None:
                mapping["quantidade"] = best_col

        return mapping

    def _filter_classification_paths(self, servicos: list) -> list:
        """
        Remove serviços que são caminhos de classificação (não serviços reais).

        Isso inclui itens que contêm ">" (caminho de classificação) ou
        começam com padrões de classificação de CAT.
        """
        if not servicos:
            return []

        filtered = []
        for servico in servicos:
            descricao = servico.get("descricao", "") or ""

            if not descricao.strip():
                continue

            # Ignorar itens que contêm ">" (caminho de classificação)
            if ">" in descricao:
                continue

            # Ignorar itens que começam com padrão de classificação
            desc_upper = descricao.upper().strip()
            invalid_prefixes = [
                "EXECUÇÃO", "DIRETA OBRAS", "1 - DIRETA",
                "2 - DIRETA", "ATIVIDADE TÉCNICA", "CLASSIFICAÇÃO",
            ]

            is_invalid = False
            for prefix in invalid_prefixes:
                if desc_upper.startswith(prefix):
                    is_invalid = True
                    break

            if is_invalid:
                continue

            # Ignorar itens muito curtos (provavelmente ruído)
            if len(descricao.strip()) < 5:
                continue

            filtered.append(servico)

        return filtered

    def _remove_duplicate_services(self, servicos: list) -> list:
        """
        Remove serviços duplicados baseado em item + descrição + quantidade + unidade.

        Mantém apenas a primeira ocorrência de cada serviço único.
        """
        if not servicos:
            return []

        seen = set()
        unique = []

        for servico in servicos:
            # Criar chave única baseada nos campos principais
            item = str(servico.get("item", "") or "").strip().upper()
            desc = str(servico.get("descricao", "") or "").strip().upper()[:50]
            qtd = servico.get("quantidade", 0)
            un = str(servico.get("unidade", "") or "").strip().upper()

            # Normalizar quantidade para comparação
            try:
                qtd_norm = round(float(qtd), 2) if qtd else 0
            except (ValueError, TypeError):
                qtd_norm = 0

            key = (item, desc, qtd_norm, un)

            if key not in seen:
                seen.add(key)
                unique.append(servico)

        return unique

    def _filter_servicos_by_item_length(self, servicos: list) -> tuple[list, dict]:
        if not servicos:
            return servicos, {"applied": False, "ratio": 0.0}

        lengths = []
        for servico in servicos:
            item_tuple = self._parse_item_tuple(servico.get("item"))
            if item_tuple:
                lengths.append(len(item_tuple))

        if not lengths:
            return servicos, {"applied": False, "ratio": 0.0}

        from collections import Counter
        counts = Counter(lengths)
        dominant_len, dominant_count = max(counts.items(), key=lambda kv: kv[1])
        ratio = dominant_count / max(1, len(lengths))
        try:
            min_ratio = float(os.getenv("ATTESTADO_ITEM_LEN_RATIO", "0.6"))
        except ValueError:
            min_ratio = 0.6

        info = {
            "dominant_len": dominant_len,
            "ratio": round(ratio, 3),
            "applied": False,
            "filtered_out": 0,
            "kept_mismatch": 0
        }
        if ratio < min_ratio or dominant_len < 2:
            return servicos, info

        try:
            min_desc_len = int(os.getenv("ATTESTADO_ITEM_LEN_KEEP_MIN_DESC", "20"))
        except ValueError:
            min_desc_len = 20

        filtered = []
        for servico in servicos:
            item_tuple = self._parse_item_tuple(servico.get("item"))
            if not item_tuple or len(item_tuple) == dominant_len:
                filtered.append(servico)
                continue
            qty = self._parse_quantity(servico.get("quantidade"))
            unit = self._normalize_unit(servico.get("unidade") or "")
            desc = (servico.get("descricao") or "").strip()
            if qty not in (None, 0) and unit and len(desc) >= min_desc_len:
                filtered.append(servico)
                info["kept_mismatch"] += 1

        info["applied"] = True
        info["filtered_out"] = len(servicos) - len(filtered)
        return filtered, info

    def _filter_servicos_by_item_prefix(self, servicos: list) -> tuple[list, dict]:
        if not servicos:
            return servicos, {"applied": False, "ratio": 0.0}

        prefixes = []
        for servico in servicos:
            item_tuple = self._parse_item_tuple(servico.get("item"))
            if item_tuple:
                prefixes.append(item_tuple[0])

        if not prefixes:
            return servicos, {"applied": False, "ratio": 0.0}

        from collections import Counter
        counts = Counter(prefixes)
        dominant_prefix, dominant_count = max(counts.items(), key=lambda kv: kv[1])
        ratio = dominant_count / max(1, len(prefixes))
        try:
            min_ratio = float(os.getenv("ATTESTADO_ITEM_PREFIX_RATIO", "0.7"))
        except ValueError:
            min_ratio = 0.7

        info = {
            "dominant_prefix": dominant_prefix,
            "ratio": round(ratio, 3),
            "applied": False,
            "filtered_out": 0
        }
        if ratio < min_ratio:
            return servicos, info

        filtered = []
        for servico in servicos:
            item_tuple = self._parse_item_tuple(servico.get("item"))
            if not item_tuple or item_tuple[0] == dominant_prefix:
                filtered.append(servico)

        info["applied"] = True
        info["filtered_out"] = len(servicos) - len(filtered)
        return filtered, info

    def _dominant_item_length(self, servicos: list) -> tuple[Optional[int], float]:
        lengths = []
        for servico in servicos:
            item_tuple = self._parse_item_tuple(servico.get("item"))
            if item_tuple:
                lengths.append(len(item_tuple))
        if not lengths:
            return None, 0.0
        from collections import Counter
        counts = Counter(lengths)
        dominant_len, dominant_count = max(counts.items(), key=lambda kv: kv[1])
        ratio = dominant_count / max(1, len(lengths))
        return dominant_len, ratio

    def _repair_missing_prefix(self, servicos: list, dominant_prefix: Optional[int]) -> tuple[list, dict]:
        if not servicos or dominant_prefix is None:
            return servicos, {"applied": False, "repaired": 0}

        existing = {s.get("item") for s in servicos if s.get("item")}
        repaired = 0
        for servico in servicos:
            item_tuple = self._parse_item_tuple(servico.get("item"))
            if not item_tuple or len(item_tuple) != 2:
                continue
            new_item = f"{dominant_prefix}.{self._item_tuple_to_str(item_tuple)}"
            if new_item in existing:
                continue
            servico["item"] = new_item
            existing.add(new_item)
            repaired += 1

        return servicos, {"applied": repaired > 0, "repaired": repaired}

    def _build_description_from_cells(self, cells: list, exclude_cols: set) -> str:
        parts = []
        for idx, cell in enumerate(cells):
            if idx in exclude_cols:
                continue
            text = str(cell or "").strip()
            if text:
                parts.append(text)
        return " ".join(parts).strip()

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

        header_index = self._detect_header_row(normalized_rows)
        header_map = {"item": None, "descricao": None, "unidade": None, "quantidade": None, "valor": None}
        data_rows = normalized_rows
        if header_index is not None:
            header_map = self._guess_columns_by_header(normalized_rows[header_index])
            data_rows = normalized_rows[header_index + 1:]

        item_col = header_map.get("item")
        item_score_data = {"score": 0.0}
        preferred_score_data = None
        preferred_used = False
        if item_col is None and preferred_item_col is not None and preferred_item_col < max_cols:
            col_cells = [row[preferred_item_col] for row in data_rows if preferred_item_col < len(row)]
            preferred_score_data = self._score_item_column(col_cells, preferred_item_col, max_cols)
            try:
                min_preferred_score = float(os.getenv("ATTESTADO_ITEM_COL_MIN_SCORE", "0.5"))
            except ValueError:
                min_preferred_score = 0.5
            if preferred_score_data["score"] >= min_preferred_score:
                item_col = preferred_item_col
                item_score_data = preferred_score_data
                preferred_used = True

        if item_col is None:
            best_score = 0.0
            best_col = None
            for col in range(max_cols):
                col_cells = [row[col] for row in data_rows if col < len(row)]
                score_data = self._score_item_column(col_cells, col, max_cols)
                if score_data["score"] > best_score:
                    best_score = score_data["score"]
                    best_col = col
                    item_score_data = score_data
            item_col = best_col
        else:
            col_cells = [row[item_col] for row in data_rows if item_col < len(row)]
            item_score_data = self._score_item_column(col_cells, item_col, max_cols)

        col_stats = self._compute_column_stats(data_rows, max_cols)
        header_map = self._guess_columns_by_content(data_rows, max_cols, header_map, col_stats)
        header_map = self._validate_column_mapping(header_map, col_stats)
        header_map = self._guess_columns_by_content(data_rows, max_cols, header_map, col_stats)
        desc_col = header_map.get("descricao")
        unit_col = header_map.get("unidade")
        qty_col = header_map.get("quantidade")

        servicos = []
        last_item = None
        item_tuples = []
        for row in data_rows:
            cells = [str(cell or "").strip() for cell in row]
            item_val = cells[item_col] if item_col is not None and item_col < len(cells) else ""
            item_tuple = self._parse_item_tuple(item_val)
            item_col_effective = item_col
            if item_tuple is None:
                for idx, cell in enumerate(cells):
                    if idx == desc_col:
                        continue
                    candidate = self._parse_item_tuple(cell)
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
                desc_val = self._build_description_from_cells(cells, exclude_cols)

            if unit_val:
                unit_val = self._normalize_unit(unit_val).strip()

            if item_tuple:
                item_tuples.append(item_tuple)
                item_str = self._item_tuple_to_str(item_tuple)
                servico = {
                    "item": item_str,
                    "descricao": desc_val.strip(),
                    "unidade": unit_val.strip(),
                    "quantidade": self._parse_quantity(qty_val)
                }
                servicos.append(servico)
                last_item = servico
            else:
                if last_item:
                    if desc_val:
                        last_item["descricao"] = (str(last_item.get("descricao") or "") + " " + str(desc_val)).strip()
                    if not last_item.get("unidade") and unit_val:
                        last_item["unidade"] = unit_val.strip()
                    if (last_item.get("quantidade") in (None, 0)) and self._parse_quantity(qty_val) not in (None, 0):
                        last_item["quantidade"] = self._parse_quantity(qty_val)

        servicos = [s for s in servicos if s.get("descricao")]
        servicos, prefix_info = self._filter_servicos_by_item_prefix(servicos)
        dominant_len, dominant_len_ratio = self._dominant_item_length(servicos)
        repair_info = {"applied": False, "repaired": 0}
        if dominant_len == 3 and prefix_info.get("dominant_prefix") is not None:
            servicos, repair_info = self._repair_missing_prefix(servicos, prefix_info.get("dominant_prefix"))
        servicos, dominant_info = self._filter_servicos_by_item_length(servicos)
        stats = self._compute_servicos_stats(servicos)
        seq_ratio = 0.0
        filtered_tuples = []
        for servico in servicos:
            item_tuple = self._parse_item_tuple(servico.get("item"))
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
        except Exception as exc:
            return [], 0.0, {"error": str(exc)}
        if not tables:
            return [], 0.0, {"tables": 0}
        best = {"servicos": [], "confidence": 0.0, "debug": {}}
        for table in tables:
            servicos, confidence, debug = self._extract_servicos_from_table(table)
            if confidence > best["confidence"] or (confidence == best["confidence"] and len(servicos) > len(best["servicos"])):
                best = {"servicos": servicos, "confidence": confidence, "debug": debug}
        best["debug"]["tables"] = len(tables)
        return best["servicos"], best["confidence"], best["debug"]

    def _extract_servicos_from_document_ai(self, file_path: str) -> tuple[list, float, dict]:
        if not document_ai_service.is_configured:
            return [], 0.0, {"enabled": False, "error": "not_configured"}
        try:
            result = document_ai_service.extract_tables(file_path)
        except Exception as exc:
            return [], 0.0, {"error": str(exc)}

        tables = result.get("tables") or []
        if not tables:
            return [], 0.0, {"tables": 0, "pages": result.get("pages", 0)}

        best = {"servicos": [], "confidence": 0.0, "debug": {}}
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
        clusters = []
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

        try:
            min_ratio = float(os.getenv("ATTESTADO_ITEM_COL_RATIO", "0.35"))
        except ValueError:
            min_ratio = 0.35
        try:
            max_x_ratio = float(os.getenv("ATTESTADO_ITEM_COL_MAX_X_RATIO", "0.35"))
        except ValueError:
            max_x_ratio = 0.35
        try:
            max_index = int(os.getenv("ATTESTADO_ITEM_COL_MAX_INDEX", "2"))
        except ValueError:
            max_index = 2
        try:
            min_count = int(os.getenv("ATTESTADO_ITEM_COL_MIN_COUNT", "6"))
        except ValueError:
            min_count = 6

        min_x = min(w["x0"] for w in words)
        max_x = max(w["x1"] for w in words)
        span = max(1.0, max_x - min_x)

        counts = [0] * len(col_centers)
        total_candidates = 0
        for word in words:
            item_tuple = self._parse_item_tuple(word.get("text"))
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
        try:
            min_conf = float(os.getenv("ATTESTADO_OCR_LAYOUT_CONFIDENCE", "0.3"))
            dpi = int(os.getenv("ATTESTADO_OCR_LAYOUT_DPI", "300"))
            page_min_items = int(os.getenv("ATTESTADO_OCR_LAYOUT_PAGE_MIN_ITEMS", "3"))
        except ValueError:
            min_conf = 0.3
            dpi = 300
            page_min_items = 3

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
            except Exception as exc:
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
            try:
                min_dom_len = int(os.getenv("ATTESTADO_OCR_PAGE_MIN_DOMINANT_LEN", "2"))
            except ValueError:
                min_dom_len = 2
            try:
                min_item_ratio = float(os.getenv("ATTESTADO_OCR_PAGE_MIN_ITEM_RATIO", "0.6"))
            except ValueError:
                min_item_ratio = 0.6
            try:
                min_unit_ratio = float(os.getenv("ATTESTADO_OCR_PAGE_MIN_UNIT_RATIO", "0.2"))
            except ValueError:
                min_unit_ratio = 0.2
            try:
                fallback_unit_ratio = float(os.getenv("ATTESTADO_OCR_PAGE_FALLBACK_UNIT_RATIO", "0.4"))
            except ValueError:
                fallback_unit_ratio = 0.4
            try:
                fallback_item_ratio = float(os.getenv("ATTESTADO_OCR_PAGE_FALLBACK_ITEM_RATIO", "0.8"))
            except ValueError:
                fallback_item_ratio = 0.8
            try:
                fallback_min_items = int(os.getenv("ATTESTADO_OCR_PAGE_MIN_ITEMS", "5"))
            except ValueError:
                fallback_min_items = 5

            primary_accept = (
                total_page_items > 0
                and dominant_len >= min_dom_len
                and item_ratio >= min_item_ratio
                and unit_ratio >= min_unit_ratio
            )
            fallback_accept = (
                total_page_items >= fallback_min_items
                and dominant_len == 1
                and item_ratio >= fallback_item_ratio
                and unit_ratio >= fallback_unit_ratio
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

    def _parse_quantity(self, value) -> Optional[float]:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        text = str(value).strip()
        if not text:
            return None
        text = text.replace(" ", "")
        # Formato brasileiro: 1.234,56
        if "," in text and "." in text:
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", ".")
        import re
        text = re.sub(r"[^0-9.\-]", "", text)
        if not text:
            return None
        try:
            return float(text)
        except ValueError:
            return None

    def _is_summary_row(self, desc: str) -> bool:
        if not desc:
            return False
        normalized = self._normalize_description(desc)
        if not normalized:
            return False
        if normalized.startswith("TOTAL") or "TOTAL DA" in normalized or "TOTAL DO" in normalized:
            return True
        if normalized.startswith("SUBTOTAL"):
            return True
        if normalized.startswith("RESUMO"):
            return True
        if normalized.startswith("#"):
            return True
        if normalized in {"ITEM", "DISCRIMINACAO", "DISCRIMINACAO DOS SERVICOS EXECUTADOS"}:
            return True
        return False

    def _filter_summary_rows(self, servicos: list) -> list:
        if not servicos:
            return servicos
        return [s for s in servicos if not self._is_summary_row(s.get("descricao", ""))]

    def _quantities_similar(self, qty_a: Optional[float], qty_b: Optional[float]) -> bool:
        if qty_a is None or qty_b is None:
            return True
        if qty_a == 0 or qty_b == 0:
            return False
        diff = abs(qty_a - qty_b)
        if diff <= 1.0:
            return True
        base = max(abs(qty_a), abs(qty_b))
        if base > 0 and diff / base <= 0.2:
            return True
        return False

    def _descriptions_similar(self, desc_a: str, desc_b: str) -> bool:
        if not desc_a or not desc_b:
            return False
        norm_a = self._normalize_description(desc_a)
        norm_b = self._normalize_description(desc_b)
        if norm_a == norm_b:
            return True
        if norm_a in norm_b or norm_b in norm_a:
            return True
        kw_a = self._extract_keywords(desc_a)
        kw_b = self._extract_keywords(desc_b)
        if not kw_a or not kw_b:
            return False
        common = len(kw_a & kw_b)
        min_len = min(len(kw_a), len(kw_b))
        return common >= max(1, min_len // 2)

    def _items_similar(self, item_a: dict, item_b: dict) -> bool:
        desc_a = (item_a.get("descricao") or "").strip()
        desc_b = (item_b.get("descricao") or "").strip()
        if not self._descriptions_similar(desc_a, desc_b):
            return False
        unit_a = self._normalize_unit(item_a.get("unidade") or "")
        unit_b = self._normalize_unit(item_b.get("unidade") or "")
        if unit_a and unit_b and unit_a != unit_b:
            return False
        qty_a = self._parse_quantity(item_a.get("quantidade"))
        qty_b = self._parse_quantity(item_b.get("quantidade"))
        return self._quantities_similar(qty_a, qty_b)

    def _compute_servicos_stats(self, servicos: list) -> dict:
        total = len(servicos)
        if total == 0:
            return {"total": 0, "with_item": 0, "with_unit": 0, "with_qty": 0, "duplicate_ratio": 0.0}
        with_item = sum(1 for s in servicos if s.get("item"))
        with_unit = sum(1 for s in servicos if s.get("unidade"))
        with_qty = sum(1 for s in servicos if self._parse_quantity(s.get("quantidade")) not in (None, 0))
        normalized_desc = [self._normalize_description(s.get("descricao", "")) for s in servicos]
        from collections import Counter
        counts = Counter(d for d in normalized_desc if d)
        duplicates = sum(v - 1 for v in counts.values() if v > 1)
        duplicate_ratio = duplicates / max(1, total)
        return {
            "total": total,
            "with_item": with_item,
            "with_unit": with_unit,
            "with_qty": with_qty,
            "duplicate_ratio": round(duplicate_ratio, 4)
        }

    def _compute_description_quality(self, servicos: list) -> dict:
        total = len(servicos)
        if total == 0:
            return {"avg_len": 0.0, "short_ratio": 0.0, "alpha_ratio": 0.0}

        try:
            short_len = int(os.getenv("ATTESTADO_OCR_NOISE_SHORT_DESC_LEN", "12"))
        except ValueError:
            short_len = 12

        lengths = []
        short_count = 0
        alpha_ratios = []

        for servico in servicos:
            desc = (servico.get("descricao") or "").strip()
            if not desc:
                short_count += 1
                continue
            length = len(desc)
            lengths.append(length)
            if length < short_len:
                short_count += 1
            letters = sum(1 for ch in desc if ch.isalpha())
            alnum = sum(1 for ch in desc if ch.isalnum())
            if alnum:
                alpha_ratios.append(letters / alnum)

        avg_len = sum(lengths) / len(lengths) if lengths else 0.0
        short_ratio = short_count / max(1, total)
        alpha_ratio = sum(alpha_ratios) / len(alpha_ratios) if alpha_ratios else 0.0
        return {
            "avg_len": round(avg_len, 2),
            "short_ratio": round(short_ratio, 3),
            "alpha_ratio": round(alpha_ratio, 3)
        }

    def _is_ocr_noisy(self, servicos: list) -> tuple[bool, dict]:
        stats = self._compute_servicos_stats(servicos)
        quality = self._compute_description_quality(servicos)
        total = max(1, stats.get("total", 0))
        unit_ratio = stats.get("with_unit", 0) / total
        qty_ratio = stats.get("with_qty", 0) / total

        try:
            min_unit_ratio = float(os.getenv("ATTESTADO_OCR_NOISE_MIN_UNIT_RATIO", "0.5"))
        except ValueError:
            min_unit_ratio = 0.5
        try:
            min_qty_ratio = float(os.getenv("ATTESTADO_OCR_NOISE_MIN_QTY_RATIO", "0.35"))
        except ValueError:
            min_qty_ratio = 0.35
        try:
            min_avg_len = float(os.getenv("ATTESTADO_OCR_NOISE_MIN_AVG_DESC_LEN", "14"))
        except ValueError:
            min_avg_len = 14.0
        try:
            max_short_ratio = float(os.getenv("ATTESTADO_OCR_NOISE_MAX_SHORT_DESC_RATIO", "0.45"))
        except ValueError:
            max_short_ratio = 0.45
        try:
            min_alpha_ratio = float(os.getenv("ATTESTADO_OCR_NOISE_MIN_ALPHA_RATIO", "0.45"))
        except ValueError:
            min_alpha_ratio = 0.45
        try:
            min_failures = int(os.getenv("ATTESTADO_OCR_NOISE_MIN_FAILS", "2"))
        except ValueError:
            min_failures = 2

        failures = 0
        reasons = {}
        if unit_ratio < min_unit_ratio:
            failures += 1
            reasons["unit_ratio"] = round(unit_ratio, 3)
        if qty_ratio < min_qty_ratio:
            failures += 1
            reasons["qty_ratio"] = round(qty_ratio, 3)
        if quality["avg_len"] < min_avg_len:
            failures += 1
            reasons["avg_desc_len"] = quality["avg_len"]
        if quality["short_ratio"] > max_short_ratio:
            failures += 1
            reasons["short_desc_ratio"] = quality["short_ratio"]
        if quality["alpha_ratio"] < min_alpha_ratio:
            failures += 1
            reasons["alpha_ratio"] = quality["alpha_ratio"]

        noisy = failures >= min_failures
        debug = {
            "noisy": noisy,
            "failures": failures,
            "min_failures": min_failures,
            "unit_ratio": round(unit_ratio, 3),
            "qty_ratio": round(qty_ratio, 3),
            "quality": quality,
            "thresholds": {
                "min_unit_ratio": min_unit_ratio,
                "min_qty_ratio": min_qty_ratio,
                "min_avg_desc_len": min_avg_len,
                "max_short_desc_ratio": max_short_ratio,
                "min_alpha_ratio": min_alpha_ratio
            },
            "reasons": reasons
        }
        return noisy, debug

    def _compute_quality_score(self, stats: dict) -> float:
        total = stats.get("total", 0)
        if total == 0:
            return 0.0
        score = 1.0
        with_unit_ratio = stats.get("with_unit", 0) / total
        with_qty_ratio = stats.get("with_qty", 0) / total
        with_item_ratio = stats.get("with_item", 0) / total
        if with_unit_ratio < 0.8:
            score -= 0.2
        if with_qty_ratio < 0.8:
            score -= 0.2
        if with_item_ratio < 0.4:
            score -= 0.2
        if stats.get("duplicate_ratio", 0) > 0.35:
            score -= 0.1
        min_items = int(os.getenv("ATTESTADO_MIN_ITEMS_FOR_CONFIDENCE", "25"))
        if total < min_items:
            score -= 0.2
        return max(0.0, min(1.0, round(score, 2)))

    def _servico_key(self, servico: dict):
        desc = (servico.get("descricao") or "").strip()
        raw_item = servico.get("item") or ""
        item_code = self._extract_item_code(str(raw_item)) or self._extract_item_code(desc)
        if item_code:
            return ("item", item_code)
        desc_norm = self._normalize_description(desc) if desc else ""
        unit_norm = self._normalize_unit(servico.get("unidade") or "")
        if desc_norm:
            return ("desc", desc_norm, unit_norm)
        return None

    def _merge_servicos_prefer_primary(self, primary: list, secondary: list) -> list:
        primary = self._filter_summary_rows(primary or [])
        secondary = self._filter_summary_rows(secondary or [])
        merged = []
        index_by_key = {}

        def add_or_update(item: dict):
            key = self._servico_key(item)
            if key is None:
                merged.append(item)
                return
            if key not in index_by_key:
                index_by_key[key] = len(merged)
                merged.append(item)
                return

            existing = merged[index_by_key[key]]
            if not existing.get("item") and item.get("item"):
                existing["item"] = item.get("item")
            if not existing.get("unidade") and item.get("unidade"):
                existing["unidade"] = item.get("unidade")
            existing_qty = self._parse_quantity(existing.get("quantidade"))
            incoming_qty = self._parse_quantity(item.get("quantidade"))
            if (existing_qty in (None, 0)) and (incoming_qty not in (None, 0)):
                existing["quantidade"] = item.get("quantidade")
            if self._is_short_description(existing.get("descricao", "")) and item.get("descricao"):
                if len(item.get("descricao", "")) > len(existing.get("descricao", "")):
                    existing["descricao"] = item.get("descricao")

        for servico in primary:
            add_or_update(servico)
        for servico in secondary:
            add_or_update(servico)

        merged = self._improve_short_descriptions(merged, primary + secondary)
        merged = self._deduplicate_by_description(merged)
        return merged

    def _deduplicate_by_description(self, servicos: list) -> list:
        """
        Remove serviços duplicados baseado na descrição normalizada.
        Prefere serviços que têm código de item sobre os que não têm.
        """
        if not servicos:
            return servicos

        # Agrupar por descrição normalizada
        by_desc = {}
        for s in servicos:
            desc = (s.get("descricao") or "").strip()
            desc_norm = self._normalize_description(desc)[:50]  # Usar apenas primeiros 50 chars
            if not desc_norm:
                continue

            if desc_norm not in by_desc:
                by_desc[desc_norm] = s
            else:
                # Já existe - preferir o que tem código de item
                existing = by_desc[desc_norm]
                existing_has_item = bool(existing.get("item"))
                new_has_item = bool(s.get("item"))

                if new_has_item and not existing_has_item:
                    by_desc[desc_norm] = s
                elif new_has_item == existing_has_item:
                    # Ambos têm ou não têm código - preferir descrição mais longa
                    if len(s.get("descricao", "")) > len(existing.get("descricao", "")):
                        by_desc[desc_norm] = s

        return list(by_desc.values())

    def _select_primary_source(self, vision_stats: dict, ocr_stats: dict, vision_score: float, ocr_score: float) -> str:
        margin = float(os.getenv("ATTESTADO_SCORE_MARGIN", "0.1"))
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
        except Exception:
            return image_bytes

    def _resize_image_bytes(self, image_bytes: bytes, scale: float = 0.5) -> bytes:
        try:
            img = Image.open(io.BytesIO(image_bytes))
            width, height = img.size
            resized = img.resize((max(1, int(width * scale)), max(1, int(height * scale))))
            buffer = io.BytesIO()
            resized.save(buffer, format="PNG")
            return buffer.getvalue()
        except Exception:
            return image_bytes

    def _detect_table_pages(self, images: List[bytes]) -> List[int]:
        keywords = {"RELATORIO", "SERVICOS", "EXECUTADOS", "ITEM", "DISCRIMINACAO", "UNID", "QUANTIDADE"}
        table_pages = []
        for index, image_bytes in enumerate(images):
            header = self._crop_region(image_bytes, 0.05, 0.0, 0.95, 0.35)
            header = self._resize_image_bytes(header, scale=0.5)
            try:
                text = ocr_service.extract_text_from_bytes(header)
            except Exception:
                text = ""
            normalized = self._normalize_description(text)
            hits = sum(1 for k in keywords if k in normalized)
            if hits >= 2:
                table_pages.append(index)
                continue
            import re
            if re.search(r"\b\d{3}\s*\d{2}\s*\d{2}\b", normalized):
                table_pages.append(index)
        return table_pages

    def _extract_servicos_pagewise(self, images: List[bytes], progress_callback=None, cancel_check=None) -> List[dict]:
        servicos: List[Dict[str, Any]] = []
        total_pages = len(images)
        if total_pages == 0:
            return servicos
        table_pages = self._detect_table_pages(images)
        page_indexes = table_pages if table_pages else list(range(total_pages))
        total = len(page_indexes)
        for idx, page_index in enumerate(page_indexes):
            self._check_cancel(cancel_check)
            self._notify_progress(progress_callback, idx + 1, total, "ia", f"Analisando pagina {page_index + 1} de {total_pages} com IA")
            image_bytes = images[page_index]
            cropped = self._crop_region(image_bytes, 0.05, 0.15, 0.95, 0.92)
            try:
                result = ai_provider.extract_atestado_from_images([cropped], provider="openai")
                page_servicos = result.get("servicos", []) if isinstance(result, dict) else []
                servicos.extend(page_servicos)
            except Exception as exc:
                print(f"Erro na IA por pagina {page_index + 1}: {exc}")
        return servicos

    def _extract_item_code(self, desc: str) -> str:
        """
        Extrai código do item da descrição (ex: "001.03.01" de "001.03.01 MOBILIZAÇÃO").
        """
        import re
        if not desc:
            return ""

        text = desc.strip()
        match = re.match(r'^(\d{1,3}(?:\s*\.\s*\d{1,3}){1,3})\b', text)
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
        import re
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

    def _normalize_desc_for_match(self, desc: str) -> str:
        import re
        code, cleaned = self._split_item_description(desc or "")
        base = cleaned if cleaned else (desc or "")
        normalized = self._normalize_description(base)
        normalized = re.sub(r"[^A-Z0-9 ]", " ", normalized)
        return " ".join(normalized.split())

    def _servico_match_key(self, servico: dict) -> str:
        desc = self._normalize_desc_for_match(servico.get("descricao") or "")
        unit = self._normalize_unit(servico.get("unidade") or "")
        if not desc:
            return ""
        return f"{desc}|||{unit}"

    def _servico_desc_key(self, servico: dict) -> str:
        return self._normalize_desc_for_match(servico.get("descricao") or "")

    def _dedupe_no_code_by_desc_unit(self, servicos: list) -> list:
        if not servicos:
            return servicos

        deduped = {}
        extras = []

        def score(item: dict) -> int:
            score_val = len((item.get("descricao") or "").strip())
            if self._parse_quantity(item.get("quantidade")) not in (None, 0):
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
                "unidade": self._normalize_unit(servico.get("unidade") or ""),
                "quantidade": self._parse_quantity(servico.get("quantidade"))
            }
            for servico in coded
        ]
        try:
            similarity_threshold = float(os.getenv("ATTESTADO_DESC_SIM_THRESHOLD", "0.7"))
        except ValueError:
            similarity_threshold = 0.7

        filtered_no_code = [
            servico for servico in no_code
            if self._servico_match_key(servico) not in coded_keys
            and self._servico_desc_key(servico) not in coded_desc_keys
        ]
        refined_no_code = []
        for servico in filtered_no_code:
            desc = servico.get("descricao") or ""
            unit = self._normalize_unit(servico.get("unidade") or "")
            qty = self._parse_quantity(servico.get("quantidade"))
            drop = False
            for coded_entry in coded_entries:
                if self._description_similarity(desc, coded_entry["descricao"]) < similarity_threshold:
                    continue
                unit_match = bool(unit and coded_entry["unidade"] and unit == coded_entry["unidade"])
                qty_match = False
                if qty not in (None, 0) and coded_entry["quantidade"] not in (None, 0):
                    diff = abs(qty - coded_entry["quantidade"])
                    denom = max(abs(qty), abs(coded_entry["quantidade"]))
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
        unit_tokens = self._unit_tokens()
        candidates = {}
        for servico in servicos_table:
            item = servico.get("item") or self._extract_item_code(servico.get("descricao") or "")
            if not item:
                continue
            item_tuple = self._parse_item_tuple(item)
            if not item_tuple:
                continue
            desc = (servico.get("descricao") or "").strip()
            if len(desc) < 8:
                continue
            qty = self._parse_quantity(servico.get("quantidade"))
            if qty is None:
                continue
            unit = self._normalize_unit(servico.get("unidade") or "")
            if unit and unit not in unit_tokens:
                unit = ""
            normalized_item = self._item_tuple_to_str(item_tuple)
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

        try:
            match_threshold = float(os.getenv("ATTESTADO_CODE_MATCH_THRESHOLD", "0.55"))
        except ValueError:
            match_threshold = 0.55

        used_codes = {s.get("item") for s in servicos if s.get("item")}
        used_codes.discard(None)
        for servico in servicos:
            if servico.get("item"):
                continue
            desc = servico.get("descricao") or ""
            unit = self._normalize_unit(servico.get("unidade") or "")
            qty = self._parse_quantity(servico.get("quantidade"))
            best_code = None
            best_score = 0.0
            best_candidate = None
            for code, candidate in table_candidates.items():
                if code in used_codes:
                    continue
                score = self._description_similarity(desc, candidate["descricao"])
                if score < match_threshold:
                    continue
                if unit and candidate["unidade"] and unit == candidate["unidade"]:
                    score += 0.1
                if qty not in (None, 0) and candidate["quantidade"] not in (None, 0):
                    diff = abs(qty - candidate["quantidade"])
                    denom = max(abs(qty), abs(candidate["quantidade"]))
                    if denom > 0 and (diff / denom) <= 0.05:
                        score += 0.1
                if score > best_score:
                    best_score = score
                    best_code = code
                    best_candidate = candidate
            if best_code:
                servico["item"] = best_code
                used_codes.add(best_code)
                if not servico.get("unidade") and best_candidate.get("unidade"):
                    servico["unidade"] = best_candidate["unidade"]
                if self._parse_quantity(servico.get("quantidade")) in (None, 0) and best_candidate.get("quantidade") is not None:
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

    def _find_better_description(self, item: dict, candidates: list) -> str:
        target_desc = (item.get('descricao') or '').strip()
        target_unit = self._normalize_unit(item.get('unidade') or '')
        try:
            target_qty = float(item.get('quantidade') or 0)
        except (TypeError, ValueError):
            target_qty = 0
        target_kw = self._extract_keywords(target_desc)

        best_desc = None
        best_len = len(target_desc)

        for cand in candidates:
            cand_desc = (cand.get('descricao') or '').strip()
            if not cand_desc or len(cand_desc) <= best_len:
                continue
            cand_unit = self._normalize_unit(cand.get('unidade') or '')
            if target_unit and cand_unit and cand_unit != target_unit:
                continue
            try:
                cand_qty = float(cand.get('quantidade') or 0)
            except (TypeError, ValueError):
                cand_qty = 0
            if target_qty and cand_qty and abs(target_qty - cand_qty) > 0.01:
                continue
            cand_kw = self._extract_keywords(cand_desc)
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

    def _merge_servicos(self, servicos1: list, servicos2: list) -> list:
        """
        Faz merge inteligente de duas listas de servicos.

        Estrategia:
        1. Priorizar itens com codigo (mais precisos)
        2. Para itens sem codigo, remover duplicatas por similaridade
        3. Itens com codigos diferentes sao mantidos
        """
        servicos1 = self._filter_summary_rows(servicos1 or [])
        servicos2 = self._filter_summary_rows(servicos2 or [])
        items_with_code: Dict[str, Dict[str, Any]] = {}
        items_without_code: List[Dict[str, Any]] = []

        for s in servicos1 + servicos2:
            desc = s.get('descricao', '')
            code = self._extract_item_code(desc)
            if code:
                existing = items_with_code.get(code)
                if not existing or len(desc) > len(existing.get('descricao', '')):
                    items_with_code[code] = s
            else:
                items_without_code.append(s)

        final_items = list(items_with_code.values())
        added_without_code: List[Dict[str, Any]] = []

        for s in items_without_code:
            desc = s.get('descricao', '')
            if self._is_summary_row(desc):
                continue
            is_duplicate = False
            for item in final_items:
                if self._items_similar(s, item):
                    is_duplicate = True
                    break
            if is_duplicate:
                continue
            for item in added_without_code:
                if self._items_similar(s, item):
                    is_duplicate = True
                    break
            if is_duplicate:
                continue
            added_without_code.append(s)

        final_items.extend(added_without_code)
        final_items = self._improve_short_descriptions(final_items, servicos1 + servicos2)
        return final_items

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
        texto = ""
        dados_vision = None
        dados_ocr = None
        self._check_cancel(cancel_check)

        # Extrair texto com OCR (sempre necessário para referência)
        if file_ext == ".pdf":
            try:
                texto = self._extract_pdf_with_ocr_fallback(
                    file_path,
                    progress_callback=progress_callback,
                    cancel_check=cancel_check
                )
            except Exception as e:
                try:
                    images = pdf_extractor.pdf_to_images(file_path)
                    texto = self._ocr_image_list(
                        images,
                        progress_callback=progress_callback,
                        cancel_check=cancel_check
                    )
                except Exception as e2:
                    raise Exception(f"Erro ao processar PDF: {str(e)} / OCR: {str(e2)}")
        elif file_ext in [".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif"]:
            try:
                self._check_cancel(cancel_check)
                self._notify_progress(progress_callback, 1, 1, "ocr", "OCR da imagem")
                texto = ocr_service.extract_text_from_image(file_path)
            except Exception as e:
                raise Exception(f"Erro no OCR da imagem: {str(e)}")
        else:
            raise Exception(f"Formato de arquivo não suportado: {file_ext}")

        if not texto.strip():
            raise Exception("Não foi possível extrair texto do documento")

        servicos_table = []
        table_confidence = 0.0
        table_debug = {}
        table_used = False
        primary_source = None
        table_attempts: Dict[str, Any] = {}
        table_threshold = float(os.getenv("ATTESTADO_TABLE_CONFIDENCE_THRESHOLD", "0.7"))
        table_min_items = int(os.getenv("ATTESTADO_TABLE_MIN_ITEMS", "10"))
        document_ai_enabled = os.getenv("DOCUMENT_AI_ENABLED", "0").lower() in {"1", "true", "yes"}
        document_ai_fallback_only = os.getenv("DOCUMENT_AI_FALLBACK_ONLY", "1").lower() in {"1", "true", "yes"}
        document_ai_ready = document_ai_enabled and document_ai_service.is_configured
        if file_ext == ".pdf":
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

            ocr_noisy = False
            if table_debug.get("source") == "ocr_layout" and servicos_table:
                ocr_noisy, ocr_noise_debug = self._is_ocr_noisy(servicos_table)
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
        elif file_ext in [".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif"]:
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
                ocr_noisy, ocr_noise_debug = self._is_ocr_noisy(servicos_table)
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

        if servicos_table and table_confidence >= table_threshold and len(servicos_table) >= table_min_items:
            table_used = True

        if isinstance(table_debug, dict):
            table_debug.setdefault("attempts", table_attempts)

        llm_fallback_only = os.getenv("ATTESTADO_LLM_FALLBACK_ONLY", "1").lower() in {"1", "true", "yes"}
        # SEMPRE executar AI para metadados (descricao, contratante, data)
        # Usar tabela apenas para servicos quando confianca for alta
        use_ai = ai_provider.is_configured  # Sempre usar AI se configurada
        use_ai_for_services = ai_provider.is_configured and (not llm_fallback_only or not table_used)
        ai_skipped = False  # AI nunca eh completamente pulada agora
        ai_skip_reason = None


        # Sempre executar extração com IA para metadados
        if use_ai:
            images = []
            vision_reprocessed = False
            vision_score = 0.0
            ocr_score = 0.0
            vision_stats = {"total": 0, "with_item": 0, "with_unit": 0, "with_qty": 0, "duplicate_ratio": 0.0}
            ocr_stats = {"total": 0, "with_item": 0, "with_unit": 0, "with_qty": 0, "duplicate_ratio": 0.0}

            # Metodo 1: OCR + analise de texto
            self._notify_progress(progress_callback, 0, 0, "ia", "Analisando texto com IA")
            self._check_cancel(cancel_check)
            dados_ocr = ai_provider.extract_atestado_info(texto)

            # Metodo 2: Vision (GPT-4o ou Gemini) (se habilitado)
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
                except Exception as e:
                    print(f"Erro no Vision: {str(e)}")
                    dados_vision = None

            servicos_vision = self._filter_summary_rows(dados_vision.get("servicos", []) if dados_vision else [])
            servicos_ocr = self._filter_summary_rows(dados_ocr.get("servicos", []) if dados_ocr else [])
            vision_stats = self._compute_servicos_stats(servicos_vision)
            ocr_stats = self._compute_servicos_stats(servicos_ocr)
            vision_score = self._compute_quality_score(vision_stats)
            ocr_score = self._compute_quality_score(ocr_stats)

            # Fallback por pagina com OpenAI quando a qualidade estiver baixa
            pagewise_enabled = os.getenv("ATTESTADO_PAGEWISE_VISION", "1").lower() in {"1", "true", "yes"}
            if pagewise_enabled and use_vision and images and "openai" in ai_provider.available_providers:
                quality_threshold = float(os.getenv("ATTESTADO_VISION_QUALITY_THRESHOLD", "0.6"))
                min_pages = int(os.getenv("ATTESTADO_PAGEWISE_MIN_PAGES", "3"))
                min_items = int(os.getenv("ATTESTADO_PAGEWISE_MIN_ITEMS", "40"))
                if vision_score < quality_threshold or (len(images) >= min_pages and vision_stats.get("total", 0) < min_items):
                    page_servicos = self._extract_servicos_pagewise(images, progress_callback, cancel_check)
                    if page_servicos:
                        dados_vision = dados_vision or {}
                        dados_vision["servicos"] = page_servicos
                        servicos_vision = self._filter_summary_rows(page_servicos)
                        vision_stats = self._compute_servicos_stats(servicos_vision)
                        vision_score = self._compute_quality_score(vision_stats)
                        vision_reprocessed = True
                        ocr_score = self._compute_quality_score(ocr_stats)

            # Combinar resultados
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

                dados["servicos"] = self._merge_servicos_prefer_primary(primary_servicos, secondary_servicos)

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

            # Se tabela foi usada com alta confiança, comparar com IA
            # e usar a fonte com mais serviços válidos
            if table_used and not use_ai_for_services:
                # Filtrar serviços sem quantidade (cabeçalhos de seção)
                servicos_table_filtered = [
                    s for s in servicos_table
                    if s.get("quantidade") is not None
                ]
                # Comparar com serviços da IA - usar tabela apenas se tiver mais ou igual itens
                ai_servicos_count = len(dados.get("servicos", []))
                table_servicos_count = len(servicos_table_filtered)

                if table_servicos_count >= ai_servicos_count:
                    dados["servicos"] = servicos_table_filtered
                    primary_source = "table_services"  # Serviços da tabela, metadados da IA
                else:
                    # IA tem mais serviços - manter serviços da IA
                    primary_source = primary_source + "_ai_preferred"  # Indica que IA foi preferida

            dados["_debug"] = {
                "vision": {"count": len(servicos_vision), "score": vision_score, "reprocessed": vision_reprocessed},
                "ocr": {"count": len(servicos_ocr), "score": ocr_score},
                "vision_stats": vision_stats,
                "ocr_stats": ocr_stats,
                "table": {
                    "count": len(servicos_table),
                    "confidence": table_confidence,
                    "used": table_used,
                    "debug": table_debug
                },
                "page_count": len(images),
                "primary_source": primary_source,
                "provider_config": ai_provider.current_provider,
                "use_ai_for_services": use_ai_for_services,
            }

        else:
            # IA não está configurada - usar apenas extração de tabela
            # Filtrar serviços sem quantidade (cabeçalhos de seção)
            servicos_table_filtered = [
                s for s in servicos_table
                if s.get("quantidade") is not None
            ] if table_used else []
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

        servicos = self._filter_summary_rows(dados.get("servicos") or [])
        if use_ai and not table_used:
            servicos = self._attach_item_codes_from_table(servicos, servicos_table)
            servicos = self._prefer_items_with_code(servicos)
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
            qty = self._parse_quantity(servico.get("quantidade"))
            if qty is not None:
                servico["quantidade"] = qty
            unit = servico.get("unidade")
            if isinstance(unit, str):
                servico["unidade"] = unit.strip()

        # Aplicar filtro para remover classificações inválidas (caminhos com ">")
        servicos = self._filter_classification_paths(servicos)

        # Remover duplicatas (mesmo item + descrição + quantidade + unidade)
        servicos = self._remove_duplicate_services(servicos)

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
            raise Exception("O arquivo do edital deve ser um PDF")

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
            except Exception as e:
                raise Exception(f"Erro no OCR do edital: {str(e)}")

        if not texto.strip():
            raise Exception("Não foi possível extrair texto do edital")

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
                "enabled": os.getenv("DOCUMENT_AI_ENABLED", "0").lower() in {"1", "true", "yes"}
            },
            "is_configured": ai_provider.is_configured,
            "mensagem": f"IA configurada ({', '.join(ai_provider.available_providers)})" if ai_provider.is_configured else "Configure OPENAI_API_KEY ou GOOGLE_API_KEY para análise inteligente"
        }


# Instância singleton para uso global
document_processor = DocumentProcessor()
