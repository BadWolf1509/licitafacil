"""
Configurações centralizadas do LicitaFacil.

Todas as constantes e configurações devem ser definidas aqui.
"""
import os
from typing import List, Optional
from dotenv import load_dotenv

load_dotenv()


# === Helpers para leitura de variáveis de ambiente ===
def env_bool(key: str, default: bool = False) -> bool:
    """Lê variável de ambiente como booleano."""
    val = os.getenv(key, "").lower()
    if val in ("1", "true", "yes", "on"):
        return True
    if val in ("0", "false", "no", "off"):
        return False
    return default


def env_int(key: str, default: int = 0) -> int:
    """Lê variável de ambiente como inteiro."""
    val = os.getenv(key)
    if val is None:
        return default
    try:
        return int(val)
    except ValueError:
        return default


def env_float(key: str, default: float = 0.0) -> float:
    """Lê variável de ambiente como float."""
    val = os.getenv(key)
    if val is None:
        return default
    try:
        return float(val)
    except ValueError:
        return default


# === Diretórios ===
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "uploads")


# === Extensões de Arquivo Permitidas ===
ALLOWED_PDF_EXTENSIONS = [".pdf"]
ALLOWED_IMAGE_EXTENSIONS = [".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp"]
ALLOWED_DOCUMENT_EXTENSIONS = ALLOWED_PDF_EXTENSIONS + ALLOWED_IMAGE_EXTENSIONS


# === CORS ===
def get_cors_origins() -> List[str]:
    """
    Retorna lista de origens permitidas para CORS.

    Em produção, defina CORS_ORIGINS como lista separada por vírgula:
    CORS_ORIGINS=https://meusite.com,https://api.meusite.com
    """
    origins_env = os.getenv("CORS_ORIGINS", "")
    if origins_env:
        return [origin.strip() for origin in origins_env.split(",") if origin.strip()]

    # Em desenvolvimento, permitir localhost
    if os.getenv("ENVIRONMENT", "development") == "development":
        return [
            "http://localhost:8000",
            "http://127.0.0.1:8000",
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ]

    # Em produção sem CORS_ORIGINS definido, não permitir nada
    return []


CORS_ORIGINS = get_cors_origins()
CORS_ALLOW_CREDENTIALS = os.getenv("CORS_ALLOW_CREDENTIALS", "true").lower() == "true"


# === Rate Limiting ===
RATE_LIMIT_ENABLED = env_bool("RATE_LIMIT_ENABLED", True)
RATE_LIMIT_REQUESTS = env_int("RATE_LIMIT_REQUESTS", 300)  # requests per window
RATE_LIMIT_WINDOW = env_int("RATE_LIMIT_WINDOW", 60)  # window in seconds


# === Segurança ===
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")

SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    if ENVIRONMENT == "production":
        raise ValueError(
            "CRÍTICO: SECRET_KEY não definida em produção! "
            "Defina a variável de ambiente SECRET_KEY com uma chave segura de pelo menos 32 caracteres."
        )
    # Em desenvolvimento, usar chave padrão com aviso
    import warnings
    warnings.warn(
        "SECRET_KEY não definida! Usando chave de desenvolvimento. "
        "Defina SECRET_KEY em produção.",
        RuntimeWarning
    )
    SECRET_KEY = "dev-only-insecure-key-do-not-use-in-production"

# Validar comprimento mínimo da chave
if len(SECRET_KEY) < 32 and ENVIRONMENT == "production":
    raise ValueError(
        f"SECRET_KEY muito curta ({len(SECRET_KEY)} chars). "
        "Use pelo menos 32 caracteres em produção."
    )

JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_EXPIRATION_HOURS = int(os.getenv("JWT_EXPIRATION_HOURS", "24"))


