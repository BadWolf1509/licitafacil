# Plano Detalhado - Modulo 2: Calendario, Lembretes e Notificacoes

> **Status**: IMPLEMENTADO
> **Data de implementacao**: 2026-02-11
> **Migracao Alembic**: `j0e4m35873ll_add_lembretes_notificacoes`
> **Testes adicionados**: 57 (schemas: 23, repository: 11, router lembretes: 11, router notificacoes: 12)
> **Total de testes apos implementacao**: 1109

---

## Contexto

O Modulo 2 adiciona gestao temporal ao LicitaFacil: lembretes vinculados a licitacoes, notificacoes in-app (sino), preferencias de notificacao, calendario mensal e infraestrutura de email (SMTP). Depende do Modulo 1 (licitacoes) ja implementado.

---

## Passo 1: Models - Lembrete, Notificacao, PreferenciaNotificacao

### Arquivo: `backend/models/lembrete.py`

```python
from __future__ import annotations
from datetime import datetime
from typing import List, Optional
from sqlalchemy import (
    Boolean, DateTime, ForeignKey, Index, Integer, JSON, String, Text
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from database import Base


class LembreteTipo:
    MANUAL = "manual"
    ABERTURA_LICITACAO = "abertura_licitacao"
    ENCERRAMENTO_PROPOSTA = "encerramento_proposta"
    VENCIMENTO_DOCUMENTO = "vencimento_documento"
    ENTREGA_CONTRATO = "entrega_contrato"
    PRAZO_RECURSO = "prazo_recurso"
    ALL = [MANUAL, ABERTURA_LICITACAO, ENCERRAMENTO_PROPOSTA,
           VENCIMENTO_DOCUMENTO, ENTREGA_CONTRATO, PRAZO_RECURSO]

class LembreteStatus:
    PENDENTE = "pendente"
    ENVIADO = "enviado"
    LIDO = "lido"
    CANCELADO = "cancelado"
    ALL = [PENDENTE, ENVIADO, LIDO, CANCELADO]

class LembreteRecorrencia:
    DIARIO = "diario"
    SEMANAL = "semanal"
    MENSAL = "mensal"
    ALL = [DIARIO, SEMANAL, MENSAL]

class NotificacaoTipo:
    LEMBRETE = "lembrete"
    DOCUMENTO_VENCENDO = "documento_vencendo"
    LICITACAO_ATUALIZADA = "licitacao_atualizada"
    PNCP_NOVA_LICITACAO = "pncp_nova_licitacao"
    CONTRATO_PRAZO = "contrato_prazo"
    SISTEMA = "sistema"
    ALL = [LEMBRETE, DOCUMENTO_VENCENDO, LICITACAO_ATUALIZADA,
           PNCP_NOVA_LICITACAO, CONTRATO_PRAZO, SISTEMA]


class Lembrete(Base):
    __tablename__ = "lembretes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True)
    licitacao_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("licitacoes.id", ondelete="CASCADE"), nullable=True, index=True)
    titulo: Mapped[str] = mapped_column(String(255), nullable=False)
    descricao: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    data_lembrete: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True)
    data_evento: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True)
    tipo: Mapped[str] = mapped_column(
        String(50), nullable=False, default=LembreteTipo.MANUAL)
    recorrencia: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    canais: Mapped[Optional[list]] = mapped_column(JSON, default=["app"])
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=LembreteStatus.PENDENTE)
    enviado_em: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now())

    usuario: Mapped["Usuario"] = relationship("Usuario")
    licitacao: Mapped[Optional["Licitacao"]] = relationship("Licitacao")

    __table_args__ = (
        Index('ix_lembretes_user_status_data', 'user_id', 'status', 'data_lembrete'),
        Index('ix_lembretes_status_data', 'status', 'data_lembrete'),
    )


class Notificacao(Base):
    __tablename__ = "notificacoes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True)
    titulo: Mapped[str] = mapped_column(String(255), nullable=False)
    mensagem: Mapped[str] = mapped_column(Text, nullable=False)
    tipo: Mapped[str] = mapped_column(String(50), nullable=False)
    link: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    lida: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    lida_em: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True)
    referencia_tipo: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    referencia_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now())

    usuario: Mapped["Usuario"] = relationship("Usuario")

    __table_args__ = (
        Index('ix_notificacoes_user_lida', 'user_id', 'lida'),
        Index('ix_notificacoes_user_created', 'user_id', 'created_at'),
    )


class PreferenciaNotificacao(Base):
    __tablename__ = "preferencias_notificacao"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    email_habilitado: Mapped[bool] = mapped_column(Boolean, default=True)
    app_habilitado: Mapped[bool] = mapped_column(Boolean, default=True)
    antecedencia_horas: Mapped[int] = mapped_column(Integer, default=24)
    email_resumo_diario: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), onupdate=func.now())

    usuario: Mapped["Usuario"] = relationship("Usuario")
```

