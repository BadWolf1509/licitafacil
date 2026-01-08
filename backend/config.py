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
UPLOAD_DIR_EDITAIS = os.path.join(UPLOAD_DIR, "editais")
UPLOAD_DIR_ATESTADOS = os.path.join(UPLOAD_DIR, "atestados")


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
RATE_LIMIT_REQUESTS = int(os.getenv("RATE_LIMIT_REQUESTS", "100"))  # requests per window
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
    NOT_FOUND = "Recurso não encontrado"
    ATESTADO_NOT_FOUND = "Atestado não encontrado"
    ANALISE_NOT_FOUND = "Análise não encontrada"
    USER_NOT_FOUND = "Usuário não encontrado"
    JOB_NOT_FOUND = "Job não encontrado"
    FILE_NOT_FOUND = "Arquivo não encontrado"
    ACCESS_DENIED = "Acesso negado"
    UNAUTHORIZED = "Acesso não autorizado"
    FORBIDDEN = "Acesso proibido"
    INVALID_FILE = "Arquivo inválido"
    INVALID_EXTENSION = "Extensão de arquivo não permitida"
    FILE_REQUIRED = "Arquivo é obrigatório"
    RATE_LIMIT_EXCEEDED = "Muitas requisições. Tente novamente em alguns minutos."
    INTERNAL_ERROR = "Erro interno do servidor"
    DB_ERROR = "Erro ao acessar o banco de dados"
    DUPLICATE_ENTRY = "Registro já existe"
    PROCESSING_ERROR = "Erro ao processar documento. Tente novamente."
    QUEUE_ERROR = "Erro ao enfileirar processamento. Tente novamente."


# === Processamento ===
OCR_PARALLEL_ENABLED = os.getenv("OCR_PARALLEL_ENABLED", "1").lower() in ("1", "true", "yes")
OCR_MAX_WORKERS = int(os.getenv("OCR_MAX_WORKERS", "4"))


# === Paginação ===
DEFAULT_PAGE_SIZE = int(os.getenv("DEFAULT_PAGE_SIZE", "20"))
MAX_PAGE_SIZE = int(os.getenv("MAX_PAGE_SIZE", "100"))


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
