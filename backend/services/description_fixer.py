"""
Corretor de descrições para garantir 100% de fidelidade ao PDF original.
Usa texto_extraido como fonte da verdade.
"""
import re
from typing import Dict, List, Optional, Tuple

from services.extraction import is_corrupted_text, normalize_item_code, normalize_accents
from services.extraction.patterns import Patterns


def _build_line_to_page_map(texto: str) -> Dict[int, int]:
    """
    Constrói mapeamento de número de linha para número de página.

    Detecta marcadores de página no texto (ex: "Página 3 / 10") e
    atribui cada linha à página correspondente.

    Args:
        texto: Texto extraído do PDF

    Returns:
        Dict mapeando linha (1-indexed) -> número da página
    """
    line_to_page: Dict[int, int] = {}
    lines = texto.split('\n')
    current_page = 1

    for i, line in enumerate(lines):
        line_num = i + 1  # 1-indexed
        line_stripped = line.strip()

        # Verificar se contém marcador de página
        page_match = Patterns.PAGE_MARKER.search(line_stripped)
        if page_match:
            current_page = int(page_match.group(1))

        # Atribuir página atual à linha
        line_to_page[line_num] = current_page

    return line_to_page


def fix_descriptions(servicos: List[Dict], texto_extraido: str) -> List[Dict]:
    """
    Corrige as descrições de todos os itens usando o texto original.

    Args:
        servicos: Lista de serviços extraídos (pode conter descrições erradas)
        texto_extraido: Texto bruto extraído do PDF (fonte da verdade)

    Returns:
        Lista de serviços com descrições corrigidas
    """
    if not texto_extraido or not servicos:
        return servicos

    # Construir índice de TODAS as linhas por item (não só primeira)
    item_lines = _build_item_line_index(texto_extraido)

    # Construir mapeamento linha -> página
    line_to_page = _build_line_to_page_map(texto_extraido)

    # Corrigir cada serviço
    for servico in servicos:
        original_item = servico.get('item', '')
        item = normalize_item_code(original_item, strip_suffixes=True)
        if not item:
            continue

        # Buscar todas as linhas candidatas para este item
        candidates = item_lines.get(item, [])
        if not candidates:
            continue

        # Descrição atual
        current_desc = servico.get('descricao', '')

        # Página do serviço (se disponível)
        servico_page = servico.get('_page')

        # Encontrar a melhor correspondência baseado em quantidade/unidade/página
        # Passa o item original (com prefixo S1-/S2-) para selecionar grupo correto
        best_match = _find_best_match(
            candidates,
            item,
            servico.get('unidade'),
            servico.get('quantidade'),
            current_desc,
            original_item,
            servico_page,
            line_to_page
        )

        if best_match:
            servico['descricao'] = best_match['descricao']
            servico['_desc_source'] = 'texto_original'
            servico['_linha_original'] = best_match['linha']
            # Marcar se descrição é corrompida/inadequada
            if best_match.get('desc_corrupted'):
                servico['_desc_corrupted'] = True
        else:
            # Limpar campos de tracking antigos se não encontrou match válido
            servico.pop('_desc_source', None)
            servico.pop('_linha_original', None)
            servico.pop('_desc_corrupted', None)

    return servicos


# Prefixos que indicam rodapé/cabeçalho (não continuação)
STOP_PREFIXES = (
    "CNPJ", "CPF", "PREFEITURA", "CONSELHO", "CREA", "CEP",
    "EMAIL", "E-MAIL", "TEL", "TELEFONE", "IMPRESSO", "PÁGINA",
    "PAGINA", "DOCUSIGN", "HTTP", "WWW"
)

# Tokens típicos de rodapé/certificação que podem aparecer invertidos no OCR
REVERSED_FOOTER_TOKENS = (
    "CONSELHO", "REGISTRADO", "DOCUMENTO", "CERTIDAO", "IMPRESSO",
    "CHAVE", "CREA", "AGRONOMIA", "ENGENHARIA", "CONFERIR",
    "FOLHAS", "QRCODE", "QR", "PAGINA", "PAG"
)

# Padrão para detectar linhas de rodapé com local/data
# Ex: "ALAGOA NOVA/PB 08 DE OUTUBRO DE 2025"
FOOTER_DATE_PATTERN = re.compile(
    r'[A-Z\s]+/[A-Z]{2}\s+\d{1,2}\s+DE\s+(JANEIRO|FEVEREIRO|MARÇO|MARCO|ABRIL|MAIO|JUNHO|'
    r'JULHO|AGOSTO|SETEMBRO|OUTUBRO|NOVEMBRO|DEZEMBRO)\s+DE\s+\d{4}',
    re.IGNORECASE
)


def _is_valid_prefix_line(prev_line: str) -> bool:
    """
    Verifica se uma linha anterior é válida para ser prefixada à descrição.

    Args:
        prev_line: Linha anterior (já stripped)

    Returns:
        True se a linha pode ser usada como prefixo
    """
    if not prev_line or len(prev_line) < 10:
        return False

    # Rejeitar se é outro item
    if Patterns.ITEM_PATTERN.match(prev_line):
        return False

    # Rejeitar se é cabeçalho de seção
    if Patterns.SECTION_HEADER_BROAD.match(prev_line):
        return False

    return True


