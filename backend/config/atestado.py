"""
Configurações de processamento de atestados do LicitaFácil.

Usa dataclasses para validação automática e documentação.
Dividido em sub-classes para melhor organização.
"""
from dataclasses import dataclass, field
from typing import ClassVar

from .base import env_int, env_float, env_bool, PAID_SERVICES_ENABLED


@dataclass(frozen=True)
class OCRLayoutConfig:
    """
    Configurações de OCR e layout para extração de texto.

    Attributes:
        CONFIDENCE: Confiança mínima para aceitar detecção OCR (0-1).
            Valores baixos capturam mais texto mas com mais erros.
        DPI: Resolução para renderização de páginas PDF.
            Maior DPI = melhor qualidade mas mais lento.
        RETRY_DPI: DPI para retry quando primeira tentativa falha.
        RETRY_DPI_HARD: DPI para retry agressivo (0 = desabilitado).
        RETRY_CONFIDENCE: Confiança mínima no retry.
        RETRY_MIN_WORDS: Mínimo de palavras para considerar OCR válido.
        RETRY_MIN_ITEMS: Mínimo de itens para considerar extração válida.
        RETRY_MIN_QTY_RATIO: Proporção mínima de itens com quantidade no retry.
        PAGE_MIN_ITEMS: Mínimo de itens por página para considerar válida.
    """
    CONFIDENCE: ClassVar[float] = env_float("ATTESTADO_OCR_LAYOUT_CONFIDENCE", 0.3)
    DPI: ClassVar[int] = env_int("ATTESTADO_OCR_LAYOUT_DPI", 300)
    RETRY_DPI: ClassVar[int] = env_int("ATTESTADO_OCR_LAYOUT_RETRY_DPI", 450)
    RETRY_DPI_HARD: ClassVar[int] = env_int("ATTESTADO_OCR_LAYOUT_RETRY_DPI_HARD", 0)
    RETRY_CONFIDENCE: ClassVar[float] = env_float("ATTESTADO_OCR_LAYOUT_RETRY_CONFIDENCE", 0.2)
    RETRY_MIN_WORDS: ClassVar[int] = env_int("ATTESTADO_OCR_LAYOUT_RETRY_MIN_WORDS", 120)
    RETRY_MIN_ITEMS: ClassVar[int] = env_int("ATTESTADO_OCR_LAYOUT_RETRY_MIN_ITEMS", 5)
    RETRY_MIN_QTY_RATIO: ClassVar[float] = env_float("ATTESTADO_OCR_LAYOUT_RETRY_MIN_QTY_RATIO", 0.35)
    PAGE_MIN_ITEMS: ClassVar[int] = env_int("ATTESTADO_OCR_LAYOUT_PAGE_MIN_ITEMS", 3)


@dataclass(frozen=True)
class OCRPageConfig:
    """
    Configurações de página OCR para validação de qualidade.

    Attributes:
        MIN_DOMINANT_LEN: Comprimento mínimo do código dominante.
        MIN_ITEM_RATIO: Proporção mínima de células com código de item válido.
        MIN_UNIT_RATIO: Proporção mínima de células com unidade válida.
        FALLBACK_UNIT_RATIO: Proporção de unidade para fallback.
        FALLBACK_ITEM_RATIO: Proporção de item para fallback.
        MIN_ITEMS: Mínimo de itens para considerar página válida.
    """
    MIN_DOMINANT_LEN: ClassVar[int] = env_int("ATTESTADO_OCR_PAGE_MIN_DOMINANT_LEN", 2)
    MIN_ITEM_RATIO: ClassVar[float] = env_float("ATTESTADO_OCR_PAGE_MIN_ITEM_RATIO", 0.6)
    MIN_UNIT_RATIO: ClassVar[float] = env_float("ATTESTADO_OCR_PAGE_MIN_UNIT_RATIO", 0.2)
    FALLBACK_UNIT_RATIO: ClassVar[float] = env_float("ATTESTADO_OCR_PAGE_FALLBACK_UNIT_RATIO", 0.4)
    FALLBACK_ITEM_RATIO: ClassVar[float] = env_float("ATTESTADO_OCR_PAGE_FALLBACK_ITEM_RATIO", 0.8)
    MIN_ITEMS: ClassVar[int] = env_int("ATTESTADO_OCR_PAGE_MIN_ITEMS", 5)