# === Mensagens de Erro Padronizadas ===
class Messages:
    # Recursos não encontrados
    NOT_FOUND = "Recurso não encontrado"
    ATESTADO_NOT_FOUND = "Atestado não encontrado"
    ANALISE_NOT_FOUND = "Análise não encontrada"
    USER_NOT_FOUND = "Usuário não encontrado"
    JOB_NOT_FOUND = "Job não encontrado"
    FILE_NOT_FOUND = "Arquivo não encontrado"
    ATESTADO_FILE_NOT_FOUND = "Arquivo do atestado não encontrado"
    EDITAL_FILE_NOT_FOUND = "Arquivo do edital não encontrado"
    # Valores padrão
    DESCRICAO_NAO_IDENTIFICADA = "Descrição não identificada"
    # Acesso e autenticação
    ACCESS_DENIED = "Acesso negado"
    UNAUTHORIZED = "Acesso não autorizado"
    FORBIDDEN = "Acesso proibido"
    CANNOT_DEACTIVATE_SELF = "Você não pode desativar sua própria conta"
    EMAIL_EXISTS = "Email já cadastrado"
    INVALID_CREDENTIALS = "Email ou senha incorretos"
    USER_INACTIVE = "Usuário inativo"
    USER_NOT_APPROVED = "Usuário aguardando aprovação do administrador"
    JOB_INVALID_STATUS = "Job não pode ser processado no status atual"
    # Validação de arquivos
    INVALID_FILE = "Arquivo inválido"
    INVALID_EXTENSION = "Extensão de arquivo não permitida"
    FILE_REQUIRED = "Arquivo é obrigatório"
    # Rate limiting e erros
    RATE_LIMIT_EXCEEDED = "Muitas requisições. Tente novamente em alguns minutos."
    INTERNAL_ERROR = "Erro interno do servidor"
    DB_ERROR = "Erro ao acessar o banco de dados"
    DUPLICATE_ENTRY = "Registro já existe"
    PROCESSING_ERROR = "Erro ao processar documento. Tente novamente."
    QUEUE_ERROR = "Erro ao enfileirar processamento. Tente novamente."
    # Atestados
    NO_ATESTADOS = "Você não possui atestados cadastrados. Cadastre atestados antes de analisar uma licitação."
    UPLOAD_SUCCESS = "Arquivo enviado. Processamento iniciado."
    ATESTADO_DELETED = "Atestado excluído com sucesso!"
    ANALISE_DELETED = "Análise excluída com sucesso!"


# === Processamento ===
OCR_PARALLEL_ENABLED = env_bool("OCR_PARALLEL_ENABLED", True)
OCR_MAX_WORKERS = env_int("OCR_MAX_WORKERS", 4)
OCR_PREPROCESS_ENABLED = env_bool("OCR_PREPROCESS", True)
OCR_TESSERACT_FALLBACK = env_bool("OCR_TESSERACT_FALLBACK", True)


# === Fila de Processamento ===
QUEUE_MAX_CONCURRENT = env_int("QUEUE_MAX_CONCURRENT", 3)
QUEUE_POLL_INTERVAL = env_float("QUEUE_POLL_INTERVAL", 1.0)


# === Autenticação ===
ACCESS_TOKEN_EXPIRE_MINUTES = env_int("ACCESS_TOKEN_EXPIRE_MINUTES", 30)


# === Paginação ===
DEFAULT_PAGE_SIZE = env_int("DEFAULT_PAGE_SIZE", 20)
MAX_PAGE_SIZE = env_int("MAX_PAGE_SIZE", 100)


# === Configurações de OCR ===
class OCRConfig:
    """Configurações para processamento OCR."""
    DPI = env_int("OCR_DPI", 300)
    MIN_TEXT_PER_PAGE = env_int("OCR_MIN_TEXT_PER_PAGE", 200)
    MIN_TEXT_LENGTH = env_int("OCR_MIN_TEXT_LENGTH", 100)
    MIN_CONFIDENT_CHARS = env_int("OCR_MIN_CONFIDENT_CHARS", 20)


# === Configurações do Pipeline ===
class PipelineConfig:
    """Configurações de confiança do pipeline de extração."""
    MIN_CONFIDENCE_LOCAL_OCR = env_float("MIN_CONFIDENCE_LOCAL_OCR", 0.70)
    MIN_CONFIDENCE_CLOUD_OCR = env_float("MIN_CONFIDENCE_CLOUD_OCR", 0.85)



