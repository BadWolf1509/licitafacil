# Plano Arquitetural Geral - LicitaFacil: Sistema de Gestao de Licitacoes

> **Ultima atualizacao**: 2026-02-11
> **Modulos implementados**: M1 (Licitacoes), M2 (Calendario/Lembretes/Notificacoes), M3 (Monitoramento PNCP), M4 (Gestao Documental)
> **Proxima fase**: F5 → M5 (Propostas e Precos)
> **Total de testes**: 1349 | **Migracoes Alembic**: 5 (base + M1 + M2 + M4 + M3)

## Contexto

O LicitaFacil hoje e uma ferramenta de analise de capacidade tecnica: o usuario faz upload de atestados (OCR + extracao) e analisa editais para verificar quais exigencias seus atestados atendem. Porem, o licitante brasileiro precisa gerenciar **todo o ciclo de vida** de uma licitacao - desde a descoberta do edital ate a execucao do contrato. O sistema atual cobre apenas 1 das 11 etapas desse ciclo.

Este plano define a **arquitetura geral** (modelo de dados, infraestrutura de notificacoes, estrutura de APIs, frontend) que suportara todos os 7 modulos futuros. Cada modulo tera seu proprio plano detalhado de implementacao.

---

## 1. Modelo de Dados Completo (5 existentes + 17 novas tabelas)

### 1.1 Alteracao em Tabela Existente

**`analises`** - Adicionar FK nullable para licitacoes:
```
licitacao_id: Optional[int] = ForeignKey("licitacoes.id", ondelete="SET NULL"), nullable=True, index=True
```
Backward-compatible: registros existentes mantem `licitacao_id=NULL`.

### 1.2 Modulo 1: Gestao de Licitacoes (tabela central)

**`licitacoes`** - Entidade central do sistema
| Coluna | Tipo | Notas |
|--------|------|-------|
| id | Integer PK | |
| user_id | FK usuarios CASCADE | index |
| numero | String(100) | "PE 001/2025" |
| orgao | String(500) | |
| objeto | Text | Descricao completa |
| modalidade | String(100) | "Pregao Eletronico", "Concorrencia", etc. |
| numero_controle_pncp | String(100) nullable | unique, index - se importada do PNCP |
| valor_estimado | Numeric(18,2) nullable | |
| valor_homologado | Numeric(18,2) nullable | |
| valor_proposta | Numeric(18,2) nullable | |
| status | String(30) default="identificada" | index - ver workflow abaixo |
| decisao_go | Boolean nullable | GO/NO-GO |
| motivo_nogo | Text nullable | |
| data_publicacao | DateTime(tz) nullable | |
| data_abertura | DateTime(tz) nullable | index |
| data_encerramento | DateTime(tz) nullable | |
| data_resultado | DateTime(tz) nullable | |
| uf | String(2) nullable | index |
| municipio | String(200) nullable | |
| esfera | String(20) nullable | "federal", "estadual", "municipal" |
| link_edital | String(1000) nullable | |
| link_sistema_origem | String(1000) nullable | |
| observacoes | Text nullable | |
| fonte | String(30) default="manual" | "manual", "pncp", "importado" |
| created_at | DateTime(tz) server_default=now() | |
| updated_at | DateTime(tz) onupdate=now() | |

**Indexes compostos:** (user_id, status), (user_id, created_at), (uf, modalidade)

**Status workflow:**
```
identificada -> em_analise -> go_nogo -> elaborando_proposta -> proposta_enviada
-> em_disputa -> vencida -> contrato_assinado -> em_execucao -> concluida
                         \-> perdida
              \-> desistida
              \-> cancelada (qualquer estagio)
```

**`licitacao_tags`** - Tags livres por licitacao
| Coluna | Tipo | Notas |
|--------|------|-------|
| id | Integer PK | |
| licitacao_id | FK licitacoes CASCADE | |
| tag | String(100) | index |
| **unique** | (licitacao_id, tag) | |

**`licitacao_historico`** - Log de mudancas de status
| Coluna | Tipo | Notas |
|--------|------|-------|
| id | Integer PK | |
| licitacao_id | FK licitacoes CASCADE | |
| user_id | Integer | |
| status_anterior | String(30) nullable | |
| status_novo | String(30) | |
| observacao | Text nullable | |
| created_at | DateTime(tz) server_default=now() | |

### 1.3 Modulo 2: Calendario e Lembretes