### Atualizar `models/__init__.py`

Adicionar:
```python
from models.lembrete import (
    Lembrete, LembreteStatus, LembreteTipo, LembreteRecorrencia,
    Notificacao, NotificacaoTipo, PreferenciaNotificacao,
)
```

---

## Passo 2: Schemas

### Arquivo: `backend/schemas/lembrete.py`

```python
# LembreteBase, LembreteCreate, LembreteUpdate, LembreteStatusUpdate, LembreteResponse
# NotificacaoResponse, NotificacaoCountResponse
# PreferenciaNotificacaoResponse, PreferenciaNotificacaoUpdate
# PaginatedLembreteResponse, PaginatedNotificacaoResponse
# CalendarioQuery (data_inicio, data_fim como query params)

# Validators:
# - LembreteStatusUpdate.status in LembreteStatus.ALL
# - LembreteCreate.tipo in LembreteTipo.ALL
# - LembreteCreate.recorrencia in LembreteRecorrencia.ALL | None
# - LembreteCreate.canais subset of ["app", "email"]
```

Schemas seguem mesmo padrao de `schemas/licitacao.py`: Base/Create/Update/Response + PaginatedResponse[T].

### Atualizar `schemas/__init__.py`

Adicionar re-exports de todos os novos schemas.

---

## Passo 3: Repositories

### Arquivo: `backend/repositories/lembrete_repository.py`

```python
class LembreteRepository(BaseRepository[Lembrete]):
    def get_calendario(self, db, user_id, data_inicio, data_fim) -> List[Lembrete]:
        """Lembretes por range de data (para calendario)."""

    def get_pendentes_para_envio(self, db, antes_de: datetime) -> List[Lembrete]:
        """Lembretes pendentes com data_lembrete <= antes_de."""

    def get_filtered(self, db, user_id, status=None, tipo=None, licitacao_id=None):
        """Query filtravel para paginacao."""

    def marcar_enviado(self, db, lembrete: Lembrete):
        """Marca status=enviado + enviado_em=now()."""

lembrete_repository = LembreteRepository()
```

### Arquivo: `backend/repositories/notificacao_repository.py`

```python
class NotificacaoRepository(BaseRepository[Notificacao]):
    def count_nao_lidas(self, db, user_id) -> int:
        """COUNT WHERE user_id=X AND lida=False."""

    def marcar_lida(self, db, notificacao: Notificacao):
        """lida=True, lida_em=now()."""

    def marcar_todas_lidas(self, db, user_id) -> int:
        """UPDATE SET lida=True WHERE user_id=X AND lida=False. Retorna count."""

notificacao_repository = NotificacaoRepository()
```

### Arquivo: `backend/repositories/preferencia_repository.py`

```python
class PreferenciaNotificacaoRepository(BaseRepository[PreferenciaNotificacao]):
    def get_or_create(self, db, user_id) -> PreferenciaNotificacao:
        """Busca preferencias ou cria com defaults."""

preferencia_repository = PreferenciaNotificacaoRepository()
```

---

## Passo 4: Services - Notificacao + Email + Scheduler

### 4.1 `backend/services/notification/__init__.py`

Vazio.

### 4.2 `backend/services/notification/email_service.py`

```python
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from config.base import (
    SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD,
    SMTP_USE_TLS, SMTP_FROM_EMAIL, SMTP_FROM_NAME, EMAIL_ENABLED
)

class EmailService:
    def send(self, to: str, subject: str, html_body: str) -> bool:
        """Envia email via SMTP. Retorna True se sucesso."""
        if not EMAIL_ENABLED:
            logger.info(f"Email desabilitado, nao enviando para {to}")
            return False
        # smtplib + MIMEMultipart + starttls

    def render_lembrete(self, titulo, descricao, data_evento, licitacao_numero=None) -> str:
        """Renderiza corpo HTML do email de lembrete."""
        # Template HTML inline simples (sem Jinja2 para evitar dependencia)
```

**Decisao**: Usar `smtplib` sincrono em thread separada (via `asyncio.to_thread()`) em vez de `aiosmtplib` para evitar nova dependencia. O email nao e critico em latencia.