# === Configuracoes de Matching ===
class MatchingConfig:
    """Configuracoes do matching deterministico."""
    SIMILARITY_THRESHOLD = env_float("MATCH_SIMILARITY_THRESHOLD", 0.35)
    MIN_COMMON_WORDS = env_int("MATCH_MIN_COMMON_WORDS", 2)
    MIN_COMMON_WORDS_SHORT = env_int("MATCH_MIN_COMMON_WORDS_SHORT", 1)
# === Configurações de Modelos de IA ===
class AIModelConfig:
    """Configurações dos modelos de IA."""
    # OpenAI
    OPENAI_TEXT_MODEL = os.getenv("OPENAI_TEXT_MODEL", "gpt-4o-mini")
    OPENAI_VISION_MODEL = os.getenv("OPENAI_VISION_MODEL", "gpt-4o")
    OPENAI_MAX_TOKENS = env_int("OPENAI_MAX_TOKENS", 16000)
    OPENAI_TEMPERATURE = env_float("OPENAI_TEMPERATURE", 0)
    # Gemini
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
    GEMINI_PRO_MODEL = os.getenv("GEMINI_PRO_MODEL", "gemini-2.0-flash")
    GEMINI_MAX_TOKENS = env_int("GEMINI_MAX_TOKENS", 16000)
    GEMINI_TEMPERATURE = env_float("GEMINI_TEMPERATURE", 0)
    GEMINI_ALLOW_LEGACY = env_bool("GEMINI_ALLOW_LEGACY", False)


# === Configurações de Extração de Tabelas ===
class TableExtractionConfig:
    """Configurações para extração e parsing de tabelas."""
    HEADER_ROWS_LIMIT = env_int("TABLE_HEADER_ROWS_LIMIT", 5)
    HEADER_MIN_KEYWORD_MATCHES = env_int("TABLE_HEADER_MIN_KEYWORDS", 2)
    MIN_DESCRIPTION_LENGTH = env_int("TABLE_MIN_DESC_LENGTH", 5)
    # Validação de colunas
    MIN_UNIT_RATIO = env_float("TABLE_MIN_UNIT_RATIO", 0.2)
    MIN_QTY_RATIO = env_float("TABLE_MIN_QTY_RATIO", 0.35)
    MIN_DESC_LEN = env_float("TABLE_MIN_DESC_LEN", 10.0)
    MAX_DESC_NUMERIC = env_float("TABLE_MAX_DESC_NUMERIC", 0.6)
    # Pesos de scoring para detecção de coluna de item
    ITEM_SCORE_PATTERN_WEIGHT = env_float("ITEM_SCORE_PATTERN_WEIGHT", 0.45)
    ITEM_SCORE_SEQ_WEIGHT = env_float("ITEM_SCORE_SEQ_WEIGHT", 0.2)
    ITEM_SCORE_UNIQUE_WEIGHT = env_float("ITEM_SCORE_UNIQUE_WEIGHT", 0.2)
    ITEM_SCORE_LEFT_BIAS_WEIGHT = env_float("ITEM_SCORE_LEFT_BIAS_WEIGHT", 0.1)
    ITEM_SCORE_LENGTH_BONUS_WEIGHT = env_float("ITEM_SCORE_LENGTH_BONUS_WEIGHT", 0.05)


# === Configurações de Deduplicação ===
class DeduplicationConfig:
    """Configurações para detecção de duplicatas."""
    SIMILARITY_THRESHOLD = env_float("DEDUP_SIMILARITY_THRESHOLD", 0.5)
    MAX_DESC_CHARS = env_int("DEDUP_MAX_DESC_CHARS", 50)
    ITEM_LENGTH_RATIO = env_float("ATTESTADO_ITEM_LEN_RATIO", 0.6)
    ITEM_LENGTH_KEEP_MIN_DESC = env_int("ATTESTADO_ITEM_LEN_KEEP_MIN_DESC", 20)
    ITEM_PREFIX_RATIO = env_float("ATTESTADO_ITEM_PREFIX_RATIO", 0.7)
    ITEM_PREFIX_KEEP_MIN_DESC = env_int("ATTESTADO_ITEM_PREFIX_KEEP_MIN_DESC", 15)
    ITEM_COL_MIN_SCORE = env_float("ATTESTADO_ITEM_COL_MIN_SCORE", 0.5)


