# LicitaFacil

Sistema para extracao de dados de atestados de capacidade tecnica e analise de exigencias de editais, com fila de processamento e pipeline orientado a custo.

## Escopo atual

- Upload e processamento de atestados (PDF e imagem) com extracao de servicos e metadados
- Analise de editais e matching com atestados
- Frontend estatico (HTML/CSS/JS) servido pelo FastAPI
- Fila de processamento com cancelamento e reprocessamento

## Pipeline de atestados (fluxo real)

1. Extracao de texto: pdfplumber + OCR local (EasyOCR, com fallback Tesseract)
2. Extracao de tabelas em cascata: pdfplumber -> Document AI (opcional)
3. IA:
   - Metadados sempre que houver provedor configurado
   - Servicos apenas quando a tabela for insuficiente ou quando ATTESTADO_LLM_FALLBACK_ONLY=0
   - Provedor selecionado automaticamente entre Gemini e OpenAI
4. Pos-processamento: normalizacao, deduplicacao, filtros e backfill de quantidades via texto

## Pipeline de qualidade/custo (/api/v1/pipeline)

Fluxo alternativo para analise de qualidade e processamento fora da fila:
- native_text: pdfplumber
- local_ocr: EasyOCR
- cloud_ocr: Azure Document Intelligence (opcional)
- vision_ai: OpenAI Vision (quando necessario)

## Matching deterministico (analises)

- Opera por item de servico (servicos_json) com unidade normalizada
- Similaridade por cobertura do requisito (keywords) com limiar configuravel
- Gate por atividade e termos obrigatorios (ex: laminad, porcelanat, canaleta, cobre)
- Seleciona atestados recomendados por soma greedy ate atingir a exigencia

Limites conhecidos:
- OCR/descricao incompleta pode gerar falso negativo nos termos obrigatorios
- Editais sem regra explicita de soma usam soma como padrao

## Tecnologias

Backend:
- FastAPI, SQLAlchemy, SQLite (WAL)
- pdfplumber e PyMuPDF
- EasyOCR + Tesseract fallback
- OpenAI (gpt-4o / gpt-4o-mini)
- Google Gemini (google-genai)
- Google Document AI (tabelas, opcional)
- Azure Document Intelligence (OCR cloud, opcional)

Frontend:
- HTML, CSS, JavaScript (arquivos estaticos em /frontend)

## Execucao local

Pre-requisitos:
- Python 3.10+
- pip

Passos:
1. Criar ambiente virtual:
   `python -m venv venv`
2. Ativar ambiente virtual:
   - Windows: `venv\Scripts\activate`
   - Linux/Mac: `source venv/bin/activate`
3. Instalar dependencias:
   `pip install -r requirements.txt`
4. Configurar variaveis:
   - Windows: `copy .env.example .env`
   - Linux/Mac: `cp .env.example .env`
5. Criar admin inicial:
   - `cd backend`
   - `python seed.py`
6. Iniciar API:
   - `cd backend`
   - `uvicorn main:app --reload --host 0.0.0.0 --port 8000`

Acesso:
- UI: http://localhost:8000/
- Docs: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Variaveis de ambiente (principais)

Obrigatorias em producao:
- SECRET_KEY
- OPENAI_API_KEY ou GOOGLE_API_KEY

Core:
- DATABASE_URL (default sqlite:///./licitafacil.db)
- UPLOAD_DIR
- AI_PROVIDER (auto, openai, gemini)
- JWT_ALGORITHM (default HS256)
- ACCESS_TOKEN_EXPIRE_MINUTES

Document AI (opcional):
- DOCUMENT_AI_ENABLED
- DOCUMENT_AI_FALLBACK_ONLY
- DOCUMENT_AI_PROJECT_ID
- DOCUMENT_AI_LOCATION
- DOCUMENT_AI_PROCESSOR_ID
- DOCUMENT_AI_PROCESSOR_VERSION
- GOOGLE_APPLICATION_CREDENTIALS

Azure OCR (opcional):
- AZURE_DOCUMENT_ENDPOINT
- AZURE_DOCUMENT_KEY

OCR e fila:
- OCR_PARALLEL_ENABLED
- OCR_TESSERACT_FALLBACK
- QUEUE_MAX_CONCURRENT
- QUEUE_POLL_INTERVAL

Admin seed:
- ADMIN_EMAIL
- ADMIN_PASSWORD
- ADMIN_NAME

Ajuste fino:
- Variaveis ATTESTADO_* em .env.example
- Matching:
  - MATCH_SIMILARITY_THRESHOLD (default 0.35)
  - MATCH_MIN_COMMON_WORDS (default 2)
  - MATCH_MIN_COMMON_WORDS_SHORT (default 1)

## Endpoints principais (prefixo /api/v1)

Auth:
- POST /auth/login
- POST /auth/login-json
- POST /auth/registrar
- GET /auth/me

Atestados:
- GET /atestados
- POST /atestados
- POST /atestados/upload
- POST /atestados/{id}/reprocess
- PATCH /atestados/{id}/servicos
- DELETE /atestados/{id}

Analises:
- GET /analises
- POST /analises
- POST /analises/{id}/processar
- GET /analises/status/servicos

Fila e IA:
- GET /ai/status
- GET /ai/queue/status
- GET /ai/queue/jobs
- GET /ai/queue/jobs/{id}
- POST /ai/queue/jobs/{id}/cancel
- POST /ai/queue/jobs/{id}/retry
- DELETE /ai/queue/jobs/{id}

Pipeline:
- GET /pipeline/status
- POST /pipeline/analyze-quality
- POST /pipeline/process
- GET /pipeline/cost-estimate

## Estrutura

- backend/ (API e processamento)
- frontend/ (UI estatica)
- uploads/ (arquivos do usuario)
- requirements.txt
- .env.example
- INICIAR.md
- PIPELINE_SETUP.md

## Licenca

Proprietario. Todos os direitos reservados.