### 4.3 `backend/services/notification/notification_service.py`

```python
class NotificationService:
    def notify(self, db, user_id, titulo, mensagem, tipo,
               canais=None, link=None, referencia_tipo=None, referencia_id=None):
        """
        Cria notificacao in-app + envia email se configurado.
        1. Verifica preferencias do usuario (get_or_create)
        2. Se app_habilitado: cria Notificacao no DB
        3. Se email em canais e email_habilitado: envia via EmailService
        """

    def notify_lembrete(self, db, lembrete: Lembrete):
        """Notifica sobre um lembrete disparado."""

notification_service = NotificationService()
```

### 4.4 `backend/services/notification/reminder_scheduler.py`

```python
class ReminderScheduler:
    """Worker background que processa lembretes pendentes."""
    def __init__(self):
        self._is_running = False
        self._task = None
        self._check_interval = REMINDER_CHECK_INTERVAL  # default 60s
        self._lookahead_minutes = REMINDER_LOOKAHEAD_MINUTES  # default 5

    async def start(self):
        self._is_running = True
        self._task = asyncio.create_task(self._worker())

    async def stop(self):
        self._is_running = False
        if self._task:
            self._task.cancel()

    async def _worker(self):
        while self._is_running:
            try:
                await self._check_lembretes()
            except Exception:
                logger.error("Erro no ReminderScheduler", exc_info=True)
            await asyncio.sleep(self._check_interval)

    async def _check_lembretes(self):
        """Busca lembretes pendentes e dispara notificacoes."""
        # 1. Abrir sessao DB
        # 2. Query lembretes pendentes com data_lembrete <= now + lookahead
        # 3. Para cada: notification_service.notify_lembrete()
        # 4. Marcar como enviado
        # 5. Se recorrente: criar proximo lembrete

reminder_scheduler = ReminderScheduler()
```

---

## Passo 5: Config - Novas variaveis de ambiente

### Modificar: `backend/config/base.py`

Adicionar ao final:
```python
# === SMTP (Email) ===
SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = env_int("SMTP_PORT", 587)
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_USE_TLS = env_bool("SMTP_USE_TLS", True)
SMTP_FROM_EMAIL = os.getenv("SMTP_FROM_EMAIL", "noreply@licitafacil.com")
SMTP_FROM_NAME = os.getenv("SMTP_FROM_NAME", "LicitaFacil")
EMAIL_ENABLED = env_bool("EMAIL_ENABLED", False)

# === Reminder Scheduler ===
REMINDER_CHECK_INTERVAL = env_int("REMINDER_CHECK_INTERVAL", 60)
REMINDER_LOOKAHEAD_MINUTES = env_int("REMINDER_LOOKAHEAD_MINUTES", 5)
```

### Modificar: `backend/config/__init__.py`

Adicionar re-exports das novas constantes.

---

## Passo 6: Messages - Novas constantes

### Modificar: `backend/config/messages.py`

Adicionar:
```python
# Lembretes
LEMBRETE_NOT_FOUND = "Lembrete nao encontrado"
LEMBRETE_DELETED = "Lembrete excluido com sucesso!"
LEMBRETE_STATUS_UPDATED = "Status do lembrete atualizado!"
INVALID_LEMBRETE_STATUS = "Status de lembrete invalido"
# Notificacoes
NOTIFICACAO_NOT_FOUND = "Notificacao nao encontrada"
NOTIFICACAO_DELETED = "Notificacao excluida com sucesso!"
TODAS_LIDAS = "Todas as notificacoes marcadas como lidas"
PREFERENCIAS_ATUALIZADAS = "Preferencias de notificacao atualizadas"
```

---

## Passo 7: Routers

### 7.1 `backend/routers/lembretes.py`

```python
router = AuthenticatedRouter(prefix="/lembretes", tags=["Lembretes"])

GET  /                  -> PaginatedLembreteResponse (filtros: status, tipo, licitacao_id)
GET  /calendario        -> List[LembreteResponse] (query: data_inicio, data_fim)
POST /                  -> LembreteResponse (201)
PUT  /{id}              -> LembreteResponse
DELETE /{id}            -> Mensagem
PATCH /{id}/status      -> LembreteResponse (body: {status, observacao?})
```

**NOTA**: `/calendario` deve vir ANTES de `/{id}` no router.

### 7.2 `backend/routers/notificacoes.py`