**`lembretes`**
| Coluna | Tipo | Notas |
|--------|------|-------|
| id | Integer PK | |
| user_id | FK usuarios CASCADE | index |
| licitacao_id | FK licitacoes CASCADE nullable | |
| titulo | String(255) | |
| descricao | Text nullable | |
| data_lembrete | DateTime(tz) | index - quando disparar |
| data_evento | DateTime(tz) nullable | quando o evento acontece |
| tipo | String(50) default="manual" | "manual", "abertura_licitacao", "encerramento_proposta", "vencimento_documento", "entrega_contrato", "prazo_recurso" |
| recorrencia | String(30) nullable | null=unico, "diario", "semanal", "mensal" |
| canais | JSON default=["app"] | ["app", "email"] |
| status | String(20) default="pendente" | "pendente", "enviado", "lido", "cancelado" |
| enviado_em | DateTime(tz) nullable | |
| created_at | DateTime(tz) server_default=now() | |

**Indexes:** (user_id, status, data_lembrete), (status, data_lembrete)

**`notificacoes`** - Historico de notificacoes in-app
| Coluna | Tipo | Notas |
|--------|------|-------|
| id | Integer PK | |
| user_id | FK usuarios CASCADE | index |
| titulo | String(255) | |
| mensagem | Text | |
| tipo | String(50) | "lembrete", "documento_vencendo", "licitacao_atualizada", "pncp_nova_licitacao", "contrato_prazo", "sistema" |
| link | String(500) nullable | Link in-app |
| lida | Boolean default=False | index |
| lida_em | DateTime(tz) nullable | |
| referencia_tipo | String(50) nullable | Referencia polimorfica |
| referencia_id | Integer nullable | |
| created_at | DateTime(tz) server_default=now() | |

**`preferencias_notificacao`** - 1:1 com usuario
| Coluna | Tipo | Notas |
|--------|------|-------|
| id | Integer PK | |
| user_id | FK usuarios CASCADE | unique |
| email_habilitado | Boolean default=True | |
| app_habilitado | Boolean default=True | |
| antecedencia_horas | Integer default=24 | |
| email_resumo_diario | Boolean default=False | |
| created_at / updated_at | DateTime(tz) | |

### 1.4 Modulo 3: Monitoramento PNCP

**`pncp_monitoramentos`** - Criterios de busca do usuario
| Coluna | Tipo | Notas |
|--------|------|-------|
| id | Integer PK | |
| user_id | FK usuarios CASCADE | index |
| nome | String(200) | |
| ativo | Boolean default=True | index |
| palavras_chave | JSON nullable | ["pavimentacao", "drenagem"] |
| ufs | JSON nullable | ["SP", "RJ"] |
| modalidades | JSON nullable | Codigos PNCP |
| valor_minimo | Numeric(18,2) nullable | |
| valor_maximo | Numeric(18,2) nullable | |
| esferas | JSON nullable | ["F", "E", "M"] |
| ultimo_check | DateTime(tz) nullable | |
| created_at | DateTime(tz) server_default=now() | |

**`pncp_resultados`** - Resultados encontrados
| Coluna | Tipo | Notas |
|--------|------|-------|
| id | Integer PK | |
| monitoramento_id | FK pncp_monitoramentos CASCADE | index |
| user_id | FK usuarios CASCADE | index |
| numero_controle_pncp | String(100) | index |
| orgao_cnpj | String(20) nullable | |
| orgao_razao_social | String(500) nullable | |
| objeto_compra | Text nullable | |
| modalidade_nome | String(100) nullable | |
| uf | String(2) nullable | |
| municipio | String(200) nullable | |
| valor_estimado | Numeric(18,2) nullable | |
| data_abertura | DateTime(tz) nullable | |
| data_encerramento | DateTime(tz) nullable | |
| link_sistema_origem | String(1000) nullable | |
| dados_completos | JSON nullable | Payload PNCP completo |
| status | String(20) default="novo" | "novo", "interessante", "descartado", "importado" |
| licitacao_id | FK licitacoes SET NULL nullable | Quando importado |
| encontrado_em | DateTime(tz) server_default=now() | |

### 1.5 Modulo 4: Gestao Documental

**`documentos_licitacao`**
| Coluna | Tipo | Notas |
|--------|------|-------|
| id | Integer PK | |
| user_id | FK usuarios CASCADE | index |
| licitacao_id | FK licitacoes SET NULL nullable | |
| nome | String(255) | |
| tipo_documento | String(100) | "edital", "certidao_negativa", "balanco", "contrato_social", "procuracao", "declaracao", "planilha", "outro" |
| arquivo_path | String(500) nullable | |
| tamanho_bytes | Integer nullable | |
| data_emissao | DateTime(tz) nullable | |
| data_validade | DateTime(tz) nullable | index |
| status | String(20) default="valido" | "valido", "vencendo", "vencido", "nao_aplicavel" |
| obrigatorio | Boolean default=False | |
| observacoes | Text nullable | |
| created_at / updated_at | DateTime(tz) | |

