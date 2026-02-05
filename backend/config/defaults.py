"""
Valores padrao do sistema LicitaFacil.

Centraliza constantes de configuracao padrao para evitar
hardcoding em multiplos lugares do codigo.
"""

# === Admin Defaults ===
# Usados no seed.py quando variaveis de ambiente nao estao definidas
DEFAULT_ADMIN_EMAIL = "admin@licitafacil.com.br"
DEFAULT_ADMIN_NAME = "Administrador"
# NOTA: Nao ha DEFAULT_ADMIN_PASSWORD - senha DEVE ser definida via .env

# === Validacao de Senha ===
MIN_PASSWORD_LENGTH = 8

# === Paginacao ===
DEFAULT_PAGE = 1
DEFAULT_PAGE_SIZE = 10
MAX_PAGE_SIZE = 100

# === Timeout ===
DEFAULT_PROCESSING_TIMEOUT_SECONDS = 300  # 5 minutos
DEFAULT_OCR_TIMEOUT_SECONDS = 60

# === Storage ===
MAX_TEMP_FILE_AGE_HOURS = 24
TEMP_CLEANUP_INTERVAL_HOURS = 6
