# Plano Detalhado - Modulo 3: Monitoramento PNCP

**Status**: PENDENTE
**Data criação**: 2026-02-11
**Dependências**: M1 (Licitações), M2 (Notificações) - ambos implementados
**Nova dependência**: `httpx>=0.25.0` (cliente HTTP async)

## Contexto

O Modulo 3 integra o LicitaFacil com a API publica do PNCP (Portal Nacional de Contratacoes Publicas) para monitoramento automatico de licitacoes. O usuario cria "monitores" com criterios de busca (palavras-chave, UFs, faixa de valor, modalidade) e o sistema busca periodicamente no PNCP, notifica novos resultados e permite importa-los como licitacoes no sistema.

---

## Passo 1: Models (`models/pncp.py`)

Criar `backend/models/pncp.py`:

```python
class PncpResultadoStatus:
    NOVO = "novo"
    INTERESSANTE = "interessante"
    DESCARTADO = "descartado"
    IMPORTADO = "importado"
    ALL = [NOVO, INTERESSANTE, DESCARTADO, IMPORTADO]

class PncpMonitoramento(Base):
    __tablename__ = "pncp_monitoramentos"
    id, user_id (FK CASCADE), nome (String 200), ativo (Bool default True, index),
    palavras_chave (JSON), ufs (JSON), modalidades (JSON), esferas (JSON),
    valor_minimo (Numeric 18,2), valor_maximo (Numeric 18,2),
    ultimo_check (DateTime tz), created_at (server_default=now)
    # Relationship: resultados (cascade all, delete-orphan)
    # Index composto: (user_id, ativo)

class PncpResultado(Base):
    __tablename__ = "pncp_resultados"
    id, monitoramento_id (FK CASCADE), user_id (FK CASCADE),
    numero_controle_pncp (String 100, index), orgao_cnpj (String 20),
    orgao_razao_social (String 500), objeto_compra (Text),
    modalidade_nome (String 100), uf (String 2, index), municipio (String 200),
    valor_estimado (Numeric 18,2), data_abertura (DateTime tz),
    data_encerramento (DateTime tz), link_sistema_origem (String 1000),
    dados_completos (JSON), status (String 20, default "novo", index),
    licitacao_id (FK SET NULL), encontrado_em (server_default=now)
    # Indexes compostos: (user_id, status), (numero_controle_pncp, user_id)
```

Atualizar `models/__init__.py`: exportar PncpMonitoramento, PncpResultado, PncpResultadoStatus.

---

## Passo 2: Schemas (`schemas/pncp.py`)

- **PncpMonitoramentoBase** - nome, ativo, palavras_chave, ufs, modalidades, esferas, valor_minimo, valor_maximo
- **PncpMonitoramentoCreate**(Base) - pass
- **PncpMonitoramentoUpdate** - todos opcionais (exclude_unset)
- **PncpMonitoramentoResponse**(Base) - + id, user_id, ultimo_check, created_at
- **PaginatedMonitoramentoResponse**(PaginatedResponse[PncpMonitoramentoResponse])
- **PncpResultadoResponse** - todos os campos
- **PaginatedResultadoResponse**(PaginatedResponse[PncpResultadoResponse])
- **PncpResultadoStatusUpdate** - status com validator in PncpResultadoStatus.ALL
- **PncpBuscaResponse** - data, total_registros, total_paginas, numero_pagina, paginas_restantes
- **PncpImportarRequest** - observacoes (Optional[str])

---

## Passo 3: Repositories (`repositories/pncp_repository.py`)

```python
class PncpMonitoramentoRepository(BaseRepository[PncpMonitoramento]):
    get_filtered(db, user_id, ativo=None, busca=None) -> Query
    get_ativos(db) -> List[PncpMonitoramento]
    atualizar_ultimo_check(db, monitoramento_id, data)

class PncpResultadoRepository(BaseRepository[PncpResultado]):
    get_filtered(db, user_id, monitoramento_id=None, status=None, uf=None, busca=None) -> Query
    existe_resultado(db, numero_controle, user_id) -> bool
    contar_por_status(db, user_id) -> dict
```

---

## Passo 4: Services PNCP

### 4.1 `services/pncp/__init__.py` - Vazio
### 4.2 `services/pncp/client.py` - PncpClient (httpx async + rate limit + retry)
### 4.3 `services/pncp/mapper.py` - PncpMapper (PNCP JSON -> models)
### 4.4 `services/pncp/matcher.py` - PncpMatcher (filtro client-side)
### 4.5 `services/pncp/sync_service.py` - PncpSyncService (worker background)

**API PNCP**: `GET /contratacoes/publicacao?dataInicial=YYYYMMDD&dataFinal=YYYYMMDD&pagina=N&tamanhoPagina=N`
**Response**: `{"data": [...], "totalRegistros", "totalPaginas", "numeroPagina", "paginasRestantes"}`

---

## Passo 5-6: Config + Messages

5 constantes PNCP_* em config/base.py + 6 mensagens em config/messages.py

---

## Passo 7: Router (`routers/pncp.py`) - 11 endpoints

Monitoramentos (6): CRUD + toggle
Resultados (2): list + status update
Importar (1): POST resultado -> licitacao
Busca + Sync (2): busca direta + sincronizar

---

## Passo 8-9: main.py + Migration Alembic

Router registration, lifespan start/stop, HTML route, 2 tabelas

---

## Passo 10-11: Notification Service + Frontend

notify_pncp_novos_resultados, monitoramento.html + js + css, nav updates

---

## Passo 12-13: requirements.txt + Testes (6 arquivos)

### Resumo: 18 novos arquivos + 12 modificados
