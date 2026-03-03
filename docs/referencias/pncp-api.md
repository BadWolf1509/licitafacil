# Referência da API do PNCP

**Portal Nacional de Contratações Públicas**
Última atualização: 2026-03-03

---

## Visão Geral

O PNCP expõe **duas APIs distintas** com propósitos diferentes:

| | API de Consulta | API de Integração |
|---|---|---|
| **URL base** | `https://pncp.gov.br/api/consulta/v1` | `https://pncp.gov.br/api/pncp/v1` |
| **Swagger** | `/api/consulta/swagger-ui/index.html` | `/api/pncp/swagger-ui/index.html` |
| **Autenticação** | Nenhuma — pública | JWT Bearer Token (validade 1h) |
| **Operações** | Somente leitura (GET) | CRUD completo |
| **Finalidade** | Transparência / dados abertos | Publicação por órgãos públicos |

O LicitaFácil usa **exclusivamente a API de Consulta** (leitura pública). A API de Integração não é relevante para o sistema.

---

## Autenticação (API de Consulta)

**Nenhuma.** Todos os endpoints de consulta são públicos e não exigem token, cadastro ou API key.

---

## Paginação

Todos os endpoints de listagem retornam:

```json
{
  "data": [ /* array de registros */ ],
  "totalRegistros": 4821,
  "totalPaginas": 97,
  "numeroPagina": 1,
  "paginasRestantes": 96,
  "empty": false
}
```

| Campo | Descrição |
|-------|-----------|
| `data` | Registros da página atual |
| `totalRegistros` | Total geral de registros no filtro |
| `totalPaginas` | Total de páginas |
| `numeroPagina` | Página atual |
| `paginasRestantes` | Páginas ainda não retornadas |
| `empty` | `true` quando `data` está vazio |

**Parâmetros de paginação:**
- `pagina` — número da página, começa em **1** (obrigatório)
- `tamanhoPagina` — registros por página; máximo **500**, padrão **500**

> **Recomendação prática:** usar `tamanhoPagina` entre **50 e 100**. O valor 500 pode causar timeouts em períodos com muitos registros. O `PncpClient` do projeto usa 50 por padrão.

---

## Endpoints da API de Consulta

### `GET /contratacoes/publicacao`

Contratações ordenadas por **data de publicação** no PNCP.

**URL completa:**
```
https://pncp.gov.br/api/consulta/v1/contratacoes/publicacao
```

| Parâmetro | Tipo | Obrigatório | Descrição |
|-----------|------|:-----------:|-----------|
| `dataInicial` | `YYYYMMDD` | **sim** | Data inicial do período de publicação |
| `dataFinal` | `YYYYMMDD` | **sim** | Data final do período de publicação |
| `pagina` | integer | **sim** | Número da página (começa em 1) |
| `tamanhoPagina` | integer | não | Registros por página (máx 500) |
| `codigoModalidadeContratacao` | integer | não | Ver tabela de modalidades |
| `uf` | string(2) | não | Sigla do estado: `SP`, `RJ`, `MG`... |
| `codigoModoDisputa` | integer | não | Ver tabela de modos de disputa |
| `cnpj` | string | não | CNPJ do órgão (somente números) |
| `codigoMunicipioIbge` | string | não | Código IBGE do município |
| `codigoUnidadeAdministrativa` | string | não | Código da unidade administrativa |

**Exemplo:**
```
GET /contratacoes/publicacao?dataInicial=20250201&dataFinal=20250228&codigoModalidadeContratacao=6&uf=SP&pagina=1&tamanhoPagina=50
```

---

### `GET /contratacoes/proposta`

Contratações com **recebimento de propostas em aberto** (encerramento futuro).

Mesmos parâmetros de `/contratacoes/publicacao`. O filtro `dataFinal` aplica-se à data de encerramento das propostas.

---

### `GET /contratacoes/atualizacao`