```python
router = AuthenticatedRouter(prefix="/notificacoes", tags=["Notificacoes"])

GET  /                  -> PaginatedNotificacaoResponse
GET  /nao-lidas/count   -> NotificacaoCountResponse
PATCH /{id}/lida        -> NotificacaoResponse
POST /marcar-todas-lidas -> Mensagem
DELETE /{id}            -> Mensagem
GET  /preferencias      -> PreferenciaNotificacaoResponse
PUT  /preferencias      -> PreferenciaNotificacaoResponse
```

**NOTA**: `/nao-lidas/count`, `/marcar-todas-lidas` e `/preferencias` devem vir ANTES de `/{id}`.

---

## Passo 8: main.py - Registrar routers + scheduler

### Modificar: `backend/main.py`

```python
# Import:
from routers import admin, ai_status, analise, atestados, auth, licitacoes, lembretes, notificacoes
from services.notification.reminder_scheduler import reminder_scheduler

# Registrar routers:
app.include_router(lembretes.router, prefix=API_PREFIX)
app.include_router(notificacoes.router, prefix=API_PREFIX)

# Lifespan - adicionar scheduler:
async def lifespan(app):
    # ... startup existente ...
    await processing_queue.start()
    await reminder_scheduler.start()
    logger.info("ReminderScheduler iniciado")
    yield
    await reminder_scheduler.stop()
    await processing_queue.stop()

# Rota HTML:
@app.get("/calendario.html")
def serve_calendario():
    return FileResponse(os.path.join(frontend_path, "calendario.html"))
```

---

## Passo 9: Migracao Alembic

### Arquivo: `backend/alembic/versions/j0e4m35873ll_add_lembretes_notificacoes.py`

```
down_revision = 'i9d3l24762kk'

upgrade():
  1. CREATE TABLE lembretes (todas as colunas + FKs)
  2. CREATE INDEX compostos
  3. CREATE TABLE notificacoes (todas as colunas + FK)
  4. CREATE INDEX compostos
  5. CREATE TABLE preferencias_notificacao (todas as colunas + FK + UNIQUE user_id)

downgrade():
  DROP TABLE preferencias_notificacao
  DROP TABLE notificacoes
  DROP TABLE lembretes
```

Usar mesmo padrao idempotente da migracao do M1 (`_table_exists`, `_index_exists`).

---

## Passo 10: Frontend - Notificacoes (sino global)

### 10.1 `frontend/js/notificacoes.js`

Componente global carregado em TODAS as paginas:

```javascript
const NotificacoesModule = {
    pollInterval: null,
    count: 0,

    init() {
        this.renderBell();      // Injeta HTML do sino no header
        this.loadCount();       // Primeira carga
        this.startPolling();    // Poll a cada 30s
    },

    renderBell() {
        // Injeta antes do link "Sair" no nav:
        // <div class="notification-bell-wrapper">
        //   <button class="notification-bell" aria-label="Notificacoes">
        //     <svg>...</svg>  (icone sino)
        //     <span class="notification-badge hidden" id="notifBadge">0</span>
        //   </button>
        //   <div class="notification-dropdown hidden" id="notifDropdown">
        //     <div class="notif-header">Notificacoes <button>Marcar todas</button></div>
        //     <div class="notif-list" id="notifList"></div>
        //     <a href="calendario.html" class="notif-footer">Ver calendario</a>
        //   </div>
        // </div>
    },

    async loadCount() {
        const resp = await api.get('/notificacoes/nao-lidas/count');
        this.count = resp.count || 0;
        this.updateBadge();
    },

    startPolling() {
        this.pollInterval = setInterval(() => this.loadCount(), 30000);
    },

    async toggleDropdown() {
        // Carrega 5 ultimas notificacoes
        // Toggle visibility do dropdown
    },

    async marcarLida(id) { ... },
    async marcarTodasLidas() { ... },
    async excluir(id) { ... },
};

// Auto-init apos DOMContentLoaded (se autenticado)
document.addEventListener('DOMContentLoaded', () => {
    // Verifica se esta logado antes de inicializar
    if (document.querySelector('.header-nav')) {
        NotificacoesModule.init();
    }
});
```

### 10.2 Estilos do sino em `frontend/css/style.css`

