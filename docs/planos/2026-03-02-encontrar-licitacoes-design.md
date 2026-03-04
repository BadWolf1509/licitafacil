# Design: Encontrar Licitações (Redesign M3 — Nova Página Unificada)

> **Data**: 2026-03-02
> **Autor**: Sessão de brainstorming assistida por Claude
> **Status**: APROVADO — pronto para implementação
> **Referência arquitetural**: `00-arquitetural-geral.md`

---

## 1. Contexto e Motivação

### 1.1 Situação atual (M3 — Monitoramento PNCP)

O módulo M3 (`monitoramento.html`) entrega a funcionalidade em 3 tabs isoladas:
- **Monitores**: Salvar buscas por palavras-chave + UF + faixa de valor
- **Resultados**: Lista de resultados armazenados no DB, com status manual
- **Busca Direta**: Consulta pontual ao PNCP por datas + modalidade

Problemas identificados:
1. UX fragmentada — o usuário precisa navegar entre 3 tabs para um fluxo que deveria ser contínuo
2. "Busca Direta" exige preenchimento de datas manualmente (não é um fluxo de descoberta)
3. Importar uma licitação **não cria lembrete** no calendário — o usuário precisa fazer isso manualmente
4. Interface não usa os filtros ricos que os líderes de mercado (ConLicitação, Licitei) oferecem

### 1.2 Análise competitiva

| Recurso | ConLicitação | Licitei | LicitaGov | LicitaFácil atual |
|---------|-------------|---------|-----------|-------------------|
| Barra de busca proeminente | Sim | Sim ("Google de licitações") | Sim | Não |
| Filtros ricos (UF, modalidade, valor, período) | Sim | Sim | Sim | Parcial |
| Feed unificado de resultados | Sim | Sim | Sim | Não (tab separada) |
| Integração com calendário | Não | Não | Não | **Oportunidade** |
| Card com badge "Novo" | Sim | Sim | Sim | Não |
| Salvamento de buscas como alertas | Sim | Sim | Sim | Sim (M3) |

**Diferencial único do LicitaFácil**: integração direta com o calendário — ao gerenciar, o lembrete da abertura da disputa é criado automaticamente.

### 1.3 Premissas

- **PNCP é a única fonte**: todos os portais licitatórios brasileiros são obrigados a publicar no PNCP. Não há necessidade de integrar outros portais nesta versão.
- **Sem IA nesta versão**: análise de editais e sugestão de preços ficam para fases posteriores.
- **Sem novas tabelas**: reutiliza as tabelas `pncp_monitoramentos`, `pncp_resultados`, `licitacoes` e `lembretes` já existentes.
- **monitoramento.html é deprecado**: redirecionamento para `encontrar.html`.

---

## 2. Solução Escolhida: Nova Página Unificada

### Abordagens consideradas

| Abordagem | Descrição | Decisão |
|-----------|-----------|---------|
| A — Descoberta Integrada | Reformular monitoramento.html mantendo estrutura de tabs, adicionar filtros ricos e endpoint de gerenciamento | Descartada |
| **B — Nova Página Unificada** | Nova página `encontrar.html` com sidebar + área principal, sem tabs de navegação, monitores como alertas salvos | **ESCOLHIDA** |
| C — Evolução Incremental | Adicionar apenas integração calendário e novos filtros ao M3 existente | Descartada |

**Justificativa da escolha B**: Permite UX superior sem restrições estruturais do layout de tabs atual. Alinhado com o padrão dos líderes de mercado (barra de busca proeminente + feed contínuo). A depreciação do monitoramento.html é gerenciada com redirecionamento.

---

## 3. Arquitetura

### 3.1 Novos arquivos

```
frontend/
  encontrar.html         # Nova página principal
  js/encontrar.js        # Lógica da nova página (ES6 modules)
  css/encontrar.css      # Estilos da nova página
```

### 3.2 Arquivos modificados