# === Configurações de Processamento de Atestados ===
class AtestadoProcessingConfig:
    """Configurações centralizadas para processamento de atestados."""
    # OCR e Layout
    OCR_LAYOUT_CONFIDENCE = env_float("ATTESTADO_OCR_LAYOUT_CONFIDENCE", 0.3)
    OCR_LAYOUT_DPI = env_int("ATTESTADO_OCR_LAYOUT_DPI", 300)
    OCR_LAYOUT_RETRY_DPI = env_int("ATTESTADO_OCR_LAYOUT_RETRY_DPI", 450)
    OCR_LAYOUT_RETRY_DPI_HARD = env_int("ATTESTADO_OCR_LAYOUT_RETRY_DPI_HARD", 0)
    OCR_LAYOUT_RETRY_CONFIDENCE = env_float("ATTESTADO_OCR_LAYOUT_RETRY_CONFIDENCE", 0.2)
    OCR_LAYOUT_RETRY_MIN_WORDS = env_int("ATTESTADO_OCR_LAYOUT_RETRY_MIN_WORDS", 120)
    OCR_LAYOUT_RETRY_MIN_ITEMS = env_int("ATTESTADO_OCR_LAYOUT_RETRY_MIN_ITEMS", 5)
    OCR_LAYOUT_RETRY_MIN_QTY_RATIO = env_float("ATTESTADO_OCR_LAYOUT_RETRY_MIN_QTY_RATIO", 0.35)
    OCR_LAYOUT_PAGE_MIN_ITEMS = env_int("ATTESTADO_OCR_LAYOUT_PAGE_MIN_ITEMS", 3)
    OCR_PAGE_MIN_DOMINANT_LEN = env_int("ATTESTADO_OCR_PAGE_MIN_DOMINANT_LEN", 2)
    OCR_PAGE_MIN_ITEM_RATIO = env_float("ATTESTADO_OCR_PAGE_MIN_ITEM_RATIO", 0.6)
    OCR_PAGE_MIN_UNIT_RATIO = env_float("ATTESTADO_OCR_PAGE_MIN_UNIT_RATIO", 0.2)
    OCR_PAGE_FALLBACK_UNIT_RATIO = env_float("ATTESTADO_OCR_PAGE_FALLBACK_UNIT_RATIO", 0.4)
    OCR_PAGE_FALLBACK_ITEM_RATIO = env_float("ATTESTADO_OCR_PAGE_FALLBACK_ITEM_RATIO", 0.8)
    OCR_PAGE_MIN_ITEMS = env_int("ATTESTADO_OCR_PAGE_MIN_ITEMS", 5)
    # Detecção de coluna de item
    ITEM_COL_MIN_SCORE = env_float("ATTESTADO_ITEM_COL_MIN_SCORE", 0.5)
    ITEM_COL_RATIO = env_float("ATTESTADO_ITEM_COL_RATIO", 0.35)
    ITEM_COL_MAX_X_RATIO = env_float("ATTESTADO_ITEM_COL_MAX_X_RATIO", 0.35)
    ITEM_COL_MAX_INDEX = env_int("ATTESTADO_ITEM_COL_MAX_INDEX", 2)
    ITEM_COL_MIN_COUNT = env_int("ATTESTADO_ITEM_COL_MIN_COUNT", 6)
    # Matching e Similaridade
    DESC_SIM_THRESHOLD = env_float("ATTESTADO_DESC_SIM_THRESHOLD", 0.7)
    CODE_MATCH_THRESHOLD = env_float("ATTESTADO_CODE_MATCH_THRESHOLD", 0.55)
    SCORE_MARGIN = env_float("ATTESTADO_SCORE_MARGIN", 0.1)
    # Tabelas
    TABLE_CONFIDENCE_THRESHOLD = env_float("ATTESTADO_TABLE_CONFIDENCE_THRESHOLD", 0.7)
    TABLE_MIN_ITEMS = env_int("ATTESTADO_TABLE_MIN_ITEMS", 10)
    # Document AI (Google Cloud)
    # IMPORTANTE: O tipo de processador é configurado no Google Cloud Console
    # Tipos disponíveis e custos (Jan/2025):
    #   - Form Parser: US$ 30/1000 páginas (US$ 0.03/pág) - detecta tabelas estruturadas
    #   - OCR Processor: US$ 1.50/1000 páginas (US$ 0.0015/pág) - apenas texto OCR
    # Recomendação: Usar Form Parser apenas se pdfplumber falhar frequentemente
    # Variáveis de ambiente:
    #   - DOCUMENT_AI_PROJECT_ID, DOCUMENT_AI_LOCATION, DOCUMENT_AI_PROCESSOR_ID
    DOCUMENT_AI_ENABLED = env_bool("DOCUMENT_AI_ENABLED", False)
    DOCUMENT_AI_FALLBACK_ONLY = env_bool("DOCUMENT_AI_FALLBACK_ONLY", True)
    DOCUMENT_AI_MIN_ITEMS = env_int("ATTESTADO_DOCUMENT_AI_MIN_ITEMS", 20)
    # Fluxo em Cascata - Thresholds de qty_ratio por etapa
    # Etapa 1 (pdfplumber): gratuito, exige alta qualidade
    STAGE1_QTY_THRESHOLD = env_float("ATTESTADO_STAGE1_QTY_THRESHOLD", 0.70)
    # Etapa 2 (Document AI): baixo custo, aceita qualidade moderada
    STAGE2_QTY_THRESHOLD = env_float("ATTESTADO_STAGE2_QTY_THRESHOLD", 0.60)
    # Etapa 3 (Vision AI): alto custo, aceita qualidade baixa
    STAGE3_QTY_THRESHOLD = env_float("ATTESTADO_STAGE3_QTY_THRESHOLD", 0.40)
    # Detecção de documento escaneado
    SCANNED_MIN_CHARS_PER_PAGE = env_int("ATTESTADO_SCANNED_MIN_CHARS", 200)
    SCANNED_IMAGE_PAGE_RATIO = env_float("ATTESTADO_SCANNED_IMG_RATIO", 0.5)
    # LLM e Vision
    LLM_FALLBACK_ONLY = env_bool("ATTESTADO_LLM_FALLBACK_ONLY", True)
    PAGEWISE_VISION_ENABLED = env_bool("ATTESTADO_PAGEWISE_VISION", True)
    VISION_QUALITY_THRESHOLD = env_float("ATTESTADO_VISION_QUALITY_THRESHOLD", 0.6)
    PAGEWISE_MIN_PAGES = env_int("ATTESTADO_PAGEWISE_MIN_PAGES", 3)
    PAGEWISE_MIN_ITEMS = env_int("ATTESTADO_PAGEWISE_MIN_ITEMS", 40)
    # Mínimo de itens para confiança
    MIN_ITEMS_FOR_CONFIDENCE = env_int("ATTESTADO_MIN_ITEMS_FOR_CONFIDENCE", 25)
    # Restart de numeracao (prefixo Sx-)
    RESTART_MIN_CODES = env_int("ATTESTADO_RESTART_MIN_CODES", 8)
    RESTART_MIN_OVERLAP = env_int("ATTESTADO_RESTART_MIN_OVERLAP", 3)
    RESTART_MIN_OVERLAP_RATIO = env_float("ATTESTADO_RESTART_MIN_OVERLAP_RATIO", 0.25)
    # Texto (fallback/descricoes)
    TEXT_SECTION_MAX_DESC_LEN = env_int("ATTESTADO_TEXT_SECTION_MAX_DESC_LEN", 240)
    TEXT_SECTION_TABLE_CONFIDENCE_MIN = env_float("ATTESTADO_TEXT_SECTION_TABLE_CONFIDENCE_MIN", 0.85)
    TEXT_SECTION_QTY_RATIO_MIN = env_float("ATTESTADO_TEXT_SECTION_QTY_RATIO_MIN", 0.8)
    TEXT_SECTION_DUP_RATIO_MAX = env_float("ATTESTADO_TEXT_SECTION_DUP_RATIO_MAX", 0.35)