**`checklist_edital`** - Itens obrigatorios por licitacao
| Coluna | Tipo | Notas |
|--------|------|-------|
| id | Integer PK | |
| licitacao_id | FK licitacoes CASCADE | index |
| user_id | FK usuarios CASCADE | |
| descricao | Text | |
| tipo_documento | String(100) nullable | |
| obrigatorio | Boolean default=True | |
| cumprido | Boolean default=False | |
| documento_id | FK documentos_licitacao SET NULL nullable | Documento que satisfaz |
| observacao | Text nullable | |
| ordem | Integer default=0 | |
| created_at | DateTime(tz) server_default=now() | |

### 1.6 Modulo 5: Propostas e Precos

**`propostas`** - 1:1 com licitacao
| Coluna | Tipo | Notas |
|--------|------|-------|
| id | Integer PK | |
| user_id | FK usuarios CASCADE | index |
| licitacao_id | FK licitacoes CASCADE | index |
| valor_total | Numeric(18,2) nullable | |
| bdi_percentual | Numeric(8,4) nullable | |
| status | String(30) default="rascunho" | "rascunho", "em_elaboracao", "revisao", "finalizada", "enviada" |
| observacoes | Text nullable | |
| arquivo_path | String(500) nullable | |
| created_at / updated_at | DateTime(tz) | |

**`proposta_itens`**
| Coluna | Tipo | Notas |
|--------|------|-------|
| id | Integer PK | |
| proposta_id | FK propostas CASCADE | index |
| descricao | Text | |
| unidade | String(50) nullable | |
| quantidade | Numeric(15,4) nullable | |
| valor_unitario | Numeric(18,4) nullable | |
| valor_total | Numeric(18,2) nullable | |
| codigo_sinapi | String(20) nullable | |
| ordem | Integer default=0 | |

**`banco_precos`** - Base de precos do usuario
| Coluna | Tipo | Notas |
|--------|------|-------|
| id | Integer PK | |
| user_id | FK usuarios CASCADE | index |
| descricao | Text | |
| unidade | String(50) nullable | |
| valor_referencia | Numeric(18,4) | |
| fonte | String(100) nullable | "SINAPI", "SICRO", "proprio" |
| codigo_referencia | String(50) nullable | index |
| data_referencia | DateTime(tz) nullable | |
| ativo | Boolean default=True | |
| created_at / updated_at | DateTime(tz) | |

### 1.7 Modulo 6: Contratos

**`contratos`**
| Coluna | Tipo | Notas |
|--------|------|-------|
| id | Integer PK | |
| user_id | FK usuarios CASCADE | index |
| licitacao_id | FK licitacoes SET NULL nullable | |
| numero_contrato | String(100) | |
| orgao_contratante | String(500) | |
| objeto | Text | |
| valor_contrato | Numeric(18,2) | |
| valor_aditivos | Numeric(18,2) default=0 | |
| valor_medido | Numeric(18,2) default=0 | |
| valor_faturado | Numeric(18,2) default=0 | |
| data_assinatura | DateTime(tz) nullable | |
| data_inicio | DateTime(tz) nullable | |
| data_termino | DateTime(tz) nullable | index |
| prazo_dias | Integer nullable | |
| status | String(30) default="ativo" | "ativo", "suspenso", "concluido", "rescindido", "encerrado" |
| percentual_execucao | Numeric(5,2) default=0 | |
| arquivo_path | String(500) nullable | |
| observacoes | Text nullable | |
| created_at / updated_at | DateTime(tz) | |

**`medicoes`**
| Coluna | Tipo | Notas |
|--------|------|-------|
| id | Integer PK | |
| contrato_id | FK contratos CASCADE | |
| user_id | FK usuarios CASCADE | |
| numero_medicao | Integer | unique com contrato_id |
| periodo_inicio / periodo_fim | DateTime(tz) nullable | |
| valor_medido | Numeric(18,2) | |
| valor_faturado | Numeric(18,2) nullable | |
| status | String(30) default="em_elaboracao" | "em_elaboracao", "enviada", "aprovada", "paga", "glosada" |
| data_envio / data_aprovacao / data_pagamento | DateTime(tz) nullable | |
| nota_fiscal | String(100) nullable | |
| arquivo_path | String(500) nullable | |
| observacoes | Text nullable | |
| created_at | DateTime(tz) server_default=now() | |