Contratações por **data de atualização** do registro no PNCP. Disponível desde fevereiro/2025.

Útil para **sincronização incremental**: retorna apenas registros inseridos ou modificados no período, reduzindo volume de dados processados.

---

### `GET /contratos`

Contratos firmados.

| Parâmetro | Tipo | Obrigatório | Descrição |
|-----------|------|:-----------:|-----------|
| `dataInicial` | `YYYYMMDD` | **sim** | |
| `dataFinal` | `YYYYMMDD` | **sim** | |
| `pagina` | integer | **sim** | |
| `tamanhoPagina` | integer | não | |
| `cnpjOrgao` | string | não | CNPJ do órgão |
| `codigoUnidadeAdministrativa` | string | não | |
| `idUsuario` | integer | não | ID do sistema de origem |

---

### `GET /contratos/atualizacao`

Contratos por data de atualização (incremental). Disponível desde fevereiro/2025.

---

### `GET /atas`

Atas de Registro de Preço.

| Parâmetro | Tipo | Obrigatório | Descrição |
|-----------|------|:-----------:|-----------|
| `dataInicial` | `YYYYMMDD` | **sim** | Data inicial de vigência |
| `dataFinal` | `YYYYMMDD` | **sim** | Data final de vigência |
| `pagina` | integer | **sim** | |
| `tamanhoPagina` | integer | não | |
| `cnpj` | string | não | CNPJ do órgão |
| `idUsuario` | integer | não | |

---

### `GET /pca/`

Plano de Contratações Anual (PCA).

| Parâmetro | Tipo | Obrigatório | Descrição |
|-----------|------|:-----------:|-----------|
| `anoPca` | integer | **sim** | Ano do PCA (ex: 2025) |
| `pagina` | integer | **sim** | |
| `tamanhoPagina` | integer | não | |
| `codigoClassificacaoSuperior` | integer | não | |

---

### Endpoints de detalhe (por órgão/sequencial)

```
GET /orgaos/{cnpj}/compras/{ano}/{sequencial}
GET /orgaos/{cnpj}/compras/{ano}/{sequencial}/itens
GET /orgaos/{cnpj}/compras/{ano}/{sequencial}/itens/{numeroItem}
GET /orgaos/{cnpj}/compras/{ano}/{sequencial}/itens/{numeroItem}/resultados
GET /orgaos/{cnpj}/compras/{ano}/{sequencial}/arquivos          ← download do edital
GET /orgaos/{cnpj}/contratos/{ano}/{sequencial}
GET /orgaos/{cnpj}/contratos/{ano}/{sequencial}/termos
```

Arquivos suportados: `.pdf`, `.txt`, `.rtf`, `.doc`, `.docx`, `.odt`, `.zip`, `.7z`, `.rar`. Tamanho máximo: **30 MB**.

---

## Estrutura de Resposta — Item de Contratação

Cada objeto dentro do array `data` retornado por `/contratacoes/publicacao`:

### Identificação

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `numeroControlePNCP` | string | Identificador único no PNCP (ex: `"00394502000144-0-000001/2025"`) |
| `numeroCompra` | string | Número da compra no órgão |
| `processo` | string | Número do processo administrativo |
| `sequencialCompra` | integer | Sequencial do PNCP |

### Objeto e Situação

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `objetoCompra` | string | Descrição do objeto da contratação |
| `situacaoCompraNome` | string | Situação atual (ex: `"Publicada"`, `"Homologada"`) |
| `modalidadeNome` | string | Nome da modalidade (ex: `"Pregão - Eletrônico"`) |
| `modoDisputaNome` | string | Modo de disputa (ex: `"Aberto"`) |
| `srp` | boolean | `true` = Sistema de Registro de Preços |
| `linkSistemaOrigem` | string | URL do edital no sistema do órgão |