@dataclass(frozen=True)
class ItemColumnConfig:
    """
    Configurações de detecção de coluna de item em tabelas.

    Attributes:
        MIN_SCORE: Score mínimo para considerar coluna como coluna de item.
        RATIO: Proporção mínima de células válidas na coluna.
        MAX_X_RATIO: Posição X máxima da coluna (0-1, da esquerda).
        MAX_INDEX: Índice máximo da coluna (0 = primeira coluna).
        MIN_COUNT: Mínimo de células válidas para confirmar coluna.
    """
    MIN_SCORE: ClassVar[float] = env_float("ATTESTADO_ITEM_COL_MIN_SCORE", 0.5)
    RATIO: ClassVar[float] = env_float("ATTESTADO_ITEM_COL_RATIO", 0.35)
    MAX_X_RATIO: ClassVar[float] = env_float("ATTESTADO_ITEM_COL_MAX_X_RATIO", 0.35)
    MAX_INDEX: ClassVar[int] = env_int("ATTESTADO_ITEM_COL_MAX_INDEX", 2)
    MIN_COUNT: ClassVar[int] = env_int("ATTESTADO_ITEM_COL_MIN_COUNT", 6)


@dataclass(frozen=True)
class SimilarityConfig:
    """
    Configurações de matching e similaridade entre textos.

    Attributes:
        DESC_THRESHOLD: Similaridade mínima para considerar descrições iguais (0-1).
            Usado para deduplicação e matching de serviços.
        CODE_MATCH_THRESHOLD: Similaridade mínima para match de código de item.
        SCORE_MARGIN: Margem de score para desempate entre candidatos.
    """
    DESC_THRESHOLD: ClassVar[float] = env_float("ATTESTADO_DESC_SIM_THRESHOLD", 0.7)
    CODE_MATCH_THRESHOLD: ClassVar[float] = env_float("ATTESTADO_CODE_MATCH_THRESHOLD", 0.55)
    SCORE_MARGIN: ClassVar[float] = env_float("ATTESTADO_SCORE_MARGIN", 0.1)


@dataclass(frozen=True)
class TableConfig:
    """
    Configurações de extração de tabelas.

    Attributes:
        CONFIDENCE_THRESHOLD: Confiança mínima para aceitar tabela extraída (0-1).
        MIN_ITEMS: Mínimo de itens para considerar tabela válida.
        QUALITY_MIN_ITEMS: Mínimo de itens para aplicar filtros de qualidade.
        MIN_UNIT_RATIO: Proporção mínima de itens com unidade válida.
        MIN_ITEM_RATIO: Proporção mínima de itens com código válido.
        BAD_INVALID_CODE_RATIO: Proporção máxima de códigos inválidos antes de rejeitar.
        BAD_BIG_COMPONENT_RATIO: Proporção máxima de componentes grandes (>50).
    """
    CONFIDENCE_THRESHOLD: ClassVar[float] = env_float("ATTESTADO_TABLE_CONFIDENCE_THRESHOLD", 0.7)
    MIN_ITEMS: ClassVar[int] = env_int("ATTESTADO_TABLE_MIN_ITEMS", 10)
    QUALITY_MIN_ITEMS: ClassVar[int] = env_int("ATTESTADO_TABLE_QUALITY_MIN_ITEMS", 15)
    MIN_UNIT_RATIO: ClassVar[float] = env_float("ATTESTADO_TABLE_MIN_UNIT_RATIO", 0.7)
    MIN_ITEM_RATIO: ClassVar[float] = env_float("ATTESTADO_TABLE_MIN_ITEM_RATIO", 0.8)
    BAD_INVALID_CODE_RATIO: ClassVar[float] = env_float("ATTESTADO_TABLE_BAD_INVALID_CODE_RATIO", 0.1)
    BAD_BIG_COMPONENT_RATIO: ClassVar[float] = env_float("ATTESTADO_TABLE_BAD_BIG_COMPONENT_RATIO", 0.2)


