"""
Configuracoes de seguranca do LicitaFacil.
SECRET_KEY, JWT e validacoes de seguranca.
"""
import os
import secrets

from .base import ENVIRONMENT

# === Seguranca ===
SECRET_KEY = os.getenv("SECRET_KEY")

if ENVIRONMENT == "production":
    # Producao: SECRET_KEY obrigatoria e segura
    if not SECRET_KEY:
        raise ValueError(
            "CRITICO: SECRET_KEY nao definida em producao! "
            "Defina a variavel de ambiente SECRET_KEY com uma chave segura de pelo menos 32 caracteres."
        )
    if SECRET_KEY.startswith("dev-"):
        raise ValueError(
            "CRITICO: SECRET_KEY de desenvolvimento detectada em producao! "
            "Gere uma nova chave com: python -c \"import secrets; print(secrets.token_urlsafe(32))\""
        )
    if len(SECRET_KEY) < 32:
        raise ValueError(
            f"SECRET_KEY muito curta ({len(SECRET_KEY)} chars). "
            "Use pelo menos 32 caracteres em producao."
        )
else:
    # Desenvolvimento: gerar chave dinamica se nao definida
    if not SECRET_KEY:
        import warnings
        SECRET_KEY = secrets.token_urlsafe(32)
        warnings.warn(
            "SECRET_KEY nao definida! Gerada dinamicamente para esta sessao. "
            "Defina SECRET_KEY em producao.",
            RuntimeWarning
        )

JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_EXPIRATION_HOURS = int(os.getenv("JWT_EXPIRATION_HOURS", "24"))

# === Security Headers ===
SECURITY_HEADERS_ENABLED = os.getenv("SECURITY_HEADERS_ENABLED", "true").lower() == "true"
HSTS_MAX_AGE = int(os.getenv("HSTS_MAX_AGE", "31536000"))  # 1 ano
FRAME_OPTIONS = os.getenv("FRAME_OPTIONS", "DENY")  # DENY ou SAMEORIGIN
REFERRER_POLICY = os.getenv("REFERRER_POLICY", "strict-origin-when-cross-origin")

# === Password Policy ===
# Used for password validation during registration (Supabase Auth)
PASSWORD_MIN_LENGTH = int(os.getenv("PASSWORD_MIN_LENGTH", "8"))
PASSWORD_REQUIRE_UPPERCASE = os.getenv("PASSWORD_REQUIRE_UPPERCASE", "true").lower() == "true"
PASSWORD_REQUIRE_LOWERCASE = os.getenv("PASSWORD_REQUIRE_LOWERCASE", "true").lower() == "true"
PASSWORD_REQUIRE_DIGIT = os.getenv("PASSWORD_REQUIRE_DIGIT", "true").lower() == "true"
PASSWORD_REQUIRE_SPECIAL = os.getenv("PASSWORD_REQUIRE_SPECIAL", "true").lower() == "true"
