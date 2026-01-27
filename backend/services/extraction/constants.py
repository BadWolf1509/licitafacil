"""
Constantes centralizadas para processamento de documentos.

Este módulo contém todas as constantes usadas pelos módulos de extração,
evitando duplicação e garantindo consistência.
"""

# Categorias conhecidas de serviços de construção civil
# Inclui versões com e sem acentos para matching robusto
KNOWN_CATEGORIES = (
    "IMPERMEABILIZACAO",
    "IMPERMEABILIZAÇÃO",
    "INSTALACOES",
    "INSTALAÇÕES",
    "COBERTURA",
    "ESTRUTURA",
    "PINTURA",
    "REVESTIMENTOS",
    "ESQUADRIAS",
    "VIDROS",
    "PAVIMENTACAO",
    "PAVIMENTAÇÃO",
    "SERVICOS",
    "SERVIÇOS",
    "DEMOLICOES",
    "DEMOLIÇÕES",
    "FUNDACOES",
    "FUNDAÇÕES",
    "ALVENARIA",
    "DRENAGEM",
    "HIDROSSANITARIAS",
    "HIDROSSANITÁRIAS",
    "ELETRICAS",
    "ELÉTRICAS",
    "URBANIZACAO",
    "URBANIZAÇÃO",
)

# Versão sem acentos para comparação normalizada
KNOWN_CATEGORIES_NORMALIZED = (
    "IMPERMEABILIZACAO",
    "INSTALACOES",
    "COBERTURA",
    "ESTRUTURA",
    "PINTURA",
    "REVESTIMENTOS",
    "ESQUADRIAS",
    "VIDROS",
    "PAVIMENTACAO",
    "SERVICOS",
    "DEMOLICOES",
    "FUNDACOES",
    "ALVENARIA",
    "DRENAGEM",
    "HIDROSSANITARIAS",
    "ELETRICAS",
    "URBANIZACAO",
)

# Cabeçalhos de seção conhecidos (para filtrar descrições inválidas)
SECTION_HEADERS = {
    "SERVICOS PRELIMINARES",
    "DEMOLICOES",
    "PAVIMENTACAO",
    "URBANIZACAO",
    "INSTALACOES",
    "REVESTIMENTOS",
    "SERVICOS EXECUTADOS",
    "SERVICOS",
    "PRACA",
}

# Tokens narrativos (indicam texto institucional, não serviços)
NARRATIVE_TOKENS = (
    "ATESTAMOS",
    "CERTIFICAMOS",
    "DECLARAMOS",
    "RESPONSAVEL TECNICO",
    "CAPACIDADE TECNICA",
    "CONSELHO REGIONAL",
    "ENGENHEIRO",
    "CREA",
    "CNPJ",
    "CPF",
    "PREFEITURA",
    "DATA",
)

# Unidades de medida válidas (frozenset para lookup O(1))
VALID_UNITS = frozenset({
    # Unidade
    "UN", "UND", "UNID", "UNIDADE",
    # Metro linear e derivados
    "M", "ML", "M2", "M²", "M3", "M³",
    # Peso
    "KG", "G", "T", "TON",
    # Volume
    "L", "LT", "LITRO",
    # Verba/Global
    "VB", "VERBA", "GB", "GLOBAL",
    # Conjunto
    "CJ", "CONJ", "CONJUNTO",
    # Peça
    "PC", "PÇ", "PEÇA", "PECA",
    # Outros
    "GL", "PT", "PONTO",
    "HA", "HECTARE",
    "KM", "QUILOMETRO",
    "MES", "MÊS", "MENSAL",
    "JG", "JOGO",
})

# Unidades que devem ser ignoradas (medidas dimensionais, não de quantidade)
IGNORE_UNITS = ("MM", "CM")

# Tokens de rodapé e metadados
FOOTER_TOKENS = (
    "ATESTAMOS",
    "CERTIFICAMOS",
    "DECLARAMOS",
    "RESPONSAVEL TECNICO",
    "RESPONSÁVEL TÉCNICO",
    "CAPACIDADE TECNICA",
    "CAPACIDADE TÉCNICA",
)

# Tokens institucionais (indicam dados de empresa/órgão)
INSTITUTIONAL_TOKENS = (
    "CNPJ",
    "CREA",
    "CPF",
    "CAU",
    "INSCRICAO",
    "INSCRIÇÃO",
    "REGISTRO",
)

# Prefixos que indicam fim de seção de serviços
STOP_PREFIXES = (
    "ATESTAMOS",
    "CERTIFICAMOS",
    "DECLARAMOS",
    "RESPONSAVEL",
    "RESPONSÁVEL",
    "ENGENHEIRO",
    "LOCAL E DATA",
    "ASSINATURA",
)