@dataclass(frozen=True)
class DocumentAIConfig:
    """
    Configurações do Google Document AI.

    IMPORTANTE: O tipo de processador é configurado no Google Cloud Console.

    Tipos disponíveis e custos (Jan/2025):
        - Form Parser: US$ 30/1000 páginas (US$ 0.03/pág) - detecta tabelas estruturadas
        - OCR Processor: US$ 1.50/1000 páginas (US$ 0.0015/pág) - apenas texto OCR

    Recomendação: Usar Form Parser apenas se pdfplumber falhar frequentemente.

    Variáveis de ambiente necessárias:
        - DOCUMENT_AI_PROJECT_ID
        - DOCUMENT_AI_LOCATION
        - DOCUMENT_AI_PROCESSOR_ID

    Attributes:
        ENABLED: Se Document AI está habilitado (requer PAID_SERVICES_ENABLED).
        FALLBACK_ONLY: Se True, usa apenas quando outras fontes falham.
        MIN_ITEMS: Mínimo de itens extraídos para considerar sucesso.
    """
    ENABLED: ClassVar[bool] = env_bool("DOCUMENT_AI_ENABLED", False) and PAID_SERVICES_ENABLED
    FALLBACK_ONLY: ClassVar[bool] = env_bool("DOCUMENT_AI_FALLBACK_ONLY", True)
    MIN_ITEMS: ClassVar[int] = env_int("ATTESTADO_DOCUMENT_AI_MIN_ITEMS", 20)


@dataclass(frozen=True)
class CascadeConfig:
    """
    Configurações do fluxo em cascata de extração.

    O processamento usa cascata de fontes com thresholds decrescentes:
    1. pdfplumber (gratuito) - exige alta qualidade
    2. Document AI (baixo custo) - aceita qualidade moderada
    3. Vision AI (alto custo) - aceita qualidade baixa

    Attributes:
        STAGE1_QTY_THRESHOLD: Proporção mínima de itens com quantidade (pdfplumber).
        STAGE2_QTY_THRESHOLD: Proporção mínima de itens com quantidade (Document AI).
        STAGE3_QTY_THRESHOLD: Proporção mínima de itens com quantidade (Vision AI).
    """
    STAGE1_QTY_THRESHOLD: ClassVar[float] = env_float("ATTESTADO_STAGE1_QTY_THRESHOLD", 0.70)
    STAGE2_QTY_THRESHOLD: ClassVar[float] = env_float("ATTESTADO_STAGE2_QTY_THRESHOLD", 0.60)
    STAGE3_QTY_THRESHOLD: ClassVar[float] = env_float("ATTESTADO_STAGE3_QTY_THRESHOLD", 0.40)


@dataclass(frozen=True)
class ScannedDocConfig:
    """
    Configurações de detecção de documento escaneado.

    Documentos escaneados requerem OCR e têm processamento diferenciado.

    Attributes:
        MIN_CHARS_PER_PAGE: Mínimo de caracteres por página para considerar digital.
            Páginas com menos caracteres são consideradas escaneadas.
        IMAGE_PAGE_RATIO: Proporção de páginas com imagem dominante para classificar como escaneado.
        DOMINANT_IMAGE_RATIO: Proporção da área da página coberta por imagem para ser dominante.
        DOMINANT_IMAGE_MIN_PAGES: Mínimo de páginas com imagem dominante para ativar Vision.
    """
    MIN_CHARS_PER_PAGE: ClassVar[int] = env_int("ATTESTADO_SCANNED_MIN_CHARS", 200)
    IMAGE_PAGE_RATIO: ClassVar[float] = env_float("ATTESTADO_SCANNED_IMG_RATIO", 0.5)
    DOMINANT_IMAGE_RATIO: ClassVar[float] = env_float("ATTESTADO_DOMINANT_IMAGE_RATIO", 0.6)
    DOMINANT_IMAGE_MIN_PAGES: ClassVar[int] = env_int("ATTESTADO_DOMINANT_IMAGE_MIN_PAGES", 2)


