# =============================================================================
# Dockerfile para LicitaFácil Backend
# =============================================================================
# Multi-stage build para imagem otimizada
# Uso: docker build -t licitafacil-backend .
# =============================================================================

# -----------------------------------------------------------------------------
# Stage 1: Builder - instala dependências
# -----------------------------------------------------------------------------
FROM python:3.11-slim as builder

WORKDIR /app

# Instalar dependências de sistema para compilação
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copiar requirements e instalar dependências Python
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# -----------------------------------------------------------------------------
# Stage 2: Runtime - imagem final otimizada
# -----------------------------------------------------------------------------
FROM python:3.11-slim as runtime

WORKDIR /app

# Instalar dependências de runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgl1-mesa-glx \
    poppler-utils \
    tesseract-ocr \
    tesseract-ocr-por \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copiar dependências Python do builder
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

# Copiar código da aplicação
COPY backend/ ./backend/
COPY requirements.txt .

# Criar diretório de uploads
RUN mkdir -p /app/uploads && chmod 755 /app/uploads

# Variáveis de ambiente padrão
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UPLOAD_DIR=/app/uploads \
    PORT=8000

# Expor porta
EXPOSE 8000

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Comando de inicialização
WORKDIR /app/backend
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