# === Configurações de Detecção de Ruído OCR ===
class OCRNoiseConfig:
    """Configurações para detecção de ruído em extração OCR."""
    MIN_UNIT_RATIO = env_float("ATTESTADO_OCR_NOISE_MIN_UNIT_RATIO", 0.5)
    MIN_QTY_RATIO = env_float("ATTESTADO_OCR_NOISE_MIN_QTY_RATIO", 0.35)
    MIN_AVG_DESC_LEN = env_float("ATTESTADO_OCR_NOISE_MIN_AVG_DESC_LEN", 14.0)
    MAX_SHORT_DESC_RATIO = env_float("ATTESTADO_OCR_NOISE_MAX_SHORT_DESC_RATIO", 0.45)
    MIN_ALPHA_RATIO = env_float("ATTESTADO_OCR_NOISE_MIN_ALPHA_RATIO", 0.45)
    MIN_FAILURES = env_int("ATTESTADO_OCR_NOISE_MIN_FAILS", 2)
    SHORT_DESC_LEN = env_int("ATTESTADO_OCR_NOISE_SHORT_DESC_LEN", 12)


# === Configurações de Score de Qualidade ===
class QualityScoreConfig:
    """Configurações para cálculo de score de qualidade."""
    MIN_UNIT_RATIO = env_float("QUALITY_SCORE_MIN_UNIT_RATIO", 0.8)
    MIN_QTY_RATIO = env_float("QUALITY_SCORE_MIN_QTY_RATIO", 0.8)
    MIN_ITEM_RATIO = env_float("QUALITY_SCORE_MIN_ITEM_RATIO", 0.4)
    MAX_DUPLICATE_RATIO = env_float("QUALITY_SCORE_MAX_DUPLICATE_RATIO", 0.35)
    PENALTY_UNIT = env_float("QUALITY_SCORE_PENALTY_UNIT", 0.2)
    PENALTY_QTY = env_float("QUALITY_SCORE_PENALTY_QTY", 0.2)
    PENALTY_ITEM = env_float("QUALITY_SCORE_PENALTY_ITEM", 0.2)
    PENALTY_DUPLICATE = env_float("QUALITY_SCORE_PENALTY_DUPLICATE", 0.1)
    PENALTY_FEW_ITEMS = env_float("QUALITY_SCORE_PENALTY_FEW_ITEMS", 0.2)