Adicionar ao final:
```css
/* Notification Bell */
.notification-bell-wrapper { position: relative; display: inline-flex; }
.notification-bell { background: none; border: none; cursor: pointer; position: relative; padding: 0.5rem; }
.notification-badge { position: absolute; top: 0; right: 0; background: var(--error); color: white;
    border-radius: 50%; min-width: 18px; height: 18px; font-size: 0.7rem; display: flex;
    align-items: center; justify-content: center; }
.notification-dropdown { position: absolute; right: 0; top: 100%; width: 320px; background: var(--bg-card);
    border: 1px solid var(--border); border-radius: var(--radius-md); box-shadow: var(--shadow);
    z-index: 1000; max-height: 400px; overflow-y: auto; }
.notif-item { padding: 0.75rem; border-bottom: 1px solid var(--border); cursor: pointer; }
.notif-item:hover { background: var(--bg-secondary); }
.notif-item.unread { border-left: 3px solid var(--primary); }
```

### 10.3 Atualizar TODOS os HTML para incluir notificacoes.js

Adicionar `<script src="js/notificacoes.js"></script>` DEPOIS de `error-handler.js` e ANTES do JS especifico da pagina, em:
- `dashboard.html`
- `atestados.html`
- `analises.html`
- `licitacoes.html`
- `admin.html`
- `perfil.html`

Tambem adicionar link "Calendario" na nav de todas as paginas (entre "Licitacoes" e "Admin").

---

## Passo 11: Frontend - Calendario

### 11.1 `frontend/calendario.html`

Estrutura:
- Header nav (com link "Calendario" ativo)
- alertContainer
- Header: "Calendario" + botoes navegacao mes (< Mes/Ano >)
- Grid calendario mensal (7 colunas DOM-SEG-TER-QUA-QUI-SEX-SAB)
- Lista de lembretes do dia selecionado
- Botao "+ Novo Lembrete"
- Modal criar/editar lembrete

### 11.2 `frontend/js/calendario.js`

```javascript
const CalendarioModule = {
    mesAtual: new Date().getMonth(),
    anoAtual: new Date().getFullYear(),
    lembretes: [],
    diaSelecionado: null,

    init() {
        this.renderCalendario();
        this.carregarLembretes();
        this.setupForms();
    },

    renderCalendario() {
        // Grid de dias do mes com indicadores de lembrete
        // Dias clicaveis -> mostra lembretes do dia
    },

    async carregarLembretes() {
        // GET /lembretes/calendario?data_inicio=...&data_fim=...
        // Marcar dias com lembretes no grid
    },

    navegarMes(delta) {
        // Muda mesAtual/anoAtual, re-renderiza
    },

    selecionarDia(dia) {
        // Filtra lembretes do dia, mostra lista lateral
    },

    renderListaDia(lembretes) {
        // Cards de lembrete com status, hora, acoes
    },

    async criarLembrete(dados) { ... },
    async editarLembrete(id, dados) { ... },
    async excluirLembrete(id) { ... },
    async mudarStatus(id, status) { ... },
};
```

### 11.3 `frontend/css/calendario.css`

```css
.calendario-grid { display: grid; grid-template-columns: repeat(7, 1fr); gap: 1px; }
.calendario-header { text-align: center; font-weight: 600; padding: 0.5rem; }
.calendario-dia { min-height: 80px; padding: 0.5rem; border: 1px solid var(--border);
    cursor: pointer; position: relative; }
.calendario-dia:hover { background: var(--bg-secondary); }
.calendario-dia.hoje { border-color: var(--primary); }
.calendario-dia.selecionado { background: rgba(245, 158, 11, 0.1); }
.calendario-dia.outro-mes { opacity: 0.4; }
.dia-numero { font-weight: 500; margin-bottom: 0.25rem; }
.dia-indicador { width: 6px; height: 6px; border-radius: 50%; background: var(--primary);
    display: inline-block; margin: 1px; }
.lembretes-dia { margin-top: 1rem; }
.lembrete-card { padding: 1rem; border-left: 3px solid var(--primary);
    background: var(--bg-card); border-radius: var(--radius-sm); margin-bottom: 0.5rem; }
.lembrete-hora { font-size: 0.85rem; color: var(--text-secondary); }
```

---

## Passo 12: Testes

### 12.1 `tests/test_schemas_lembrete.py`
- Testar LembreteCreate com dados validos/invalidos
- Testar LembreteStatusUpdate com status validos/invalidos
- Testar PreferenciaNotificacaoUpdate
- Testar NotificacaoCountResponse

### 12.2 `tests/test_lembrete_repository.py`
- Testar CRUD (create, get_by_id_for_user, delete)
- Testar get_calendario com range de datas
- Testar get_pendentes_para_envio
- Testar get_filtered com cada combinacao de filtros
- Testar marcar_enviado