### Datas

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `dataInclusao` | ISO 8601 | Data de inclusão no PNCP |
| `dataPublicacaoPncp` | ISO 8601 | Data de publicação |
| `dataAtualizacao` | ISO 8601 | Data da última atualização |
| `dataAberturaProposta` | ISO 8601 | Data/hora de abertura das propostas |
| `dataEncerramentoProposta` | ISO 8601 | Data/hora de encerramento |

### Valores

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `valorTotalEstimado` | decimal | Valor total estimado |
| `valorTotalHomologado` | decimal | Valor após homologação |

### Órgão

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `orgaoEntidade.cnpj` | string | CNPJ do órgão |
| `orgaoEntidade.razaoSocial` | string | Razão social |
| `orgaoEntidade.poderId` | string | `E`=Executivo, `L`=Legislativo, `J`=Judiciário |
| `orgaoEntidade.esferaId` | string | `F`=Federal, `E`=Estadual, `M`=Municipal, `D`=Distrital |

### Unidade Administrativa

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `unidadeOrgao.nomeUnidade` | string | Nome da unidade |
| `unidadeOrgao.codigoUnidade` | string | Código da unidade |
| `unidadeOrgao.ufSigla` | string | Sigla do estado (ex: `"SP"`) |
| `unidadeOrgao.ufNome` | string | Nome do estado |
| `unidadeOrgao.municipioNome` | string | Nome do município |
| `unidadeOrgao.codigoIbge` | string | Código IBGE do município |

### Amparo Legal

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `amparoLegal.codigo` | integer | Código do amparo |
| `amparoLegal.nome` | string | Citação legal (ex: `"Art. 75, inciso II"`) |
| `amparoLegal.descricao` | string | Descrição do amparo |

---

## Tabelas de Domínio

### Modalidades de Contratação (`codigoModalidadeContratacao`)

Endpoint de referência: `GET /api/pncp/v1/modalidades?statusAtivo=true`

| Código | Nome |
|--------|------|
| 1 | Leilão - Eletrônico |
| 2 | Diálogo Competitivo |
| **3** | **Concurso** |
| **4** | **Concorrência - Eletrônica** |
| **5** | **Concorrência - Presencial** |
| **6** | **Pregão - Eletrônico** |
| **7** | **Pregão - Presencial** |
| **8** | **Dispensa** |
| **9** | **Inexigibilidade** |
| 10 | Manifestação de Interesse |
| 11 | Pré-qualificação |
| 12 | Credenciamento |
| 13 | Leilão - Presencial |
| 14 | Inaplicabilidade da Licitação |
| 15 | Chamada Pública |
| 16 | Concorrência - Eletrônica Internacional |
| 17 | Concorrência - Presencial Internacional |
| 18 | Pregão - Eletrônico Internacional |
| 19 | Pregão - Presencial Internacional |

> **Em negrito:** modalidades usadas por padrão no `PncpSyncService` (`MODALIDADES_PADRAO = ["4","5","6","7","8"]`).

### Modos de Disputa (`codigoModoDisputa`)

| Código | Nome |
|--------|------|
| 1 | Aberto |
| 2 | Fechado |
| 3 | Aberto-Fechado |
| 4 | Dispensa Com Disputa |
| 5 | Não se aplica |
| 6 | Fechado-Aberto |

### Esfera do Órgão (`esferaId`)

| Valor | Significado |
|-------|-------------|
| `F` | Federal |
| `E` | Estadual |
| `M` | Municipal |
| `D` | Distrital |

### Poder do Órgão (`poderId`)

| Valor | Significado |
|-------|-------------|
| `E` | Executivo |
| `L` | Legislativo |
| `J` | Judiciário |

---

## Códigos HTTP

| Código | Situação |
|--------|----------|
| 200 | Sucesso |
| 204 | Sem conteúdo (período sem dados) |
| 400 | Parâmetros inválidos ou faltando |
| 422 | Dados semanticamente inválidos / período sem dados para a modalidade |
| 429 | Rate limit atingido |
| 500 | Erro interno (instabilidade da API) |
| 502/504 | Gateway timeout (a API pode ser lenta em picos) |