# === API Versioning ===
API_VERSION = "v1"
API_PREFIX = f"/api/{API_VERSION}"


# === Função auxiliar para validar extensões ===
def is_allowed_extension(filename: str, allowed: Optional[List[str]] = None) -> bool:
    """Verifica se a extensão do arquivo é permitida."""
    if allowed is None:
        allowed = ALLOWED_DOCUMENT_EXTENSIONS
    ext = os.path.splitext(filename)[1].lower()
    return ext in allowed


def get_file_extension(filename: str) -> str:
    """Retorna a extensão do arquivo em minúsculas."""
    return os.path.splitext(filename)[1].lower()


def validate_upload_file(
    filename: Optional[str],
    allowed_extensions: Optional[List[str]] = None
) -> str:
    """
    Valida arquivo de upload e retorna a extensão.

    Args:
        filename: Nome do arquivo
        allowed_extensions: Lista de extensões permitidas (usa ALLOWED_DOCUMENT_EXTENSIONS se None)

    Returns:
        Extensão do arquivo em minúsculas

    Raises:
        ValueError: Se o arquivo for inválido
    """
    if not filename:
        raise ValueError(Messages.FILE_REQUIRED)

    if allowed_extensions is None:
        allowed_extensions = ALLOWED_DOCUMENT_EXTENSIONS

    ext = get_file_extension(filename)
    if ext not in allowed_extensions:
        raise ValueError(
            f"{Messages.INVALID_EXTENSION}. Use: {', '.join(allowed_extensions)}"
        )

    return ext
