import os
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from dotenv import load_dotenv
from sqlalchemy.exc import SQLAlchemyError, IntegrityError as SAIntegrityError, OperationalError

from database import engine, Base, get_db
from sqlalchemy.orm import Session
from sqlalchemy import text
from routers import auth, admin, atestados, analise, ai_status
from services.processing_queue import processing_queue
from middleware.rate_limit import RateLimitMiddleware
from middleware.security_headers import SecurityHeadersMiddleware
from starlette.middleware.gzip import GZipMiddleware
from config import CORS_ORIGINS, CORS_ALLOW_CREDENTIALS, UPLOAD_DIR, Messages, API_PREFIX, API_VERSION
from exceptions import (
    LicitaFacilError,
    DatabaseError,
    RecordNotFoundError,
    DuplicateRecordError,
    ValidationError,
    ProcessingError
)

from logging_config import get_logger, set_correlation_id, clear_correlation_id
logger = get_logger('main')

# Carregar variáveis de ambiente
load_dotenv()

# Criar tabelas no banco de dados
Base.metadata.create_all(bind=engine)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gerenciador de ciclo de vida da aplicação."""
    # Startup: validar configuracao
    from config.validators import validate_atestado_config, get_config_summary
    from config import ENVIRONMENT

    logger.info("Validando configuracao...")
    validation_result = validate_atestado_config()

    if not validation_result.is_valid:
        for error in validation_result.errors:
            logger.error(f"Erro de configuracao: {error.config_name}={error.value}: {error.message}")
        # Em producao, falhar se configuracao invalida
        if ENVIRONMENT == "production":
            raise RuntimeError("Configuracao invalida. Corrija os erros acima antes de iniciar.")
        logger.warning("Continuando com configuracao invalida (ambiente de desenvolvimento)")

    for warning in validation_result.warnings:
        logger.warning(f"Aviso de configuracao: {warning.config_name}={warning.value}: {warning.message}")

    logger.info(f"Configuracao validada: {get_config_summary()}")

    # Startup: iniciar fila de processamento
    await processing_queue.start()
    logger.info("Fila de processamento iniciada")
    logger.info("OCR será carregado sob demanda (lazy loading)")

    yield

    # Shutdown: parar fila de processamento
    await processing_queue.stop()
    logger.info("Fila de processamento parada")


# Criar aplicação FastAPI
app = FastAPI(
    title="LicitaFácil",
    description="Sistema de Análise de Capacidade Técnica para Licitações de Obras Públicas",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# Configurar middlewares na ordem correta
# 1. Rate Limiting (primeiro a executar, último a responder)
app.add_middleware(RateLimitMiddleware)

# 2. Security Headers (adiciona headers de seguranca a todas as respostas)
from config.security import SECURITY_HEADERS_ENABLED, HSTS_MAX_AGE, FRAME_OPTIONS, REFERRER_POLICY
if SECURITY_HEADERS_ENABLED:
    app.add_middleware(
        SecurityHeadersMiddleware,
        enable_hsts=True,
        hsts_max_age=HSTS_MAX_AGE,
        frame_options=FRAME_OPTIONS,
        referrer_policy=REFERRER_POLICY
    )
    logger.info("Security Headers middleware habilitado")

# 3. Compressao GZip (comprime respostas maiores que 1000 bytes)
app.add_middleware(GZipMiddleware, minimum_size=1000)


# Middleware para Correlation ID (request tracing)
@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next):
    """Adiciona correlation ID para rastreamento de requisições."""
    # Usar header X-Correlation-ID se fornecido, senão gerar novo
    correlation_id = request.headers.get("X-Correlation-ID")
    correlation_id = set_correlation_id(correlation_id)

    response = await call_next(request)

    # Incluir correlation ID na resposta
    response.headers["X-Correlation-ID"] = correlation_id
    clear_correlation_id()

    return response

# Configurar CORS com origens da configuração
# Em desenvolvimento: localhost. Em produção: definir CORS_ORIGINS no .env
from config import ENVIRONMENT

if not CORS_ORIGINS:
    if ENVIRONMENT == "production":
        logger.error("CORS_ORIGINS não definido em produção! Usando lista vazia.")
        cors_origins = []
    else:
        cors_origins = ["*"]
        logger.warning("CORS configurado para aceitar todas as origens (desenvolvimento)")
else:
    cors_origins = CORS_ORIGINS
    logger.info(f"CORS configurado para origens: {cors_origins}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=CORS_ALLOW_CREDENTIALS,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Criar diretório de uploads se não existir
os.makedirs(UPLOAD_DIR, exist_ok=True)


# === Exception Handlers ===

@app.exception_handler(RecordNotFoundError)
async def record_not_found_handler(request: Request, exc: RecordNotFoundError):
    """Handler para registros não encontrados."""
    return JSONResponse(
        status_code=404,
        content={"detail": exc.message}
    )


@app.exception_handler(DuplicateRecordError)
async def duplicate_record_handler(request: Request, exc: DuplicateRecordError):
    """Handler para registros duplicados."""
    return JSONResponse(
        status_code=409,
        content={"detail": exc.message}
    )


@app.exception_handler(ValidationError)
async def validation_error_handler(request: Request, exc: ValidationError):
    """Handler para erros de validação."""
    return JSONResponse(
        status_code=422,
        content={"detail": exc.message}
    )


@app.exception_handler(ProcessingError)
async def processing_error_handler(request: Request, exc: ProcessingError):
    """Handler para erros de processamento."""
    logger.error(f"Erro de processamento: {exc.message}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": exc.message}
    )


@app.exception_handler(DatabaseError)
async def database_error_handler(request: Request, exc: DatabaseError):
    """Handler para erros de banco de dados customizados."""
    logger.error(f"Erro de banco de dados: {exc.message}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": Messages.DB_ERROR}
    )


@app.exception_handler(SAIntegrityError)
async def sqlalchemy_integrity_handler(request: Request, exc: SAIntegrityError):
    """Handler para violações de integridade do SQLAlchemy."""
    logger.error(f"Violação de integridade: {exc}", exc_info=True)
    return JSONResponse(
        status_code=409,
        content={"detail": Messages.DUPLICATE_ENTRY}
    )


@app.exception_handler(OperationalError)
async def sqlalchemy_operational_handler(request: Request, exc: OperationalError):
    """Handler para erros operacionais do SQLAlchemy (conexão, etc)."""
    logger.error(f"Erro operacional do banco: {exc}", exc_info=True)
    return JSONResponse(
        status_code=503,
        content={"detail": "Serviço de banco de dados temporariamente indisponível"}
    )


@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_generic_handler(request: Request, exc: SQLAlchemyError):
    """Handler genérico para erros do SQLAlchemy."""
    logger.error(f"Erro SQLAlchemy: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": Messages.DB_ERROR}
    )


@app.exception_handler(LicitaFacilError)
async def licitafacil_error_handler(request: Request, exc: LicitaFacilError):
    """Handler genérico para exceções do LicitaFacil."""
    logger.error(f"Erro da aplicação: {exc.message}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": exc.message}
    )


# Caminho do frontend
frontend_path = os.path.join(os.path.dirname(__file__), "..", "frontend")

# Registrar routers com prefixo de versão da API
app.include_router(auth.router, prefix=API_PREFIX)
app.include_router(admin.router, prefix=API_PREFIX)
app.include_router(atestados.router, prefix=API_PREFIX)
app.include_router(analise.router, prefix=API_PREFIX)
app.include_router(ai_status.router, prefix=API_PREFIX)


# Servir arquivos estáticos do frontend (CSS, JS)
if os.path.exists(frontend_path):
    app.mount("/css", StaticFiles(directory=os.path.join(frontend_path, "css")), name="css")
    app.mount("/js", StaticFiles(directory=os.path.join(frontend_path, "js")), name="js")


# Rotas para servir páginas HTML do frontend
@app.get("/")
def serve_index():
    """Página de login."""
    return FileResponse(os.path.join(frontend_path, "index.html"))


@app.get("/dashboard.html")
def serve_dashboard():
    """Dashboard do usuário."""
    return FileResponse(os.path.join(frontend_path, "dashboard.html"))


@app.get("/atestados.html")
def serve_atestados():
    """Gestão de atestados."""
    return FileResponse(os.path.join(frontend_path, "atestados.html"))


@app.get("/analises.html")
def serve_analises():
    """Análise de licitações."""
    return FileResponse(os.path.join(frontend_path, "analises.html"))


@app.get("/admin.html")
def serve_admin():
    """Painel administrativo."""
    return FileResponse(os.path.join(frontend_path, "admin.html"))


@app.get("/perfil.html")
def serve_perfil():
    """Página de perfil do usuário."""
    return FileResponse(os.path.join(frontend_path, "perfil.html"))


@app.get("/admin")
def serve_admin_alias():
    """Painel administrativo (alias sem .html)."""
    return FileResponse(os.path.join(frontend_path, "admin.html"))


@app.get("/index.html")
def serve_index_alias():
    """Página de login (alias)."""
    return FileResponse(os.path.join(frontend_path, "index.html"))


@app.get("/favicon.ico")
def serve_favicon():
    """Favicon do site."""
    return FileResponse(os.path.join(frontend_path, "favicon.ico"))


@app.get("/health")
def health_check(db: Session = Depends(get_db)):
    """Endpoint de verificação de saúde da API com checks de dependências."""
    checks = {
        "database": "unknown",
        "supabase": "disabled"
    }

    # Verificar banco de dados
    try:
        db.execute(text("SELECT 1"))
        checks["database"] = "healthy"
    except Exception:
        checks["database"] = "unhealthy"

    # Verificar Supabase se habilitado
    try:
        from config import SUPABASE_AUTH_ENABLED
        if SUPABASE_AUTH_ENABLED:
            from services.supabase_auth import _get_supabase_client
            client = _get_supabase_client()
            checks["supabase"] = "healthy" if client else "unhealthy"
    except Exception:
        checks["supabase"] = "unhealthy"

    # Status geral
    all_healthy = all(v in ("healthy", "disabled") for v in checks.values())

    return {
        "status": "healthy" if all_healthy else "degraded",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": API_VERSION,
        "checks": checks
    }


@app.get("/api/version")
def api_version():
    """Retorna informações sobre a versão da API."""
    return {
        "version": API_VERSION,
        "prefix": API_PREFIX,
        "status": "stable"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True  # Apenas para desenvolvimento
    )
