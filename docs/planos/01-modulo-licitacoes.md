# Plano Detalhado - Modulo 1: Gestao de Licitacoes

> **Status**: IMPLEMENTADO
> **Data de implementacao**: 2026-02-11
> **Migracao Alembic**: `i9d3l24762kk_add_licitacoes_module`
> **Testes adicionados**: 64 (schemas: 23, repository: 22, router: 19)
> **Total de testes apos implementacao**: 1052

---

## Contexto

O Modulo 1 e a entidade central do LicitaFacil expandido. Todas as licitacoes que o usuario acompanha sao gerenciadas aqui. Os demais modulos (calendario, documentos, propostas, contratos, BI, PNCP) dependem desta tabela como FK.

Antes de implementar o modulo propriamente dito, foi necessario refatorar `models.py` e `schemas.py` em packages para suportar os 22 modelos futuros.

---

## Passo 0: Infraestrutura - Refatorar models.py e schemas.py em packages

### 0.1 Refatorar models.py -> models/ package

**Objetivo**: Mover os 5 modelos existentes para arquivos individuais, mantendo backward compat total.

**Arquivos criados**:
```
backend/models/
    __init__.py          # Re-exporta TUDO para backward compat
    base.py              # Re-export de Base
    usuario.py           # Classe Usuario
    atestado.py          # Classe Atestado
    analise.py           # Classe Analise
    processing_job.py    # Classe ProcessingJobModel
    audit_log.py         # Classe AuditLog
```

**`models/__init__.py`** (backward compat):
```python
"""
Package de modelos SQLAlchemy.

Re-exporta todos os modelos para manter backward compatibility
com imports existentes: `from models import Usuario, Atestado, ...`
"""
from models.usuario import Usuario
from models.atestado import Atestado
from models.analise import Analise
from models.processing_job import ProcessingJobModel
from models.audit_log import AuditLog

__all__ = [
    "Usuario", "Atestado", "Analise",
    "ProcessingJobModel", "AuditLog",
]
```

**Cuidados com imports circulares**:
- `models/usuario.py` usa `relationship("Atestado")` como string (lazy) - OK
- `models/atestado.py` usa `relationship("Usuario")` como string (lazy) - OK
- SQLAlchemy resolve relationships por nome de classe, nao por import

### 0.2 Refatorar schemas.py -> schemas/ package

**Arquivos criados**:
```
backend/schemas/
    __init__.py          # Re-exporta TUDO
    base.py              # PaginatedResponse, Mensagem, T
    usuario.py           # Schemas de usuario
    auth.py              # Token, AuthConfig, PasswordPolicy
    atestado.py          # Schemas de atestado
    analise.py           # Schemas de analise
    processing.py        # JobResponse, ProcessingJobDetail, etc.
    admin.py             # AdminStatsResponse, etc.
```

---

## Passo 1: Modelos - Licitacao, LicitacaoTag, LicitacaoHistorico

### 1.1 Arquivo: `backend/models/licitacao.py`