```
frontend/monitoramento.html          # Adicionar <meta http-equiv="refresh"> redirect
frontend/[todos os *.html]           # Atualizar link "Monitoramento" para "Encontrar"
backend/routers/pncp.py              # Adicionar endpoint POST /pncp/gerenciar
backend/schemas/pncp.py              # Adicionar schema GerenciarRequest / GerenciarResponse
```

### 3.3 Sem alterações em

- Tabelas de banco de dados (zero migrações)
- Serviços PNCP existentes (pncp_client, pncp_sync_service, pncp_mapper, pncp_matcher)
- Repositórios pncp_repository, licitacao_repository, lembrete_repository
- Routers licitacoes.py, lembretes.py (reutilizados internamente pelo novo endpoint)
- Testes existentes do M3

---

## 4. Layout e UX

### 4.1 Estrutura geral

```
┌─────────────────────────────────────────────────────────────────┐
│  HEADER: Logo  |  Dashboard  Licitações  Encontrar ✦  Docs  ... │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  🔍  Buscar por objeto, palavras-chave...   [Buscar]            │
│  ─────────────────────────────────────────────────────────────  │
│  [UF: SP,RJ ×]  [Modalidade: Pregão ×]  [+ Filtros]  [Limpar] │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Tabs: [ Busca (1.247 resultados) ]  [ Meus Alertas (3 novos) ] │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Ordenar: Abertura ▾    Visualizar: [▦ Grade] [☰ Lista]        │
│                                                                 │
│  ┌──────────────────────┐  ┌──────────────────────┐            │
│  │ PREGÃO  [SP] ● Novo  │  │ CONCORRÊNCIA  [MG]   │            │
│  │ Contratação de TI... │  │ Obras de infraestr...│            │
│  │ Pref. São Paulo      │  │ Governo do Estado MG │            │
│  │ R$ 250.000,00        │  │ R$ 1.200.000,00      │            │
│  │ ⏱ Abertura: 15/03    │  │ ⏱ Abertura: 22/03    │            │
│  │ [Edital ↗] [→ Gerenc]│  │ [Edital ↗] [→ Gerenc]│            │
│  └──────────────────────┘  └──────────────────────┘            │
│                                                                 │
│  ← 1  2  3  ...  63  →                                         │
└─────────────────────────────────────────────────────────────────┘
```

### 4.2 Filtros disponíveis

| Filtro | Tipo | Valores |
|--------|------|---------|
| Palavras-chave | Text input | Livre (debounce 300ms) |
| UF | Multi-select chips | 27 UFs brasileiras |
| Modalidade | Multi-select chips | Pregão Eletrônico, Concorrência, Dispensa, Inexigibilidade, Diálogo Competitivo, Leilão, Credenciamento |
| Valor estimado | Range (mín – máx) | Formato monetário |
| Período de abertura | Date range (de – até) | Default: próximos 30 dias |
| Esfera | Multi-select | Federal, Estadual, Municipal |

**Filtros rápidos** (chips no topo, visíveis sem expandir):
- UF, Modalidade

**Filtros avançados** (collapse `+ Mais filtros`):
- Valor, Período, Esfera

### 4.3 Card de licitação

```
┌──────────────────────────────────────────────────────────────┐
│  [PREGÃO ELETRÔNICO]  [SP]  ● Novo                           │
│                                                              │
│  Contratação de serviços de tecnologia da informação para    │
│  suporte e manutenção de sistemas...                         │
│                                                              │
│  Prefeitura de São Paulo — CNPJ 46.395.000/0001-39           │
│                                                              │
│  💰 R$ 250.000,00 estimado                                   │
│  ⏱ Abertura: 15/03/2026 10h00    📅 Publicado: 28/02/2026   │
│                                                              │
│  [Ver Edital ↗]                         [→ Gerenciar]        │
└──────────────────────────────────────────────────────────────┘
```

