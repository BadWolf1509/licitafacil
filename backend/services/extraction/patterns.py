"""
Padrões regex centralizados e compilados.

Este módulo contém todos os padrões regex usados pelos módulos de extração,
pré-compilados para melhor performance.
"""
import re


class Patterns:
    """Registry de padrões regex compilados para processamento de documentos."""

    # =========================================================================
    # CÓDIGOS DE ITEM
    # =========================================================================

    # Código de item simples: 1.2.3, 1.2, 1.2.3.4
    ITEM_CODE = re.compile(r'^\d{1,3}(?:\.\d{1,3}){0,4}$')

    # Código de item com prefixo opcional: S1-1.2.3, AD-1.2, 1.2.3
    ITEM_WITH_PREFIX = re.compile(r'^(?:S\d+-|AD-)?\d{1,3}(?:\.\d{1,3}){0,4}$', re.IGNORECASE)

    # Prefixo de restart: S1-, S2-, AD-
    RESTART_PREFIX = re.compile(r'^(S\d+-|AD-)', re.IGNORECASE)

    # Extrai índice do prefixo S: S1-, S2-, etc.
    RESTART_INDEX = re.compile(r'^S(\d+)-')

    # Item no início de linha: "1.1 DESCRIÇÃO"
    ITEM_LINE_START = re.compile(r'^\s*(\d{1,2}\.\d{1,2}(?:\.\d{1,2})?)\s+')

    # Item no início de linha com descrição maiúscula
    ITEM_WITH_DESC = re.compile(r'^\s*(\d{1,2}\.\d{1,2}(?:\.\d{1,2})?)\s+([A-ZÀ-ÚÇ][\w\sÀ-ÚÇ,.\-/()]+)')

    # =========================================================================
    # METADADOS DE PÁGINA
    # =========================================================================

    # Número de página: "Página 5/10", "PÁGINA 5 / 10"
    PAGE_NUMBER = re.compile(r'^P[AÁ]GINA\s*\d+\s*/\s*\d+', re.IGNORECASE)

    # Número de página abreviado: "Pág. 5/10"
    PAGE_ABBREV = re.compile(r'^P[AÁ]G\.?\s*\d+\s*/\s*\d+', re.IGNORECASE)

    # Número de página simples: "5/10"
    PAGE_BARE = re.compile(r'^\d{1,3}\s*/\s*\d{1,3}$')

    # "Página X de Y"
    PAGE_DE = re.compile(r'^P[AÁ]GINA\s*\d+\s+DE\s+\d+', re.IGNORECASE)

    # Página em qualquer posição do texto
    PAGE_ANYWHERE = re.compile(r'P[AÁ]GINA\s*\d+\s*/\s*\d+', re.IGNORECASE)

    # Data e hora de impressão
    PRINT_DATETIME = re.compile(r'^\d{2}/\d{2}/\d{4},?\s*\d{2}:\d{2}')

    # "IMPRESSO EM:"
    PRINT_HEADER = re.compile(r'^IMPRESSO\s+EM\s*:?', re.IGNORECASE)

    # =========================================================================
    # CABEÇALHOS DE SEÇÃO
    # =========================================================================

    # Cabeçalho de categoria: "8 INSTALAÇÕES HIDROSSANITÁRIAS"
    SECTION_HEADER = re.compile(
        r'^(\d{1,2})\s+([A-ZÁÉÍÓÚÂÊÎÔÛÃÕÇ][A-ZÁÉÍÓÚÂÊÎÔÛÃÕÇ\s]+)$'
    )

    # Número de seção simples: "8"
    SECTION_NUMBER = re.compile(r'^\d{1,2}$')

    # =========================================================================
    # UNIDADE E QUANTIDADE
    # =========================================================================

    # Unidade + quantidade no final da linha: "UN 100", "M² 25,50"
    UNIT_QTY_END = re.compile(
        r'\b(UN|M|M2|M3|M²|M³|KG|L|VB|CJ|PC|GL|T|HA|KM|MES|PÇ|JG|CONJ)\s+([\d.,]+)\s*$',
        re.IGNORECASE
    )

    # Unidade + quantidade no início: "UN 100 DESCRIÇÃO"
    UNIT_QTY_START = re.compile(
        r'^(UN|M|M2|M3|M²|M³|KG|L|VB|CJ|PC|GL)\s+([\d.,]+)\s+',
        re.IGNORECASE
    )

    # Par unidade-quantidade em qualquer posição
    UNIT_QTY_PAIR = re.compile(
        r'(UN|M|M2|M3|M²|M³|KG|L|VB|CJ|PC|GL)\s+([\d.,]+)',
        re.IGNORECASE
    )

    # =========================================================================
    # DADOS INSTITUCIONAIS
    # =========================================================================

    # CNPJ: 12.345.678/0001-90
    CNPJ = re.compile(r'\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}')

    # CNPJ formato numérico: 12345678000190
    CNPJ_NUMERIC = re.compile(r'\d{14}')

    # CPF: 123.456.789-00
    CPF = re.compile(r'\d{3}\.\d{3}\.\d{3}-\d{2}')

    # CREA: CREA-XX 123456
    CREA = re.compile(r'CREA[:\s-]*[A-Z]{2}[:\s-]*\d+', re.IGNORECASE)

    # Certificado/Certidão número
    CERTIDAO = re.compile(r'^CERTID[AÃ]O\s+N[º°]?\s*\d+', re.IGNORECASE)

    # Documento número
    DOCUMENTO = re.compile(r'^DOC(?:UMENTO)?\.?\s+N[º°]?\s*\d+', re.IGNORECASE)

    # Chave de impressão
    CHAVE_IMPRESSAO = re.compile(r'^CHAVE\s+DE\s+IMPRESS[AÃ]O\s*:?', re.IGNORECASE)

    # =========================================================================
    # CÓDIGOS DE REFERÊNCIA
    # =========================================================================

    # Código SINAPI/AF: "AF_02/2021", "SINAPI 12345"
    REFERENCE_CODE = re.compile(r'(?:SINAPI|REF\.?|REFER[ÊE]NCIA)\s*\d+', re.IGNORECASE)

    # Código AF isolado
    AF_CODE = re.compile(r'AF_\d+/?\d*')

    # =========================================================================
    # TOKENS DE TEXTO
    # =========================================================================

    # Token alfanumérico com caracteres especiais de unidade
    TOKEN_UNIT = re.compile(r'[\w\u00ba\u00b0/%\u00b2\u00b3\.]+')

    # Número decimal
    NUMBER = re.compile(r'[\d.,]+')

    # Palavra com pelo menos 3 letras
    WORD_3PLUS = re.compile(r'[A-Za-zÀ-ÿ]{3,}')

    # =========================================================================
    # CONTINUAÇÃO DE LINHA
    # =========================================================================

    # Palavras de continuação no final
    CONTINUATION_END = re.compile(
        r'[,\s](PARA|COM|DE|DO|DA|NO|NA|EM|E|OU)\s*$|,\s*$',
        re.IGNORECASE
    )

    # Padrões de spillover (continuação de linha anterior)
    SPILLOVER_START = re.compile(
        r'^(E\s|MM,|EL[AÁ]STICA|TICO\s|ADOS?\s)',
        re.IGNORECASE
    )

    # =========================================================================
    # PADRÕES PARA DESCRIPTION FIXER
    # =========================================================================

    # Marcador de página flexível: "Página 3 / 10", "PÁGINA 5/10", "Pagina 1 / 20"
    PAGE_MARKER = re.compile(
        r'[Pp][aáAÁ][gG][iI][nN][aA]\s+(\d+)\s*/\s*\d+',
        re.IGNORECASE
    )

    # Item no início com descrição: "1.2.3 Descrição completa"
    ITEM_PATTERN = re.compile(
        r'^(\d{1,2}\.\d{1,2}(?:\.\d{1,2})?)\s+(.+)',
        re.IGNORECASE
    )

    # Cabeçalho de seção amplo: "2 DEMOLIÇÕES E RETIRADAS" (mínimo 5 chars maiúsculas)
    SECTION_HEADER_BROAD = re.compile(
        r'^\d{1,2}\s+[A-ZÁÉÍÓÚÀÂÊÔÃÕÇ\s]{5,}$'
    )

    # CÓDIGO + UNIDADE + QUANTIDADE no início
    # Ex: "9.9 UN 1,00 ..." - indica que descrição está na linha anterior
    UNIT_FIRST = re.compile(
        r'^(\d{1,2}\.\d{1,2}(?:\.\d{1,2})?)\s+'
        r'(UN|M|M2|M3|M²|M³|KG|L|VB|CJ|PC|GL|PAR|JG|SC)\s+'
        r'([\d.,]+)',
        re.IGNORECASE
    )

    # CÓDIGO ... UNIDADE QUANTIDADE no final
    # Ex: "9.5 20A/250V, CAIXA ELÉTRICA, ... UN 19,00"
    UNIT_LAST = re.compile(
        r'^(\d{1,2}\.\d{1,2}(?:\.\d{1,2})?)\s+'
        r'(.+?)\s+'
        r'(UN|M|M2|M3|M²|M³|KG|L|VB|CJ|PC|GL|PAR|JG|SC)\s+'
        r'([\d.,]+)\s*$',
        re.IGNORECASE
    )

    # Linha que é APENAS código AF: "AF_01/2021" ou "AF_01/2021_P"
    AF_ONLY = re.compile(r'^AF_\d+/\d+(_\w+)?$', re.IGNORECASE)

    # Paginação simples: "Página 5/10"
    PAGINATION_SIMPLE = re.compile(r'^P[aá]gina\s+\d+\s*/\s*\d+$', re.IGNORECASE)

    # Código AF em qualquer posição (inclui sufixo opcional como _PS, _P)
    AF_CODE_ANYWHERE = re.compile(r'\bAF_\d+/\d+(?:_\w+)?', re.IGNORECASE)

    # AF no final da linha
    AF_CODE_END = re.compile(r'AF_\d+/\d+(_\w+)?\s*$', re.IGNORECASE)

    # Unidade/quantidade no final do texto (para extração)
    UNIT_QTY_EXTRACT_END = re.compile(
        r'\b(UN|M|M2|M3|M²|M³|KG|L|VB|CJ|PC|GL|PAR|JG|SC)\s+([\d.,]+)\s*$',
        re.IGNORECASE
    )

    # Unidade/quantidade no meio do texto (seguida de letra)
    UNIT_QTY_EXTRACT_MID = re.compile(
        r'\b(UN|M|M2|M3|M²|M³|KG|L|VB|CJ|PC|GL|PAR|JG|SC)\s+([\d.,]+)\s+[A-Z]',
        re.IGNORECASE
    )

    # Unidade/quantidade no início (após remover código)
    # Ex: "m³ 143,56 CARGA MANUAL..." -> "CARGA MANUAL..."
    UNIT_QTY_DESC_START = re.compile(
        r'^(UN|M|M2|M3|M²|M³|KG|L|VB|CJ|PC|GL|PAR|JG|SC)\s+[\d.,]+\s+',
        re.IGNORECASE
    )

    # Unidade/quantidade no meio ou final (para remoção)
    UNIT_QTY_DESC_MID = re.compile(
        r'\s+(UN|M|M2|M3|M²|M³|KG|L|VB|CJ|PC|GL|PAR|JG|SC)\s+[\d.,]+(?:\s|$)',
        re.IGNORECASE
    )

    # Palavras de continuação no final da linha
    CONTINUATION_WORDS_END = re.compile(
        r'\s(PARA|COM|DE|DA|DO|EM|NO|NA|E|OU|A|O)\s*$',
        re.IGNORECASE
    )

    # Descrição que começa com unidade/quantidade (erro comum)
    DESC_STARTS_WITH_UNIT = re.compile(
        r'^(UN|M|M2|M3|M²|M³|KG|L|VB|CJ|PC|GL|PAR|JG|SC)\s+[\d.,]+',
        re.IGNORECASE
    )

    # Descrição que é só unidade/quantidade (lixo)
    DESC_ONLY_UNIT_QTY = re.compile(r'^[A-Z]{1,3}\s*[\d.,]+$')

    # Prefixo de segmento: S1-, S2-, etc.
    SEGMENT_PREFIX = re.compile(r'^S(\d+)-')

    # Código de item no MEIO da linha (não no início)
    # Ex: "...texto 6.6 para Uso Geral..." - detecta "6.6" no meio
    ITEM_CODE_MID = re.compile(
        r'\s(\d{1,2}\.\d{1,2})\s+(?:UN|M|M2|M3|M²|M³|KG|L|VB|CJ|PC|GL|PAR|JG|SC)\s+[\d.,]+',
        re.IGNORECASE
    )

    # =========================================================================
    # PADRÕES PARA ADITIVO TRANSFORMER
    # =========================================================================

    # Item de contrato com descrição e opcional unidade/quantidade
    # Ex: "1.1 DESCRIÇÃO DO SERVIÇO UN 100,00"
    CONTRATO_ITEM = re.compile(
        r"^\s*(\d{1,2}\.\d{1,2}(?:\.\d{1,2})?)\s+([A-ZÀ-ÚÇ][\w\sÀ-ÚÇ,.\-/()]+?)"
        r"(?:\s*,?\s*(UN|M|KG|M2|M3|M²|M³|L|VB|CJ|PC|GL|und|un|m|m²|m³|pç|pc)\s+([\d,.]+))?\s*$",
        re.IGNORECASE
    )

    # Item de aditivo com descrição e opcional unidade/quantidade
    # Ex: "1.1 DESCRIÇÃO UN 50,00"
    ADITIVO_ITEM = re.compile(
        r"^\s*(\d+\.\d+)\s+(\S.*?)"
        r"(?:\s+(UN|M|KG|M2|M3|M²|M³|L|VB|CJ|PC|GL|un|m|m²|m³)\s+([\d,.]+))?\s*$",
        re.IGNORECASE
    )

    # Item embutido no final da linha: "DESCRIÇÃO... 1.1 UN 100,00"
    EMBEDDED_ITEM_END = re.compile(
        r'(\d+\.\d+)\s+(UN|M|KG|M2|M3|M²|M³|L|VB|CJ|PC|GL)\s+([\d,.]+)\s*$',
        re.IGNORECASE
    )

    # Unidade + quantidade inline (detecção rápida)
    UNIT_QTY_INLINE = re.compile(
        r"\b(?:UN|M|KG|M2|M3|L|VB|CJ)\s+\d+",
        re.IGNORECASE
    )

    # Código de item no final da linha (para remoção)
    TRAILING_ITEM_CODE = re.compile(r'\s+\d+\.\d+\s*$')

    # Palavra com 4+ letras (para validar texto)
    WORD_4PLUS_LETTERS = re.compile(r'[A-Za-zÀ-ÿ]{4,}')

    # Sufixo de item: -A, -B, -C no final
    ITEM_SUFFIX = re.compile(r'-[A-Z]$')

    # Sufixo de item com captura
    ITEM_SUFFIX_CAPTURE = re.compile(r'-([A-Z])$')

    # Item simples no início da linha: "1.1 A..."
    ITEM_LINE_SIMPLE = re.compile(r"^\s*(\d{1,2}\.\d{1,2})\s+[A-Z]")


# Aliases para compatibilidade
PAGE_METADATA_PATTERNS = (
    Patterns.PAGE_NUMBER,
    Patterns.PAGE_ABBREV,
    Patterns.PAGE_BARE,
    Patterns.PAGE_DE,
    Patterns.PRINT_DATETIME,
    Patterns.PRINT_HEADER,
)
