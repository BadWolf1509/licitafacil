import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from dotenv import load_dotenv

from database import engine, Base
from routers import auth, admin, atestados, analise, ai_status
from services.processing_queue import processing_queue

# Carregar variáveis de ambiente
load_dotenv()

# Criar tabelas no banco de dados
Base.metadata.create_all(bind=engine)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gerenciador de ciclo de vida da aplicação."""
    # Startup: iniciar fila de processamento
    await processing_queue.start()
    print("Fila de processamento iniciada")

    yield

    # Shutdown: parar fila de processamento
    await processing_queue.stop()
    print("Fila de processamento parada")


# Criar aplicação FastAPI
app = FastAPI(
    title="LicitaFácil",
    description="Sistema de Análise de Capacidade Técnica para Licitações de Obras Públicas",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Em produção, especificar domínios permitidos
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Criar diretório de uploads se não existir
os.makedirs("uploads", exist_ok=True)

# Caminho do frontend
frontend_path = os.path.join(os.path.dirname(__file__), "..", "frontend")

# Registrar routers (ANTES de montar arquivos estáticos)
app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(atestados.router)
app.include_router(analise.router)
app.include_router(ai_status.router)


# Servir arquivos estáticos do frontend (CSS, JS)
if os.path.exists(frontend_path):
    app.mount("/css", StaticFiles(directory=os.path.join(frontend_path, "css")), name="css")
    app.mount("/js", StaticFiles(directory=os.path.join(frontend_path, "js")), name="js")


# Rotas para servir páginas HTML do frontend
@app.get("/")
def serve_index():
    """Página de login."""
    return FileResponse(os.path.join(frontend_path, "index.html"))


@app.get("/index.html")
def serve_index_html():
    """Página de login (alternativo)."""
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


@app.get("/health")
def health_check():
    """Endpoint de verificação de saúde da API."""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True  # Apenas para desenvolvimento
    )
