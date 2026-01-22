"""
Processamento de aditivos contratuais.

Módulo responsável por detectar e processar seções de aditivos
em documentos de atestado de capacidade técnica.
"""

import re
from typing import List, Dict, Any

from logging_config import get_logger
from .extraction import (
    parse_item_tuple,
)

logger = get_logger('services.aditivo_processor')


def detect_aditivo_sections(texto: str) -> list:
    """
    Detecta seções de aditivo contratual no texto extraído.

    Identifica reinício de numeração (quando itens voltam para 1.x após números altos)
    e headers de seção do aditivo. Só considera seções APÓS o reinício.

    Returns:
        Lista de seções: [{"start_line": int, "title": str, "prefix": str}, ...]
    """
    if not texto:
        return []

    lines = texto.split("\n")
    sections = []

    # Padrão para headers de seção do aditivo (ex: "1 Drenagem", "2 Muro")
    header_pattern = re.compile(r"^\s*(\d+)\s+([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ\s/]+)$")
    # Padrão para itens numerados - requer espaço/texto após o número
    # Exclui CNPJs (XX.XXX.XXX/XXXX-XX) verificando que não há mais dígitos após o minor
    item_pattern = re.compile(r"^\s*(\d{1,2})\.(\d{1,2})(?:\s|$|[^\d])")
    # Padrão para excluir CNPJs e números de documento
    cnpj_pattern = re.compile(r"\d{2}\.\d{3}\.\d{3}")

    # Rastrear último número maior de item encontrado
    last_major = 0
    max_major_seen = 0
    aditivo_start_line = None
    # Contador de itens sequenciais para confirmar padrão de contrato
    sequential_items_seen = 0

    for i, line in enumerate(lines):
        # Ignorar linhas que parecem CNPJs ou números de documento
        if cnpj_pattern.search(line):
            continue

        # Verificar se é um item numerado
        item_match = item_pattern.match(line)
        if item_match:
            major = int(item_match.group(1))
            minor = int(item_match.group(2))

            # Contar itens sequenciais para confirmar padrão
            if major >= last_major or (major == last_major and minor > 0):
                sequential_items_seen += 1

            max_major_seen = max(max_major_seen, major)

            # Detectar reinício de numeração (volta para números baixos após altos)
            # Só considera reinício se:
            # 1. Já vimos números >= 10 (garante que passamos por todo o contrato)
            # 2. Vimos pelo menos 20 itens sequenciais (confirma padrão de contrato)
            # 3. Agora voltou para <= 3
            if aditivo_start_line is None and major <= 3 and max_major_seen >= 10 and sequential_items_seen >= 20:
                if major < last_major:
                    # Reinício detectado - marcar início do aditivo
                    aditivo_start_line = i

                    # Procurar header de seção nas linhas anteriores
                    for j in range(max(0, i - 5), i):
                        header_match = header_pattern.match(lines[j].strip())
                        if header_match:
                            num = header_match.group(1)
                            title = header_match.group(2).strip()
                            # Só adiciona se o número do header for baixo (1, 2, 3)
                            if int(num) <= 3:
                                sections.append({
                                    "start_line": j,
                                    "item_line": i,
                                    "title": title,
                                    "prefix": f"AD{num}",
                                    "section_num": int(num)
                                })
                            break

            last_major = major

        # Detectar headers de seção SOMENTE após o início do aditivo
        if aditivo_start_line is not None and i > aditivo_start_line:
            header_match = header_pattern.match(line.strip())
            if header_match:
                num = header_match.group(1)
                title = header_match.group(2).strip()
                # Só considera headers com números baixos (séries do aditivo)
                if int(num) <= 10:  # Aditivos geralmente têm poucas séries
                    # Verificar se já não adicionamos esta seção
                    if not any(s["start_line"] == i for s in sections):
                        sections.append({
                            "start_line": i,
                            "item_line": i,
                            "title": title,
                            "prefix": f"AD{num}",
                            "section_num": int(num)
                        })

    return sections