def _is_description_fragment(desc: str, prev_line: str) -> bool:
    """
    Verifica se uma descrição parece ser um fragmento que precisa da linha anterior.

    Args:
        desc: Texto da descrição (entre código e unidade/quantidade)
        prev_line: Linha anterior para verificar continuação

    Returns:
        True se a descrição parece ser um fragmento
    """
    if not desc:
        return True

    first_word = desc.split()[0] if desc.split() else ""

    # Começa com parêntese ou colchete
    if re.match(r'^[(\[]', desc):
        return True

    # Começa com letra minúscula
    if desc[0].islower():
        return True

    # Começa com preposição/conjunção
    if re.match(r'^(DE|DA|DO|E|OU|COM|PARA|EM|NO|NA)\s', desc, re.I):
        return True

    # Palavra muito curta (MM, CM, etc.)
    if re.match(r'^[A-Z]{1,3}[,\s]', desc):
        return True

    # Começa com especificação técnica (número + unidade)
    # Ex: "20A/250V", "6MM²", "4,00 MM²"
    if re.match(r'^\d+[A-Z/,]', desc):
        return True
    # Começa com traço de argamassa (ex: "1:2:8", "1:3")
    if re.match(r'^\d+(?::\d+){1,3}\b', desc):
        return True

    # Linha anterior termina com palavra de continuação
    if prev_line and Patterns.CONTINUATION_WORDS_END.search(prev_line):
        return True

    # Verificar se linha anterior termina com palavra incompleta
    # e descrição começa com adjetivo
    if prev_line:
        prev_last_word = prev_line.split()[-1] if prev_line.split() else ""
        prev_ends_clean = bool(
            prev_last_word and
            not prev_last_word.endswith(('.', ',', ';', ':')) and
            'AF_' not in prev_last_word
        )

        first_word_clean = first_word.rstrip(',.;:')
        first_word_upper = first_word_clean.upper() if first_word_clean else ""
        # Evitar tratar substantivos técnicos como adjetivos (ex: DISJUNTOR)
        noun_starters = {
            'CABO', 'TUBO', 'CAIXA', 'TOMADA', 'DISJUNTOR', 'DISJUNTORES', 'QUADRO',
            'PONTO', 'ELETRODUTO', 'INTERRUPTOR', 'LUMINARIA', 'LAMPADA',
            'TORNEIRA', 'REGISTRO', 'VALVULA', 'TANQUE', 'CHUVEIRO',
            'PORTA', 'JANELA', 'VIDRO', 'PINTURA', 'REVESTIMENTO',
            'ARGAMASSA', 'CONCRETO', 'ALVENARIA', 'DEMOLICAO', 'DEMOLIÇÃO',
            'ESCAVACAO', 'ESCAVAÇÃO', 'FORNECIMENTO', 'EXECUCAO', 'EXECUÇÃO',
            'INSTALACAO', 'INSTALAÇÃO', 'ASSENTAMENTO',
            'CALHA', 'MOLA', 'TRILHO', 'RALO', 'VISOR', 'FECHADURA',
            'PISO', 'TETO', 'FORRO', 'RODAPE', 'RODAPÉ', 'SOLEIRA',
            'PEITORIL', 'BANCADA', 'GUARDA', 'CORRIMAO', 'CORRIMÃO',
            'GRAMA', 'GRAMADO', 'JARDIM', 'PAISAGISMO', 'PLANTIO',
            'MEIO-FIO', 'SARJETA', 'CALCADA', 'CALÇADA', 'PASSEIO'
        }
        is_noun_starter = (
            first_word_upper in noun_starters or
            (first_word_upper.endswith('S') and first_word_upper[:-1] in noun_starters)
        )
        first_word_is_adjective = bool(
            first_word_clean and not is_noun_starter and
            # Adjetivos singulares (INTERNA, EXTERNA, etc.) e plurais (INTERNAS, EXTERNAS)
            (re.match(r'^[A-ZÁÉÍÓÚÀÂÊÔ]{4,}[AOEIAS]$', first_word_clean) or
             re.match(r'^[A-ZÁÉÍÓÚÀÂÊÔ]{4,}(AL|AR|ER|OR|VEL|AIS|EIS|OS)$', first_word_clean, re.I))
        )

        if prev_ends_clean and first_word_is_adjective:
            return True

        # Verificar se forma palavra composta comum em descrições técnicas
        # Ex: "CAIXA" + "ELÉTRICA", "TOMADA" + "RESIDENCIAL", "CABO" + "FLEXÍVEL"
        prev_last_upper = prev_last_word.upper() if prev_last_word else ""
        first_upper = first_word_clean.upper() if first_word_clean else ""

        # Pares comuns de substantivo + adjetivo em construção civil
        compound_pairs = {
            'CAIXA': {'ELÉTRICA', 'ELETRICA', 'PLÁSTICA', 'PLASTICA'},
            'TOMADA': {'RESIDENCIAL', 'INDUSTRIAL', 'ESPECIAL'},
            'CABO': {'FLEXÍVEL', 'FLEXIVEL', 'RÍGIDO', 'RIGIDO', 'ISOLADO'},
            'DISJUNTOR': {'MONOPOLAR', 'BIPOLAR', 'TRIPOLAR', 'TERMOMAGNETICO', 'TERMOMAGNÉTICO'},
            'QUADRO': {'ELÉTRICO', 'ELETRICO', 'DISTRIBUIÇÃO', 'DISTRIBUICAO'},
            'PONTO': {'ELÉTRICO', 'ELETRICO', 'HIDRÁULICO', 'HIDRAULICO'},
            'ELETRODUTO': {'FLEXÍVEL', 'FLEXIVEL', 'RÍGIDO', 'RIGIDO', 'PVC'},
            'TUBO': {'PVC', 'GALVANIZADO', 'FLEXÍVEL', 'FLEXIVEL'},
            # Adicionados para construção civil geral
            'CONCRETO': {'INTERNA', 'INTERNAS', 'EXTERNA', 'EXTERNAS', 'INTERNO',
                         'EXTERNO', 'APARENTE', 'ARMADO', 'SIMPLES', 'MAGRO'},
            'ALVENARIA': {'INTERNA', 'INTERNAS', 'EXTERNA', 'EXTERNAS',
                          'ESTRUTURAL', 'VEDAÇÃO', 'VEDACAO'},
            'PAREDE': {'INTERNA', 'INTERNAS', 'EXTERNA', 'EXTERNAS'},
            'ESTRUTURA': {'METÁLICA', 'METALICA', 'MADEIRA'},
            'LAJE': {'MACIÇA', 'MACICA', 'NERVURADA', 'PRÉ-MOLDADA', 'PRE-MOLDADA'},
        }

        if prev_last_upper in compound_pairs:
            if first_upper in compound_pairs[prev_last_upper]:
                return True

        # Verificar se linha anterior termina com vírgula (lista)
        # e descrição parece continuar a lista
        if prev_line.rstrip().endswith(','):
            return True

    return False


