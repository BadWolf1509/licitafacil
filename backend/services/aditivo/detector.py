"""
Detector de seções de aditivo.

Identifica seções de aditivo contratual em documentos de atestado.
"""

import re
from typing import List, Dict, Any


def detect_aditivo_sections(texto: str) -> List[Dict[str, Any]]:
    """
    Detecta seções de aditivo contratual no texto extraído.

    Identifica reinício de numeração (quando itens voltam para 1.x após números altos)
    e headers de seção do aditivo. Só considera seções APÓS o reinício.

    Args:
        texto: Texto extraído do documento

    Returns:
        Lista de seções: [{"start_line": int, "item_line": int, "title": str,
                          "prefix": str, "section_num": int}, ...]
    """
    if not texto:
        return []

    lines = texto.split("\n")
    sections: List[Dict[str, Any]] = []

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
            if (aditivo_start_line is None and
                major <= 3 and
                max_major_seen >= 10 and
                sequential_items_seen >= 20):

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


def get_aditivo_start_line(sections: List[Dict[str, Any]]) -> int:
    """
    Retorna a linha de início do aditivo a partir das seções detectadas.

    Args:
        sections: Lista de seções detectadas

    Returns:
        Número da linha de início do aditivo, ou -1 se não houver seções
    """
    if not sections:
        return -1
    return min(s["start_line"] for s in sections)
