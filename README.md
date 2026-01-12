# LicitaFácil

Sistema inteligente para análise de atestados de capacidade técnica em licitações públicas brasileiras.

## Sobre o Projeto

O LicitaFácil automatiza a extração de dados de atestados de capacidade técnica (documentos PDF) e faz matching automático com exigências de editais de licitação. Utiliza um pipeline em cascata que otimiza custos, escolhendo automaticamente a ferramenta mais econômica que funcione para cada documento.

**Economia estimada:** ~91% comparado a usar GPT-4o Vision para todos os documentos.

## Funcionalidades

- **Extração Inteligente**: Processa PDFs usando múltiplos pipelines (texto nativo, OCR local, OCR cloud, Vision AI)
- **Pipeline em Cascata**: Seleciona automaticamente o método mais econômico por documento
- **Processamento Assíncrono**: Fila em background para processar múltiplos documentos simultaneamente
- **Matching com Editais**: Compara atestados extraídos com exigências técnicas de editais
- **Interface Web**: Frontend responsivo para upload, gerenciamento e visualização de resultados

## Pipeline de Processamento

```
Documento → Análise de Qualidade → Pipeline Apropriado → Resultado
                    ↓
    ┌───────────────┼───────────────┬───────────────┐
    ↓               ↓               ↓               ↓
NATIVE_TEXT    LOCAL_OCR      CLOUD_OCR      VISION_AI
(pdfplumber)   (EasyOCR)      (Azure)        (GPT-4o)
 ~R$ 0.002     ~R$ 0.002      ~R$ 0.011      ~R$ 0.10
```

| Pipeline | Quando é Usado | Custo/Página |
|----------|----------------|--------------|
| **Extração Nativa** | PDF com texto selecionável | ~R$ 0.002 |
| **OCR Local** | PDF escaneado com boa qualidade | ~R$ 0.002 |
| **OCR Cloud** | PDF escaneado com baixa qualidade | ~R$ 0.011 |
| **GPT-4o Vision** | Documentos muito degradados ou manuscritos | ~R$ 0.10 |

### Economia para 1000 Documentos (Mix Típico)

| Categoria | % | Pipeline | Custo |
|-----------|---|----------|-------|
| Fácil | 30% | pdfplumber | R$ 0.60 |
| Médio | 40% | EasyOCR | R$ 0.80 |
| Difícil | 25% | Azure | R$ 2.75 |
| Muito Difícil | 5% | GPT-4o Vision | R$ 5.00 |
| **Total** | 100% | | **R$ 9.15** |

**Economia: ~91%** vs usar GPT-4o Vision para tudo (R$ 100.00).

## Tecnologias

### Backend
- **FastAPI 0.109** - Framework web assíncrono
- **SQLAlchemy 2.0** - ORM para banco de dados
- **SQLite (WAL mode)** - Banco de dados com suporte a concorrência
- **EasyOCR 1.7** - OCR local gratuito
- **OpenAI GPT-4o** - Análise de documentos com IA
- **Google Gemini** - Alternativa econômica ao GPT-4o
- **Azure Document Intelligence** - OCR cloud de alta precisão
- **Google Document AI** - Extração de tabelas (opcional)
- **PyMuPDF / pdfplumber** - Extração de texto nativo de PDFs

### Frontend
- **HTML5 / CSS3 / JavaScript** - Interface web vanilla
- **Fetch API** - Comunicação com backend

## Instalação

### Pré-requisitos

- Python 3.11+
- pip

### 1. Clone o repositório

```bash
git clone https://github.com/seu-usuario/licitafacil.git
cd licitafacil
```

### 2. Crie e ative o ambiente virtual

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate
```

### 3. Instale as dependências

```bash
pip install -r requirements.txt
```

### 4. Configure as variáveis de ambiente

```bash
# Windows
copy .env.example .env

# Linux/Mac
cp .env.example .env
```

Edite o arquivo `.env` com suas credenciais (veja seção Variáveis de Ambiente).

### 5. Inicie o servidor

```bash
cd backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 6. Acesse a aplicação

- **Frontend**: http://localhost:8000/atestados.html
- **API Docs (Swagger)**: http://localhost:8000/docs
- **API Docs (ReDoc)**: http://localhost:8000/redoc

## Variáveis de Ambiente

### Obrigatórias

| Variável | Descrição |
|----------|-----------|
| `SECRET_KEY` | Chave secreta para JWT (gere com `openssl rand -hex 32`) |
| `OPENAI_API_KEY` | Chave da API OpenAI (obrigatório se GOOGLE_API_KEY não estiver configurado) |

### Banco de Dados

| Variável | Descrição | Padrão |
|----------|-----------|--------|
| `DATABASE_URL` | URL de conexão do banco | `sqlite:///./licitafacil.db` |

### Autenticação

