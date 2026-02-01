"""
Constantes e padrões para o corretor de descrições.
"""
import re

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
FOOTER_DATE_PATTERN = re.compile(
    r'[A-Z\s]+/[A-Z]{2}\s+\d{1,2}\s+DE\s+(JANEIRO|FEVEREIRO|MARÇO|MARCO|ABRIL|MAIO|JUNHO|'
    r'JULHO|AGOSTO|SETEMBRO|OUTUBRO|NOVEMBRO|DEZEMBRO)\s+DE\s+\d{4}',
    re.IGNORECASE
)

# Substantivos técnicos comuns em descrições de construção civil
TECHNICAL_NOUNS = {
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

# Pares comuns de substantivo + adjetivo em construção civil
COMPOUND_PAIRS = {
    'CAIXA': {'ELÉTRICA', 'ELETRICA', 'PLÁSTICA', 'PLASTICA'},
    'TOMADA': {'RESIDENCIAL', 'INDUSTRIAL', 'ESPECIAL'},
    'CABO': {'FLEXÍVEL', 'FLEXIVEL', 'RÍGIDO', 'RIGIDO', 'ISOLADO'},
    'DISJUNTOR': {'MONOPOLAR', 'BIPOLAR', 'TRIPOLAR', 'TERMOMAGNETICO', 'TERMOMAGNÉTICO'},
    'QUADRO': {'ELÉTRICO', 'ELETRICO', 'DISTRIBUIÇÃO', 'DISTRIBUICAO'},
    'PONTO': {'ELÉTRICO', 'ELETRICO', 'HIDRÁULICO', 'HIDRAULICO'},
    'ELETRODUTO': {'FLEXÍVEL', 'FLEXIVEL', 'RÍGIDO', 'RIGIDO', 'PVC'},
    'TUBO': {'PVC', 'GALVANIZADO', 'FLEXÍVEL', 'FLEXIVEL'},
    'CONCRETO': {'INTERNA', 'INTERNAS', 'EXTERNA', 'EXTERNAS', 'INTERNO',
                 'EXTERNO', 'APARENTE', 'ARMADO', 'SIMPLES', 'MAGRO'},
    'ALVENARIA': {'INTERNA', 'INTERNAS', 'EXTERNA', 'EXTERNAS',
                  'ESTRUTURAL', 'VEDAÇÃO', 'VEDACAO'},
    'PAREDE': {'INTERNA', 'INTERNAS', 'EXTERNA', 'EXTERNAS'},
    'ESTRUTURA': {'METÁLICA', 'METALICA', 'MADEIRA'},
    'LAJE': {'MACIÇA', 'MACICA', 'NERVURADA', 'PRÉ-MOLDADA', 'PRE-MOLDADA'},
}
