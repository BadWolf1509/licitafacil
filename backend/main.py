import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from dotenv import load_dotenv
from sqlalchemy.exc import SQLAlchemyError, IntegrityError as SAIntegrityError, OperationalError

from database import engine, Base
from routers import auth, admin, atestados, analise, ai_status
from services.processing_queue import processing_queue
from middleware.rate_limit import RateLimitMiddleware
from config import CORS_ORIGINS, CORS_ALLOW_CREDENTIALS, UPLOAD_DIR, Messages, API_PREFIX, API_VERSION
from exceptions import (
    LicitaFacilError,
    DatabaseError,
    RecordNotFoundError,
    DuplicateRecordError,
    ValidationError,
    ProcessingError
)

from logging_config import get_logger
logger = get_logger('main')

# Carregar variáveis de ambiente
load_dotenv()

# Criar tabelas no banco de dados
Base.metadata.create_all(bind=engine)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gerenciador de ciclo de vida da aplicação."""
    import asyncio
    from services.ocr_service import ocr_service

    # Pré-inicializar OCR em thread separada (não bloqueia o startup)
    async def init_ocr_background():
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, ocr_service.initialize)

    # Agendar inicialização do OCR em background
    ocr_task = asyncio.create_task(init_ocr_background())
    logger.info("Inicializacao do OCR agendada em background")

    # Startup: iniciar fila de processamento
    await processing_queue.start()
    logger.info("Fila de processamento iniciada")

    yield

    # Shutdown: parar fila de processamento
    await processing_queue.stop()
    logger.info("Fila de processamento parada")

    # Cancelar task do OCR se ainda estiver rodando
    if not ocr_task.done():
        ocr_task.cancel()
        try:
            await ocr_task
        except asyncio.CancelledError:
            pass


# Criar aplicação FastAPI
app = FastAPI(
    title="LicitaFácil",
    description="Sistema de Análise de Capacidade Técnica para Licitações de Obras Públicas",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# Configurar Rate Limiting (deve vir antes do CORS)
app.add_middleware(RateLimitMiddleware)

# Configurar CORS com origens da configuração
# Em desenvolvimento: localhost. Em produção: definir CORS_ORIGINS no .env
cors_origins = CORS_ORIGINS if CORS_ORIGINS else ["*"]
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
def health_check():
    """Endpoint de verificação de saúde da API."""
    return {"status": "healthy"}


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