def _prev_line_is_continuation(prev_line: str, lines: list | None = None, line_idx: int = 0) -> bool:
    """
    Verifica se a linha anterior parece ser continuação de OUTRO item.

    Args:
        prev_line: Linha anterior
        lines: Lista completa de linhas (para busca recursiva)
        line_idx: Índice da linha atual

    Returns:
        True se a linha parece ser continuação de outro item
    """
    if not prev_line:
        return False

    # Termina com código AF
    if Patterns.AF_CODE_END.search(prev_line):
        return True

    # Fecha parêntese seguido de texto
    if re.match(r'^[)}\]]\s*[A-Z]', prev_line):
        return True

    # Termina com ponto final e contém AF
    if prev_line.endswith('.') and 'AF_' in prev_line:
        return True

    # Se prev_line não começa com código de item, verificar se há item anterior
    # (busca recursiva para trás até encontrar item ou linha vazia)
    if lines and line_idx >= 2:
        prev_line_is_item = bool(Patterns.ITEM_PATTERN.match(prev_line))
        if not prev_line_is_item:
            # Verificar se prev_line parece ser INÍCIO de nova descrição
            # (começa com substantivo técnico comum em descrições de construção)
            prev_upper = prev_line.upper() if prev_line else ""
            tech_starters = (
                'CABO', 'TUBO', 'CAIXA', 'TOMADA', 'DISJUNTOR', 'QUADRO',
                'PONTO', 'ELETRODUTO', 'INTERRUPTOR', 'LUMINARIA', 'LAMPADA',
                'TORNEIRA', 'REGISTRO', 'VALVULA', 'TANQUE', 'CHUVEIRO',
                'PORTA', 'JANELA', 'VIDRO', 'PINTURA', 'REVESTIMENTO',
                'ARGAMASSA', 'CONCRETO', 'ALVENARIA', 'DEMOLIÇÃO', 'ESCAVAÇÃO',
                'FORNECIMENTO', 'EXECUÇÃO', 'INSTALAÇÃO', 'ASSENTAMENTO',
                # Adicionados para cobrir mais itens de construção
                'CALHA', 'MOLA', 'TRILHO', 'RALO', 'VISOR', 'FECHADURA',
                'PISO', 'TETO', 'FORRO', 'RODAPÉ', 'RODAPE', 'SOLEIRA',
                'PEITORIL', 'BANCADA', 'GUARDA', 'CORRIMÃO', 'CORRIMAO',
                # Paisagismo e áreas externas
                'GRAMA', 'GRAMADO', 'JARDIM', 'PAISAGISMO', 'PLANTIO',
                'MEIO-FIO', 'SARJETA', 'CALÇADA', 'CALCADA', 'PASSEIO'
            )
            if any(prev_upper.startswith(starter) for starter in tech_starters):
                return False  # prev_line é início de nova descrição

            # Buscar item nas linhas anteriores (máximo 5 linhas para trás)
            for j in range(line_idx - 2, max(line_idx - 7, -1), -1):
                check_line = lines[j].strip()
                if not check_line:
                    break  # Linha vazia = fim do bloco
                # Parar se encontrar header de seção (indica nova seção)
                if Patterns.SECTION_HEADER_BROAD.match(check_line):
                    break  # Header de seção = fim do bloco anterior
                # Parar se encontrar código AF (indica fim de item anterior)
                if Patterns.AF_CODE_ANYWHERE.search(check_line):
                    break  # Código AF = fim do item anterior
                if Patterns.ITEM_PATTERN.match(check_line):
                    return True  # Encontrou item anterior, prev_line é continuação

    return False


def _should_prefix_with_previous(
    desc_in_line: str,
    prev_line: str,
    lines: list | None = None,
    line_idx: int = 0
) -> bool:
    """
    Determina se deve prefixar a descrição com a linha anterior.

    Usado quando a linha tem padrão CÓDIGO ... UNIDADE QUANTIDADE no final.

    Args:
        desc_in_line: Texto entre código e unidade/quantidade
        prev_line: Linha anterior (já stripped)
        lines: Lista completa de linhas (para detectar continuação)
        line_idx: Índice da linha atual

    Returns:
        True se deve prefixar com a linha anterior
    """
    # Verificar se descrição é fragmento ou curta
    is_fragment = _is_description_fragment(desc_in_line, prev_line)
    should_prefix = is_fragment or len(desc_in_line) < 25

    if not should_prefix:
        return False

    # Verificar se linha anterior é válida para prefixar
    if not _is_valid_prefix_line(prev_line):
        return False

    # Rejeitar se linha anterior é só código AF
    if Patterns.AF_ONLY.match(prev_line):
        return False

    # Rejeitar se linha anterior é paginação
    if Patterns.PAGINATION_SIMPLE.match(prev_line):
        return False

    # Rejeitar se linha anterior é continuação de outro item
    if _prev_line_is_continuation(prev_line, lines, line_idx):
        return False

    return True