@dataclass(frozen=True)
class VisionConfig:
    """
    Configurações de LLM e Vision AI (GPT-4o, Gemini).

    Vision AI é usado para documentos complexos com tabelas em imagem.

    Attributes:
        LLM_FALLBACK_ONLY: Se True, usa LLM apenas quando outras fontes falham.
        PAGEWISE_ENABLED: Se True, processa páginas individualmente com Vision.
        QUALITY_THRESHOLD: Qualidade mínima da extração para aceitar resultado.
        PAGEWISE_MIN_PAGES: Mínimo de páginas para ativar processamento por página.
        PAGEWISE_MIN_ITEMS: Mínimo de itens esperados para ativar pagewise.
        MIN_ITEMS_FOR_CONFIDENCE: Mínimo de itens para calcular confiança.
    """
    LLM_FALLBACK_ONLY: ClassVar[bool] = env_bool("ATTESTADO_LLM_FALLBACK_ONLY", True)
    PAGEWISE_ENABLED: ClassVar[bool] = env_bool("ATTESTADO_PAGEWISE_VISION", True)
    QUALITY_THRESHOLD: ClassVar[float] = env_float("ATTESTADO_VISION_QUALITY_THRESHOLD", 0.6)
    PAGEWISE_MIN_PAGES: ClassVar[int] = env_int("ATTESTADO_PAGEWISE_MIN_PAGES", 3)
    PAGEWISE_MIN_ITEMS: ClassVar[int] = env_int("ATTESTADO_PAGEWISE_MIN_ITEMS", 40)
    MIN_ITEMS_FOR_CONFIDENCE: ClassVar[int] = env_int("ATTESTADO_MIN_ITEMS_FOR_CONFIDENCE", 25)


@dataclass(frozen=True)
class RestartConfig:
    """
    Configurações de restart de numeração (prefixo Sx-).

    Alguns documentos reiniciam a numeração de itens (1.1, 1.2... depois 1.1, 1.2 novamente).
    O sistema detecta isso e adiciona prefixos S2-, S3- para diferenciar.

    Attributes:
        MIN_CODES: Mínimo de códigos repetidos para detectar restart.
        MIN_OVERLAP: Mínimo de códigos sobrepostos entre segmentos.
        MIN_OVERLAP_RATIO: Proporção mínima de sobreposição para confirmar restart.
    """
    MIN_CODES: ClassVar[int] = env_int("ATTESTADO_RESTART_MIN_CODES", 8)
    MIN_OVERLAP: ClassVar[int] = env_int("ATTESTADO_RESTART_MIN_OVERLAP", 2)
    MIN_OVERLAP_RATIO: ClassVar[float] = env_float("ATTESTADO_RESTART_MIN_OVERLAP_RATIO", 0.25)


