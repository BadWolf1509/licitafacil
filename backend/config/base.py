"""
Configuracoes base do LicitaFacil.
Helpers de ambiente, diretorios e extensoes de arquivo.
"""
import os
from typing import List, Optional
from dotenv import load_dotenv

load_dotenv()


# === Helpers para leitura de variaveis de ambiente ===
def env_bool(key: str, default: bool = False) -> bool:
    """Le variavel de ambiente como booleano."""
    val = os.getenv(key, "").lower()
    if val in ("1", "true", "yes", "on"):
        return True
    if val in ("0", "false", "no", "off"):
        return False
    return default


def env_int(key: str, default: int = 0) -> int:
    """Le variavel de ambiente como inteiro."""
    val = os.getenv(key)
    if val is None:
        return default
    try:
        return int(val)
    except ValueError:
        return default


def env_float(key: str, default: float = 0.0) -> float:
    """Le variavel de ambiente como float."""
    val = os.getenv(key)
    if val is None:
        return default
    try:
        return float(val)
    except ValueError:
        return default


# === Diretorios ===
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Detectar ambiente serverless (Vercel, AWS Lambda)
IS_SERVERLESS = os.getenv("VERCEL") or os.getenv("AWS_LAMBDA_FUNCTION_NAME")

# Em serverless, usar /tmp (único diretório gravável)
if IS_SERVERLESS:
    UPLOAD_DIR = "/tmp/uploads"
else:
    UPLOAD_DIR = os.getenv("UPLOAD_DIR", "uploads")


# === Extensoes de Arquivo Permitidas ===
ALLOWED_PDF_EXTENSIONS = [".pdf"]
ALLOWED_IMAGE_EXTENSIONS = [".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp"]
ALLOWED_DOCUMENT_EXTENSIONS = ALLOWED_PDF_EXTENSIONS + ALLOWED_IMAGE_EXTENSIONS

# === Limite de Upload ===
MAX_UPLOAD_SIZE_MB = env_int("MAX_UPLOAD_SIZE_MB", 50)
MAX_UPLOAD_SIZE_BYTES = MAX_UPLOAD_SIZE_MB * 1024 * 1024

# === MIME Types Permitidos ===
ALLOWED_MIME_TYPES = {
    'application/pdf': ['.pdf'],
    'image/png': ['.png'],
    'image/jpeg': ['.jpg', '.jpeg'],
    'image/tiff': ['.tiff', '.tif'],
    'image/bmp': ['.bmp'],
}


# === CORS ===
def get_cors_origins() -> List[str]:
    """
    Retorna lista de origens permitidas para CORS.

    Em producao, defina CORS_ORIGINS como lista separada por virgula:
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

    # Em producao sem CORS_ORIGINS definido, nao permitir nada
    return []


CORS_ORIGINS = get_cors_origins()
CORS_ALLOW_CREDENTIALS = os.getenv("CORS_ALLOW_CREDENTIALS", "true").lower() == "true"


# === Rate Limiting ===
RATE_LIMIT_ENABLED = env_bool("RATE_LIMIT_ENABLED", True)
RATE_LIMIT_REQUESTS = env_int("RATE_LIMIT_REQUESTS", 300)
RATE_LIMIT_WINDOW = env_int("RATE_LIMIT_WINDOW", 60)

# Rate Limiting especifico para autenticacao (mais restritivo)
# Formato: {path_prefix: (requests, window_seconds)}
RATE_LIMIT_AUTH_LOGIN = env_int("RATE_LIMIT_AUTH_LOGIN", 5)  # 5 tentativas
RATE_LIMIT_AUTH_REGISTER = env_int("RATE_LIMIT_AUTH_REGISTER", 3)  # 3 registros
RATE_LIMIT_AUTH_WINDOW = env_int("RATE_LIMIT_AUTH_WINDOW", 60)  # por minuto


# === Ambiente ===
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")


# === Processamento ===
OCR_PARALLEL_ENABLED = env_bool("OCR_PARALLEL_ENABLED", True)
OCR_MAX_WORKERS = env_int("OCR_MAX_WORKERS", 4)
OCR_PREPROCESS_ENABLED = env_bool("OCR_PREPROCESS", True)
OCR_TESSERACT_FALLBACK = env_bool("OCR_TESSERACT_FALLBACK", True)
# Preferir Tesseract (leve ~50MB) sobre EasyOCR (pesado ~1GB)
OCR_PREFER_TESSERACT = env_bool("OCR_PREFER_TESSERACT", True)

# === Serviços externos pagos ===
# APIs PAGAS PERMANENTEMENTE DESABILITADAS
# OpenAI, Gemini e Document AI não são mais usados
PAID_SERVICES_ENABLED = False  # Sempre False - não lê do .env


# === Fila de Processamento ===
QUEUE_MAX_CONCURRENT = env_int("QUEUE_MAX_CONCURRENT", 3)
QUEUE_POLL_INTERVAL = env_float("QUEUE_POLL_INTERVAL", 1.0)


# === Autenticacao ===
ACCESS_TOKEN_EXPIRE_MINUTES = env_int("ACCESS_TOKEN_EXPIRE_MINUTES", 30)


# === Supabase ===
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")


# === Paginacao ===
DEFAULT_PAGE_SIZE = env_int("DEFAULT_PAGE_SIZE", 20)
MAX_PAGE_SIZE = env_int("MAX_PAGE_SIZE", 500)


# === Funcoes auxiliares para validar extensoes ===
def is_allowed_extension(filename: str, allowed: Optional[List[str]] = None) -> bool:
    """Verifica se a extensao do arquivo e permitida."""
    if allowed is None:
        allowed = ALLOWED_DOCUMENT_EXTENSIONS
    ext = os.path.splitext(filename)[1].lower()
    return ext in allowed


def get_file_extension(filename: str) -> str:
    """Retorna a extensao do arquivo em minusculas."""
    return os.path.splitext(filename)[1].lower()
