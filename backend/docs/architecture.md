# Arquitetura do Backend LicitaFácil

## Visão Geral

O backend do LicitaFácil é responsável pelo processamento de documentos de licitação,
extração de informações de atestados de capacidade técnica e editais, e matching
entre exigências e atestados disponíveis.

**Importante:** O sistema usa apenas processamento local (pdfplumber, PyMuPDF, EasyOCR, Tesseract).
APIs pagas de IA (OpenAI, Gemini, Document AI, Azure) foram desabilitadas.

## Estrutura de Diretórios

```
backend/
├── alembic/                   # Migrations de banco de dados
│   ├── versions/              # Arquivos de migration
│   └── env.py                 # Configuração do Alembic
├── config/                    # Configurações
│   ├── atestado.py           # Parâmetros de processamento
│   ├── base.py               # Configurações base
│   └── validation.py         # Validações
├── docs/                      # Documentação
│   └── architecture.md       # Este arquivo
├── repositories/              # Repositórios de dados
│   ├── base.py               # Repositório base genérico
│   └── atestado_repository.py # Repositório de atestados
├── routers/                   # Endpoints da API
│   ├── admin.py              # Rotas de administração
│   ├── analise.py            # Rotas de análises
│   ├── atestados.py          # Rotas de atestados
│   ├── auth.py               # Rotas de autenticação
│   └── base.py               # Router base autenticado
├── services/                  # Serviços de negócio
│   ├── aditivo/              # Processamento de aditivos
│   ├── atestado/             # Processamento de atestados
│   ├── extraction/           # Módulos de extração
│   ├── processors/           # Processadores de texto
│   └── table_extraction/     # Extração de tabelas
├── tests/                     # Testes automatizados
├── utils/                     # Utilitários
│   ├── error_handlers.py     # Tratamento de erros
│   ├── pagination.py         # Paginação
│   ├── retry.py              # Retry com backoff
│   └── validation.py         # Validações de upload
├── main.py                    # Ponto de entrada
├── models.py                  # Modelos SQLAlchemy
├── schemas.py                 # Schemas Pydantic
├── auth.py                    # Autenticação JWT
├── database.py                # Conexão com banco
└── seed.py                    # Script para criar admin
```

## Módulos Principais

### services/extraction/ - Módulos de Extração

Funções puras para processamento de dados extraídos.

| Módulo | Responsabilidade |
|--------|------------------|
| `constants.py` | Constantes (categorias, tokens, unidades) |
| `patterns.py` | Padrões regex compilados |
| `item_utils.py` | Utilitários para códigos de item |
| `text_normalizer.py` | Normalização de texto e unidades |
| `table_processor.py` | Processamento de tabelas |
| `service_filter.py` | Filtragem e deduplicação |

**Uso:**
```python
from services.extraction import (
    normalize_description,
    normalize_unit,
    parse_item_tuple,
    parse_quantity,
    normalize_item_code,
)
```

### services/aditivo/ - Processamento de Aditivos

Detecta e processa seções de aditivos contratuais em atestados.

| Módulo | Responsabilidade |
|--------|------------------|
| `detector.py` | Detecção de seções de aditivo |
| `validators.py` | Validação de linhas e descrições |
| `extractors.py` | Extração de informações |
| `transformer.py` | Prefixação de itens (S1-, S2-) |

### services/table_extraction/ - Extração de Tabelas

Extrai serviços de tabelas em documentos PDF.

```
table_extraction/
├── cascade.py           # Fluxo de extração em cascata
├── parsers/             # Parsing de texto
├── filters/             # Filtros de ruído
├── extractors/          # Extratores (pdfplumber, OCR)
├── analyzers/           # Analisadores de documento
└── utils/               # Utilitários
```

### services/processors/ - Processadores de Texto

Classes para processamento de texto extraído.

| Classe | Responsabilidade |
|--------|------------------|
| `TextProcessor` | Extração de itens de texto |
| `ServiceDeduplicator` | Remoção de duplicatas |
| `ServiceMerger` | Mesclagem de planilhas |
| `ServiceFilter` | Filtros de validação |

### services/atestado/ - Processamento de Atestados

| Módulo | Responsabilidade |
|--------|------------------|
| `processor.py` | AtestadoProcessor principal |
| `service.py` | Funções utilitárias |
| `persistence.py` | Persistência no banco |
| `pipeline.py` | Pipeline de processamento |

### Serviços de Alto Nível

| Módulo | Responsabilidade |
|--------|------------------|
| `matching_service.py` | Matching entre exigências e atestados |
| `ocr_service.py` | Serviço de OCR (EasyOCR + Tesseract) |
| `pdf_extractor.py` | Extração de PDFs (pdfplumber + PyMuPDF) |
| `sync_processor.py` | Processador síncrono (serverless) |
| `cache.py` | Cache em memória com TTL |

## Fluxo de Processamento

### Processamento de Atestado