@dataclass(frozen=True)
class TextSectionConfig:
    """
    Configurações de extração de texto (fallback e descrições).

    Usado quando tabelas não são suficientes ou para enriquecer descrições.

    Attributes:
        MAX_DESC_LEN: Comprimento máximo de descrição extraída do texto.
        TABLE_CONFIDENCE_MIN: Confiança mínima da tabela para desabilitar text_section.
            Se tabela tem alta confiança, não precisa extrair do texto.
        QTY_RATIO_MIN: Proporção mínima de quantidades para desabilitar text_section.
        DUP_RATIO_MAX: Proporção máxima de duplicatas para desabilitar text_section.
    """
    MAX_DESC_LEN: ClassVar[int] = env_int("ATTESTADO_TEXT_SECTION_MAX_DESC_LEN", 500)
    TABLE_CONFIDENCE_MIN: ClassVar[float] = env_float("ATTESTADO_TEXT_SECTION_TABLE_CONFIDENCE_MIN", 0.85)
    QTY_RATIO_MIN: ClassVar[float] = env_float("ATTESTADO_TEXT_SECTION_QTY_RATIO_MIN", 0.90)
    DUP_RATIO_MAX: ClassVar[float] = env_float("ATTESTADO_TEXT_SECTION_DUP_RATIO_MAX", 0.35)