**Badge "● Novo"**: aparece em licitações publicadas nas últimas 48h.

**Modo lista** (alternativo ao grade): linha compacta com objeto, órgão, UF, valor e data de abertura. Útil para visualizar muitos itens.

### 4.4 Tab "Meus Alertas"

```
┌─────────────────────────────────────────────────────────────────┐
│  Meus Alertas                                  [+ Novo Alerta]  │
├─────────────────────────────────────────────────────────────────┤
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  🔔 TI — São Paulo               Última sync: há 2h       │ │
│  │  "tecnologia informação" | SP | R$ 50k–R$ 500k            │  │
│  │  ✦ 12 novos resultados desde a última visualização        │  │
│  │  [Ver resultados]  [✏ Editar]  [⏸ Pausar]  [🗑 Remover]  │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  🔔 Obras — Rio de Janeiro       Última sync: há 45min    │ │
│  │  "pavimentação drenagem" | RJ | qualquer valor            │  │
│  │  ✦ 3 novos resultados                                     │  │
│  │  [Ver resultados]  [✏ Editar]  [⏸ Pausar]  [🗑 Remover]  │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

Ao clicar "Ver resultados": aplica os critérios do alerta na tab "Busca" e filtra pelos resultados já armazenados.

### 4.5 Modal "Gerenciar Licitação" — fluxo principal

```
┌──────────────────────────────────────────────────────────────┐
│  → Gerenciar Licitação                                  [✕]  │
│  ────────────────────────────────────────────────────────    │
│  Objeto: Contratação de serviços de tecnologia da infor...   │
│  Órgão:  Prefeitura de São Paulo                             │
│  Valor:  R$ 250.000,00                                       │
│  PNCP:   01.001.000/0001-01-0001234/2026-1                   │
│                                                              │
│  ────────────────────────────────────────────────────────    │
│  Status inicial: [Em análise                          ▾]     │
│                                                              │
│  🗓 Criar lembrete no Calendário                             │
│  ────────────────────────────────────────────────────────    │
│  ✅ Abertura da disputa: 15/03/2026 às 10h00                 │
│     Avisar com: [24 horas ▾] de antecedência                 │
│                                                              │
│  Observações: ________________________________________       │
│                                                              │
│  [Cancelar]                              [→ Gerenciar]       │
└──────────────────────────────────────────────────────────────┘
```

**Comportamento após confirmar:**
1. Chama `POST /api/v1/pncp/gerenciar`
2. Backend cria Licitacao (M1) + Lembrete (M2) atomicamente
3. Toast: `"Licitação adicionada. Lembrete criado para 14/03 às 10h00"`
4. Botão "Gerenciar" do card some / vira "Ver em Licitações →"

---

## 5. Backend

### 5.1 Novo endpoint: `POST /api/v1/pncp/gerenciar`

**Responsabilidade**: Recebe os dados de um item PNCP e atomicamente:
1. Cria o registro `Licitacao` (M1), se não existir (checa `numero_controle_pncp`)
2. Extrai `dataAberturaProposta` para criar `Lembrete` com data = abertura − antecedência_horas (M2)
3. Se veio de um `pncp_resultado`, atualiza `status = "importado"` e seta `licitacao_id`
4. Retorna os IDs criados + mensagem amigável

**Schema de request:**
```python
class GerenciarRequest(BaseModel):
    # Dados do item PNCP
    numero_controle_pncp: str
    orgao_razao_social: str
    objeto_compra: str
    modalidade_nome: str | None = None
    uf: str | None = None
    municipio: str | None = None
    valor_estimado: float | None = None
    data_abertura: datetime | None = None
    link_sistema_origem: str | None = None
    dados_completos: dict | None = None  # payload PNCP completo

    # Configurações de gerenciamento
    status_inicial: str = "em_analise"
    observacoes: str | None = None
    criar_lembrete: bool = True
    antecedencia_horas: int = 24

    # Referência ao resultado armazenado (opcional)
    pncp_resultado_id: int | None = None
