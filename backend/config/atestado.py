"""
Configuracoes de processamento de atestados do LicitaFacil.
Dividido em sub-classes para melhor organizacao.
"""
from .base import env_int, env_float, env_bool, PAID_SERVICES_ENABLED


class OCRLayoutConfig:
    """Configuracoes de OCR e layout."""
    CONFIDENCE = env_float("ATTESTADO_OCR_LAYOUT_CONFIDENCE", 0.3)
    DPI = env_int("ATTESTADO_OCR_LAYOUT_DPI", 300)
    RETRY_DPI = env_int("ATTESTADO_OCR_LAYOUT_RETRY_DPI", 450)
    RETRY_DPI_HARD = env_int("ATTESTADO_OCR_LAYOUT_RETRY_DPI_HARD", 0)
    RETRY_CONFIDENCE = env_float("ATTESTADO_OCR_LAYOUT_RETRY_CONFIDENCE", 0.2)
    RETRY_MIN_WORDS = env_int("ATTESTADO_OCR_LAYOUT_RETRY_MIN_WORDS", 120)
    RETRY_MIN_ITEMS = env_int("ATTESTADO_OCR_LAYOUT_RETRY_MIN_ITEMS", 5)
    RETRY_MIN_QTY_RATIO = env_float("ATTESTADO_OCR_LAYOUT_RETRY_MIN_QTY_RATIO", 0.35)
    PAGE_MIN_ITEMS = env_int("ATTESTADO_OCR_LAYOUT_PAGE_MIN_ITEMS", 3)


class OCRPageConfig:
    """Configuracoes de pagina OCR."""
    MIN_DOMINANT_LEN = env_int("ATTESTADO_OCR_PAGE_MIN_DOMINANT_LEN", 2)
    MIN_ITEM_RATIO = env_float("ATTESTADO_OCR_PAGE_MIN_ITEM_RATIO", 0.6)
    MIN_UNIT_RATIO = env_float("ATTESTADO_OCR_PAGE_MIN_UNIT_RATIO", 0.2)
    FALLBACK_UNIT_RATIO = env_float("ATTESTADO_OCR_PAGE_FALLBACK_UNIT_RATIO", 0.4)
    FALLBACK_ITEM_RATIO = env_float("ATTESTADO_OCR_PAGE_FALLBACK_ITEM_RATIO", 0.8)
    MIN_ITEMS = env_int("ATTESTADO_OCR_PAGE_MIN_ITEMS", 5)


class ItemColumnConfig:
    """Configuracoes de deteccao de coluna de item."""
    MIN_SCORE = env_float("ATTESTADO_ITEM_COL_MIN_SCORE", 0.5)
    RATIO = env_float("ATTESTADO_ITEM_COL_RATIO", 0.35)
    MAX_X_RATIO = env_float("ATTESTADO_ITEM_COL_MAX_X_RATIO", 0.35)
    MAX_INDEX = env_int("ATTESTADO_ITEM_COL_MAX_INDEX", 2)
    MIN_COUNT = env_int("ATTESTADO_ITEM_COL_MIN_COUNT", 6)


class SimilarityConfig:
    """Configuracoes de matching e similaridade."""
    DESC_THRESHOLD = env_float("ATTESTADO_DESC_SIM_THRESHOLD", 0.7)
    CODE_MATCH_THRESHOLD = env_float("ATTESTADO_CODE_MATCH_THRESHOLD", 0.55)
    SCORE_MARGIN = env_float("ATTESTADO_SCORE_MARGIN", 0.1)


class TableConfig:
    """Configuracoes de extracao de tabelas."""
    CONFIDENCE_THRESHOLD = env_float("ATTESTADO_TABLE_CONFIDENCE_THRESHOLD", 0.7)
    MIN_ITEMS = env_int("ATTESTADO_TABLE_MIN_ITEMS", 10)
    QUALITY_MIN_ITEMS = env_int("ATTESTADO_TABLE_QUALITY_MIN_ITEMS", 15)
    MIN_UNIT_RATIO = env_float("ATTESTADO_TABLE_MIN_UNIT_RATIO", 0.7)
    MIN_ITEM_RATIO = env_float("ATTESTADO_TABLE_MIN_ITEM_RATIO", 0.8)
    BAD_INVALID_CODE_RATIO = env_float("ATTESTADO_TABLE_BAD_INVALID_CODE_RATIO", 0.1)
    BAD_BIG_COMPONENT_RATIO = env_float("ATTESTADO_TABLE_BAD_BIG_COMPONENT_RATIO", 0.2)