```python
from __future__ import annotations
from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from sqlalchemy import (
    Boolean, DateTime, ForeignKey, Index, Integer,
    Numeric, String, Text, UniqueConstraint
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from database import Base


class LicitacaoStatus:
    IDENTIFICADA = "identificada"
    EM_ANALISE = "em_analise"
    GO_NOGO = "go_nogo"
    ELABORANDO_PROPOSTA = "elaborando_proposta"
    PROPOSTA_ENVIADA = "proposta_enviada"
    EM_DISPUTA = "em_disputa"
    VENCIDA = "vencida"
    PERDIDA = "perdida"
    CONTRATO_ASSINADO = "contrato_assinado"
    EM_EXECUCAO = "em_execucao"
    CONCLUIDA = "concluida"
    DESISTIDA = "desistida"
    CANCELADA = "cancelada"

    ALL = [
        IDENTIFICADA, EM_ANALISE, GO_NOGO, ELABORANDO_PROPOSTA,
        PROPOSTA_ENVIADA, EM_DISPUTA, VENCIDA, PERDIDA,
        CONTRATO_ASSINADO, EM_EXECUCAO, CONCLUIDA,
        DESISTIDA, CANCELADA,
    ]

    TRANSITIONS = {
        IDENTIFICADA: [EM_ANALISE, DESISTIDA, CANCELADA],
        EM_ANALISE: [GO_NOGO, DESISTIDA, CANCELADA],
        GO_NOGO: [ELABORANDO_PROPOSTA, DESISTIDA, CANCELADA],
        ELABORANDO_PROPOSTA: [PROPOSTA_ENVIADA, DESISTIDA, CANCELADA],
        PROPOSTA_ENVIADA: [EM_DISPUTA, DESISTIDA, CANCELADA],
        EM_DISPUTA: [VENCIDA, PERDIDA, CANCELADA],
        VENCIDA: [CONTRATO_ASSINADO, CANCELADA],
        PERDIDA: [],
        CONTRATO_ASSINADO: [EM_EXECUCAO, CANCELADA],
        EM_EXECUCAO: [CONCLUIDA, CANCELADA],
        CONCLUIDA: [],
        DESISTIDA: [],
        CANCELADA: [],
    }

    LABELS = {
        IDENTIFICADA: "Identificada",
        EM_ANALISE: "Em Analise",
        GO_NOGO: "GO/NO-GO",
        ELABORANDO_PROPOSTA: "Elaborando Proposta",
        PROPOSTA_ENVIADA: "Proposta Enviada",
        EM_DISPUTA: "Em Disputa",
        VENCIDA: "Vencida",
        PERDIDA: "Perdida",
        CONTRATO_ASSINADO: "Contrato Assinado",
        EM_EXECUCAO: "Em Execucao",
        CONCLUIDA: "Concluida",
        DESISTIDA: "Desistida",
        CANCELADA: "Cancelada",
    }


class LicitacaoFonte:
    MANUAL = "manual"
    PNCP = "pncp"
    IMPORTADO = "importado"


class Licitacao(Base):
    __tablename__ = "licitacoes"
    # 25+ colunas incluindo: id, user_id, numero, orgao, objeto, modalidade,
    # numero_controle_pncp, valor_estimado/homologado/proposta, status,
    # decisao_go, motivo_nogo, datas (publicacao/abertura/encerramento/resultado),
    # uf, municipio, esfera, links, observacoes, fonte, timestamps

class LicitacaoTag(Base):
    __tablename__ = "licitacao_tags"
    # UniqueConstraint('licitacao_id', 'tag')

class LicitacaoHistorico(Base):
    __tablename__ = "licitacao_historico"
    # Log de mudancas de status
```

### 1.2 Alteracao em models/analise.py

FK nullable para licitacoes:
```python
licitacao_id: Mapped[Optional[int]] = mapped_column(
    ForeignKey("licitacoes.id", ondelete="SET NULL"), nullable=True, index=True
)
```

---

## Passo 2: Schemas - LicitacaoBase, Create, Update, Response

### Arquivo: `backend/schemas/licitacao.py`

11 schemas Pydantic:
- `LicitacaoBase` - campos compartilhados (numero, orgao, objeto, modalidade + 15 opcionais)
- `LicitacaoCreate(LicitacaoBase)` - herda todos os campos
- `LicitacaoUpdate(BaseModel)` - todos opcionais para update parcial
- `LicitacaoStatusUpdate` - status + observacao, com `@field_validator` contra `LicitacaoStatus.ALL`
- `LicitacaoTagCreate` - tag com max_length=100
- `LicitacaoTagResponse` - id + tag
- `LicitacaoHistoricoResponse` - id, licitacao_id, user_id, status_anterior/novo, observacao, created_at
- `LicitacaoResponse(LicitacaoBase)` - + id, user_id, status, tags[], timestamps
- `LicitacaoDetalheResponse(LicitacaoResponse)` - + historico[]
- `PaginatedLicitacaoResponse(PaginatedResponse[LicitacaoResponse])` - paginacao tipada
- `LicitacaoEstatisticasResponse` - total, por_status, por_uf, por_modalidade

---

## Passo 3: Repository - LicitacaoRepository

### Arquivo: `backend/repositories/licitacao_repository.py`