def _collect_continuation_lines(
    lines: List[str],
    start_idx: int,
    max_lines: int = 5
) -> str:
    """
    Coleta linhas de continuação após uma linha de item.

    Args:
        lines: Lista de todas as linhas do texto
        start_idx: Índice da próxima linha após o item
        max_lines: Máximo de linhas de continuação a coletar

    Returns:
        Texto concatenado das linhas de continuação
    """
    continuation_parts: list[str] = []
    j = start_idx

    while j < len(lines) and len(continuation_parts) < max_lines:
        cont_line = lines[j].strip()

        # Parar se linha vazia
        if not cont_line:
            break

        # Ignorar linhas muito curtas (provavelmente lixo de OCR)
        if len(cont_line) < 4:
            j += 1
            continue

        # Ignorar linhas de rodapé invertidas pelo OCR
        if _looks_like_reversed_footer_line(cont_line):
            j += 1
            continue

        # Ignorar linhas que parecem ser lixo de OCR (sem vogais comuns)
        # Exceção: linhas com código AF_ são válidas
        has_af = bool(Patterns.AF_CODE_ANYWHERE.search(cont_line))
        if not has_af:
            cont_lower = cont_line.lower()
            vowels_count = sum(1 for c in cont_lower if c in 'aeiouáéíóúàâêô')
            if len(cont_line) > 3 and vowels_count < len(cont_line) * 0.15:
                j += 1
                continue

            # Ignorar linhas curtas que parecem texto invertido/corrompido
            # Ex: "ohlesnoC" (Conselho invertido), "iof odartsiger" (registrado foi)
            if len(cont_line) < 25:
                # Permitir fechamento de parênteses em continuação curta
                if ')' in cont_line:
                    prev_line = lines[j - 1].strip() if j - 1 >= 0 else ""
                    if prev_line.count('(') > prev_line.count(')'):
                        continuation_parts.append(cont_line)
                        j += 1
                        break

                words = cont_line.split()
                # Verificar se começa com minúscula (padrão de texto invertido)
                if cont_line[0].islower():
                    # Exceção: preposições/artigos podem começar linhas válidas
                    # MAS só se houver palavras válidas depois
                    valid_starters = {'de', 'da', 'do', 'das', 'dos', 'e', 'ou', 'a', 'o',
                                      'para', 'com', 'em', 'no', 'na', 'nos', 'nas',
                                      'por', 'pelo', 'pela', 'ao', 'aos', 'as'}
                    # Palavras que indicam continuação explícita
                    continuation_starters = {'inclusive', 'incluindo', 'conforme', 'segundo',
                                             'tipo', 'como', 'sendo', 'sem', 'ref', 'exceto',
                                             'excetuando', 'exclusive', 'exclusivo'}
                    first_word = words[0].lower() if words else ""

                    # Se começa com palavra de continuação explícita, aceitar
                    if first_word in continuation_starters:
                        pass  # Aceitar linha
                    elif first_word in valid_starters and len(words) > 1:
                        # Verificar se alguma palavra >= 4 letras começa com maiúscula
                        # OU se há palavras válidas em minúsculo (substantivos comuns)
                        has_valid_word = any(
                            (len(w) >= 4 and w[0].isupper()) or
                            (len(w) >= 5 and w.isalpha())  # Palavra longa alfabética
                            for w in words[1:]
                        )
                        if not has_valid_word:
                            j += 1
                            continue
                    else:
                        j += 1
                        continue
                # Verificar linha sem espaço que não é sigla
                elif ' ' not in cont_line and not cont_line.isupper() and not cont_line.isdigit():
                    if not cont_line[0].isupper():
                        j += 1
                        continue

            # Ignorar linhas que começam com pontuação (lixo de OCR)
            # Ex: ",abáaraP" (Paraíba, invertido), ":oãsserpmI" (Impressão: invertido)
            if cont_line[0] in ',:;.!?-':
                j += 1
                continue

        # Parar se é outro item
        if Patterns.ITEM_PATTERN.match(cont_line):
            break

        # Parar se linha contém código de item no MEIO (ex: "...texto 6.6 UN 1,00...")
        # Isso indica que a linha pertence a outro item
        if Patterns.ITEM_CODE_MID.search(cont_line):
            break

        # Parar se a PRÓXIMA linha começa com código de item
        # (significa que cont_line pode ser início de outro item)
        if j + 1 < len(lines):
            next_line = lines[j + 1].strip()
            if Patterns.ITEM_PATTERN.match(next_line):
                prev_line = lines[j - 1].strip() if j - 1 >= 0 else ""
                prev_ends_with_continuation = (
                    prev_line.endswith(('-', '–', '—')) or
                    Patterns.CONTINUATION_WORDS_END.search(prev_line)
                )
                if prev_ends_with_continuation:
                    continuation_parts.append(cont_line)
                    break

                # Se o item terminou com "- UN 10" (hífen antes de unidade/quantidade),
                # aceitar continuação de "FORNECIMENTO/EXECUÇÃO/INSTALAÇÃO" mesmo com próximo item.
                prev_has_dash_unit_qty = bool(re.search(
                    r'\s-\s*(UN|M|M2|M3|M²|M³|KG|L|VB|CJ|PC|GL|PAR|JG|SC)\s+[\d.,]+\s*$',
                    prev_line,
                    re.IGNORECASE
                ))
                cont_upper = cont_line.upper()
                tail_starters = (
                    "FORNECIMENTO", "EXECUÇÃO", "EXECUCAO",
                    "INSTALAÇÃO", "INSTALACAO", "ASSENTAMENTO"
                )
                if prev_has_dash_unit_qty and cont_upper.startswith(tail_starters):
                    continuation_parts.append(cont_line)
                    break

                # Se o item terminou com unidade/quantidade e a continuação
                # começa com conjunção/preposição, manter mesmo com próximo item.
                prev_has_unit_qty_end = bool(re.search(
                    r'(UN|M|M2|M3|M²|M³|KG|L|VB|CJ|PC|GL|PAR|JG|SC)\s+[\d.,]+\s*$',
                    prev_line,
                    re.IGNORECASE
                ))
                if prev_has_unit_qty_end and cont_upper.startswith(('E ', 'OU ', 'COM ', 'SEM ', 'INCLUSIVE', 'INCLUINDO')):
                    continuation_parts.append(cont_line)
                    break

                # Se o próximo item é do tipo UNIT_FIRST (ex: "7.8 M² 4,80"),
                # a linha atual tende a ser prefixo do próximo item.
                if Patterns.UNIT_FIRST.match(next_line):
                    break

                # Verificar se cont_line parece ser início de descrição do PRÓXIMO item
                # Se sim, NÃO adicionar (pertence ao próximo item)
                # Se não, adicionar (é continuação válida do item atual)

                # Verificar se parece início de nova descrição
                first_word = cont_line.split()[0] if cont_line.split() else ""
                first_word_upper = first_word.upper() if first_word else ""

                # Lista de palavras que indicam início de nova descrição
                desc_starters = (
                    'CABO', 'TUBO', 'CAIXA', 'TOMADA', 'DISJUNTOR', 'QUADRO',
                    'PONTO', 'ELETRODUTO', 'INTERRUPTOR', 'LUMINARIA', 'LAMPADA',
                    'TORNEIRA', 'REGISTRO', 'VALVULA', 'TANQUE', 'CHUVEIRO',
                    'PORTA', 'JANELA', 'VIDRO', 'PINTURA', 'REVESTIMENTO',
                    'ARGAMASSA', 'CONCRETO', 'ALVENARIA', 'DEMOLIÇÃO', 'ESCAVAÇÃO',
                    'FORNECIMENTO', 'EXECUÇÃO', 'INSTALAÇÃO', 'ASSENTAMENTO',
                    'CALHA', 'MOLA', 'TRILHO', 'RALO', 'VISOR', 'FECHADURA',
                    'PISO', 'TETO', 'FORRO', 'RODAPÉ', 'RODAPE', 'SOLEIRA',
                    'PEITORIL', 'BANCADA', 'GUARDA', 'CORRIMÃO', 'CORRIMAO',
                    # Termos de paisagismo e áreas externas
                    'GRAMA', 'GRAMADO', 'JARDIM', 'PAISAGISMO', 'PLANTIO',
                    'MEIO-FIO', 'SARJETA', 'CALÇADA', 'CALCADA', 'PASSEIO'
                )

                # PRIORIDADE 1: Se começa com termo técnico, é nova descrição (mesmo que termine com preposição)
                if first_word_upper in desc_starters:
                    break  # É início de nova descrição, NÃO adicionar

                # PRIORIDADE 2: Se é header de seção, não adicionar
                if Patterns.SECTION_HEADER_BROAD.match(cont_line):
                    break

                # PRIORIDADE 3: Se termina com palavra de continuação E não é termo técnico,
                # pode ser continuação válida do item atual
                if Patterns.CONTINUATION_WORDS_END.search(cont_line):
                    continuation_parts.append(cont_line)
                    break

                # PRIORIDADE 4: Verificar outros indicadores de nova descrição
                is_new_desc_start = (
                    (len(first_word) >= 4 and first_word[0].isupper() and
                     not first_word.isupper()) or  # Palavra capitalizada
                    (cont_line.endswith('.') and len(cont_line) > 20)  # Sentença completa
                )
                if not is_new_desc_start:
                    # É continuação válida, adicionar antes de parar
                    continuation_parts.append(cont_line)
                # Se é início de nova descrição, NÃO adicionar
                break

        # Parar se é cabeçalho de seção
        if Patterns.SECTION_HEADER_BROAD.match(cont_line):
            break

        # Parar se é rodapé/cabeçalho
        cont_upper = cont_line.upper()
        if any(cont_upper.startswith(prefix) for prefix in STOP_PREFIXES):
            break

        # Parar se é rodapé com local/data (ex: "ALAGOA NOVA/PB 08 DE OUTUBRO DE 2025")
        if FOOTER_DATE_PATTERN.search(cont_line):
            break

        # Parar se é paginação (ex: "2 / 11")
        if Patterns.PAGE_BARE.match(cont_line):
            break

        # Adicionar linha de continuação
        continuation_parts.append(cont_line)
        j += 1

        # Parar se encontrou código AF (fim da descrição)
        if Patterns.AF_CODE_ANYWHERE.search(cont_line):
            break

    return " ".join(continuation_parts)