**`aditivos`**
| Coluna | Tipo | Notas |
|--------|------|-------|
| id | Integer PK | |
| contrato_id | FK contratos CASCADE | |
| user_id | FK usuarios CASCADE | |
| numero_aditivo | Integer | unique com contrato_id |
| tipo | String(50) | "valor", "prazo", "valor_e_prazo", "supressao", "acrescimo" |
| valor_aditivo | Numeric(18,2) nullable | |
| dias_acrescidos | Integer nullable | |
| nova_data_termino | DateTime(tz) nullable | |
| justificativa | Text nullable | |
| data_assinatura | DateTime(tz) nullable | |
| arquivo_path | String(500) nullable | |
| created_at | DateTime(tz) server_default=now() | |

### 1.8 Modulo 7: BI (Concorrentes)

**`concorrentes`** - Unica tabela nova do modulo BI
| Coluna | Tipo | Notas |
|--------|------|-------|
| id | Integer PK | |
| user_id | FK usuarios CASCADE | index |
| licitacao_id | FK licitacoes CASCADE | index |
| nome_empresa | String(500) | |
| cnpj | String(20) nullable | index |
| valor_proposta | Numeric(18,2) nullable | |
| posicao | Integer nullable | 1=vencedor |
| vencedor | Boolean default=False | |
| observacoes | Text nullable | |
| created_at | DateTime(tz) server_default=now() | |

### 1.9 Resumo: 22 tabelas totais

| # | Tabela | Modulo | Dependencias FK |
|---|--------|--------|-----------------|
| 1-5 | usuarios, atestados, analises*, processing_jobs, audit_logs | Existentes | *analises ganha FK nullable p/ licitacoes |
| 6 | licitacoes | M1 | usuarios |
| 7 | licitacao_tags | M1 | licitacoes |
| 8 | licitacao_historico | M1 | licitacoes |
| 9 | lembretes | M2 | usuarios, licitacoes |
| 10 | notificacoes | M2 | usuarios |
| 11 | preferencias_notificacao | M2 | usuarios |
| 12 | pncp_monitoramentos | M3 | usuarios |
| 13 | pncp_resultados | M3 | pncp_monitoramentos, usuarios, licitacoes |
| 14 | documentos_licitacao | M4 | usuarios, licitacoes |
| 15 | checklist_edital | M4 | licitacoes, documentos_licitacao |
| 16 | propostas | M5 | usuarios, licitacoes |
| 17 | proposta_itens | M5 | propostas |
| 18 | banco_precos | M5 | usuarios |
| 19 | contratos | M6 | usuarios, licitacoes |
| 20 | medicoes | M6 | contratos, usuarios |
| 21 | aditivos | M6 | contratos, usuarios |
| 22 | concorrentes | M7 | usuarios, licitacoes |

---

## 2. Infraestrutura de Notificacoes

### 2.1 Email: SMTP Direto

Configuracao via variaveis de ambiente:
```
SMTP_HOST=smtp.exemplo.com
SMTP_PORT=587
SMTP_USER=notificacoes@licitafacil.com.br
SMTP_PASSWORD=xxx
SMTP_USE_TLS=true
EMAIL_FROM=LicitaFacil <notificacoes@licitafacil.com.br>
EMAIL_ENABLED=true
```

### 2.2 Novos Arquivos de Servico

```
backend/services/notification/
    __init__.py
    notification_service.py    # Orquestrador: cria Notificacao + despacha canais
    email_service.py           # Cliente SMTP com smtplib (sincrono, HTML inline)
    reminder_scheduler.py      # Task async que verifica lembretes pendentes
```
> **Nota (implementacao)**: Templates HTML sao inline no email_service.py para evitar dependencia de Jinja2. Podem ser extraidos para templates/ se necessario no futuro.

### 2.3 NotificationService

```python
class NotificationService:
    def notify(self, db, user_id, titulo, mensagem, tipo, canais=["app"], link=None,
               referencia_tipo=None, referencia_id=None) -> Notificacao:
        # 1. Sempre cria notificacao in-app
        # 2. Verifica preferencias do usuario
        # 3. Se "email" em canais e usuario permite: envia via EmailService
```

### 2.4 ReminderScheduler - Task async no lifespan do FastAPI

```python
class ReminderScheduler:
    # Roda a cada 60s (como o processing_queue existente)
    # Query: lembretes WHERE status='pendente' AND data_lembrete <= NOW()
    # Para cada: NotificationService.notify() + status='enviado'
    # Tambem verifica documentos vencendo (a cada 1h)
```

Integracao no `main.py` lifespan (ao lado do `processing_queue` existente):
```python
async with lifespan(app):
    await processing_queue.start()
    await reminder_scheduler.start()
    yield
    await reminder_scheduler.stop()
    await processing_queue.stop()
```

### 2.5 Eventos que Geram Notificacoes