| Variável | Descrição | Padrão |
|----------|-----------|--------|
| `ALGORITHM` | Algoritmo JWT | `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Expiração do token em minutos | `30` |

### Provedores de IA

| Variável | Descrição |
|----------|-----------|
| `OPENAI_API_KEY` | Chave da API OpenAI |
| `GOOGLE_API_KEY` | Chave da API Google Gemini |
| `AI_PROVIDER` | Provedor preferencial: `auto`, `openai`, `gemini` |

### Google Document AI (Opcional)

| Variável | Descrição |
|----------|-----------|
| `DOCUMENT_AI_ENABLED` | Habilitar Document AI (`0` ou `1`) |
| `DOCUMENT_AI_FALLBACK_ONLY` | Usar apenas como fallback (`0` ou `1`) |
| `DOCUMENT_AI_PROJECT_ID` | ID do projeto Google Cloud |
| `DOCUMENT_AI_LOCATION` | Região (ex: `us`) |
| `DOCUMENT_AI_PROCESSOR_ID` | ID do processador |
| `GOOGLE_APPLICATION_CREDENTIALS` | Caminho para service account JSON |

### Azure Document Intelligence (Opcional)

| Variável | Descrição |
|----------|-----------|
| `AZURE_DOCUMENT_ENDPOINT` | Endpoint do recurso Azure |
| `AZURE_DOCUMENT_KEY` | Chave de acesso |

### Fila de Processamento

| Variável | Descrição | Padrão |
|----------|-----------|--------|
| `QUEUE_MAX_CONCURRENT` | Jobs simultâneos na fila | `3` |
| `QUEUE_POLL_INTERVAL` | Intervalo de verificação (segundos) | `1.0` |

### Admin Seed

| Variável | Descrição | Padrão |
|----------|-----------|--------|
| `ADMIN_EMAIL` | Email do admin inicial | `admin@licitafacil.com.br` |
| `ADMIN_PASSWORD` | Senha do admin inicial | `admin123` |
| `ADMIN_NAME` | Nome do admin inicial | `Administrador` |

### Configurações de Extração de Atestados

O sistema possui diversas variáveis `ATTESTADO_*` para ajuste fino da extração. Consulte o arquivo `.env.example` para a lista completa.

## Estrutura do Projeto

```
licitafacil/
├── backend/
│   ├── main.py                    # Entrada FastAPI + lifespan
│   ├── config.py                  # Pydantic Settings
│   ├── database.py                # SQLAlchemy + WAL mode
│   ├── auth.py                    # JWT authentication
│   ├── models.py                  # Modelos SQLAlchemy
│   ├── routers/
│   │   ├── atestados.py           # CRUD atestados + upload
│   │   ├── analise.py             # Análise de editais
│   │   ├── ai_status.py           # Status da fila de processamento
│   │   ├── auth.py                # Login/Register
│   │   ├── pipeline_status.py     # Status do pipeline
│   │   └── users.py               # Gestão de usuários
│   ├── services/
│   │   ├── document_processor.py  # Processamento principal de documentos
│   │   ├── processing_queue.py    # Fila assíncrona de processamento
│   │   ├── ocr_service.py         # Wrapper EasyOCR
│   │   ├── ai_provider.py         # Integração OpenAI/Gemini
│   │   ├── azure_document_service.py  # Integração Azure
│   │   ├── cascade_pipeline.py    # Orquestrador do pipeline
│   │   ├── quality_detector.py    # Detector de qualidade de documentos
│   │   ├── image_preprocessor.py  # Pré-processamento de imagens
│   │   └── atestado_service.py    # Lógica de negócio de atestados
│   └── tests/                     # Testes automatizados
├── frontend/
│   ├── atestados.html             # Página de atestados
│   ├── analise.html               # Página de análises
│   ├── css/                       # Estilos CSS
│   └── js/                        # Scripts JavaScript
├── uploads/                       # Arquivos enviados (não versionado)
├── requirements.txt               # Dependências Python
├── .env.example                   # Exemplo de variáveis de ambiente
├── PIPELINE_SETUP.md              # Guia de configuração do pipeline
└── README.md
```

## API Endpoints

### Autenticação (`/api/v1/auth`)

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| POST | `/login` | Login com email/senha |
| POST | `/register` | Registro de novo usuário |

### Atestados (`/api/v1/atestados`)

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| GET | `/` | Listar atestados do usuário |
| POST | `/upload` | Upload de atestado para processamento |
| GET | `/{id}` | Detalhes de um atestado |
| PUT | `/{id}` | Atualizar atestado |
| DELETE | `/{id}` | Remover atestado |

### Fila de Processamento (`/api/v1/ai/queue`)

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| GET | `/jobs` | Listar jobs do usuário |
| GET | `/jobs/{id}` | Status detalhado de um job |
| POST | `/jobs/{id}/cancel` | Cancelar job em andamento |
| POST | `/jobs/{id}/retry` | Reprocessar job falho |

### Análises (`/api/v1/analises`)

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| POST | `/` | Criar análise (upload de edital) |
| GET | `/` | Listar análises |
| GET | `/{id}` | Detalhes de uma análise |

### Pipeline (`/api/v1/pipeline`)

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| GET | `/status` | Status dos serviços disponíveis |
| POST | `/analyze-quality` | Analisar qualidade de documento |
| POST | `/process` | Processar documento pelo pipeline |
| GET | `/cost-estimate` | Estimar custo de processamento |

## Desenvolvimento

### Servidor de Desenvolvimento

```bash
cd backend
uvicorn main:app --reload --port 8000
```

### Testes

```bash
cd backend
pytest tests/ -v
```

### Linting

```bash
cd backend
ruff check .
```

### Type Checking

```bash
cd backend
mypy services/
```

## Licença

Este projeto é proprietário. Todos os direitos reservados.

---

Desenvolvido para análise de capacidade técnica em licitações públicas brasileiras.