def _collect_previous_lines(
    lines: List[str],
    start_idx: int,
    max_lines: int = 3
) -> str:
    """
    Coleta linhas ANTERIORES para formar descrição completa.

    Usado quando o padrão é UNIT_FIRST (ex: "7.11 M² 2,10 texto...").
    A descrição pode estar em múltiplas linhas anteriores.

    Args:
        lines: Lista de todas as linhas do texto
        start_idx: Índice da linha atual (com o item)
        max_lines: Máximo de linhas anteriores a coletar

    Returns:
        Texto concatenado das linhas anteriores (ordem correta)
    """
    prev_parts: list[str] = []
    j = start_idx - 1

    while j >= 0 and len(prev_parts) < max_lines:
        prev_line = lines[j].strip()

        # Parar se linha vazia
        if not prev_line:
            break

        # Parar se é outro item
        if Patterns.ITEM_PATTERN.match(prev_line):
            break

        # Parar se é cabeçalho de seção
        if Patterns.SECTION_HEADER_BROAD.match(prev_line):
            break

        # Parar se é rodapé/cabeçalho
        prev_upper = prev_line.upper()
        if any(prev_upper.startswith(prefix) for prefix in STOP_PREFIXES):
            break

        # Parar se contém código AF (fim de outro item)
        if Patterns.AF_CODE_ANYWHERE.search(prev_line):
            break

        # Parar se contém código de item no meio
        if Patterns.ITEM_CODE_MID.search(prev_line):
            break

        # Adicionar linha (no início da lista para manter ordem)
        prev_parts.insert(0, prev_line)
        j -= 1

        # Parar se linha parece ser início de descrição
        # (começa com letra maiúscula e tem 4+ letras)
        if prev_line and prev_line[0].isupper():
            first_word = prev_line.split()[0] if prev_line.split() else ""
            if len(first_word) >= 4 and first_word[0].isupper():
                break

    return " ".join(prev_parts)


def _looks_like_reversed_footer_line(line: str) -> bool:
    """
    Detecta linhas de rodapé invertidas pelo OCR.

    Ex.: "ohlesnoC" -> "Conselho", "a rirefnoc" -> "a conferir"
    """
    if not line or len(line) < 6:
        return False

    words = line.split()
    if not words:
        return False

    reversed_line = " ".join(word[::-1] for word in words)
    normalized = normalize_accents(reversed_line).upper()

    return any(token in normalized for token in REVERSED_FOOTER_TOKENS)