```

**Schema de response:**
```python
class GerenciarResponse(BaseModel):
    licitacao_id: int
    lembrete_id: int | None  # None se criar_lembrete=False ou data_abertura=None
    licitacao_ja_existia: bool
    mensagem: str
```

**Regras de negócio:**
- Se `numero_controle_pncp` já existe em `licitacoes` para o usuário → retorna a licitação existente com `licitacao_ja_existia=True`
- Lembrete criado com `tipo="abertura_licitacao"` e `data_lembrete = data_abertura - antecedencia_horas`
- Se `data_abertura` é None → `criar_lembrete` é ignorado (sem data para calcular)
- Toda a operação em um único try/except com rollback

### 5.2 Busca enriquecida: `GET /api/v1/pncp/busca`

O endpoint existente é estendido com novos parâmetros (backwards-compatible):

```
GET /api/v1/pncp/busca
  ?keywords=tecnologia informação
  &ufs=SP,RJ                          # NOVO: múltiplas UFs
  &modalidades=6,8                    # NOVO: códigos numéricos PNCP
  &valor_minimo=50000                 # NOVO: filtro de valor
  &valor_maximo=500000                # NOVO: filtro de valor
  &data_abertura_ini=20260301         # Existente (renomeado internamente)
  &data_abertura_fim=20260331         # Existente
  &page=1
  &page_size=20
  &ordenar_por=dataAberturaProposta   # NOVO: campo de ordenação
  &ordem=asc                          # NOVO: asc/desc
```

**Comportamento**: o endpoint proxy ao PNCP aplica os filtros disponíveis na API PNCP. Filtros não suportados pela API PNCP (valor_minimo/maximo) são aplicados **client-side** após receber os resultados — mesmo padrão do `PncpMatcher` já implementado.

---

## 6. Design Visual

### 6.1 Paleta de cores

Inspirada no ConLicitação:

| Token | Cor | Uso |
|-------|-----|-----|
| `--cor-primaria` | `#0D875E` | Botões de ação, links, badges de alerta |
| `--cor-primaria-hover` | `#0a6b4a` | Hover de botões |
| `--cor-badge-novo` | `#2563EB` | Badge "● Novo" |
| `--cor-card-bg` | `#FFFFFF` | Fundo dos cards |
| `--cor-card-border` | `#E5E7EB` | Borda dos cards |
| `--cor-filtro-chip` | `#F3F4F6` | Chips de filtros aplicados |

### 6.2 Componentes

- **Cards**: `border-radius: 12px`, sombra suave (`box-shadow: 0 1px 3px rgba(0,0,0,0.1)`)
- **Botão primário**: verde `#0D875E`, texto branco, `border-radius: 6px`
- **Botão secundário**: borda cinza, fundo transparente
- **Chips de filtro**: fundo `#F3F4F6`, badge com ícone `×` para remover
- **Badge modalidade**: fundo colorido por tipo (Pregão=azul, Concorrência=roxo, Dispensa=laranja)
- **Badge "Novo"**: ponto azul `#2563EB` + texto pequeno

### 6.3 Responsividade

- Desktop (≥1024px): filtros como barra horizontal sobre os resultados
- Tablet (768–1023px): filtros em 2 linhas, grade 2 colunas
- Mobile (<768px): filtros em bottom sheet, lista ao invés de grade

---

## 7. Fluxo de navegação

### 7.1 Redirecionamento do M3

```html
<!-- monitoramento.html — adicionar no <head> -->
<meta http-equiv="refresh" content="0; url=encontrar.html">
<script>window.location.replace('encontrar.html');</script>
```

### 7.2 Atualização da navegação global

Todos os `*.html` têm link "Monitoramento PNCP" que deve ser atualizado para "Encontrar Licitações" apontando para `encontrar.html`.

