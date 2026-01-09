"""
Configurações centralizadas do LicitaFacil.

Todas as constantes e configurações devem ser definidas aqui.
"""
import os
from typing import List, Optional
from dotenv import load_dotenv

load_dotenv()


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
RATE_LIMIT_ENABLED = os.getenv("RATE_LIMIT_ENABLED", "true").lower() == "true"
RATE_LIMIT_REQUESTS = int(os.getenv("RATE_LIMIT_REQUESTS", "300"))  # requests per window
RATE_LIMIT_WINDOW = int(os.getenv("RATE_LIMIT_WINDOW", "60"))  # window in seconds


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
OCR_PARALLEL_ENABLED = os.getenv("OCR_PARALLEL_ENABLED", "1").lower() in ("1", "true", "yes")
OCR_MAX_WORKERS = int(os.getenv("OCR_MAX_WORKERS", "4"))


# === Paginação ===
DEFAULT_PAGE_SIZE = int(os.getenv("DEFAULT_PAGE_SIZE", "20"))
MAX_PAGE_SIZE = int(os.getenv("MAX_PAGE_SIZE", "100"))


# === Configurações de OCR ===
class OCRConfig:
    """Configurações para processamento OCR."""
    DPI = int(os.getenv("OCR_DPI", "300"))
    MIN_TEXT_PER_PAGE = int(os.getenv("OCR_MIN_TEXT_PER_PAGE", "200"))
    MIN_TEXT_LENGTH = int(os.getenv("OCR_MIN_TEXT_LENGTH", "100"))
    MIN_CONFIDENT_CHARS = int(os.getenv("OCR_MIN_CONFIDENT_CHARS", "20"))


# === Configurações do Pipeline ===
class PipelineConfig:
    """Configurações de confiança do pipeline de extração."""
    MIN_CONFIDENCE_LOCAL_OCR = float(os.getenv("MIN_CONFIDENCE_LOCAL_OCR", "0.70"))
    MIN_CONFIDENCE_CLOUD_OCR = float(os.getenv("MIN_CONFIDENCE_CLOUD_OCR", "0.85"))


# === Configurações de Modelos de IA ===
class AIModelConfig:
    """Configurações dos modelos de IA."""
    # OpenAI
    OPENAI_TEXT_MODEL = os.getenv("OPENAI_TEXT_MODEL", "gpt-4o-mini")
    OPENAI_VISION_MODEL = os.getenv("OPENAI_VISION_MODEL", "gpt-4o")
    OPENAI_MAX_TOKENS = int(os.getenv("OPENAI_MAX_TOKENS", "16000"))
    OPENAI_TEMPERATURE = float(os.getenv("OPENAI_TEMPERATURE", "0"))
    # Gemini
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
    GEMINI_PRO_MODEL = os.getenv("GEMINI_PRO_MODEL", "gemini-2.0-flash")
    GEMINI_MAX_TOKENS = int(os.getenv("GEMINI_MAX_TOKENS", "16000"))
    GEMINI_TEMPERATURE = float(os.getenv("GEMINI_TEMPERATURE", "0"))


# === Configurações de Extração de Tabelas ===
class TableExtractionConfig:
    """Configurações para extração e parsing de tabelas."""
    HEADER_ROWS_LIMIT = int(os.getenv("TABLE_HEADER_ROWS_LIMIT", "5"))
    HEADER_MIN_KEYWORD_MATCHES = int(os.getenv("TABLE_HEADER_MIN_KEYWORDS", "2"))
    MIN_DESCRIPTION_LENGTH = int(os.getenv("TABLE_MIN_DESC_LENGTH", "5"))
    # Validação de colunas
    MIN_UNIT_RATIO = float(os.getenv("TABLE_MIN_UNIT_RATIO", "0.2"))
    MIN_QTY_RATIO = float(os.getenv("TABLE_MIN_QTY_RATIO", "0.35"))
    MIN_DESC_LEN = float(os.getenv("TABLE_MIN_DESC_LEN", "10.0"))
    MAX_DESC_NUMERIC = float(os.getenv("TABLE_MAX_DESC_NUMERIC", "0.6"))
    # Pesos de scoring para detecção de coluna de item
    ITEM_SCORE_PATTERN_WEIGHT = float(os.getenv("ITEM_SCORE_PATTERN_WEIGHT", "0.45"))
    ITEM_SCORE_SEQ_WEIGHT = float(os.getenv("ITEM_SCORE_SEQ_WEIGHT", "0.2"))
    ITEM_SCORE_UNIQUE_WEIGHT = float(os.getenv("ITEM_SCORE_UNIQUE_WEIGHT", "0.2"))
    ITEM_SCORE_LEFT_BIAS_WEIGHT = float(os.getenv("ITEM_SCORE_LEFT_BIAS_WEIGHT", "0.1"))
    ITEM_SCORE_LENGTH_BONUS_WEIGHT = float(os.getenv("ITEM_SCORE_LENGTH_BONUS_WEIGHT", "0.05"))


# === Configurações de Deduplicação ===
class DeduplicationConfig:
    """Configurações para detecção de duplicatas."""
    SIMILARITY_THRESHOLD = float(os.getenv("DEDUP_SIMILARITY_THRESHOLD", "0.5"))
    MAX_DESC_CHARS = int(os.getenv("DEDUP_MAX_DESC_CHARS", "50"))
    ITEM_LENGTH_RATIO = float(os.getenv("ATTESTADO_ITEM_LEN_RATIO", "0.6"))
    ITEM_LENGTH_KEEP_MIN_DESC = int(os.getenv("ATTESTADO_ITEM_LEN_KEEP_MIN_DESC", "20"))
    ITEM_PREFIX_RATIO = float(os.getenv("ATTESTADO_ITEM_PREFIX_RATIO", "0.7"))
    ITEM_PREFIX_KEEP_MIN_DESC = int(os.getenv("ATTESTADO_ITEM_PREFIX_KEEP_MIN_DESC", "15"))
    ITEM_COL_MIN_SCORE = float(os.getenv("ATTESTADO_ITEM_COL_MIN_SCORE", "0.5"))


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