`LicitacaoRepository(BaseRepository[Licitacao])` com metodos:
- `get_by_id_with_relations()` - joinedload tags + historico
- `get_filtered()` - filtros por status, uf, modalidade, busca (ilike em numero/orgao/objeto)
- `transition_status()` - muda status, cria LicitacaoHistorico, auto-set decisao_go=False em DESISTIDA
- `add_tag()` / `remove_tag()` - normalizacao strip + lowercase
- `get_estatisticas()` - group_by counts por status, uf, modalidade
- `get_historico()` - ordenado desc por created_at

Singleton: `licitacao_repository = LicitacaoRepository()`

---

## Passo 4: Messages - Novas constantes

### Arquivo modificado: `backend/config/messages.py`

```python
LICITACAO_NOT_FOUND = "Licitacao nao encontrada"
LICITACAO_DELETED = "Licitacao excluida com sucesso!"
LICITACAO_STATUS_UPDATED = "Status da licitacao atualizado com sucesso!"
INVALID_STATUS_TRANSITION = "Transicao de status invalida"
TAG_ALREADY_EXISTS = "Tag ja existe nesta licitacao"
TAG_NOT_FOUND = "Tag nao encontrada"
```

---

## Passo 5: Router - /api/v1/licitacoes (10 endpoints)

### Arquivo: `backend/routers/licitacoes.py`

10 endpoints usando `AuthenticatedRouter(prefix="/licitacoes", tags=["Licitacoes"])`:

| Metodo | Path | Descricao |
|--------|------|-----------|
| GET | `/` | Listar com paginacao + filtros (status, uf, modalidade, busca) |
| GET | `/estatisticas` | Stats agrupadas (ANTES de `/{id}`) |
| GET | `/{id}` | Detalhe com tags + historico |
| POST | `/` | Criar + historico inicial automatico |
| PUT | `/{id}` | Update parcial via `model_dump(exclude_unset=True)` |
| DELETE | `/{id}` | Excluir com cascade |
| PATCH | `/{id}/status` | Mudar status (valida transicao) |
| GET | `/{id}/historico` | Log de mudancas de status |
| POST | `/{id}/tags` | Adicionar tag (409 em duplicata) |
| DELETE | `/{id}/tags/{tag}` | Remover tag (404 se inexistente) |

**NOTA**: `/estatisticas` deve vir ANTES de `/{id}` para evitar conflito de rota.

---

## Passo 6: main.py - Registrar router + servir pagina HTML

```python
from routers import ... licitacoes
app.include_router(licitacoes.router, prefix=API_PREFIX)

@app.get("/licitacoes.html")
def serve_licitacoes():
    return FileResponse(os.path.join(frontend_path, "licitacoes.html"))
```

---

## Passo 7: Migracao Alembic

Revisao: `i9d3l24762kk` (depende de `h8c2k13651jj`)

upgrade():
1. `create_table("licitacoes")` - todas as colunas + 9 indexes
2. `create_table("licitacao_tags")` - 3 indexes + UniqueConstraint
3. `create_table("licitacao_historico")` - 3 indexes
4. `add_column("analises", "licitacao_id")` + FK + index

downgrade(): reverso

---

## Passo 8: Frontend

### 8.1 `frontend/licitacoes.html`
- Header nav com link ativo
- Grid de estatisticas
- Barra de filtros (status, UF, modalidade, busca com debounce)
- Lista de cards
- Detalhe com tabs (Dados, Historico, Tags)
- 3 modais (Nova, Editar, MudarStatus)

### 8.2 `frontend/js/licitacoes.js`
- `LicitacoesModule` com event delegation via `data-action`
- Filtros com `ui.debounce()` no campo busca
- CRUD completo + mudanca de status + tags
- `Sanitize.escapeHtml()` em todo innerHTML
- `confirmAction()` para exclusoes

### 8.3 `frontend/css/licitacoes.css`
- 13 variantes de `.status-badge-*` com cores por status
- Cards com borda lateral colorida
- Timeline vertical para historico
- Tag chips com botao remover
- Grid responsivo

---

## Passo 9: Testes

### 9.1 `tests/test_licitacao_schemas.py` (23 testes)
- LicitacaoCreate: validos, invalidos, max_length
- LicitacaoUpdate: campos opcionais
- LicitacaoStatusUpdate: validos, invalidos, todos os 13 status
- LicitacaoTagCreate, Response schemas, PaginatedLicitacaoResponse.create