### 7.3 Fluxo completo do usuário

```
1. Usuário acessa "Encontrar Licitações"
2. Digita palavras-chave na barra de busca
3. Seleciona filtros (UF, modalidade)
4. Clica "Buscar" → cards aparecem
5. Encontra oportunidade interessante
6. Clica "→ Gerenciar"
7. Modal confirma: título, órgão, lembrete pré-configurado
8. Usuário confirma
9. Licitação aparece em "Gestão de Licitações" (M1)
10. Lembrete aparece em "Calendário" (M2)
11. Notificação in-app na data configurada (M2)
```

---

## 8. Integração com módulos existentes

| Módulo | Integração |
|--------|------------|
| M1 — Licitações | `POST /pncp/gerenciar` cria registro em `licitacoes` |
| M2 — Lembretes/Calendário | `POST /pncp/gerenciar` cria lembrete tipo `"abertura_licitacao"` |
| M3 — PNCP (existente) | Dados de monitores aparecem na tab "Meus Alertas"; `pncp_resultados` são marcados como `"importado"` |
| M4 — Documentos | Sem integração direta nesta versão |

---

## 9. Testes esperados

### 9.1 Backend

| Teste | Tipo | Arquivo |
|-------|------|---------|
| `test_gerenciar_cria_licitacao_e_lembrete` | Unitário | `tests/test_pncp_router.py` |
| `test_gerenciar_licitacao_ja_existia` | Unitário | `tests/test_pncp_router.py` |
| `test_gerenciar_sem_data_abertura_nao_cria_lembrete` | Unitário | `tests/test_pncp_router.py` |
| `test_busca_filtros_uf_multiplos` | Unitário | `tests/test_pncp_router.py` |
| `test_gerenciar_schema_request` | Schema | `tests/test_pncp_schemas.py` |
| `test_gerenciar_schema_response` | Schema | `tests/test_pncp_schemas.py` |

### 9.2 Frontend (teste manual E2E)

- [ ] Busca por palavras-chave retorna resultados do PNCP
- [ ] Filtros de UF e modalidade funcionam individualmente e combinados
- [ ] Badge "Novo" aparece em licitações das últimas 48h
- [ ] Modal "Gerenciar" preenche dados corretamente
- [ ] Após gerenciar: licitação aparece em `licitacoes.html`
- [ ] Após gerenciar: lembrete aparece em `calendario.html`
- [ ] Tab "Meus Alertas" lista monitores do M3 existente
- [ ] Redirect de `monitoramento.html` → `encontrar.html` funciona
- [ ] Responsivo em mobile

---

## 10. Decisões técnicas

| Decisão | Escolha | Justificativa |
|---------|---------|---------------|
| Nova página vs. reformular M3 | Nova página `encontrar.html` | Sem restrições estruturais; alinhado ao mercado |
| Fonte de dados | Apenas PNCP | Obrigatoriedade legal; cobre todos os portais brasileiros |
| IA nesta versão | Não | Simplicidade; entrega de valor imediata sem overhead |
| Novas tabelas | Zero | Reutiliza estrutura do M3 + M1 + M2 |
| Filtro de valor | Client-side (PncpMatcher) | PNCP API não suporta filtro por valor diretamente |
| Endpoint gerenciar | Novo `POST /pncp/gerenciar` | Atomicidade; separa responsabilidades |
| Cor primária | `#0D875E` (verde) | Alinhado ao ConLicitação; credibilidade no setor |
| Templates de busca salva | Monitores existentes (M3) | Sem duplicação de dados ou lógica |

---

## 11. O que fica fora desta versão (backlog)

- IA para análise de editais (ConLicitação, LicitaIA)
- Alertas via WhatsApp ou Slack
- Inteligência competitiva (CNPJ de concorrentes)
- App mobile
- Robôs de lances automáticos
- Filtro por CNPJ do órgão
- Histórico de buscas