def _build_item_line_index(texto: str) -> Dict[str, List[Dict]]:
    """
    Constrói índice de TODAS as linhas que contêm cada item,
    incluindo linhas de continuação.

    Returns:
        {
            '1.2': [
                {'linha': 45, 'texto_linha': '1.2 Descrição completa UN 10', 'unit': 'UN', 'qty': 10.0},
                {'linha': 200, 'texto_linha': '1.2 Descrição B M² 5', 'unit': 'M2', 'qty': 5.0}
            ]
        }
    """
    index: Dict[str, List[Dict]] = {}
    lines = texto.split('\n')

    i = 0
    while i < len(lines):
        line_stripped = lines[i].strip()
        if not line_stripped:
            i += 1
            continue

        match = Patterns.ITEM_PATTERN.match(line_stripped)
        if match:
            item_code = match.group(1)
            full_text = line_stripped

            # Detectar se linha tem texto corrompido (mas não rejeitar)
            line_is_corrupted = is_corrupted_text(line_stripped)

            # Verificar se linha começa com CÓDIGO + UNIDADE + QUANTIDADE
            # Nesse caso, a descrição está nas linhas ANTERIORES
            unit_first_match = Patterns.UNIT_FIRST.match(line_stripped)
            if unit_first_match and i > 0:
                # Coletar múltiplas linhas anteriores
                prev_text = _collect_previous_lines(lines, i)
                if prev_text:
                    full_text = prev_text + " " + line_stripped

            # Verificar se linha tem CÓDIGO ... UNIDADE QUANTIDADE no final
            # Nesse caso, a descrição pode começar na linha ANTERIOR
            if not unit_first_match and i > 0:
                unit_last_match = Patterns.UNIT_LAST.match(line_stripped)
                if unit_last_match:
                    desc_in_line = unit_last_match.group(2).strip()
                    prev_line = lines[i - 1].strip()

                    if _should_prefix_with_previous(desc_in_line, prev_line, lines, i):
                        full_text = prev_line + " " + line_stripped

            # Se a primeira linha já tem código AF, não precisa coletar continuação
            has_af_code = bool(Patterns.AF_CODE_ANYWHERE.search(line_stripped))

            # Coletar linhas de continuação (apenas se não tem AF na primeira linha)
            if not has_af_code:
                continuation = _collect_continuation_lines(lines, i + 1)
                if continuation:
                    full_text = full_text + " " + continuation

            # Extrair unidade e quantidade do texto completo
            unit, qty = _extract_unit_qty(full_text)

            entry = {
                'linha': i + 1,  # 1-indexed
                'texto_linha': full_text,
                'unit': unit,
                'qty': qty,
                'corrupted': line_is_corrupted
            }

            if item_code not in index:
                index[item_code] = []
            index[item_code].append(entry)

        else:
            # Verificar se linha tem código de item EMBUTIDO no final
            # Ex: "Disjuntor tripolar 63 A... 9.13 UN 2,00"
            # Nesse caso, a descrição está ANTES do código na mesma linha
            embedded_match = Patterns.EMBEDDED_ITEM_END.search(line_stripped)
            if embedded_match:
                item_code = embedded_match.group(1)
                unit = embedded_match.group(2).upper()
                unit = unit.replace('²', '2').replace('³', '3')
                qty_str = embedded_match.group(3).replace('.', '').replace(',', '.')
                try:
                    qty = float(qty_str)
                except ValueError:
                    qty = None

                # Extrair descrição (texto antes do código)
                desc_end_pos = embedded_match.start()
                desc_part = line_stripped[:desc_end_pos].strip()

                # Só indexar se há descrição substantiva antes do código
                if desc_part and len(desc_part) >= 20:
                    line_is_corrupted = is_corrupted_text(line_stripped)
                    full_text = line_stripped

                    # Prefixar com linhas anteriores se descrição parece fragmento
                    if i > 0:
                        prev_line = lines[i - 1].strip()
                        if _is_description_fragment(desc_part, prev_line) or len(desc_part) < 25:
                            prev_text = _collect_previous_lines(lines, i)
                            if prev_text:
                                full_text = prev_text + " " + line_stripped

                    # Coletar linhas de continuação após item embutido
                    continuation = _collect_continuation_lines(lines, i + 1)
                    if continuation:
                        full_text = full_text + " " + continuation

                    # Verificar se próxima linha contém código AF (continuação)
                    # Ex: linha atual = "DESCRIÇÃO 14.7 M² 44,10"
                    #     próxima linha = "AF_06/2014"
                    if i + 1 < len(lines):
                        next_line = lines[i + 1].strip()
                        if Patterns.AF_ONLY.match(next_line):
                            # Próxima linha é só código AF - adicionar ao texto
                            full_text = line_stripped + " " + next_line

                    entry = {
                        'linha': i + 1,  # 1-indexed
                        'texto_linha': full_text,
                        'unit': unit,
                        'qty': qty,
                        'corrupted': line_is_corrupted,
                        'embedded': True  # Marcar como item embutido
                    }

                    if item_code not in index:
                        index[item_code] = []
                    index[item_code].append(entry)

        i += 1

    return index


def _extract_unit_qty(texto: str) -> Tuple[Optional[str], Optional[float]]:
    """Extrai unidade e quantidade do texto (final ou meio)."""
    # Primeiro tentar no final
    match = Patterns.UNIT_QTY_EXTRACT_END.search(texto)

    # Se não encontrou no final, procurar no meio (antes de texto de continuação)
    if not match:
        match = Patterns.UNIT_QTY_EXTRACT_MID.search(texto)

    if match:
        unit = match.group(1).upper()
        # Normalizar unidade
        unit = unit.replace('²', '2').replace('³', '3')
        qty_str = match.group(2).replace('.', '').replace(',', '.')
        try:
            qty = float(qty_str)
            return unit, qty
        except ValueError:
            return unit, None

    return None, None


def _normalize_unit(unit: Optional[str]) -> Optional[str]:
    """Normaliza unidade para comparação."""
    if not unit:
        return None
    unit = unit.upper().strip()
    unit = unit.replace('²', '2').replace('³', '3')
    # Mapeamentos comuns
    mappings = {
        'UND': 'UN',
        'UNID': 'UN',
        'UNIDADE': 'UN',
        'METRO': 'M',
        'METROS': 'M',
    }
    return mappings.get(unit, unit)


def _group_candidates_by_proximity(candidates: List[Dict]) -> List[List[Dict]]:
    """
    Agrupa candidatos por proximidade de linhas.

    Se há ocorrências em linhas muito distantes (> 200 linhas de diferença),
    provavelmente são itens diferentes em seções diferentes do documento.

    Returns:
        Lista de grupos, onde cada grupo contém candidatos próximos entre si.
        Grupos ordenados por linha (primeiro grupo = linhas menores).
    """
    if len(candidates) <= 1:
        return [candidates] if candidates else []

    # Ordenar por linha
    sorted_candidates = sorted(candidates, key=lambda c: c['linha'])

    # Agrupar por proximidade (máx 200 linhas de diferença)
    groups = []
    current_group = [sorted_candidates[0]]

    for i in range(1, len(sorted_candidates)):
        prev_line = sorted_candidates[i - 1]['linha']
        curr_line = sorted_candidates[i]['linha']

        if curr_line - prev_line <= 200:
            current_group.append(sorted_candidates[i])
        else:
            groups.append(current_group)
            current_group = [sorted_candidates[i]]

    groups.append(current_group)

    return groups


def _get_segment_index(item_code: str) -> int:
    """
    Extrai o índice do segmento do código do item.

    Args:
        item_code: Código do item (ex: "S2-4.1", "S1-7.9", "4.1")

    Returns:
        Índice do segmento (0 para sem prefixo ou S1-, 1 para S2-, etc.)
    """
    match = Patterns.SEGMENT_PREFIX.match(item_code)
    if match:
        return int(match.group(1)) - 1  # S1 = 0, S2 = 1, etc.
    return 0  # Sem prefixo = primeiro segmento