```
PDF/Imagem
    ↓
Extração de texto (pdfplumber)
    ↓
OCR se necessário (EasyOCR/Tesseract)
    ↓
Extração de tabelas (pdfplumber)
    ↓
Detecção de aditivos (prefixos S1-, S2-)
    ↓
Enriquecimento via texto (TextProcessor)
    ↓
Deduplicação e filtragem
    ↓
Serviços extraídos
```

### Processamento de Edital

```
PDF
    ↓
Extração de texto
    ↓
Identificação de exigências
    ↓
Lista de exigências de capacidade técnica
```

### Matching

```
Exigências do Edital + Atestados do Usuário
    ↓
Normalização de unidades e descrições
    ↓
Cálculo de similaridade (keywords)
    ↓
Soma de quantidades por atestado
    ↓
Seleção greedy de atestados
    ↓
Resultado: atende/parcial/não_atende
```

## Modelos de Dados

### Usuario
```python
class Usuario(Base):
    id: int
    email: str
    senha_hash: str
    nome: str
    is_admin: bool
    is_approved: bool
    is_active: bool
    tema_preferido: str  # "light" ou "dark"
    created_at: datetime
```

### Atestado
```python
class Atestado(Base):
    id: int
    user_id: int
    descricao_servico: str
    quantidade: Decimal
    unidade: str
    contratante: str
    data_emissao: datetime
    arquivo_path: str
    texto_extraido: str
    servicos_json: List[Dict]  # Lista de serviços extraídos
    created_at: datetime
```

### Analise
```python
class Analise(Base):
    id: int
    user_id: int
    nome_licitacao: str
    arquivo_path: str
    exigencias_json: List[Dict]  # Exigências do edital
    resultado_json: List[Dict]   # Resultado do matching
    created_at: datetime
```

## Padrões Arquiteturais

### Repository Pattern

```python
class BaseRepository(Generic[ModelType]):
    def get_by_id(self, db, id) -> Optional[ModelType]
    def get_all_for_user(self, db, user_id) -> List[ModelType]
    def create(self, db, entity) -> ModelType
    def delete(self, db, entity) -> None
```

### Singleton para Serviços

```python
class TextProcessor:
    """Processador de texto."""
    ...

# Instância singleton
text_processor = TextProcessor()
```

### Injeção de Dependência

```python
@router.get("/")
def listar(
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_approved_user)
):
    ...
```

## Testes

| Arquivo | Cobertura |
|---------|-----------|
| `test_item_utils.py` | item_utils (29 testes) |
| `test_patterns.py` | patterns (18 testes) |
| `test_aditivo.py` | services/aditivo (17 testes) |
| `test_table_extraction.py` | table_extraction (49 testes) |
| `test_text_processor.py` | TextProcessor (29 testes) |
| `test_matching_service.py` | MatchingService (8 testes) |
| `test_deduplication.py` | ServiceDeduplicator (26 testes) |
| `test_service_merger.py` | ServiceMerger (15 testes) |
| `test_service_filter.py` | ServiceFilter (23 testes) |
| ... | ... |

**Total:** 1000+ testes automatizados

## Configuração

### Variáveis de Ambiente

```env
# Banco de dados
DATABASE_URL=sqlite:///./licitafacil.db

# JWT
SECRET_KEY=<chave-secreta>
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# OCR
OCR_TESSERACT_FALLBACK=true

# Uploads
UPLOAD_DIR=uploads
MAX_UPLOAD_SIZE=10485760
```

### Alembic (Migrations)

```bash
# Verificar status
alembic current

# Aplicar migrations
alembic upgrade head

# Criar nova migration
alembic revision --autogenerate -m "descricao"
```

## Convenções de Código

### Organização de Imports

```python
# 1. Stdlib
import re
from typing import Dict, List, Optional

# 2. Dependências externas
from fastapi import Depends, HTTPException

# 3. Imports internos
from config import AtestadoProcessingConfig
from services.extraction import normalize_unit

# 4. Imports relativos
from .text_cleanup import strip_trailing_unit_qty
```

### Naming

| Tipo | Convenção | Exemplo |
|------|-----------|---------|
| Módulos de filtro | `*_filters.py` | `validation_filters.py` |
| Módulos de parse | `*_parser.py` | `text_line_parser.py` |
| Classes | CamelCase | `TextProcessor` |
| Instâncias singleton | snake_case | `text_processor` |
| Funções privadas | `_prefixo` | `_build_description` |
| Constantes | UPPER_SNAKE | `STOP_PREFIXES` |

### Limite de Linhas

Módulos devem ter no máximo ~500-800 linhas. Funcionalidades complexas devem ser organizadas em pacotes.

## Métricas de Código

| Pacote | Linhas | Testes |
|--------|--------|--------|
| `services/extraction/` | ~1100 | 47 |
| `services/aditivo/` | ~1200 | 17 |
| `services/table_extraction/` | ~2500 | 49 |
| `services/processors/` | ~1800 | 94 |
| **Total** | ~6600 | 1000+ |