> **Nota:** A API retorna **422** quando não há registros para uma modalidade/período específico, não apenas para erros de validação. O `PncpClient` trata isso como resultado vazio.

---

## Estabilidade e Boas Práticas

A API do PNCP não tem SLA ou rate limit documentado publicamente. Na prática:

- **Erros esporádicos:** 500, 422, 504 ocorrem em momentos de instabilidade
- **Retry:** implementar backoff exponencial (máx 5 tentativas, intervalo de 3s)
- **Tamanho de página:** 50–100 registros é mais confiável que 500
- **Rate limit auto-imposto:** o `PncpClient` do projeto usa delay de **0,6s** entre requests (~1,67 req/s)

---

## Implementação no LicitaFácil

### `services/pncp/client.py` — `PncpClient`

Cliente HTTP async (`httpx`) que encapsula a API de consulta.

```python
# Busca uma página
await pncp_client.buscar_contratacoes(
    data_inicial="20250201",   # YYYYMMDD
    data_final="20250228",
    pagina=1,
    tamanho_pagina=50,         # max 50 configurado no projeto
    codigo_modalidade="6",     # opcional
    uf="SP",                   # opcional
    cnpj="12345678000190",     # opcional
)
# Retorna: {"data": [...], "totalRegistros": N, "totalPaginas": N, ...}

# Busca todas as páginas (até max_paginas)
await pncp_client.buscar_todas_paginas(
    data_inicial="20250201",
    data_final="20250228",
    max_paginas=5,
    codigo_modalidade="6",
)
# Retorna: lista flat de todos os itens
```

### `services/pncp/mapper.py` — `PncpMapper`

Converte os dados crus da API PNCP para os modelos internos do sistema.

| Método | Entrada | Saída |
|--------|---------|-------|
| `extrair_resultado(item, monitor_id, user_id)` | Item da API | Dict para `PncpResultado` |
| `resultado_para_licitacao(resultado)` | `PncpResultado` | Dict para `Licitacao` |
| `item_pncp_para_licitacao(item)` | Item cru da API | Dict para `Licitacao` |

**Mapeamento de campos relevantes:**

| Campo PNCP | Campo interno |
|------------|--------------|
| `numeroControlePNCP` | `numero_controle_pncp` |
| `objetoCompra` | `objeto_compra` / `objeto` |
| `orgaoEntidade.razaoSocial` | `orgao_razao_social` / `orgao` |
| `modalidadeNome` | `modalidade_nome` / `modalidade` |
| `unidadeOrgao.ufSigla` | `uf` |
| `unidadeOrgao.municipioNome` | `municipio` |
| `valorTotalEstimado` | `valor_estimado` |
| `dataAberturaProposta` | `data_abertura` |
| `dataEncerramentoProposta` | `data_encerramento` |
| `linkSistemaOrigem` | `link_sistema_origem` |

### `services/pncp/sync_service.py` — `PncpSyncService`

Worker background que sincroniza monitores ativos periodicamente.

**Fluxo:**
1. Busca todos os monitores ativos no banco
2. Para cada monitor: itera por `modalidades` × `ufs` configuradas
3. Modalidades padrão (quando monitor não especifica): `["4","5","6","7","8"]`
4. Filtra resultados com `PncpMatcher` (palavras-chave, valor, etc.)
5. Deduplica via `numero_controle_pncp` + `user_id`
6. Salva novos `PncpResultado` e dispara notificação

**Variáveis de ambiente:**