def _filter_candidates_by_page(
    candidates: List[Dict],
    servico_page: Optional[int],
    line_to_page: Optional[Dict[int, int]],
    max_page_distance: int = 2
) -> List[Dict]:
    """
    Filtra candidatos para incluir apenas linhas da mesma página ou páginas próximas.

    Prioridade:
    1. Candidatos na mesma página
    2. Candidatos em páginas próximas (±max_page_distance)
    3. Lista vazia se todos os candidatos estão muito distantes

    Args:
        candidates: Lista de candidatos
        servico_page: Página do serviço (se disponível)
        line_to_page: Mapeamento linha -> página
        max_page_distance: Distância máxima de páginas permitida

    Returns:
        Lista filtrada de candidatos
    """
    if not servico_page or not line_to_page:
        return candidates

    # Primeiro: tentar candidatos na mesma página
    same_page = [
        c for c in candidates
        if line_to_page.get(c['linha']) == servico_page
    ]
    if same_page:
        return same_page

    # Segundo: aceitar candidatos em páginas próximas
    nearby = [
        c for c in candidates
        if abs(line_to_page.get(c['linha'], 0) - servico_page) <= max_page_distance
    ]
    if nearby:
        return nearby

    # Terceiro: rejeitar candidatos muito distantes (retornar lista vazia)
    # Isso força o sistema a manter a descrição original ao invés de usar uma errada
    return []


def _select_candidate_group(
    candidates: List[Dict],
    original_item: str,
    item: str
) -> tuple:
    """
    Agrupa candidatos por proximidade e seleciona o grupo apropriado.

    Args:
        candidates: Lista de candidatos
        original_item: Código original do item (pode ter prefixo S1-/S2-)
        item: Código normalizado do item

    Returns:
        Tuple (working_candidates, group_explicitly_selected)
    """
    has_segment_prefix = bool(Patterns.SEGMENT_PREFIX.match(original_item)) if original_item else False
    group_explicitly_selected = has_segment_prefix

    if len(candidates) <= 1:
        return candidates, group_explicitly_selected

    groups = _group_candidates_by_proximity(candidates)
    if len(groups) > 1:
        segment_idx = _get_segment_index(original_item or item)
        segment_idx = min(segment_idx, len(groups) - 1)
        return groups[segment_idx], True

    return groups[0] if groups else [], group_explicitly_selected


def _find_quantity_match(
    candidates: List[Dict],
    expected_unit_norm: Optional[str],
    expected_qty: Optional[float]
) -> Optional[Dict]:
    """
    Encontra candidato com quantidade e unidade exatas.

    Args:
        candidates: Lista de candidatos
        expected_unit_norm: Unidade esperada (normalizada)
        expected_qty: Quantidade esperada

    Returns:
        Candidato com match exato ou None
    """
    if not expected_qty or not expected_unit_norm:
        return None

    for candidate in candidates:
        cand_qty = candidate.get('qty')
        cand_unit = _normalize_unit(candidate.get('unit'))

        if (cand_qty and cand_qty == expected_qty and
                cand_unit and cand_unit == expected_unit_norm):
            return candidate

    return None


def _build_match_result_from_qty_match(
    qty_match_candidate: Dict,
    item: str,
    current_desc: str
) -> Dict:
    """
    Constrói resultado de match a partir de candidato com quantidade correta.

    Args:
        qty_match_candidate: Candidato com match de quantidade
        item: Código do item
        current_desc: Descrição atual do serviço

    Returns:
        Dict com linha, descrição e flag de corrompido se aplicável
    """
    desc = _extract_description_from_line(qty_match_candidate['texto_linha'], item)
    is_corrupted = (
        qty_match_candidate.get('corrupted', False) or
        is_corrupted_text(qty_match_candidate['texto_linha'])
    )

    if desc and len(desc) >= 10 and not is_corrupted:
        return {
            'linha': qty_match_candidate['linha'],
            'descricao': desc
        }

    # Descrição corrompida ou inválida - tentar usar existente
    if current_desc and len(current_desc) >= 20 and not is_corrupted_text(current_desc):
        return {
            'linha': qty_match_candidate['linha'],
            'descricao': current_desc,
            'desc_corrupted': True
        }

    return {
        'linha': qty_match_candidate['linha'],
        'descricao': desc if desc else current_desc,
        'desc_corrupted': True
    }


def _score_candidate(
    candidate: Dict,
    desc: str,
    expected_unit_norm: Optional[str],
    expected_qty: Optional[float]
) -> int:
    """
    Calcula pontuação de um candidato para ranking.

    Args:
        candidate: Candidato a pontuar
        desc: Descrição extraída do candidato
        expected_unit_norm: Unidade esperada (normalizada)
        expected_qty: Quantidade esperada

    Returns:
        Pontuação do candidato (maior = melhor)
    """
    score = 0
    cand_unit = _normalize_unit(candidate.get('unit'))
    cand_qty = candidate.get('qty')

    # Pontuação por tamanho da descrição
    if len(desc) >= 50:
        score += 50
    elif len(desc) >= 30:
        score += 25

    # Pontuação por unidade
    if expected_unit_norm and cand_unit and expected_unit_norm == cand_unit:
        score += 100

    # Pontuação por quantidade
    if expected_qty is not None and cand_qty is not None:
        # Converter para float se necessário
        try:
            exp_qty = float(str(expected_qty).replace('.', '').replace(',', '.')) if isinstance(expected_qty, str) else float(expected_qty)
            cnd_qty = float(cand_qty) if isinstance(cand_qty, (int, float)) else float(str(cand_qty).replace('.', '').replace(',', '.'))
            if exp_qty == cnd_qty:
                score += 200
            elif abs(exp_qty - cnd_qty) / max(exp_qty, 0.01) < 0.05:
                score += 150
        except (ValueError, TypeError):
            pass

    # Se sem critério, usar tamanho como desempate
    if score == 0:
        score = len(desc)

    return score