### 12.3 `tests/test_lembretes_router.py`
- Testar todos os 6 endpoints
- Testar autenticacao (401 sem token)
- Testar ownership (404 para lembrete de outro usuario)
- Testar filtros de listagem
- Testar paginacao
- Testar endpoint /calendario com range de datas

### 12.4 `tests/test_notificacoes_router.py`
- Testar GET / (listagem paginada)
- Testar GET /nao-lidas/count
- Testar PATCH /{id}/lida
- Testar POST /marcar-todas-lidas
- Testar DELETE /{id}
- Testar GET /preferencias (get_or_create)
- Testar PUT /preferencias

---

## Resumo de Arquivos

### Novos arquivos (criar):
| # | Arquivo | Descricao |
|---|---------|-----------|
| 1 | `backend/models/lembrete.py` | Lembrete, Notificacao, PreferenciaNotificacao + constantes |
| 2 | `backend/schemas/lembrete.py` | Todos os schemas de lembretes e notificacoes |
| 3 | `backend/repositories/lembrete_repository.py` | LembreteRepository |
| 4 | `backend/repositories/notificacao_repository.py` | NotificacaoRepository |
| 5 | `backend/repositories/preferencia_repository.py` | PreferenciaNotificacaoRepository |
| 6 | `backend/services/notification/__init__.py` | Package |
| 7 | `backend/services/notification/email_service.py` | EmailService (SMTP) |
| 8 | `backend/services/notification/notification_service.py` | NotificationService (orquestrador) |
| 9 | `backend/services/notification/reminder_scheduler.py` | ReminderScheduler (worker background) |
| 10 | `backend/routers/lembretes.py` | 6 endpoints |
| 11 | `backend/routers/notificacoes.py` | 7 endpoints |
| 12 | `backend/alembic/versions/j0e4m35873ll_add_lembretes_notificacoes.py` | Migracao 3 tabelas |
| 13 | `frontend/calendario.html` | Pagina de calendario |
| 14 | `frontend/js/calendario.js` | Logica do calendario |
| 15 | `frontend/js/notificacoes.js` | Componente sino global |
| 16 | `frontend/css/calendario.css` | Estilos do calendario |
| 17 | `tests/test_schemas_lembrete.py` | Testes de schema |
| 18 | `tests/test_lembrete_repository.py` | Testes de repository |
| 19 | `tests/test_lembretes_router.py` | Testes de router lembretes |
| 20 | `tests/test_notificacoes_router.py` | Testes de router notificacoes |

### Arquivos existentes modificados:
| # | Arquivo | Mudanca |
|---|---------|---------|
| 1 | `backend/models/__init__.py` | Re-exportar novos modelos |
| 2 | `backend/schemas/__init__.py` | Re-exportar novos schemas |
| 3 | `backend/config/base.py` | Adicionar constantes SMTP_* e REMINDER_* |
| 4 | `backend/config/__init__.py` | Re-exportar novas constantes |
| 5 | `backend/config/messages.py` | Adicionar 8 novas constantes |
| 6 | `backend/main.py` | Registrar 2 routers + iniciar/parar scheduler + rota HTML |
| 7 | `frontend/css/style.css` | Estilos do sino de notificacoes |
| 8 | `frontend/dashboard.html` | + notificacoes.js + link Calendario na nav |
| 9 | `frontend/atestados.html` | + notificacoes.js + link Calendario na nav |
| 10 | `frontend/analises.html` | + notificacoes.js + link Calendario na nav |
| 11 | `frontend/licitacoes.html` | + notificacoes.js + link Calendario na nav |
| 12 | `frontend/admin.html` | + notificacoes.js + link Calendario na nav |
| 13 | `frontend/perfil.html` | + notificacoes.js + link Calendario na nav |

---

## Verificacao Final

1. **Testes unitarios**: `python -m pytest tests/ -x -q --ignore=tests/integration` - **1109 passed** (1052 existentes + 57 novos)
2. **Migracao**: `alembic upgrade head` sem erros
3. **Backend**: `uvicorn main:app --reload` inicia sem erros
4. **Swagger**: Abrir `/docs` e verificar 13 novos endpoints (/lembretes + /notificacoes)
5. **Frontend calendario**: Abrir `/calendario.html`, criar lembrete, navegar meses
6. **Sino**: Verificar sino aparece em todas as paginas, badge atualiza
7. **Backward compat**: Todas as paginas existentes continuam funcionando
8. **CI**: `ruff check . && python -m pytest tests/ -x -q --ignore=tests/integration`