| Variável | Padrão | Descrição |
|----------|--------|-----------|
| `PNCP_API_BASE_URL` | `https://pncp.gov.br/api/consulta/v1` | URL base |
| `PNCP_TIMEOUT_SECONDS` | `30` | Timeout HTTP |
| `PNCP_SYNC_ENABLED` | `true` | Liga/desliga o worker |
| `PNCP_SYNC_INTERVAL` | `3600` | Intervalo entre ciclos (segundos) |
| `PNCP_SYNC_LOOKBACK_DAYS` | `7` | Janela de busca retroativa (dias) |

### `routers/pncp.py` — Endpoints da API interna

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| `GET` | `/pncp/monitoramentos` | Listar monitores do usuário |
| `POST` | `/pncp/monitoramentos` | Criar monitor |
| `GET` | `/pncp/monitoramentos/{id}` | Detalhe do monitor |
| `PUT` | `/pncp/monitoramentos/{id}` | Atualizar monitor |
| `DELETE` | `/pncp/monitoramentos/{id}` | Excluir monitor |
| `PATCH` | `/pncp/monitoramentos/{id}/toggle` | Ativar/desativar |
| `GET` | `/pncp/resultados` | Listar resultados |
| `PATCH` | `/pncp/resultados/{id}/status` | Atualizar status do resultado |
| `POST` | `/pncp/resultados/{id}/importar` | Importar resultado como Licitação |
| `GET` | `/pncp/busca` | Proxy de busca direta no PNCP |
| `POST` | `/pncp/gerenciar` | Importar item da busca direta como Licitação + lembrete |
| `POST` | `/pncp/sincronizar` | Disparar sincronização manual |

### `GET /pncp/busca` — parâmetros

| Parâmetro | Tipo | Descrição |
|-----------|------|-----------|
| `data_inicial` | `YYYYMMDD` | Padrão: 7 dias atrás |
| `data_final` | `YYYYMMDD` | Padrão: hoje |
| `codigo_modalidade` | string | Código da modalidade (opcional) |
| `uf` | string | Sigla da UF (opcional) |
| `valor_minimo` | float | Valor mínimo estimado (opcional) |
| `valor_maximo` | float | Valor máximo estimado (opcional) |

Quando `codigo_modalidade` não informado, busca em todas as `MODALIDADES_PADRAO` e deduplica por `numeroControlePNCP`.

---

## ⚠️ Bug Conhecido: Códigos de Modalidade em `encontrar.html`

O filtro de modalidade no frontend (`frontend/encontrar.html`) contém **mapeamentos incorretos**:

| Label no filtro | Código usado | Código correto |
|-----------------|-------------|----------------|
| Pregão Eletrônico | `6` | ✅ correto |
| Pregão **Presencial** | `8` | ❌ `8` = Dispensa; correto = **`7`** |
| Concorrência (genérica) | `1` | ❌ `1` = Leilão Eletrônico; não existe código genérico |
| Concorrência Eletrônica | `4` | ✅ correto |
| **Concurso** | `5` | ❌ `5` = Concorrência Presencial; correto = **`3`** |
| **Dispensa** | `3` | ❌ `3` = Concurso; correto = **`8`** |
| **Inexigibilidade** | `7` | ❌ `7` = Pregão Presencial; correto = **`9`** |
| Leilão | `9` | ❌ `9` = Inexigibilidade; correto = **`1`** (eletrônico) ou **`13`** (presencial) |

**Arquivo:** `frontend/encontrar.html`, linhas 104–117.

---

## Documentação Oficial

| Recurso | URL |
|---------|-----|
| Swagger — API de Consulta | https://pncp.gov.br/api/consulta/swagger-ui/index.html |
| Swagger — API de Integração | https://www.pncp.gov.br/api/pncp/swagger-ui/index.html |
| Manual de Integração v2.3.9 (jan/2026) | https://www.gov.br/pncp/pt-br/central-de-conteudo/manuais/manual-de-integracao-pncp |
| Dados Abertos | https://www.gov.br/pncp/pt-br/acesso-a-informacao/dados-abertos |
| Portal PNCP | https://pncp.gov.br/app/ |