| Evento | Tipo | Canais |
|--------|------|--------|
| Lembrete atinge data_lembrete | lembrete | app + email |
| Documento vence em N dias | documento_vencendo | app + email |
| PNCP encontra novos editais | pncp_nova_licitacao | app + email |
| Contrato proximo do termino | contrato_prazo | app + email |
| Mudanca de status de licitacao | licitacao_atualizada | app |
| Resumo diario (se habilitado) | resumo_diario | email |

---

## 3. Estrutura de APIs

### 3.1 Novos Routers (8 arquivos)

Todos seguem o padrao existente: `AuthenticatedRouter` com `prefix` e `tags`.

```
backend/routers/
    licitacoes.py        (NOVO) - /api/v1/licitacoes
    lembretes.py         (NOVO) - /api/v1/lembretes
    notificacoes.py      (NOVO) - /api/v1/notificacoes
    pncp.py              (NOVO) - /api/v1/pncp
    documentos.py        (NOVO) - /api/v1/documentos
    propostas.py         (NOVO) - /api/v1/propostas
    contratos.py         (NOVO) - /api/v1/contratos
    bi.py                (NOVO) - /api/v1/bi
```

### 3.2 Endpoints por Modulo

**M1 - Licitacoes** (`/api/v1/licitacoes`)
```
GET    /                        Lista (paginado, filtravel por status/uf/modalidade)
GET    /{id}                    Detalhe
POST   /                        Criar
PUT    /{id}                    Atualizar
DELETE /{id}                    Excluir
PATCH  /{id}/status             Mudar status (gera historico)
GET    /{id}/historico           Timeline de mudancas
POST   /{id}/tags               Adicionar tag
DELETE /{id}/tags/{tag}          Remover tag
GET    /estatisticas             Contagem por status/uf/modalidade
```

**M2 - Lembretes** (`/api/v1/lembretes`)
```
GET    /                        Lista (paginado, filtravel)
GET    /calendario               Lembretes por range de data (para calendario)
POST   /                        Criar
PUT    /{id}                    Atualizar
DELETE /{id}                    Excluir
PATCH  /{id}/status             Marcar lido/cancelado
```

**M2 - Notificacoes** (`/api/v1/notificacoes`)
```
GET    /                        Lista (paginado)
GET    /nao-lidas/count         Contagem nao-lidas (badge do sino)
PATCH  /{id}/lida               Marcar como lida
POST   /marcar-todas-lidas      Marcar todas como lidas
DELETE /{id}                    Excluir
GET    /preferencias            Preferencias do usuario
PUT    /preferencias            Atualizar preferencias
```

**M3 - PNCP** (`/api/v1/pncp`)
```
GET    /monitoramentos          Lista monitores
POST   /monitoramentos          Criar monitor
PUT    /monitoramentos/{id}     Atualizar
DELETE /monitoramentos/{id}     Excluir
PATCH  /monitoramentos/{id}/toggle  Ativar/desativar
GET    /resultados              Lista resultados (paginado, filtravel)
PATCH  /resultados/{id}/status  Marcar interessante/descartado
POST   /resultados/{id}/importar  Importar como Licitacao
GET    /busca                   Busca direta no PNCP (proxy p/ evitar CORS)
POST   /sincronizar             Sync manual de todos monitores ativos
```

**M4 - Documentos** (`/api/v1/documentos`)
```
GET    /                        Lista (paginado, filtravel por tipo/status)
GET    /{id}                    Detalhe
POST   /upload                  Upload documento
PUT    /{id}                    Atualizar metadados
DELETE /{id}                    Excluir
GET    /vencendo                Documentos vencendo em 30 dias
GET    /licitacao/{id}          Documentos de uma licitacao
GET    /checklist/{id}          Checklist de uma licitacao
POST   /checklist/{id}          Criar/atualizar itens checklist
PATCH  /checklist/{id}/{item_id}  Toggle item checklist
```

**M5 - Propostas** (`/api/v1/propostas`)
```
GET    /                        Lista (paginado)
GET    /{id}                    Proposta com itens
POST   /                        Criar para uma licitacao
PUT    /{id}                    Atualizar cabecalho
DELETE /{id}                    Excluir
POST   /{id}/itens              Adicionar item
PUT    /{id}/itens/{item_id}    Atualizar item
DELETE /{id}/itens/{item_id}    Excluir item
POST   /{id}/calcular           Recalcular totais
GET    /banco-precos             Lista banco de precos
POST   /banco-precos             Adicionar preco
PUT    /banco-precos/{id}        Atualizar preco
DELETE /banco-precos/{id}        Excluir preco
GET    /banco-precos/busca       Buscar precos
```