def _find_best_match(
    candidates: List[Dict],
    item: str,
    expected_unit: Optional[str],
    expected_qty: Optional[float],
    current_desc: str = "",
    original_item: str = "",
    servico_page: Optional[int] = None,
    line_to_page: Optional[Dict[int, int]] = None
) -> Optional[Dict]:
    """
    Encontra a melhor correspondência entre as linhas candidatas.

    Prioriza correspondência por:
    1. PÁGINA - candidatos na mesma página do serviço têm prioridade ABSOLUTA
    2. QUANTIDADE - quantidade exata tem prioridade sobre descrição
    3. Descrição substantiva (>= 30 chars) + unidade
    4. Descrição mais longa entre candidatos válidos
    """
    if not candidates:
        return None

    expected_unit_norm = _normalize_unit(expected_unit)

    # Detectar se é item de planilha secundária (prefixo S1-, S2-, etc.)
    has_segment_prefix = bool(
        original_item and Patterns.SEGMENT_PREFIX.match(original_item)
    )

    # FASE 0: Filtrar por página
    # Para itens com prefixo S-, ser mais restritivo (max 1 página de distância)
    max_distance = 1 if has_segment_prefix else 2
    page_filtered = _filter_candidates_by_page(
        candidates, servico_page, line_to_page, max_page_distance=max_distance
    )

    # Se filtro de página retornou vazio, não há candidatos válidos
    if not page_filtered:
        return None

    # Selecionar grupo por proximidade/segmento
    group_selected_by_page = bool(servico_page and line_to_page)
    working_candidates, group_selected = _select_candidate_group(
        page_filtered, original_item, item
    )
    group_explicitly_selected = group_selected_by_page or group_selected

    # FASE 1: Match por quantidade exata
    qty_match = _find_quantity_match(working_candidates, expected_unit_norm, expected_qty)
    if qty_match:
        return _build_match_result_from_qty_match(qty_match, item, current_desc)

    # Para itens com prefixo S-, exigir match de quantidade
    # (evita pegar descrição de planilha errada)
    if has_segment_prefix and expected_qty:
        # Verificar se há algum candidato com quantidade próxima (tolerância 10%)
        has_qty_match = any(
            c.get('qty') and abs(c['qty'] - expected_qty) / max(expected_qty, 0.01) < 0.1
            for c in working_candidates
        )
        if not has_qty_match:
            return None

    # FASE 2: Scoring de candidatos
    best = None
    best_score = -1
    current_starts_with_unit = bool(Patterns.DESC_STARTS_WITH_UNIT.match(current_desc))

    for candidate in working_candidates:
        desc = _extract_description_from_line(candidate['texto_linha'], item)
        if not desc or len(desc) < 10:
            continue

        # Rejeitar descrições corrompidas
        if candidate.get('corrupted', False) or is_corrupted_text(candidate['texto_linha']):
            continue

        # Rejeitar descrições que começam com unidade/quantidade
        if Patterns.DESC_STARTS_WITH_UNIT.match(desc):
            continue

        # Proteger descrição atual se já é boa
        if not group_explicitly_selected and not current_starts_with_unit:
            if len(current_desc) >= 50 and len(desc) < len(current_desc):
                continue

        score = _score_candidate(candidate, desc, expected_unit_norm, expected_qty)

        if score > best_score:
            best_score = score
            best = {
                'linha': candidate['linha'],
                'descricao': desc
            }

    return best


def _extract_description_from_line(line: str, item: str) -> Optional[str]:
    """
    Extrai a descrição exata de uma linha de texto (pode conter linhas de continuação).

    Formatos suportados:
        "1.2 Descrição do serviço completa UN 10,50"
        "1.2 Descrição parte 1 M³ 63,448 PARTE 2. AF_12/2017"
        "Descrição anterior 1.2 UN 10,50 continuação"  (quando desc vem da linha anterior)
        "Descrição completa aqui 9.13 UN 2,00"  (código embutido no final)
        "Descrição 14.7 M² 44,10 AF_06/2014"  (embutido com AF depois)
             ^-------------------------------------------^
                    parte a extrair (sem unit/qty e sem código)
    """
    if not line:
        return None

    desc = line.strip()

    # Verificar se é linha com código EMBUTIDO no MEIO (não no início)
    # Ex: "Disjuntor tripolar 63 A... 9.13 UN 2,00 AF_06/2014"
    # Ex: "Banco com encosto... 16.5 UN 3,00 com 10 réguas de madeira..."
    # IMPORTANTE: Só aplicar se o código NÃO está no início da linha
    # (itens que começam com código são tratados de forma diferente)
    if not desc.startswith(item):
        embedded_pattern = re.compile(
            rf'{re.escape(item)}\s+'
            r'(UN|M|M2|M3|M²|M³|KG|L|VB|CJ|PC|GL)\s+'
            r'[\d.,]+',
            re.IGNORECASE
        )
        embedded_match = embedded_pattern.search(desc)
        if embedded_match and embedded_match.start() > 0:
            # Extrair descrição ANTES do código
            desc_before = desc[:embedded_match.start()].strip()
            # Extrair texto DEPOIS da unidade/quantidade (continuação)
            desc_after = desc[embedded_match.end():].strip()

            # Separar código AF do texto de continuação
            af_match = Patterns.AF_CODE_ANYWHERE.search(desc_after)
            if af_match:
                # Se encontrou AF, separar continuação do AF
                continuation = desc_after[:af_match.start()].strip()
                af_code = af_match.group(0)
            else:
                continuation = desc_after
                af_code = ""

            if desc_before:
                # Combinar: descrição + continuação + AF
                result = desc_before
                if continuation:
                    result = result + " " + continuation
                if af_code:
                    result = result + " " + af_code
                # Limpar espaços extras
                result = ' '.join(result.split())
                if len(result) >= 5:
                    return result

    # Remover o item do início (se presente)
    pattern_start = rf'^{re.escape(item)}\s+'
    desc = re.sub(pattern_start, '', desc)

    # Remover o item do meio (quando prefixado com linha anterior)
    # Ex: "DESCRIÇÃO ANTERIOR 9.9 UN 1,00 CONTINUAÇÃO"
    pattern_mid = rf'\s+{re.escape(item)}\s+'
    desc = re.sub(pattern_mid, ' ', desc)

    if not desc:
        return None

    # Padrão para unidade e quantidade no INÍCIO (após remover código)
    # Ex: "m³ 143,56 CARGA MANUAL..." -> "CARGA MANUAL..."
    desc = Patterns.UNIT_QTY_DESC_START.sub('', desc)

    # Remover TODAS as ocorrências de unidade/quantidade (meio ou final)
    desc = Patterns.UNIT_QTY_DESC_MID.sub(' ', desc)

    # Limpar espaços extras
    desc = ' '.join(desc.split())

    # Validação: descrição não deve ser muito curta
    if len(desc) < 5:
        return None

    # Validação: descrição não deve ser só unidade/quantidade
    if Patterns.DESC_ONLY_UNIT_QTY.match(desc):
        return None

    return desc