class AtestadoProcessingConfig:
    """
    Configurações centralizadas para processamento de atestados.

    Acesso via sub-classes organizadas (recomendado):
        AtestadoProcessingConfig.ocr_layout.DPI
        AtestadoProcessingConfig.cascade.STAGE1_QTY_THRESHOLD

    Ou acesso direto para compatibilidade (legado):
        AtestadoProcessingConfig.OCR_LAYOUT_DPI
    """
    # Sub-classes organizadas (dataclasses documentadas)
    ocr_layout = OCRLayoutConfig
    ocr_page = OCRPageConfig
    item_column = ItemColumnConfig
    similarity = SimilarityConfig
    table = TableConfig
    document_ai = DocumentAIConfig
    cascade = CascadeConfig
    scanned = ScannedDocConfig
    vision = VisionConfig
    restart = RestartConfig
    text_section = TextSectionConfig

    # === Acesso direto para compatibilidade (legado) ===
    # OCR e Layout
    OCR_LAYOUT_CONFIDENCE = OCRLayoutConfig.CONFIDENCE
    OCR_LAYOUT_DPI = OCRLayoutConfig.DPI
    OCR_LAYOUT_RETRY_DPI = OCRLayoutConfig.RETRY_DPI
    OCR_LAYOUT_RETRY_DPI_HARD = OCRLayoutConfig.RETRY_DPI_HARD
    OCR_LAYOUT_RETRY_CONFIDENCE = OCRLayoutConfig.RETRY_CONFIDENCE
    OCR_LAYOUT_RETRY_MIN_WORDS = OCRLayoutConfig.RETRY_MIN_WORDS
    OCR_LAYOUT_RETRY_MIN_ITEMS = OCRLayoutConfig.RETRY_MIN_ITEMS
    OCR_LAYOUT_RETRY_MIN_QTY_RATIO = OCRLayoutConfig.RETRY_MIN_QTY_RATIO
    OCR_LAYOUT_PAGE_MIN_ITEMS = OCRLayoutConfig.PAGE_MIN_ITEMS
    OCR_PAGE_MIN_DOMINANT_LEN = OCRPageConfig.MIN_DOMINANT_LEN
    OCR_PAGE_MIN_ITEM_RATIO = OCRPageConfig.MIN_ITEM_RATIO
    OCR_PAGE_MIN_UNIT_RATIO = OCRPageConfig.MIN_UNIT_RATIO
    OCR_PAGE_FALLBACK_UNIT_RATIO = OCRPageConfig.FALLBACK_UNIT_RATIO
    OCR_PAGE_FALLBACK_ITEM_RATIO = OCRPageConfig.FALLBACK_ITEM_RATIO
    OCR_PAGE_MIN_ITEMS = OCRPageConfig.MIN_ITEMS
    # Detecção de coluna de item
    ITEM_COL_MIN_SCORE = ItemColumnConfig.MIN_SCORE
    ITEM_COL_RATIO = ItemColumnConfig.RATIO
    ITEM_COL_MAX_X_RATIO = ItemColumnConfig.MAX_X_RATIO
    ITEM_COL_MAX_INDEX = ItemColumnConfig.MAX_INDEX
    ITEM_COL_MIN_COUNT = ItemColumnConfig.MIN_COUNT
    # Matching e Similaridade
    DESC_SIM_THRESHOLD = SimilarityConfig.DESC_THRESHOLD
    CODE_MATCH_THRESHOLD = SimilarityConfig.CODE_MATCH_THRESHOLD
    SCORE_MARGIN = SimilarityConfig.SCORE_MARGIN
    # Tabelas
    TABLE_CONFIDENCE_THRESHOLD = TableConfig.CONFIDENCE_THRESHOLD
    TABLE_MIN_ITEMS = TableConfig.MIN_ITEMS
    TABLE_QUALITY_MIN_ITEMS = TableConfig.QUALITY_MIN_ITEMS
    TABLE_MIN_UNIT_RATIO = TableConfig.MIN_UNIT_RATIO
    TABLE_MIN_ITEM_RATIO = TableConfig.MIN_ITEM_RATIO
    TABLE_BAD_INVALID_CODE_RATIO = TableConfig.BAD_INVALID_CODE_RATIO
    TABLE_BAD_BIG_COMPONENT_RATIO = TableConfig.BAD_BIG_COMPONENT_RATIO
    # Document AI
    DOCUMENT_AI_ENABLED = DocumentAIConfig.ENABLED
    DOCUMENT_AI_FALLBACK_ONLY = DocumentAIConfig.FALLBACK_ONLY
    DOCUMENT_AI_MIN_ITEMS = DocumentAIConfig.MIN_ITEMS
    # Cascata
    STAGE1_QTY_THRESHOLD = CascadeConfig.STAGE1_QTY_THRESHOLD
    STAGE2_QTY_THRESHOLD = CascadeConfig.STAGE2_QTY_THRESHOLD
    STAGE3_QTY_THRESHOLD = CascadeConfig.STAGE3_QTY_THRESHOLD
    # Documento escaneado
    SCANNED_MIN_CHARS_PER_PAGE = ScannedDocConfig.MIN_CHARS_PER_PAGE
    SCANNED_IMAGE_PAGE_RATIO = ScannedDocConfig.IMAGE_PAGE_RATIO
    DOMINANT_IMAGE_RATIO = ScannedDocConfig.DOMINANT_IMAGE_RATIO
    DOMINANT_IMAGE_MIN_PAGES = ScannedDocConfig.DOMINANT_IMAGE_MIN_PAGES
    # LLM e Vision
    LLM_FALLBACK_ONLY = VisionConfig.LLM_FALLBACK_ONLY
    PAGEWISE_VISION_ENABLED = VisionConfig.PAGEWISE_ENABLED
    VISION_QUALITY_THRESHOLD = VisionConfig.QUALITY_THRESHOLD
    PAGEWISE_MIN_PAGES = VisionConfig.PAGEWISE_MIN_PAGES
    PAGEWISE_MIN_ITEMS = VisionConfig.PAGEWISE_MIN_ITEMS
    MIN_ITEMS_FOR_CONFIDENCE = VisionConfig.MIN_ITEMS_FOR_CONFIDENCE
    # Restart
    RESTART_MIN_CODES = RestartConfig.MIN_CODES
    RESTART_MIN_OVERLAP = RestartConfig.MIN_OVERLAP
    RESTART_MIN_OVERLAP_RATIO = RestartConfig.MIN_OVERLAP_RATIO
    # Texto
    TEXT_SECTION_MAX_DESC_LEN = TextSectionConfig.MAX_DESC_LEN
    TEXT_SECTION_TABLE_CONFIDENCE_MIN = TextSectionConfig.TABLE_CONFIDENCE_MIN
    TEXT_SECTION_QTY_RATIO_MIN = TextSectionConfig.QTY_RATIO_MIN
    TEXT_SECTION_DUP_RATIO_MAX = TextSectionConfig.DUP_RATIO_MAX