**M6 - Contratos** (`/api/v1/contratos`)
```
GET    /                            Lista (paginado, filtravel por status)
GET    /{id}                        Detalhe com medicoes e aditivos
POST   /                            Criar
PUT    /{id}                        Atualizar
DELETE /{id}                        Excluir
POST   /{id}/medicoes               Criar medicao
PUT    /{id}/medicoes/{mid}          Atualizar medicao
DELETE /{id}/medicoes/{mid}          Excluir medicao
PATCH  /{id}/medicoes/{mid}/status   Mudar status medicao
POST   /{id}/aditivos               Criar aditivo
PUT    /{id}/aditivos/{aid}          Atualizar aditivo
DELETE /{id}/aditivos/{aid}          Excluir aditivo
GET    /resumo                       Resumo financeiro geral
```

**M7 - BI** (`/api/v1/bi`)
```
GET    /dashboard                  Stats agregadas do dashboard
GET    /licitacoes/funil           Funil por status
GET    /licitacoes/taxa-sucesso    Win/loss rate
GET    /licitacoes/por-uf          Distribuicao geografica
GET    /licitacoes/por-modalidade  Distribuicao por modalidade
GET    /financeiro/resumo          Total estimado/proposto/contratado/medido/faturado
GET    /financeiro/evolucao        Evolucao mensal
GET    /concorrentes/ranking       Concorrentes mais frequentes
GET    /concorrentes/comparativo   Taxa de vitoria vs concorrentes
GET    /documentos/status          Saude documental (validos/vencendo/vencidos)
```

### 3.3 Novos Repositories (8 arquivos)

Todos herdam `BaseRepository[ModelType]` seguindo o padrao de `base.py`:
```
backend/repositories/
    licitacao_repository.py       LicitacaoRepository + singleton
    lembrete_repository.py        LembreteRepository + singleton
    notificacao_repository.py     NotificacaoRepository + singleton
    pncp_repository.py            PncpMonitoramentoRepository, PncpResultadoRepository
    documento_repository.py       DocumentoLicitacaoRepository, ChecklistRepository
    proposta_repository.py        PropostaRepository, BancoPrecoRepository
    contrato_repository.py        ContratoRepository, MedicaoRepository, AditivoRepository
    concorrente_repository.py     ConcorrenteRepository
```

---

## 4. Integracao PNCP

### 4.1 Novos Arquivos

```
backend/services/pncp/
    __init__.py
    pncp_client.py           # Cliente HTTP async (httpx) para API PNCP
    pncp_sync_service.py     # Task background: verifica monitores a cada 1h
    pncp_mapper.py           # Mapeia JSON do PNCP para modelos internos
```

### 4.2 API PNCP (publica, sem auth)

Base: `https://pncp.gov.br/api/consulta/v1/`
- `GET /contratacoes/publicacao?dataInicial=YYYYMMDD&dataFinal=YYYYMMDD&codigoModalidadeContratacao=N&uf=XX&pagina=N&tamanhoPagina=N`
- `GET /contratos?dataInicial=YYYYMMDD&dataFinal=YYYYMMDD&pagina=N`

### 4.3 Mapeamento PNCP -> LicitaFacil

| Campo PNCP | -> | Campo interno |
|------------|-----|---------------|
| numeroControlePNCP | | numero_controle_pncp |
| orgaoEntidade.cnpj | | orgao_cnpj |
| orgaoEntidade.razaoSocial | | orgao_razao_social |
| objetoCompra | | objeto_compra |
| modalidadeNome | | modalidade_nome |
| unidadeOrgao.ufSigla | | uf |
| valorTotalEstimado | | valor_estimado |
| dataAberturaProposta | | data_abertura |
| linkSistemaOrigem | | link_sistema_origem |

---

## 5. Frontend

### 5.1 Novas Paginas HTML (7)

```
frontend/
    licitacoes.html      Gestao de licitacoes (lista + kanban + detalhe)
    calendario.html      Calendario mensal + lista de lembretes
    monitoramento.html   Monitoramento PNCP (monitores + resultados)
    documentos.html      Gestao documental (upload + validades + checklist)
    propostas.html       Propostas + banco de precos
    contratos.html       Contratos + medicoes + aditivos
    bi.html              Dashboards e graficos (Chart.js)
```

### 5.2 Novos JS (8 arquivos)

```
frontend/js/
    licitacoes.js        Logica de gestao de licitacoes
    calendario.js        Renderizacao do calendario + CRUD lembretes
    monitoramento.js     Gestao de monitores PNCP + resultados
    documentos.js        Upload, validades, checklist
    propostas.js         CRUD propostas + itens + banco precos
    contratos.js         CRUD contratos + medicoes + aditivos
    bi.js                Graficos Chart.js + dashboards
    notificacoes.js      Componente sino (compartilhado em todas as paginas)
```