class DocumentAIConfig:
    """
    Configuracoes do Google Document AI.

    IMPORTANTE: O tipo de processador e configurado no Google Cloud Console
    Tipos disponiveis e custos (Jan/2025):
      - Form Parser: US$ 30/1000 paginas (US$ 0.03/pag) - detecta tabelas estruturadas
      - OCR Processor: US$ 1.50/1000 paginas (US$ 0.0015/pag) - apenas texto OCR
    Recomendacao: Usar Form Parser apenas se pdfplumber falhar frequentemente
    Variaveis de ambiente:
      - DOCUMENT_AI_PROJECT_ID, DOCUMENT_AI_LOCATION, DOCUMENT_AI_PROCESSOR_ID
    """
    ENABLED = env_bool("DOCUMENT_AI_ENABLED", False) and PAID_SERVICES_ENABLED
    FALLBACK_ONLY = env_bool("DOCUMENT_AI_FALLBACK_ONLY", True)
    MIN_ITEMS = env_int("ATTESTADO_DOCUMENT_AI_MIN_ITEMS", 20)


class CascadeConfig:
    """
    Configuracoes do fluxo em cascata.
    Thresholds de qty_ratio por etapa de processamento.
    """
    # Etapa 1 (pdfplumber): gratuito, exige alta qualidade
    STAGE1_QTY_THRESHOLD = env_float("ATTESTADO_STAGE1_QTY_THRESHOLD", 0.70)
    # Etapa 2 (Document AI): baixo custo, aceita qualidade moderada
    STAGE2_QTY_THRESHOLD = env_float("ATTESTADO_STAGE2_QTY_THRESHOLD", 0.60)
    # Etapa 3 (Vision AI): alto custo, aceita qualidade baixa
    STAGE3_QTY_THRESHOLD = env_float("ATTESTADO_STAGE3_QTY_THRESHOLD", 0.40)


class ScannedDocConfig:
    """Configuracoes de deteccao de documento escaneado."""
    MIN_CHARS_PER_PAGE = env_int("ATTESTADO_SCANNED_MIN_CHARS", 200)
    IMAGE_PAGE_RATIO = env_float("ATTESTADO_SCANNED_IMG_RATIO", 0.5)
    DOMINANT_IMAGE_RATIO = env_float("ATTESTADO_DOMINANT_IMAGE_RATIO", 0.6)
    DOMINANT_IMAGE_MIN_PAGES = env_int("ATTESTADO_DOMINANT_IMAGE_MIN_PAGES", 2)


class VisionConfig:
    """Configuracoes de LLM e Vision AI."""
    LLM_FALLBACK_ONLY = env_bool("ATTESTADO_LLM_FALLBACK_ONLY", True)
    PAGEWISE_ENABLED = env_bool("ATTESTADO_PAGEWISE_VISION", True)
    QUALITY_THRESHOLD = env_float("ATTESTADO_VISION_QUALITY_THRESHOLD", 0.6)
    PAGEWISE_MIN_PAGES = env_int("ATTESTADO_PAGEWISE_MIN_PAGES", 3)
    PAGEWISE_MIN_ITEMS = env_int("ATTESTADO_PAGEWISE_MIN_ITEMS", 40)
    MIN_ITEMS_FOR_CONFIDENCE = env_int("ATTESTADO_MIN_ITEMS_FOR_CONFIDENCE", 25)


class RestartConfig:
    """Configuracoes de restart de numeracao (prefixo Sx-)."""
    MIN_CODES = env_int("ATTESTADO_RESTART_MIN_CODES", 8)
    MIN_OVERLAP = env_int("ATTESTADO_RESTART_MIN_OVERLAP", 2)
    MIN_OVERLAP_RATIO = env_float("ATTESTADO_RESTART_MIN_OVERLAP_RATIO", 0.25)


class TextSectionConfig:
    """Configuracoes de texto (fallback/descricoes)."""
    MAX_DESC_LEN = env_int("ATTESTADO_TEXT_SECTION_MAX_DESC_LEN", 500)
    # Aumentado para ser mais conservador e garantir extração de texto
    TABLE_CONFIDENCE_MIN = env_float("ATTESTADO_TEXT_SECTION_TABLE_CONFIDENCE_MIN", 0.85)
    QTY_RATIO_MIN = env_float("ATTESTADO_TEXT_SECTION_QTY_RATIO_MIN", 0.90)  # Aumentado de 0.8 para 0.90
    DUP_RATIO_MAX = env_float("ATTESTADO_TEXT_SECTION_DUP_RATIO_MAX", 0.35)


class AtestadoProcessingConfig:
    """
    Configuracoes centralizadas para processamento de atestados.

    Acesso via sub-classes organizadas:
        AtestadoProcessingConfig.ocr_layout.DPI
        AtestadoProcessingConfig.cascade.STAGE1_QTY_THRESHOLD

    Ou acesso direto para compatibilidade:
        AtestadoProcessingConfig.OCR_LAYOUT_DPI
    """
    # Sub-classes organizadas
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

    # === Acesso direto para compatibilidade ===
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
    # Deteccao de coluna de item
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
