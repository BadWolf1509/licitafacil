"""
Servico de extracao de texto de documentos.
Extrai itens, quantidades e descricoes de texto bruto.

Inclui cache de resultados para evitar reprocessamento de arquivos identicos.
"""
from typing import Dict, Any, Optional, Set, Callable
import re
import os

from .extraction import (
    normalize_description,
    normalize_unit,
    parse_quantity,
    UNIT_TOKENS,
    normalize_item_code as _normalize_item_code,
    item_code_in_text as _item_code_in_text,
)
from .pdf_extractor import pdf_extractor
from .ocr_service import ocr_service
from .pdf_extraction_service import pdf_extraction_service
from .cache import get_cache
from exceptions import PDFError, OCRError, UnsupportedFileError, TextExtractionError
from logging_config import get_logger

logger = get_logger('services.text_extraction')

# TTL do cache de texto extraido (1 hora)
TEXT_CACHE_TTL = int(os.getenv("TEXT_CACHE_TTL", "3600"))


class TextExtractionService:
    """Servico de extracao de itens de texto."""

    def normalize_item_code(self, item: Any) -> Optional[str]:
        """Normaliza codigo de item removendo espacos e prefixos."""
        return _normalize_item_code(item)

    def item_code_in_text(self, item_code: str, texto: str) -> bool:
        """Verifica se codigo de item aparece no texto."""
        return _item_code_in_text(item_code, texto)

    def count_item_codes_in_text(self, texto: str) -> int:
        """Conta quantos codigos de item aparecem no texto."""
        if not texto:
            return 0
        pattern = re.compile(r'\b\d{1,3}(?:\s*\.\s*\d{1,3}){1,4}\b')
        matches = pattern.findall(texto)
        unique = set()
        for m in matches:
            code = re.sub(r'\s+', '', m)
            if re.match(r'^\d+(\.\d+)+$', code):
                unique.add(code)
        return len(unique)

    def extract_item_codes_from_text_lines(self, texto: str) -> list:
        """Extrai codigos de item do texto linha a linha."""
        if not texto:
            return []
        codes = []
        pattern = re.compile(r'\b(\d{1,3}(?:\s*\.\s*\d{1,3}){1,4})\b')
        for line in texto.splitlines():
            matches = pattern.findall(line)
            for m in matches:
                code = re.sub(r'\s+', '', m)
                if re.match(r'^\d+(\.\d+)+$', code):
                    codes.append(code)
        return codes

    def split_text_by_pages(self, texto: str) -> list:
        """Divide texto em segmentos por pagina."""
        if not texto:
            return []
        matches = list(re.finditer(r'P[aá]gina\s+(\d+)\s*/\s*(\d+)', texto, re.IGNORECASE))
        if not matches:
            return []
        segments = []
        for idx, match in enumerate(matches):
            start = match.start()
            end = matches[idx + 1].start() if idx + 1 < len(matches) else len(texto)
            try:
                page_num = int(match.group(1))
            except (TypeError, ValueError):
                continue
            segments.append((page_num, texto[start:end]))
        merged: Dict[int, str] = {}
        for page_num, content in segments:
            if page_num in merged:
                merged[page_num] += "\n" + content
            else:
                merged[page_num] = content
        return [(p, c) for p, c in sorted(merged.items())]

    def find_servicos_anchor_line(self, lines: list) -> Optional[int]:
        """Encontra linha ancora 'SERVICOS EXECUTADOS'."""
        if not lines:
            return None
        anchors = ("SERVICOS EXECUTADOS", "SERVICOS EXECUTADO")
        for idx, line in enumerate(lines):
            normalized = normalize_description(line)
            if not normalized:
                continue
            for anchor in anchors:
                if anchor in normalized:
                    return idx
        return None

    def find_unit_qty_in_line(self, line: str) -> Optional[tuple]:
        """Encontra unidade e quantidade em uma linha."""
        if not line:
            return None
        stop_units = {"N", "A", "NO", "AO", "NA", "EM", "DE", "DO", "DA", "ITEM", "LINHA", "01", "02", "03"}
        allowed_units = UNIT_TOKENS
        pattern = re.compile(
            r'(?<![A-Za-z0-9])'
            r'([A-Za-z][A-Za-z0-9\u00ba\u00b0/%\u00b2\u00b3\.]*)'
            r'\s+'
            r'([\d.,]+)'
            r'(?:\s|$)',
            re.IGNORECASE
        )
        last_valid = None
        for match in pattern.finditer(line):
            unit_raw = match.group(1)
            qty_raw = match.group(2)
            qty = parse_quantity(qty_raw)
            if qty is None or qty == 0:
                continue
            unit_norm = normalize_unit(unit_raw)
            if not unit_norm:
                continue
            if unit_norm in stop_units:
                continue
            if unit_norm not in allowed_units:
                continue
            last_valid = (unit_norm, qty, match.start(), match.end())
        return last_valid

    def parse_unit_qty_from_line(self, line: str) -> Optional[tuple]:
        """Extrai unidade e quantidade de uma linha."""
        if not line:
            return None
        # Padrao: UNIDADE QTY no final
        match = re.search(
            r'\b([A-Za-z][A-Za-z0-9\u00ba\u00b0/%\u00b2\u00b3\.]*)\s+([\d.,]+)\s*$',
            line
        )
        if match:
            unit_raw = match.group(1)
            qty_raw = match.group(2)
            qty = parse_quantity(qty_raw)
            if qty is not None and qty > 0:
                unit_norm = normalize_unit(unit_raw)
                if unit_norm and unit_norm in UNIT_TOKENS:
                    return (unit_norm, qty)
        return None

    def strip_trailing_unit_qty(
        self,
        desc: str,
        unit: str,
        qty: float,
        max_tries: int = 3
    ) -> str:
        """Remove unidade/quantidade do final da descricao."""
        if not desc:
            return desc
        for _ in range(max_tries):
            match = re.search(
                r'\s+([A-Za-z][A-Za-z0-9\u00ba\u00b0/%\u00b2\u00b3\.]*)\s+([\d.,]+)\s*$',
                desc
            )
            if not match:
                break
            trail_unit = normalize_unit(match.group(1))
            trail_qty = parse_quantity(match.group(2))
            if trail_unit and trail_qty is not None:
                desc = desc[:match.start()].strip()
            else:
                break
        return desc

    def strip_unit_qty_prefix(self, desc: str) -> str:
        """Remove unidade/quantidade do inicio da descricao."""
        if not desc:
            return desc
        match = re.match(
            r'^([A-Za-z][A-Za-z0-9\u00ba\u00b0/%\u00b2\u00b3\.]*)\s+([\d.,]+)\s+(.+)$',
            desc
        )
        if match:
            unit_norm = normalize_unit(match.group(1))
            qty = parse_quantity(match.group(2))
            if unit_norm and qty is not None:
                return match.group(3).strip()
        return desc

    def strip_footer_prefix_from_desc(self, desc: str) -> str:
        """Remove prefixos de rodape da descricao."""
        if not desc:
            return desc
        anchors = [
            "FORNECIMENTO", "EXECUCAO", "LOCACAO", "ESCAVACAO",
            "REATERRO", "LASTRO", "FUNDACAO", "CONCRETO",
            "ADMINISTRACAO", "MOBILIZACAO", "PLACA", "PERFURACAO"
        ]
        normalized = normalize_description(desc)
        if not normalized:
            return desc
        anchor_pos = None
        for anchor in anchors:
            pos = normalized.find(anchor)
            if pos != -1:
                if anchor_pos is None or pos < anchor_pos:
                    anchor_pos = pos
        if anchor_pos is None or anchor_pos == 0:
            return desc
        prefix_norm = normalized[:anchor_pos].strip()
        footer_tokens = (
            "CNPJ", "CPF", "PREFEITURA", "CONSELHO REGIONAL", "CREA",
            "DOCUSIGN", "CEP", "RUA", "EMAIL", "TEL", "IMPRESSO"
        )
        for token in footer_tokens:
            if re.search(rf'\b{re.escape(token)}\b', prefix_norm):
                return desc[anchor_pos:].strip()
        return desc

    def extract_items_from_text_lines(self, texto: str) -> list:
        """
        Extrai itens de servico do texto linha a linha.

        Delega para TextProcessor que tem implementação mais completa.
        """
        # Import local para evitar dependência circular
        from .processors.text_processor import text_processor
        return text_processor.extract_items_from_text_lines(texto)

    def extract_items_without_codes_from_text(self, texto: str) -> list:
        """
        Extrai itens sem codigo do texto.

        Delega para TextProcessor que tem implementação mais completa.
        """
        # Import local para evitar dependência circular
        from .processors.text_processor import text_processor
        return text_processor.extract_items_without_codes_from_text(texto)

    def extract_quantities_from_text(self, texto: str, item_codes: Set[str]) -> Dict[str, list]:
        """
        Extrai quantidades do texto para codigos de item especificos.

        Delega para TextProcessor que usa QuantityExtractor.
        """
        # Import local para evitar dependência circular
        from .processors.text_processor import text_processor
        return text_processor.extract_quantities_from_text(texto, item_codes)

    def detect_planilha_signature(self, texto: str) -> Optional[str]:
        """Detecta assinatura de planilha no texto (ORCAMENTO, FISICO, etc)."""
        normalized = normalize_description(texto or "")
        if not normalized:
            return None
        has_orcamento = "ORCAMENTO" in normalized
        has_fisico = "FISICO" in normalized
        has_geobras = "GEOBRAS" in normalized
        has_contrato = "CONTRATO" in normalized
        if has_fisico:
            if has_geobras or has_contrato:
                return "FISICO_CONTRATO"
            return "FISICO"
        if has_orcamento:
            return "ORCAMENTO"
        return None

    def _extract_item_codes_from_page(self, page_text: str) -> list:
        """
        Extrai códigos de item de uma página e retorna como tuplas ordenáveis.

        Considera apenas códigos no início de linhas para evitar falsos positivos
        (ex: datas, medidas).
        """
        codes = []
        # Padrão: código no início da linha seguido de espaço e texto
        pattern = re.compile(r'^\s*(\d{1,2}\.\d{1,2}(?:\.\d{1,2})?)\s+\S', re.MULTILINE)
        for match in pattern.finditer(page_text):
            code = match.group(1)
            parts = code.split('.')
            try:
                tup = tuple(int(p) for p in parts)
                # Filtrar códigos suspeitos (segundo componente > 30)
                if len(tup) > 1 and tup[1] > 30:
                    continue
                codes.append(tup)
            except (TypeError, ValueError):
                continue
        return codes

    def _detect_restart(self, prev_codes: list, curr_codes: list) -> bool:
        """
        Detecta se há reinício de numeração entre duas páginas.

        Analisa a progressão de itens para detectar quando uma nova planilha
        começa com numeração reiniciada (ex: de 3.10 volta para 1.1).

        Critérios de detecção:
        1. Seção principal (primeiro componente) diminuiu
        2. Mesma seção, mas numeração secundária regrediu significativamente
        """
        if not prev_codes or not curr_codes:
            return False

        prev_max = max(prev_codes)
        curr_min = min(curr_codes)

        # Se a numeração atual não é menor que a anterior, não há reinício
        if curr_min >= prev_max:
            return False

        # Regra 1: Seção principal (primeiro componente) diminuiu
        # Ex: prev_max = (3, 10), curr_min = (1, 1) → 3 > 1 → reinício
        if curr_min[0] < prev_max[0]:
            return True

        # Regra 2: Mesma seção, mas numeração secundária regrediu significativamente
        # Ex: prev_max = (2, 15), curr_min = (2, 1) → de 15 para 1 = reinício
        if len(curr_min) > 1 and len(prev_max) > 1:
            if curr_min[0] == prev_max[0]:  # Mesma seção
                item_regression = prev_max[1] - curr_min[1]
                # Grande regressão (>= 5) E começando do início (item <= 3)
                if item_regression >= 5 and curr_min[1] <= 3:
                    return True

        return False

    def build_page_planilha_map(self, page_segments: list) -> tuple:
        """Constroi mapeamento de pagina para planilha baseado em reinício de numeração."""
        if not page_segments:
            return {}, []
        page_map: Dict[int, int] = {}
        audit: list = []
        planilha_id = 0
        prev_codes: list = []
        started = False

        for page_num, page_text in page_segments:
            curr_codes = self._extract_item_codes_from_page(page_text)

            # Detectar nova planilha por reinício de numeração
            restart_reason = None

            # Só começar a contar planilhas quando encontrar itens
            if curr_codes and not started:
                started = True
                planilha_id = 1
                restart_reason = "first_items"

            # Verificar reinício de numeração
            elif curr_codes and prev_codes:
                if self._detect_restart(prev_codes, curr_codes):
                    planilha_id += 1
                    restart_reason = f"restart:{min(curr_codes)}<{max(prev_codes)}"

            page_map[page_num] = planilha_id if planilha_id else 0
            audit.append({
                "page": page_num,
                "planilha_id": page_map[page_num],
                "restart": restart_reason
            })

            # Atualizar códigos anteriores
            if curr_codes:
                prev_codes = curr_codes

        if not started:
            return {}, []
        return page_map, audit

    def apply_page_planilha_map(self, servicos: list, page_map: Dict[int, int]) -> int:
        """Aplica mapeamento de pagina para planilha nos servicos."""
        if not servicos or not page_map:
            return 0
        remapped = 0
        for servico in servicos:
            page = servico.get("_page")
            if page is None:
                continue
            try:
                page_num = int(page)
            except (TypeError, ValueError):
                continue
            target_id = page_map.get(page_num)
            if not target_id:
                continue
            current_id = int(servico.get("_planilha_id") or 0)
            if current_id != target_id:
                servico["_planilha_id"] = target_id
                servico.pop("_planilha_label", None)
                remapped += 1
        return remapped

    def _get_cache_key(self, file_path: str) -> Optional[str]:
        """Gera chave de cache baseada no hash do arquivo."""
        try:
            from utils.file_hash import get_text_extraction_cache_key
            return get_text_extraction_cache_key(file_path)
        except Exception as e:
            logger.debug(f"Erro ao gerar cache key: {e}")
            return None

    def extract_text_from_file(
        self,
        file_path: str,
        file_ext: str,
        progress_callback: Optional[Callable] = None,
        cancel_check: Optional[Callable] = None,
        use_cache: bool = True
    ) -> str:
        """
        Extrai texto do arquivo (PDF ou imagem) usando OCR quando necessário.

        Implementa cache para evitar reprocessamento de arquivos identicos.

        Args:
            file_path: Caminho para o arquivo
            file_ext: Extensão do arquivo (ex: ".pdf", ".png")
            progress_callback: Callback para progresso
            cancel_check: Função para verificar cancelamento
            use_cache: Se True, tenta usar cache (default: True)

        Returns:
            Texto extraído do documento

        Raises:
            PDFError, OCRError, UnsupportedFileError, TextExtractionError
        """
        # Tentar obter do cache
        cache_key = None
        if use_cache:
            cache_key = self._get_cache_key(file_path)
            if cache_key:
                cache = get_cache()
                cached_text = cache.get(cache_key)
                if cached_text is not None:
                    logger.info(f"Cache hit para extracao de texto: {cache_key}")
                    return cached_text

        texto = ""

        if file_ext == ".pdf":
            try:
                texto = pdf_extraction_service.extract_text_with_ocr_fallback(
                    file_path,
                    progress_callback=progress_callback,
                    cancel_check=cancel_check
                )
            except (PDFError, TextExtractionError) as e:
                logger.warning(f"Fallback para OCR apos erro: {e}")
                try:
                    images = pdf_extractor.pdf_to_images(file_path)
                    texto = pdf_extraction_service.ocr_image_list(
                        images,
                        progress_callback=progress_callback,
                        cancel_check=cancel_check
                    )
                except (PDFError, OCRError) as e2:
                    raise PDFError("processar", f"{e} / OCR: {e2}")
        elif file_ext in [".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif"]:
            try:
                pdf_extraction_service._check_cancel(cancel_check)
                pdf_extraction_service._notify_progress(progress_callback, 1, 1, "ocr", "OCR da imagem")
                texto = ocr_service.extract_text_from_image(file_path)
            except (OCRError, IOError) as e:
                raise OCRError(str(e))
        else:
            raise UnsupportedFileError(file_ext)

        if not texto.strip():
            raise TextExtractionError("documento")

        # Salvar no cache
        if use_cache and cache_key and texto:
            cache = get_cache()
            cache.set(cache_key, texto, TEXT_CACHE_TTL)
            logger.info(f"Cache set para extracao de texto: {cache_key}")

        return texto

    def invalidate_cache(self, file_path: str) -> bool:
        """
        Invalida o cache para um arquivo especifico.

        Args:
            file_path: Caminho do arquivo

        Returns:
            True se o cache foi invalidado, False caso contrario
        """
        cache_key = self._get_cache_key(file_path)
        if cache_key:
            cache = get_cache()
            return cache.delete(cache_key)
        return False


# Singleton
text_extraction_service = TextExtractionService()