### 5.3 Novos CSS (7 arquivos)

```
frontend/css/
    licitacoes.css, calendario.css, monitoramento.css,
    documentos.css, propostas.css, contratos.css, bi.css
```

### 5.4 Navegacao - Dropdown Menus

Substituir a nav linear atual por dropdowns agrupados:

```
Dashboard | Licitacoes v | Documentos v | Execucao v | BI | [sino] | Admin | Perfil | Sair

Licitacoes:          Documentos:          Execucao:
  Gestao               Atestados            Propostas
  Monitoramento PNCP   Documentos           Contratos
  Calendario           Analises
```

### 5.5 Componente Sino de Notificacoes

- `notificacoes.js` carregado em todas as paginas
- Poll `GET /notificacoes/nao-lidas/count` a cada 30s
- Badge com contagem no icone
- Click abre dropdown com 10 ultimas notificacoes
- Cada notificacao linka para a pagina relevante
- Botao "Marcar todas como lidas"

### 5.6 Dashboard Expandido

O dashboard.html ganha novos widgets:
1. **Stats row**: licitacoes ativas, contratos ativos, valor faturado, docs vencendo
2. **Pipeline**: Funil horizontal de licitacoes por estagio
3. **Calendario**: Proximos 5 compromissos/lembretes
4. **PNCP**: Novos editais encontrados (com link "Ver")
5. **Atividade recente**: Ultimas 5 acoes em qualquer modulo
6. Manter stats existentes (atestados, analises)

Dados via `GET /api/v1/bi/dashboard`.

### 5.7 Graficos BI: Chart.js

```html
<script src="https://cdn.jsdelivr.net/npm/chart.js@4/dist/chart.umd.min.js"></script>
```
Sem build step. Consistente com a abordagem vanilla JS do projeto.

---

## 6. Alteracoes em Codigo Existente

### 6.1 Arquivos Criticos a Modificar

| Arquivo | Mudanca |
|---------|---------|
| `backend/models.py` | Refatorar em `models/` package (22 modelos). `__init__.py` re-exporta tudo para backward compat |
| `backend/schemas.py` | Refatorar em `schemas/` package. Mesma estrutura do models/ |
| `backend/main.py` | Registrar 8 novos routers + iniciar reminder_scheduler e pncp_sync no lifespan |
| `backend/config/base.py` | Adicionar configs: SMTP_*, PNCP_*, REMINDER_*, DOCUMENT_EXPIRY_* |
| `frontend/dashboard.html` | Expandir com novos widgets + nav dropdown + sino |
| Todos os HTML | Atualizar nav header para dropdown + sino |
| `frontend/js/config.js` | Sem mudancas necessarias (api client ja suporta tudo) |

### 6.2 Organizacao Models (refatorar em package)

```
backend/models/
    __init__.py          # from .usuario import Usuario; from .atestado import Atestado; ...
    base.py              # from database import Base
    usuario.py
    atestado.py
    analise.py           # + licitacao_id FK
    processing_job.py
    audit_log.py
    licitacao.py         # Licitacao, LicitacaoTag, LicitacaoHistorico
    lembrete.py          # Lembrete, Notificacao, PreferenciaNotificacao
    pncp.py              # PncpMonitoramento, PncpResultado
    documento.py         # DocumentoLicitacao, ChecklistEdital
    proposta.py          # Proposta, PropostaItem, BancoPreco
    contrato.py          # Contrato, Medicao, Aditivo
    concorrente.py       # Concorrente
```

### 6.3 Novas Dependencias

```
# requirements.txt - adicionar (por fase):
# F4 (M3 PNCP):
httpx>=0.25.0          # Cliente HTTP async para PNCP

# Nota: aiosmtplib e jinja2 NAO foram necessarios.
# Email usa smtplib (stdlib) com templates HTML inline.
```

### 6.4 Novas Variaveis de Ambiente

```env
# SMTP
SMTP_HOST=smtp.exemplo.com
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
SMTP_USE_TLS=true
EMAIL_FROM=LicitaFacil <noreply@licitafacil.com.br>
EMAIL_ENABLED=false

# PNCP
PNCP_SYNC_ENABLED=false
PNCP_SYNC_INTERVAL=3600

# Lembretes
REMINDER_CHECK_INTERVAL=60
DOCUMENT_EXPIRY_CHECK_INTERVAL=3600
DOCUMENT_EXPIRY_WARNING_DAYS=30
```

---

## 7. Migracao de Banco de Dados

### 7.1 Estrategia

Migracoes incrementais por modulo. Cada modulo cria suas proprias tabelas via Alembic.