def prefix_aditivo_items(servicos: list, texto: str) -> list:
    """
    Prefixa itens do aditivo contratual para diferenciá-los do contrato.

    Detecta seções de aditivo e adiciona prefixo de reinício (Sx-) aos itens.
    O aditivo é indicado via metadado _section="AD".

    A lógica identifica itens do aditivo buscando-os no texto após a linha
    de reinício de numeração. Apenas itens com números 1, 2 ou 3 são
    candidatos a prefixação.

    Args:
        servicos: Lista de serviços extraídos
        texto: Texto extraído do documento

    Returns:
        Lista de serviços com itens do aditivo prefixados
    """
    if not servicos or not texto:
        return servicos

    # Detectar seções do aditivo
    aditivo_sections = detect_aditivo_sections(texto)
    if not aditivo_sections:
        return servicos

    # Encontrar a linha de início do aditivo (menor start_line das seções)
    # Usa start_line (header da seção) ao invés de item_line para incluir
    # descrições que aparecem entre o header e o primeiro item
    aditivo_start_line = min(s["start_line"] for s in aditivo_sections)
    lines = texto.split("\n")

    def strip_restart_prefix(item_value: str) -> str:
        if not item_value:
            return ""
        return re.sub(r"^(S\d+-|AD-)", "", item_value, flags=re.IGNORECASE).strip()

    def max_restart_prefix_index(items: list) -> int:
        max_idx = 1
        for s in items:
            item_val = str(s.get("item") or "").strip()
            match = re.match(r"^S(\d+)-", item_val, re.IGNORECASE)
            if match:
                try:
                    max_idx = max(max_idx, int(match.group(1)))
                except ValueError:
                    continue
        return max_idx

    def apply_restart_prefix(item_value: str, segment_idx: int) -> tuple[str, str]:
        item_str = strip_restart_prefix(str(item_value or "").strip())
        if not item_str:
            return "", ""
        if segment_idx <= 1:
            return item_str, ""
        prefix = f"S{segment_idx}"
        return f"{prefix}-{item_str}", prefix

    # Criar mapeamento de prefixo de item para seção do aditivo (Sx)
    aditivo_prefixes = {}
    next_segment = max_restart_prefix_index(servicos) + 1
    for section in sorted(aditivo_sections, key=lambda s: s.get("start_line", 0)):
        section_num = section["section_num"]
        if section_num not in aditivo_prefixes:
            aditivo_prefixes[section_num] = next_segment
            next_segment += 1

    # Função para verificar se um item aparece após a linha de início do aditivo
    def find_item_in_text(item_str: str) -> tuple:
        """
        Busca um item no texto e retorna (encontrado_antes, encontrado_depois, aditivo_tem_quantidade).
        """
        # Padrão para encontrar o item exato
        pattern = re.compile(rf"^\s*{re.escape(item_str)}(?:\s|$)", re.MULTILINE)
        found_before = False
        found_after = False
        aditivo_has_qty = False

        for i, line in enumerate(lines):
            if pattern.match(line):
                if i < aditivo_start_line:
                    found_before = True
                else:
                    found_after = True
                    # Verificar se o texto do aditivo tem quantidade (número no final)
                    # Padrões como "UN 6", "M 310", "KG 63,2"
                    if re.search(r"\b(?:UN|M|KG|M2|M3|L|VB|CJ)\s+\d+", line, re.IGNORECASE):
                        aditivo_has_qty = True

        return (found_before, found_after, aditivo_has_qty)

    def is_good_description(desc: str) -> bool:
        """Verifica se uma descrição extraída tem qualidade suficiente."""
        if not desc:
            return False
        # Mínimo de caracteres
        if len(desc) < 10:
            return False
        # Deve ter palavras reais (não só números/códigos)
        words = re.findall(r"[A-Za-zÀ-ÿ]{3,}", desc)
        if len(words) < 2:
            return False
        # Não deve ser só código de referência (AF_XX/XXXX)
        if re.match(r"^AF_\d+/\d+$", desc.strip()):
            return False
        return True

    def extract_aditivo_item_info(item_str: str, major: int) -> dict:
        """
        Extrai informações de um item da seção de aditivo no texto.
        Usa múltiplos padrões para diferentes formatos de documento.

        Formatos suportados:
        1. Tudo em uma linha: "1.1 DESCRIÇÃO COMPLETA UN 100"
        2. Descrição antes do item:
           "INÍCIO DA DESCRIÇÃO"
           "1.1 CONTINUAÇÃO UN 100"
        3. Formato de tabela com colunas separadas
        """
        result: Dict[str, Any] = {"descricao": None, "quantidade": None, "unidade": None, "_source": "text"}

        # Padrão para encontrar o item no texto do aditivo
        pattern = re.compile(rf"^\s*{re.escape(item_str)}(?:\s|$)", re.MULTILINE)

        for i, line in enumerate(lines):
            if i < aditivo_start_line:
                continue  # Ignorar linhas antes do aditivo

            if not pattern.match(line):
                continue

            # Encontrou o item na seção do aditivo
            logger.debug(f"[ADITIVO] Encontrou item {item_str} na linha {i}: {line[:100]}")

            # Extrair quantidade e unidade do final da linha
            qty_match = re.search(r"\b(UN|M|KG|M2|M3|M²|M³|L|VB|CJ|PC|GL|un|m|m²|m³)\s+([\d,.]+)\s*$", line, re.IGNORECASE)
            if qty_match:
                result["unidade"] = qty_match.group(1).upper().replace("²", "2").replace("³", "3")
                qty_str = qty_match.group(2).replace(",", ".")
                try:
                    result["quantidade"] = float(qty_str)
                except ValueError:
                    pass

            # PADRÃO 1: Descrição completa na mesma linha
            # Ex: "1.1 ESCAVAÇÃO MANUAL DE VALA M 100"
            full_match = re.match(
                rf"^\s*{re.escape(item_str)}\s+([A-Za-zÀ-ÿ][\w\s\-,./()À-ÿ]+?)(?:\s+(?:UN|M|KG|M2|M3|M²|M³|L|VB|CJ|PC|GL)\s+[\d,.]+)?\s*$",
                line, re.IGNORECASE
            )
            if full_match:
                desc = full_match.group(1).strip()
                if is_good_description(desc):
                    result["descricao"] = desc
                    logger.debug(f"[ADITIVO] Padrão 1 (linha única): {desc[:50]}")
                    break

            # PADRÃO 2: Descrição começa na linha ANTERIOR (formato comum em tabelas)
            # Ex: "ESCAVAÇÃO MANUAL DE VALA COM PROFUNDIDADE..."
            #     "1.1 1,30 M. AF_02/2021 m³ 100"
            desc_parts: List[str] = []

            # Extrair texto após o número do item na linha atual
            after_item = re.sub(rf"^\s*{re.escape(item_str)}\s*", "", line)
            # Remover unidade/quantidade do final
            after_item = re.sub(r"\s*(?:UN|M|KG|M2|M3|M²|M³|L|VB|CJ|PC|GL|un|m|m²|m³)\s+[\d,.]+\s*$", "", after_item, flags=re.IGNORECASE).strip()

            # Buscar linhas anteriores que fazem parte da descrição
            for j in range(i - 1, max(aditivo_start_line - 1, i - 4), -1):
                prev_line = lines[j].strip()
                if not prev_line:
                    continue
                # Parar se encontrar outro item numerado ou header
                if re.match(r"^\d+\.\d+\s", prev_line) or re.match(r"^\d+\s+[A-Z][a-zÀ-ÿ]", prev_line):
                    break
                # Parar se encontrar linha com unidade/quantidade (outro item)
                if re.search(r"\b(?:UN|M|KG|M2|M3|M²|M³|L|VB|CJ|PC|GL)\s+[\d,.]+\s*$", prev_line, re.IGNORECASE):
                    break
                # Linha parece ser descrição (tem palavras)
                if re.search(r"[A-Za-zÀ-ÿ]{3,}", prev_line) and len(prev_line) > 5:
                    desc_parts.insert(0, prev_line)

            # Montar descrição: linhas anteriores + texto após item
            if desc_parts:
                full_desc = " ".join(desc_parts)
                if after_item and len(after_item) > 2:
                    full_desc += " " + after_item
                full_desc = full_desc.strip()
                if is_good_description(full_desc):
                    result["descricao"] = full_desc
                    logger.debug(f"[ADITIVO] Padrão 2 (linhas anteriores): {full_desc[:50]}")
                    break

            # PADRÃO 3: Descrição na próxima linha
            if i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                if next_line and not re.match(r"^\d+\.\d+", next_line):
                    if is_good_description(next_line):
                        result["descricao"] = next_line[:200]
                        logger.debug(f"[ADITIVO] Padrão 3 (próxima linha): {next_line[:50]}")

            break  # Usar a primeira ocorrência encontrada no aditivo

        return result

    # Criar índice de itens para detectar headers
    # Um item X.Y é header se existem sub-itens X.Y.Z no documento
    item_set = set()
    planilha_candidates: dict[str, dict[int, int]] = {}
    for s in servicos:
        item_val = s.get("item")
        if item_val:
            base_item = strip_restart_prefix(str(item_val))
            if base_item:
                item_set.add(base_item)
                planilha_id = s.get("_planilha_id")
                if planilha_id is not None:
                    counts = planilha_candidates.setdefault(base_item, {})
                    counts[planilha_id] = counts.get(planilha_id, 0) + 1

    planilha_by_code: dict[str, int] = {}
    for code, counts in planilha_candidates.items():
        planilha_by_code[code] = max(counts.items(), key=lambda x: x[1])[0]

    def is_header_item(item_str: str) -> bool:
        """
        Verifica se um item é um header (título de seção) no contrato.
        Um item é header se existem sub-itens dele na lista.
        Ex: 2.1 é header se existe 2.1.1, 2.1.2, etc.
        """
        prefix = item_str + "."
        for other_item in item_set:
            if other_item.startswith(prefix):
                return True
        return False

    # Prefixar itens do aditivo
    logger.debug(f"[ADITIVO] Iniciando prefixação. Seções detectadas: {aditivo_prefixes}")
    logger.debug(f"[ADITIVO] Linha de início do aditivo: {aditivo_start_line}")

    result = []
    for s in servicos:
        item = s.get("item")
        if not item:
            result.append(s)
            continue

        item_tuple = parse_item_tuple(strip_restart_prefix(str(item)))
        if not item_tuple:
            result.append(s)
            continue

        major = item_tuple[0]

        # Só considerar itens com números baixos (1, 2, 3) que são candidatos
        if major not in aditivo_prefixes:
            result.append(s)
            continue

        # Só processar itens de profundidade 2 (ex: 1.1, 2.3)
        # Itens de profundidade 1 (ex: 2, 3) são headers de seção
        # Itens de profundidade > 2 (ex: 1.1.1) são sub-itens do contrato
        if len(item_tuple) != 2:
            result.append(s)
            continue

        # Verificar onde o item aparece no texto
        item_str = strip_restart_prefix(str(item))
        found_before, found_after, aditivo_has_qty = find_item_in_text(item_str)
        logger.debug(f"[ADITIVO] Item {item_str}: antes={found_before}, depois={found_after}, desc_orig={s.get('descricao', '')[:30]}")

        # Se aparece APENAS após a linha de início do aditivo, é do aditivo
        # Se aparece em ambos (antes e depois), gerar DUAS versões:
        # - Uma para o contrato (sem prefixo)
        # - Uma para o aditivo (com prefixo e descrição extraída do texto do aditivo)
        if found_after and not found_before:
            # Item exclusivo do aditivo - prefixar
            s_copy = s.copy()
            new_item, prefix = apply_restart_prefix(item, aditivo_prefixes.get(major, 1))
            s_copy["item"] = new_item
            s_copy["_section"] = "AD"
            if prefix:
                s_copy["_item_prefix"] = prefix
            if s.get("_planilha_id") is not None:
                s_copy["_planilha_id"] = s.get("_planilha_id")
            if s.get("_planilha_label"):
                s_copy["_planilha_label"] = s.get("_planilha_label")

            # HÍBRIDO: tentar extrair do texto, fallback para IA
            aditivo_info = extract_aditivo_item_info(item_str, major)
            text_desc = aditivo_info.get("descricao")
            ai_desc = s.get("descricao", "")

            if text_desc and is_good_description(text_desc):
                s_copy["descricao"] = text_desc
                s_copy["_desc_source"] = "texto"
            else:
                # Fallback para descrição da IA (já está no s_copy)
                s_copy["_desc_source"] = "IA"

            if aditivo_info["quantidade"] is not None:
                s_copy["quantidade"] = aditivo_info["quantidade"]
            if aditivo_info["unidade"]:
                s_copy["unidade"] = aditivo_info["unidade"]

            logger.debug(f"[ADITIVO] Item exclusivo: {s_copy['item']} -> {s_copy['descricao'][:40]} (fonte: {s_copy['_desc_source']})")
            result.append(s_copy)
        elif found_after and found_before:
            # Item aparece em ambos os lugares (contrato E aditivo)
            # Verificar se é um HEADER no contrato (tem sub-itens)
            is_header = is_header_item(item_str)

            if is_header:
                # Item é HEADER no contrato (ex: 2.1 com sub-itens 2.1.1, 2.1.2)
                # NÃO manter versão do contrato, pois é apenas título de seção
                logger.debug(f"[ADITIVO] Item {item_str} é HEADER no contrato (tem sub-itens), ignorando versão contrato")
            else:
                # Item é real no contrato, manter versão sem prefixo
                result.append(s)
                logger.debug(f"[ADITIVO] Mantendo versão contrato: {item_str} -> {s.get('descricao', '')[:40]}")

            # Criar versão do aditivo com descrição extraída do texto (híbrido)
            aditivo_info = extract_aditivo_item_info(item_str, major)

            # HÍBRIDO: usar descrição do texto se boa, senão fallback para IA
            text_desc = aditivo_info.get("descricao")
            ai_desc = s.get("descricao", "")
            text_desc_is_good = text_desc is not None and is_good_description(text_desc)
            final_desc = text_desc if text_desc_is_good else ai_desc
            desc_source = "texto" if text_desc_is_good else "IA"

            logger.debug(f"[ADITIVO] Híbrido: text_desc={text_desc[:40] if text_desc else 'None'}, usando={desc_source}")

            # Criar versão do aditivo
            new_item, prefix = apply_restart_prefix(item, aditivo_prefixes.get(major, 1))
            s_aditivo = {
                "item": new_item,
                "_section": "AD",
                "_desc_source": desc_source,
                "descricao": final_desc,
                "quantidade": aditivo_info["quantidade"] if aditivo_info["quantidade"] is not None else s.get("quantidade", 0),
                "unidade": aditivo_info["unidade"] or s.get("unidade", ""),
            }
            if prefix:
                s_aditivo["_item_prefix"] = prefix
            if s.get("_planilha_id") is not None:
                s_aditivo["_planilha_id"] = s.get("_planilha_id")
            if s.get("_planilha_label"):
                s_aditivo["_planilha_label"] = s.get("_planilha_label")
            result.append(s_aditivo)
            logger.debug(f"[ADITIVO] Criada versão aditivo: {s_aditivo['item']} -> {s_aditivo['descricao'][:40]} (fonte: {desc_source})")
        else:
            # Item do contrato
            result.append(s)

    # FASE 1.5: Detectar itens do CONTRATO que não foram extraídos pela IA
    # Alguns itens podem estar após quebra de página e não serem capturados
    result_items = set(r.get("item", "") for r in result)
    logger.info(f"[CONTRATO-FASE1.5] Detectando itens faltantes do contrato (linhas 0-{aditivo_start_line})")

    # Padrão para encontrar itens no texto do contrato (X.Y ou X.Y.Z seguido de descrição)
    # Ex: "10.5 EXTINTOR DE INCÊNDIO..." ou "2.6.2 CABO DE COBRE..."
    contrato_item_pattern = re.compile(
        r"^\s*(\d{1,2}\.\d{1,2}(?:\.\d{1,2})?)\s+([A-ZÀ-ÚÇ][\w\sÀ-ÚÇ,.\-/()]+?)(?:\s*,?\s*(UN|M|KG|M2|M3|M²|M³|L|VB|CJ|PC|GL|und|un|m|m²|m³|pç|pc)\s+([\d,.]+))?\s*$",
        re.IGNORECASE
    )

    items_added = 0
    for i, line in enumerate(lines):
        # Apenas linhas do contrato (antes do aditivo)
        if aditivo_start_line and i >= aditivo_start_line:
            break

        match = contrato_item_pattern.match(line)
        if not match:
            continue

        item_str = match.group(1)
        descricao = match.group(2).strip() if match.group(2) else ""
        unidade = match.group(3) or ""
        quantidade_str = match.group(4) or ""

        # Verificar se este item já existe no resultado
        if item_str in result_items:
            continue

        # Ignorar se descrição parece ser cabeçalho de seção (muito curta)
        if len(descricao) < 15:
            continue

        # Converter quantidade
        quantidade = 0.0
        if quantidade_str:
            try:
                quantidade = float(quantidade_str.replace(",", "."))
            except ValueError:
                quantidade = 0.0

        # Item do contrato não capturado pela IA - adicionar
        s_new = {
            "item": item_str,
            "_desc_source": "texto",
            "_auto_detected": True,
            "descricao": descricao,
            "quantidade": quantidade,
            "unidade": unidade.upper() if unidade else "",
        }
        result.append(s_new)
        result_items.add(item_str)
        items_added += 1
        logger.info(f"[CONTRATO-FASE1.5] Item faltante detectado: {item_str} -> {descricao[:50]} (linha {i})")

    if items_added > 0:
        logger.info(f"[CONTRATO-FASE1.5] {items_added} itens do contrato adicionados automaticamente")

    # FASE 2: Detectar itens do aditivo que não foram extraídos pela IA
    # Alguns itens existem apenas no aditivo e não foram capturados
    result_items = set(r.get("item", "") for r in result)
    logger.info(f"[ADITIVO-FASE2] INICIANDO. result_items={sorted(result_items)[:20]}... (total: {len(result_items)})")
    logger.info(f"[ADITIVO-FASE2] aditivo_start_line={aditivo_start_line}, total_lines={len(lines)}")
    logger.info(f"[ADITIVO-FASE2] aditivo_prefixes={aditivo_prefixes}")

    # Padrão para encontrar itens no texto do aditivo (X.Y seguido de texto)
    # Descrição pode começar com letra ou número (ex: "2.2 4 UTILIZAÇÕES...")
    aditivo_item_pattern = re.compile(r"^\s*(\d+\.\d+)\s+(\S.*?)(?:\s+(UN|M|KG|M2|M3|M²|M³|L|VB|CJ|PC|GL|un|m|m²|m³)\s+([\d,.]+))?\s*$", re.IGNORECASE)

    lines_checked = 0
    for i, line in enumerate(lines):
        if i < aditivo_start_line:
            continue
        lines_checked += 1

        match = aditivo_item_pattern.match(line)
        # Log linhas que começam com número para debug
        if line.strip() and re.match(r"^\s*\d+\.\d+", line):
            logger.info(f"[ADITIVO-FASE2] Linha {i}: {line[:80]!r} -> match={bool(match)}")

        if not match:
            continue

        item_str = match.group(1)
        item_tuple = parse_item_tuple(item_str)
        if not item_tuple or len(item_tuple) != 2:
            continue

        major = item_tuple[0]
        if major not in aditivo_prefixes:
            continue

        ad_item, ad_prefix = apply_restart_prefix(item_str, aditivo_prefixes.get(major, 1))

        # Verificar se este item já existe no resultado
        if ad_item in result_items or item_str in result_items:
            continue

        # Item do aditivo não capturado pela IA - extrair e adicionar
        logger.info(f"[ADITIVO-FASE2] Candidato encontrado: {item_str} (linha {i})")

        aditivo_info = extract_aditivo_item_info(item_str, major)
        logger.info(f"[ADITIVO-FASE2] Info para {item_str}: desc={bool(aditivo_info.get('descricao'))}, qty={aditivo_info.get('quantidade')}")

        if aditivo_info.get("descricao") or aditivo_info.get("quantidade") is not None:
            s_new = {
                "item": ad_item,
                "_section": "AD",
                "_desc_source": "texto",
                "_auto_detected": True,
                "descricao": aditivo_info.get("descricao") or "",
                "quantidade": aditivo_info.get("quantidade") or 0,
                "unidade": aditivo_info.get("unidade") or "",
            }
            if ad_prefix:
                s_new["_item_prefix"] = ad_prefix
            base_planilha = planilha_by_code.get(item_str)
            if base_planilha is not None:
                s_new["_planilha_id"] = base_planilha
            result.append(s_new)
            result_items.add(ad_item)
            logger.info(f"[ADITIVO] Adicionado item auto-detectado: {ad_item} -> {str(s_new['descricao'])[:40]}")

    logger.info(f"[ADITIVO-FASE2] FIM. Linhas verificadas: {lines_checked}")

    # FASE 2.5: Remover duplicatas EXATAS (mesmo item + descrição + quantidade + unidade)
    # ANTES de renomear com sufixo. Isso evita criar sufixo -A quando é duplicata exata
    seen_exact: set[tuple] = set()
    exact_deduped = []
    exact_removed = 0
    for r in result:
        item = r.get("item", "")
        desc = (r.get("descricao") or "").strip()[:100].lower()
        qty = r.get("quantidade", 0)
        unit = (r.get("unidade") or "").strip().upper()
        key = (item, desc, qty, unit)
        if key in seen_exact:
            exact_removed += 1
            logger.info(f"[DEDUP-EXATO] Removido duplicata exata: {item} ({desc[:40]}... {qty} {unit})")
            continue
        seen_exact.add(key)
        exact_deduped.append(r)

    if exact_removed > 0:
        logger.info(f"[DEDUP-EXATO] {exact_removed} duplicatas exatas removidas")

    # Tratar itens com MESMO NÚMERO mas DIFERENTES descrições adicionando sufixo alfabético (-A, -B, etc.)
    # Isso preserva todos os itens quando o documento original tem erro de numeração (ex: dois itens 10.4 diferentes)
    item_counts: dict[str, int] = {}
    deduped_result = []
    duplicates_renamed = 0

    for r in exact_deduped:
        item = r.get("item", "")
        if item:
            count = item_counts.get(item, 0)
            if count == 0:
                # Primeira ocorrência - manter item original
                item_counts[item] = 1
            else:
                # Item duplicado (mesmo número, descrição diferente) - adicionar sufixo alfabético (-A, -B, -C, ...)
                suffix = chr(ord('A') + count - 1)  # 1->A, 2->B, 3->C
                new_item = f"{item}-{suffix}"
                r["item"] = new_item
                item_counts[item] = count + 1
                duplicates_renamed += 1
                logger.info(f"[DEDUP] Item duplicado renomeado: {item} -> {new_item}")
        deduped_result.append(r)

    if duplicates_renamed > 0:
        logger.info(f"[DEDUP] {duplicates_renamed} itens duplicados renomeados com sufixo alfabético")

    # FASE 3: Filtrar itens problemáticos da extração da IA
    # 3.1: Filtrar itens com seção pai inexistente (ex: 11.10.5 quando não existe 11.10)
    # Extrair seções X.Y que existem no texto
    secoes_texto = set()
    for linha in lines:
        match = re.match(r"^\s*(\d{1,2}\.\d{1,2})\s+[A-Z]", linha)
        if match:
            secoes_texto.add(match.group(1))

    # Verificar itens X.Y.Z cujo pai X.Y não existe
    filtered_result = []
    items_removed_secao = 0
    for r in deduped_result:
        item = r.get("item", "")
        # Ignorar itens do aditivo
        if r.get("_section") == "AD":
            filtered_result.append(r)
            continue

        # Remover sufixo -A, -B se existir para análise
        base_item = re.sub(r"-[A-Z]$", "", item)
        parts = base_item.split(".")

        if len(parts) == 3:  # Item X.Y.Z
            parent = f"{parts[0]}.{parts[1]}"  # Seção pai X.Y
            # Verificar se seção pai existe no texto
            if parent not in secoes_texto:
                # Verificar se há irmãos (outros filhos de X.Y)
                siblings = [
                    r2.get("item", "") for r2 in deduped_result
                    if re.sub(r"-[A-Z]$", "", r2.get("item", "")).startswith(parent + ".")
                    and r2.get("item", "") != item
                ]
                if not siblings:
                    # Seção pai não existe e não há irmãos - item é provavelmente erro
                    items_removed_secao += 1
                    logger.info(f"[VALIDACAO] Removido item com seção inexistente: {item} (pai {parent} não existe)")
                    continue
        filtered_result.append(r)

    if items_removed_secao > 0:
        logger.info(f"[VALIDACAO] {items_removed_secao} itens removidos por seção pai inexistente")

    # 3.2: Filtrar duplicatas entre contrato e aditivo
    # Se item do contrato tem mesma desc+qtd que item do aditivo, é erro de extração
    aditivo_map: dict[tuple, str] = {}
    for r in filtered_result:
        item = r.get("item", "")
        if r.get("_section") == "AD":
            # Criar chave: descrição normalizada + quantidade
            desc = (r.get("descricao") or "").strip()[:50].lower()
            qtd = r.get("quantidade", 0)
            # Item base sem prefixo e sem sufixo
            base_item = re.sub(r"-[A-Z]$", "", strip_restart_prefix(item))
            aditivo_map[(desc, qtd, base_item)] = item

    final_result = []
    items_removed_dup = 0
    for r in filtered_result:
        item = r.get("item", "")
        # Verificar apenas itens do contrato com sufixo (-A, -B, etc.)
        if r.get("_section") != "AD" and re.search(r"-[A-Z]$", item):
            desc = (r.get("descricao") or "").strip()[:50].lower()
            qtd = r.get("quantidade", 0)
            base_item = re.sub(r"-[A-Z]$", "", item)
            dup_key = (desc, qtd, base_item)

            if dup_key in aditivo_map:
                # Item do contrato é duplicata de item do aditivo
                items_removed_dup += 1
                logger.info(f"[VALIDACAO] Removido duplicata contrato/aditivo: {item} (duplicata de {aditivo_map[dup_key]})")
                continue
        final_result.append(r)

    if items_removed_dup > 0:
        logger.info(f"[VALIDACAO] {items_removed_dup} itens removidos por duplicata contrato/aditivo")

    deduped_result = final_result

    # Log resumo
    aditivo_count = sum(1 for r in deduped_result if r.get("_section") == "AD")
    contrato_count = len(deduped_result) - aditivo_count
    auto_detected = sum(1 for r in deduped_result if r.get("_auto_detected"))
    logger.info(f"[ADITIVO] Resultado: {len(deduped_result)} itens total ({contrato_count} contrato, {aditivo_count} aditivo, {auto_detected} auto-detectados)")

    return deduped_result

