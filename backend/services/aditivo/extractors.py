"""
Extratores de informações de itens de aditivo.

Contém funções para extrair descrição, quantidade e unidade de itens
a partir do texto do documento.
"""

import re
from typing import Any, Dict, List, Optional

from logging_config import get_logger
from utils.text_utils import sanitize_description

from .validators import is_contaminated_line, is_good_description

logger = get_logger('services.aditivo.extractors')


class AditivoItemExtractor:
    """
    Extrai informações de itens da seção de aditivo no texto.

    Usa múltiplos padrões para diferentes formatos de documento.
    """

    def __init__(self, lines: List[str], aditivo_start_line: int):
        """
        Inicializa o extrator.

        Args:
            lines: Lista de linhas do documento
            aditivo_start_line: Linha onde começa a seção de aditivo
        """
        self.lines = lines
        self.aditivo_start_line = aditivo_start_line

    def extract(self, item_str: str, major: int) -> Dict[str, Any]:
        """
        Extrai informações de um item da seção de aditivo no texto.

        Formatos suportados:
        1. Tudo em uma linha: "1.1 DESCRIÇÃO COMPLETA UN 100"
        2. Descrição antes do item:
           "INÍCIO DA DESCRIÇÃO"
           "1.1 CONTINUAÇÃO UN 100"
        3. Formato de tabela com colunas separadas

        Args:
            item_str: Código do item (ex: "1.1")
            major: Número maior do item (ex: 1)

        Returns:
            Dict com descricao, quantidade, unidade e _source
        """
        result: Dict[str, Any] = {
            "descricao": None,
            "quantidade": None,
            "unidade": None,
            "_source": "text"
        }

        # Padrão para encontrar o item no texto do aditivo (início da linha)
        pattern_start = re.compile(rf"^\s*{re.escape(item_str)}(?:\s|$)", re.MULTILINE)
        # Padrão para encontrar o item embutido no meio da linha
        pattern_embedded = re.compile(
            rf'(?<!\d\.){re.escape(item_str)}(?:\s+(?:UN|M|KG)\s+[\d,.]+)?'
        )

        for i, line in enumerate(self.lines):
            if i < self.aditivo_start_line:
                continue  # Ignorar linhas antes do aditivo

            item_at_start = pattern_start.match(line)
            item_embedded = pattern_embedded.search(line) if not item_at_start else None

            # PADRÃO 0: Item EMBUTIDO no meio da linha
            if item_embedded and item_embedded.start() > 10:
                extracted = self._extract_embedded_pattern(line, item_embedded, item_str, i)
                if extracted:
                    return extracted

            if not item_at_start:
                continue

            # Extrair quantidade e unidade do final da linha
            self._extract_qty_unit(line, result)

            # PADRÃO 1: Descrição completa na mesma linha
            extracted = self._extract_single_line_pattern(line, item_str, i, result)
            if extracted:
                return extracted

            # PADRÃO 2: Descrição começa na linha ANTERIOR
            extracted = self._extract_multiline_pattern(line, item_str, i, result)
            if extracted:
                return extracted

            # PADRÃO 3: Descrição na próxima linha
            extracted = self._extract_next_line_pattern(i, result)
            if extracted:
                return extracted

            break  # Usar a primeira ocorrência encontrada no aditivo

        return result

    def _extract_qty_unit(self, line: str, result: Dict[str, Any]) -> None:
        """Extrai quantidade e unidade do final da linha."""
        qty_match = re.search(
            r"\b(UN|M|KG|M2|M3|M²|M³|L|VB|CJ|PC|GL|un|m|m²|m³)\s+([\d,.]+)\s*$",
            line,
            re.IGNORECASE
        )
        if qty_match:
            result["unidade"] = qty_match.group(1).upper().replace("²", "2").replace("³", "3")
            qty_str = qty_match.group(2).replace(",", ".")
            try:
                result["quantidade"] = float(qty_str)
            except ValueError:
                pass

    def _extract_embedded_pattern(
        self, line: str, item_embedded, item_str: str, line_idx: int
    ) -> Optional[Dict[str, Any]]:
        """Extrai item embutido no meio da linha (PADRÃO 0)."""
        before_item = line[:item_embedded.start()].strip()
        before_item = re.sub(r'\s+\d+\.\d+\s*$', '', before_item).strip()

        if not (re.search(r'[A-Za-zÀ-ÿ]{4,}', before_item) and len(before_item) > 15):
            return None

        result: Dict[str, Any] = {
            "descricao": None,
            "quantidade": None,
            "unidade": None,
            "_source": "text_embedded"
        }

        # Extrair quantidade e unidade
        qty_match = re.search(
            r"\b(UN|M|KG|M2|M3|M²|M³|L|VB|CJ|PC|GL)\s+([\d,.]+)\s*$",
            line,
            re.IGNORECASE
        )
        if qty_match:
            result["unidade"] = qty_match.group(1).upper().replace("²", "2").replace("³", "3")
            qty_str = qty_match.group(2).replace(",", ".")
            try:
                result["quantidade"] = float(qty_str)
            except ValueError:
                pass

        # Buscar linhas de continuação APÓS
        desc_continuation = []
        for k in range(line_idx + 1, min(len(self.lines), line_idx + 4)):
            next_line = self.lines[k].strip()
            if not next_line:
                continue
            if re.match(r'^\d+\.\d+\s', next_line) or re.match(r'^\d{1,2}\s+[A-Z]{2,}', next_line):
                break
            if len(next_line) < 80 and not re.search(r'\b(?:UN|M|KG)\s+[\d,.]+\s*$', next_line, re.IGNORECASE):
                desc_continuation.append(next_line)
            else:
                break

        full_desc = before_item
        if desc_continuation:
            full_desc += " " + " ".join(desc_continuation)
        full_desc = full_desc.strip()

        if is_good_description(full_desc):
            result["descricao"] = full_desc
            logger.debug(f"[ADITIVO] Padrão 0 (item embutido): {full_desc[:50]}")
            return result

        return None

    def _extract_single_line_pattern(
        self, line: str, item_str: str, line_idx: int, result: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Extrai descrição completa na mesma linha (PADRÃO 1)."""
        # Verificar se linha anterior termina com preposição/vírgula
        prev_line_ends_with_continuation = False
        if line_idx > 0:
            prev_line_check = self.lines[line_idx - 1].strip()
            prev_line_ends_with_continuation = bool(re.search(
                r'[,\s](PARA|COM|DE|DO|DA|NO|NA|EM|E|OU)\s*$|,\s*$',
                prev_line_check,
                re.IGNORECASE
            ))

        full_match = re.match(
            rf"^\s*{re.escape(item_str)}\s+([A-Za-zÀ-ÿ][\w\s\-,./()À-ÿ]+?)"
            r"(?:\s+(?:UN|M|KG|M2|M3|M²|M³|L|VB|CJ|PC|GL)\s+[\d,.]+)?\s*$",
            line,
            re.IGNORECASE
        )

        if not full_match:
            return None

        desc = full_match.group(1).strip()

        continuation_starts = (
            'E ', 'EM ', 'DE ', 'DO ', 'DA ', 'NO ', 'NA ', 'PARA ', 'COM ',
            'MM,', 'MM ', 'ELÁSTICA', 'ELASTICA', 'INCLUSIVE', 'INCLUINDO',
            'INSTALAD',
        )
        desc_looks_truncated = desc.upper().startswith(continuation_starts)

        if is_good_description(desc) and not desc_looks_truncated and not prev_line_ends_with_continuation:
            result["descricao"] = desc
            logger.debug(f"[ADITIVO] Padrão 1 (linha única): {desc[:50]}")
            return result

        return None

    def _extract_multiline_pattern(
        self, line: str, item_str: str, line_idx: int, result: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Extrai descrição de múltiplas linhas (PADRÃO 2)."""
        # Verificar se linha anterior termina com preposição/vírgula
        prev_line_ends_with_continuation = False
        if line_idx > 0:
            prev_line_check = self.lines[line_idx - 1].strip()
            prev_line_ends_with_continuation = bool(re.search(
                r'[,\s](PARA|COM|DE|DO|DA|NO|NA|EM|E|OU)\s*$|,\s*$',
                prev_line_check,
                re.IGNORECASE
            ))

        desc_parts: List[str] = []

        # Extrair texto após o número do item na linha atual
        after_item = re.sub(rf"^\s*{re.escape(item_str)}\s*", "", line)
        after_item = re.sub(
            r"\s*(?:UN|M|KG|M2|M3|M²|M³|L|VB|CJ|PC|GL|un|m|m²|m³)\s+[\d,.]+\s*$",
            "", after_item, flags=re.IGNORECASE
        ).strip()
        after_item = re.sub(
            r"^(?:UN|M[²³2-3\xb2\xb3]?|KG|L|VB|CJ|PC|GL|BUN)\s+[\d,.]+\s+",
            "", after_item, flags=re.IGNORECASE
        ).strip()

        desc_seems_continuation = bool(re.match(
            r'^(E\s|EM\s|MM|EL[AÁ]STICA|PARA\s|COM\s|DE\s|DO\s|DA\s|NO\s|NA\s|TE,|INCLUSIVE|INSTALAD)',
            after_item,
            re.IGNORECASE
        )) or prev_line_ends_with_continuation

        # Buscar linhas anteriores
        for j in range(line_idx - 1, max(self.aditivo_start_line - 1, line_idx - 6), -1):
            prev_line = self.lines[j].strip()
            if not prev_line:
                continue

            has_unit_qty = re.search(
                r"\b(?:UN|M|KG|M2|M3|M²|M³|L|VB|CJ|PC|GL)\s+[\d,.]+\s*$",
                prev_line, re.IGNORECASE
            )
            is_numbered_item = re.match(r"^\d+\.\d+\s", prev_line)

            if is_numbered_item and has_unit_qty and desc_seems_continuation and not desc_parts:
                prev_desc = re.sub(
                    r'\s*(?:UN|M|KG|M2|M3|M²|M³|L|VB|CJ|PC|GL)\s+[\d,.]+\s*$',
                    '', prev_line, flags=re.IGNORECASE
                ).strip()
                prev_desc = re.sub(r'^\d+\.\d+\s+', '', prev_desc).strip()
                if prev_desc and len(prev_desc) > 10 and not is_contaminated_line(prev_desc):
                    desc_parts.insert(0, prev_desc)
                break

            if is_numbered_item or re.match(r"^\d+\s+[A-Z][a-zÀ-ÿ]", prev_line):
                break

            if has_unit_qty:
                if desc_seems_continuation and not desc_parts:
                    prev_desc = re.sub(
                        r'\s*(?:UN|M|KG|M2|M3|M²|M³|L|VB|CJ|PC|GL)\s+[\d,.]+\s*$',
                        '', prev_line, flags=re.IGNORECASE
                    ).strip()
                    if prev_desc and len(prev_desc) > 10 and not is_contaminated_line(prev_desc):
                        desc_parts.insert(0, prev_desc)
                break

            if re.search(r"[A-Za-zÀ-ÿ]{3,}", prev_line) and len(prev_line) > 5:
                if not is_contaminated_line(prev_line):
                    # Verificar se linha parece ser continuação órfã
                    looks_like_orphan = self._is_orphan_continuation(prev_line)
                    if looks_like_orphan:
                        break
                    desc_parts.insert(0, prev_line)
                else:
                    break

        # Montar descrição
        if desc_parts:
            full_desc = " ".join(desc_parts)
            if after_item and len(after_item) > 2:
                full_desc += " " + after_item

            # Buscar linhas de continuação APÓS o item
            for k in range(line_idx + 1, min(len(self.lines), line_idx + 4)):
                next_line = self.lines[k].strip()
                if not next_line:
                    continue
                if re.match(r'^\d+\.\d+\s', next_line):
                    break
                if re.match(r'^\d{1,2}\s+[A-ZÁÉÍÓÚÂÊÎÔÛÃÕÇ]{2,}', next_line):
                    break
                has_unit_qty_end = re.search(
                    r'\b(?:UN|M|KG|M2|M3|L|VB|CJ|PC|GL)\s+[\d,.]+\s*$',
                    next_line, re.IGNORECASE
                )
                if not has_unit_qty_end and len(next_line) < 80 and re.search(r'[A-Za-zÀ-ÿ]{2,}', next_line):
                    full_desc += " " + next_line
                else:
                    break

            full_desc = sanitize_description(full_desc.strip())
            if is_good_description(full_desc):
                result["descricao"] = full_desc
                logger.debug(f"[ADITIVO] Padrão 2 (linhas anteriores + posteriores): {full_desc[:50]}")
                return result

        return None

    def _extract_next_line_pattern(
        self, line_idx: int, result: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Extrai descrição da próxima linha (PADRÃO 3)."""
        if line_idx + 1 < len(self.lines):
            next_line = self.lines[line_idx + 1].strip()
            if next_line and not re.match(r"^\d+\.\d+", next_line):
                if is_good_description(next_line):
                    result["descricao"] = next_line[:200]
                    logger.debug(f"[ADITIVO] Padrão 3 (próxima linha): {next_line[:50]}")
                    return result
        return None

    def _is_orphan_continuation(self, line: str) -> bool:
        """Verifica se linha parece continuação órfã."""
        line_stripped = line.strip()

        # Código AF_XX/XXXX no final
        if len(line_stripped) < 35 and re.search(r'AF_\d+/\d{4}\s*$', line_stripped, re.IGNORECASE):
            return True

        # Medida isolada
        if len(line_stripped) < 40 and re.match(r'^\d+[,.]?\d*\s*m\s*[-–]', line_stripped, re.IGNORECASE):
            return True

        # Fragmento órfão
        if len(line_stripped) < 30 and line_stripped and (line_stripped[0].islower() or line_stripped[0] in '(),;-'):
            return True

        # Código de referência
        if re.match(r'^(SINAPI|REF\.?|REFER[ÊE]NCIA)\s*\d+', line_stripped, re.IGNORECASE):
            return True

        return False