A migracao de `analises.licitacao_id` deve:
1. Criar tabela `licitacoes` ANTES (por causa da FK)
2. Adicionar coluna como nullable
3. Criar FK constraint e index
4. NAO alterar registros existentes

### 7.2 Backward Compatibility

- `analises.licitacao_id` nullable: analises antigas continuam com NULL
- Todos os endpoints existentes permanecem inalterados
- Todas as paginas HTML existentes continuam funcionando
- Frontend `api` client em config.js nao precisa de mudancas
- Processing queue e realtime nao sao modificados

---

## 8. Ordem de Implementacao

| Fase | Modulo | Depende de | Status | Descricao |
|------|--------|------------|--------|-----------|
| **F1** | Infraestrutura + M1 | - | IMPLEMENTADO (2026-02-11) | models/ package, schemas/ package, migracao `i9d3l24762kk`, 10 endpoints, licitacoes.html. Plano: `01-modulo-licitacoes.md` |
| **F2** | M2: Calendario + Lembretes + Notificacoes | F1 | IMPLEMENTADO (2026-02-11) | 3 tabelas, 13 endpoints, EmailService, ReminderScheduler, calendario.html, sino global. Migracao `j0e4m35873ll`. Plano: `02-modulo-calendario-lembretes.md` |
| **F3** | M4: Gestao Documental | F1 | IMPLEMENTADO (2026-02-11) | 2 tabelas, 15 endpoints, DocumentExpiryChecker, documentos.html. Migracao `k1f5n46984mm`. Plano: `03-modulo-gestao-documental.md` |
| **F4** | M3: Monitoramento PNCP | F1, F2 | IMPLEMENTADO (2026-02-11) | 2 tabelas, 11 endpoints, PncpClient (httpx), PncpSyncService, PncpMapper, PncpMatcher, monitoramento.html (3 tabs). Migracao `l2g6o57095nn`. Plano: `04-modulo-pncp.md` |
| **F5** | M5: Propostas e Precos | F1 | PENDENTE | CRUD propostas + itens + banco precos |
| **F6** | M6: Contratos | F1 | PENDENTE | CRUD contratos + medicoes + aditivos |
| **F7** | M7: BI + Dashboard | F1-F6 | PENDENTE | Endpoints BI, Chart.js, dashboard expandido |

---

## 9. Decisoes Tecnicas

| Decisao | Escolha | Justificativa |
|---------|---------|---------------|
| Email | SMTP direto (smtplib sincrono) | Sem dependencia extra; pode usar asyncio.to_thread() se necessario |
| Graficos BI | Chart.js 4 | Leve, sem build step, CDN |
| HTTP client PNCP | httpx async | Moderno, async-nativo, retries built-in |
| Frontend | Manter Vanilla JS | Consistencia, sem migracao de framework |
| Models | Refatorar em package | 22 modelos nao cabem em 1 arquivo |
| Schemas | Refatorar em package | Mesma razao dos models |
| Tasks background | asyncio no lifespan | Padrao ja usado pelo processing_queue |
| Status enums | String constants | Padrao existente (ProcessingJob.status) |
| Tags | Tabela separada | Flexivel, queryable, melhor que JSON |
| Calendario | Renderizacao frontend pura | Grid mensal simples, sem lib externa |
| Migracoes | Incrementais por modulo | Evita criar tabelas especulativas |

---

## 10. Verificacao / Testes

### Para cada modulo implementado:
1. **Testes unitarios**: Repositorio (CRUD), Service (logica), Router (endpoints) - seguir padrao existente
2. **Testes de migracao**: `alembic upgrade head` e `alembic downgrade -1` sem erros
3. **Teste E2E manual**: Criar licitacao no frontend, mudar status, verificar historico
4. **CI**: `python -m pytest tests/ -x -q --ignore=tests/integration` deve continuar passando
5. **Backward compat**: Todas as funcionalidades existentes (atestados, analises, admin) devem continuar funcionando sem mudancas

### Historico de testes:
| Fase | Testes adicionados | Total acumulado |
|------|-------------------|-----------------|
| Base (pre-modulos) | 958 | 958 |
| F1 (M1: Licitacoes) | 94 (schemas: 23, repository: 22, router: 19, migration+other: 30) | 1052 |
| F2 (M2: Calendario) | 57 (schemas: 23, repository: 11, router lembretes: 11, router notificacoes: 12) | 1109 |
| F3 (M4: Gestao Documental) | 100 (schemas: 37, repository: 24, router: 31, document_checker: 8) | 1209 |
| F4 (M3: Monitoramento PNCP) | 140 (schemas: 31, repository: 24, router: 26, client: 9, mapper+matcher: 50) | 1349 |
