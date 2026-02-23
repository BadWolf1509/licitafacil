"""
Configurações de segurança do LicitaFácil.
SECRET_KEY, JWT e validações de segurança.
"""
import os
import secrets

from .base import ENVIRONMENT

# === Segurança ===
SECRET_KEY = os.getenv("SECRET_KEY")

if ENVIRONMENT == "production":
    # Produção: SECRET_KEY obrigatória e segura
    if not SECRET_KEY:
        raise ValueError(
            "CRÍTICO: SECRET_KEY não definida em produção! "
            "Defina a variável de ambiente SECRET_KEY com uma chave segura de pelo menos 32 caracteres."
        )
    if SECRET_KEY.startswith("dev-"):
        raise ValueError(
            "CRÍTICO: SECRET_KEY de desenvolvimento detectada em produção! "
            "Gere uma nova chave com: python -c \"import secrets; print(secrets.token_urlsafe(32))\""
        )
    if len(SECRET_KEY) < 32:
        raise ValueError(
            f"SECRET_KEY muito curta ({len(SECRET_KEY)} chars). "
            "Use pelo menos 32 caracteres em produção."
        )
else:
    # Desenvolvimento: gerar chave dinâmica se não definida
    if not SECRET_KEY:
        import warnings
        SECRET_KEY = secrets.token_urlsafe(32)
        warnings.warn(
            "SECRET_KEY não definida! Gerada dinamicamente para esta sessão. "
            "Defina SECRET_KEY em produção.",
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