### 9.2 `tests/test_licitacao_repository.py` (22 testes)
- CRUD basico (create, get_by_id, ownership, relations, cascade delete)
- Filtros (status, uf, modalidade, busca, orgao, isolamento por usuario, combinados)
- Transicoes de status (historico, decisao_go automatico, multiplas transicoes)
- Tags (add, normalizacao lowercase, duplicata, remove, inexistente)
- Estatisticas (vazio, com dados)
- Historico (ordenacao desc)

### 9.3 `tests/test_licitacao_router.py` (19 testes)
- Auth (401 sem token)
- CRUD endpoints (create 201, list, list com filtro, detalhe, 404s, update, delete)
- Transicoes de status (valida, invalida 400, estado final 400)
- Historico, Tags (add 201, duplicata 409, remove, inexistente 404)
- Estatisticas

---

## Passo 10: Atualizar nav em TODOS os HTML existentes

Link "Licitacoes" adicionado na nav de:
- `dashboard.html`
- `atestados.html`
- `analises.html`
- `admin.html`
- `perfil.html`

---

## Resumo de Arquivos

### Novos arquivos criados:
| # | Arquivo | Descricao |
|---|---------|-----------|
| 1 | `backend/models/__init__.py` | Re-exports para backward compat |
| 2 | `backend/models/usuario.py` | Modelo Usuario (movido) |
| 3 | `backend/models/atestado.py` | Modelo Atestado (movido) |
| 4 | `backend/models/analise.py` | Modelo Analise (movido + licitacao_id FK) |
| 5 | `backend/models/processing_job.py` | Modelo ProcessingJobModel (movido) |
| 6 | `backend/models/audit_log.py` | Modelo AuditLog (movido) |
| 7 | `backend/models/licitacao.py` | Licitacao, LicitacaoTag, LicitacaoHistorico, LicitacaoStatus |
| 8 | `backend/schemas/__init__.py` | Re-exports para backward compat |
| 9 | `backend/schemas/base.py` | PaginatedResponse, Mensagem (movido) |
| 10 | `backend/schemas/usuario.py` | Schemas usuario (movido) |
| 11 | `backend/schemas/auth.py` | Schemas auth (movido) |
| 12 | `backend/schemas/atestado.py` | Schemas atestado (movido) |
| 13 | `backend/schemas/analise.py` | Schemas analise (movido) |
| 14 | `backend/schemas/processing.py` | Schemas processing jobs (movido) |
| 15 | `backend/schemas/admin.py` | Schemas admin stats (movido) |
| 16 | `backend/schemas/licitacao.py` | Todos os schemas de licitacao |
| 17 | `backend/repositories/licitacao_repository.py` | LicitacaoRepository |
| 18 | `backend/routers/licitacoes.py` | 10 endpoints |
| 19 | `backend/alembic/versions/i9d3l24762kk_add_licitacoes_module.py` | Migracao |
| 20 | `frontend/licitacoes.html` | Pagina de gestao |
| 21 | `frontend/js/licitacoes.js` | Logica JS |
| 22 | `frontend/css/licitacoes.css` | Estilos |
| 23 | `tests/test_licitacao_schemas.py` | 23 testes de schema |
| 24 | `tests/test_licitacao_repository.py` | 22 testes de repository |
| 25 | `tests/test_licitacao_router.py` | 19 testes de router |

### Arquivos existentes modificados:
| # | Arquivo | Mudanca |
|---|---------|---------|
| 1 | `backend/models.py` | Substituido por models/ package |
| 2 | `backend/schemas.py` | Substituido por schemas/ package |
| 3 | `backend/config/messages.py` | 6 novas constantes |
| 4 | `backend/main.py` | Router licitacoes + rota HTML |
| 5 | `backend/tests/conftest.py` | Cleanup de tabelas licitacao |
| 6 | `frontend/dashboard.html` | Link Licitacoes na nav |
| 7 | `frontend/atestados.html` | Link Licitacoes na nav |
| 8 | `frontend/analises.html` | Link Licitacoes na nav |
| 9 | `frontend/admin.html` | Link Licitacoes na nav |
| 10 | `frontend/perfil.html` | Link Licitacoes na nav |
