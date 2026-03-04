# Encontrar Licitações — Implementation Plan

> **Status: IMPLEMENTADO — CONCLUÍDO (2026-03-03)**
> Tasks 1–7 + busca dual-endpoint (`/proposta` + `/publicacao`) implementados.

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Substituir `monitoramento.html` por uma nova página `encontrar.html` com busca rica no PNCP, cards de licitação, e fluxo "Gerenciar" que cria Licitação (M1) + Lembrete no calendário da aplicação (M2) atomicamente.

**Architecture:** Nova página HTML+JS+CSS independente. Reutiliza endpoints e tabelas existentes do M3 (pncp_monitoramentos, pncp_resultados), M1 (licitacoes) e M2 (lembretes). Adiciona endpoint `POST /pncp/gerenciar` que orquestra a criação atômica. `monitoramento.html` vira redirect.

**Tech Stack:** Python/FastAPI (backend), Vanilla JS ES module (frontend), SQLAlchemy (ORM), pytest/MagicMock (testes)

---

## Task 1: Backend — Schemas + Mensagens

**Files:**
- Modify: `backend/schemas/pncp.py`
- Modify: `backend/config/messages.py`
- Modify: `backend/tests/test_schemas_pncp.py`

### Step 1: Escrever testes dos novos schemas (failing)

Abra `backend/tests/test_schemas_pncp.py` e adicione ao final do arquivo:

```python
# ==================== GerenciarRequest ====================


class TestGerenciarRequest:
    from schemas.pncp import GerenciarRequest  # noqa: E402 - import inside class for clarity

    def test_valid_minimal(self):
        from schemas.pncp import GerenciarRequest
        data = GerenciarRequest(
            numero_controle_pncp="01.001.000/0001-01-0001234/2026-1",
            orgao_razao_social="Prefeitura de São Paulo",
            objeto_compra="Contratação de TI",
        )
        assert data.numero_controle_pncp == "01.001.000/0001-01-0001234/2026-1"
        assert data.criar_lembrete is True
        assert data.antecedencia_horas == 24
        assert data.status_inicial == "em_analise"

    def test_valid_full(self):
        from datetime import datetime
        from decimal import Decimal
        from schemas.pncp import GerenciarRequest
        data = GerenciarRequest(
            numero_controle_pncp="01.001.000/0001-01-0001234/2026-1",
            orgao_razao_social="Prefeitura de São Paulo",
            objeto_compra="Contratação de TI",
            modalidade_nome="Pregão Eletrônico",
            uf="SP",
            municipio="São Paulo",
            valor_estimado=Decimal("250000.00"),
            data_abertura=datetime(2026, 3, 15, 10, 0),
            link_sistema_origem="https://pncp.gov.br/test",
            status_inicial="identificada",
            observacoes="Observação teste",
            criar_lembrete=False,
            antecedencia_horas=48,
            pncp_resultado_id=5,
        )
        assert data.criar_lembrete is False
        assert data.antecedencia_horas == 48
        assert data.pncp_resultado_id == 5

    def test_missing_numero_controle_raises(self):
        from pydantic import ValidationError
        from schemas.pncp import GerenciarRequest
        with pytest.raises(ValidationError):
            GerenciarRequest(
                orgao_razao_social="Prefeitura",
                objeto_compra="TI",
            )

    def test_antecedencia_negativa_raises(self):
        from pydantic import ValidationError
        from schemas.pncp import GerenciarRequest
        with pytest.raises(ValidationError):
            GerenciarRequest(
                numero_controle_pncp="1234",
                orgao_razao_social="Prefeitura",
                objeto_compra="TI",
                antecedencia_horas=-1,
            )


# ==================== GerenciarResponse ====================


class TestGerenciarResponse:

    def test_valid_with_lembrete(self):
        from schemas.pncp import GerenciarResponse
        data = GerenciarResponse(
            licitacao_id=42,
            lembrete_id=7,
            licitacao_ja_existia=False,
            mensagem="Licitação criada com sucesso.",
        )
        assert data.licitacao_id == 42
        assert data.lembrete_id == 7
        assert data.licitacao_ja_existia is False

    def test_valid_sem_lembrete(self):
        from schemas.pncp import GerenciarResponse
        data = GerenciarResponse(
            licitacao_id=42,
            lembrete_id=None,
            licitacao_ja_existia=True,
            mensagem="Licitação já existia.",
        )
        assert data.lembrete_id is None
        assert data.licitacao_ja_existia is True
```

### Step 2: Confirmar que testes falham

```bash
cd d:/Analise\ de\ Capacitade\ Técnica/licitafacil/backend
python -m pytest tests/test_schemas_pncp.py::TestGerenciarRequest tests/test_schemas_pncp.py::TestGerenciarResponse -v
```
Esperado: `ImportError: cannot import name 'GerenciarRequest' from 'schemas.pncp'`

### Step 3: Adicionar schemas em `backend/schemas/pncp.py`

Adicione ao final do arquivo (após `PncpImportarRequest`):

```python
# ==================== Gerenciar ====================


class GerenciarRequest(BaseModel):
    """Payload para gerenciar uma licitação a partir de um item PNCP."""

    # Dados do item PNCP
    numero_controle_pncp: str = Field(..., min_length=1)
    orgao_razao_social: str
    objeto_compra: str
    modalidade_nome: Optional[str] = None
    uf: Optional[str] = None
    municipio: Optional[str] = None
    valor_estimado: Optional[Decimal] = None
    data_abertura: Optional[datetime] = None
    link_sistema_origem: Optional[str] = None
    dados_completos: Optional[dict] = None

    # Configurações de gerenciamento
    status_inicial: str = "em_analise"
    observacoes: Optional[str] = None
    criar_lembrete: bool = True
    antecedencia_horas: int = Field(default=24, ge=0)

    # Referência ao resultado armazenado (opcional)
    pncp_resultado_id: Optional[int] = None


class GerenciarResponse(BaseModel):
    licitacao_id: int
    lembrete_id: Optional[int] = None
    licitacao_ja_existia: bool
    mensagem: str
```

### Step 4: Adicionar mensagens em `backend/config/messages.py`

Adicione ao final da classe `Messages`, após `PNCP_BUSCA_ERRO`:

```python
    PNCP_GERENCIAR_CRIADO = "Licitação criada e lembrete agendado."
    PNCP_GERENCIAR_JA_EXISTIA = "Licitação já existia no sistema."
    PNCP_GERENCIAR_SEM_DATA = "Licitação criada. Sem data de abertura para criar lembrete."
```

### Step 5: Rodar testes novamente — devem passar

```bash
python -m pytest tests/test_schemas_pncp.py::TestGerenciarRequest tests/test_schemas_pncp.py::TestGerenciarResponse -v
```
Esperado: todos passando.

### Step 6: Rodar suite completa para verificar regressão

```bash
python -m pytest tests/ -x -q --ignore=tests/integration
```
Esperado: todos passando.

### Step 7: Commit

```bash
cd d:/Analise\ de\ Capacitade\ Técnica/licitafacil
git add backend/schemas/pncp.py backend/config/messages.py backend/tests/test_schemas_pncp.py
git commit -m "feat(pncp): add GerenciarRequest/Response schemas and messages"
```

---

## Task 2: Backend — Endpoint `POST /pncp/gerenciar`

**Files:**
- Modify: `backend/routers/pncp.py`
- Modify: `backend/tests/test_pncp_router.py`

**Contexto:** O endpoint cria atomicamente uma `Licitacao` (M1) e um `Lembrete` (M2) a partir de dados de um item PNCP. Se já existe licitação com mesmo `numero_controle_pncp` para o usuário, retorna a existente com `licitacao_ja_existia=True`. Se veio de um `pncp_resultado_id`, marca o resultado como `"importado"`.

### Step 1: Escrever testes do endpoint (failing)

Adicione ao final de `backend/tests/test_pncp_router.py`:

```python
# ===========================================================================
# POST /pncp/gerenciar
# ===========================================================================


class TestGerenciar:
    """Testa o endpoint POST /pncp/gerenciar."""

    BASE_PAYLOAD = {
        "numero_controle_pncp": "01.001.000/0001-01-0001/2026-1",
        "orgao_razao_social": "Prefeitura de São Paulo",
        "objeto_compra": "Contratação de TI",
        "modalidade_nome": "Pregão Eletrônico",
        "uf": "SP",
        "valor_estimado": 250000.00,
        "data_abertura": "2026-03-15T10:00:00",
        "criar_lembrete": True,
        "antecedencia_horas": 24,
    }

    @patch("routers.pncp.log_action")
    @patch("routers.pncp.lembrete_repository")
    @patch("routers.pncp.licitacao_repository")
    def test_gerenciar_cria_licitacao_e_lembrete(
        self, mock_lic_repo, mock_lem_repo, mock_log, client, mock_db
    ):
        """Deve criar licitação nova + lembrete e retornar IDs."""
        # Sem duplicata
        mock_lic_repo.get_by_numero_controle_pncp.return_value = None

        # Licitação criada
        mock_licitacao = MagicMock()
        mock_licitacao.id = 42
        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()
        mock_db.refresh = MagicMock(side_effect=lambda obj: setattr(obj, 'id', 42) if hasattr(obj, 'numero') else setattr(obj, 'id', 7))

        response = client.post("/pncp/gerenciar", json=self.BASE_PAYLOAD)
        assert response.status_code == 201
        data = response.json()
        assert data["licitacao_ja_existia"] is False
        assert "licitacao_id" in data

    @patch("routers.pncp.log_action")
    @patch("routers.pncp.licitacao_repository")
    def test_gerenciar_licitacao_ja_existia(
        self, mock_lic_repo, mock_log, client
    ):
        """Se licitação já existe, retorna existente com licitacao_ja_existia=True."""
        mock_existente = MagicMock()
        mock_existente.id = 99
        mock_lic_repo.get_by_numero_controle_pncp.return_value = mock_existente

        response = client.post("/pncp/gerenciar", json=self.BASE_PAYLOAD)
        assert response.status_code == 200
        data = response.json()
        assert data["licitacao_ja_existia"] is True
        assert data["licitacao_id"] == 99

    @patch("routers.pncp.log_action")
    @patch("routers.pncp.licitacao_repository")
    def test_gerenciar_sem_data_abertura_nao_cria_lembrete(
        self, mock_lic_repo, mock_log, client, mock_db
    ):
        """Se data_abertura ausente, cria licitação mas não cria lembrete."""
        mock_lic_repo.get_by_numero_controle_pncp.return_value = None
        payload = {**self.BASE_PAYLOAD, "data_abertura": None, "criar_lembrete": True}
        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()
        mock_db.refresh = MagicMock(side_effect=lambda obj: setattr(obj, 'id', 42))

        response = client.post("/pncp/gerenciar", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert data["lembrete_id"] is None

    def test_gerenciar_payload_invalido(self, client):
        """Payload sem numero_controle_pncp → 422."""
        response = client.post("/pncp/gerenciar", json={
            "orgao_razao_social": "Pref",
            "objeto_compra": "TI",
        })
        assert response.status_code == 422
```

### Step 2: Confirmar que testes falham

```bash
python -m pytest tests/test_pncp_router.py::TestGerenciar -v
```
Esperado: `AttributeError` ou `404 Not Found` (endpoint não existe ainda).

### Step 3: Adicionar imports e repositório no `backend/routers/pncp.py`

No topo do arquivo, após os imports existentes, adicione:

```python
from datetime import timedelta

from models.lembrete import Lembrete, LembreteTipo
from repositories.lembrete_repository import lembrete_repository
from repositories.licitacao_repository import licitacao_repository
from schemas.pncp import GerenciarRequest, GerenciarResponse
```

> **Nota:** `licitacao_repository` e `lembrete_repository` são singletons já existentes nos respectivos módulos. Verifique o nome exato do singleton em `backend/repositories/licitacao_repository.py` e `backend/repositories/lembrete_repository.py`.

### Step 4: Adicionar o endpoint em `backend/routers/pncp.py`

Adicione após o bloco `# ===================== Busca + Sync =====================`:

```python
# ===================== Gerenciar =====================


@router.post("/gerenciar", response_model=GerenciarResponse, status_code=201)
def gerenciar_licitacao(
    dados: GerenciarRequest,
    current_user: Usuario = Depends(get_current_approved_user),
    db: Session = Depends(get_db),
):
    """
    Cria atomicamente uma Licitação (M1) + Lembrete no calendário (M2)
    a partir de dados de um item PNCP.

    - Se a licitação já existe (mesmo numero_controle_pncp), retorna a existente.
    - Se criar_lembrete=True e data_abertura presente, cria Lembrete com
      data = data_abertura - antecedencia_horas.
    - Se pncp_resultado_id fornecido, marca o PncpResultado como 'importado'.
    """
    from models.pncp import PncpResultado

    # 1. Verificar duplicata
    existente = licitacao_repository.get_by_numero_controle_pncp(
        db, current_user.id, dados.numero_controle_pncp,
    )
    if existente:
        log_action(
            logger, "pncp_gerenciar_existente",
            user_id=current_user.id,
            resource_type="licitacao",
            resource_id=existente.id,
        )
        from http import HTTPStatus
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=200,
            content=GerenciarResponse(
                licitacao_id=existente.id,
                lembrete_id=None,
                licitacao_ja_existia=True,
                mensagem=Messages.PNCP_GERENCIAR_JA_EXISTIA,
            ).model_dump(),
        )

    # 2. Criar Licitacao
    numero_controle = dados.numero_controle_pncp
    numero = (
        f"PNCP-{numero_controle[-10:]}"
        if len(numero_controle) > 10
        else f"PNCP-{numero_controle}"
    )
    licitacao = Licitacao(
        user_id=current_user.id,
        numero=numero,
        objeto=dados.objeto_compra,
        orgao=dados.orgao_razao_social,
        modalidade=dados.modalidade_nome or "Não informada",
        fonte="pncp",
        status=dados.status_inicial,
        numero_controle_pncp=numero_controle,
        valor_estimado=dados.valor_estimado,
        data_abertura=dados.data_abertura,
        uf=dados.uf,
        municipio=dados.municipio,
        link_sistema_origem=dados.link_sistema_origem,
        observacoes=dados.observacoes or f"Importado do PNCP. Controle: {numero_controle}",
    )
    db.add(licitacao)
    db.commit()
    db.refresh(licitacao)

    # 3. Criar Lembrete (se solicitado e data disponível)
    lembrete_id = None
    if dados.criar_lembrete and dados.data_abertura:
        data_lembrete = dados.data_abertura - timedelta(hours=dados.antecedencia_horas)
        titulo = f"Abertura: {dados.objeto_compra[:80]}"
        lembrete = Lembrete(
            user_id=current_user.id,
            licitacao_id=licitacao.id,
            titulo=titulo,
            descricao=f"Abertura da disputa — {dados.orgao_razao_social}",
            data_lembrete=data_lembrete,
            data_evento=dados.data_abertura,
            tipo=LembreteTipo.ABERTURA_LICITACAO,
            canais=["app"],
        )
        db.add(lembrete)
        db.commit()
        db.refresh(lembrete)
        lembrete_id = lembrete.id

    # 4. Atualizar PncpResultado se fornecido
    if dados.pncp_resultado_id:
        from models.pncp import PncpResultadoStatus
        resultado = pncp_resultado_repository.get_by_id_for_user(
            db, dados.pncp_resultado_id, current_user.id,
        )
        if resultado:
            resultado.status = PncpResultadoStatus.IMPORTADO
            resultado.licitacao_id = licitacao.id
            db.commit()

    log_action(
        logger, "pncp_gerenciar",
        user_id=current_user.id,
        resource_type="licitacao",
        resource_id=licitacao.id,
    )

    mensagem = (
        Messages.PNCP_GERENCIAR_CRIADO
        if lembrete_id
        else Messages.PNCP_GERENCIAR_SEM_DATA
    )
    return GerenciarResponse(
        licitacao_id=licitacao.id,
        lembrete_id=lembrete_id,
        licitacao_ja_existia=False,
        mensagem=mensagem,
    )
```

### Step 5: Adicionar `get_by_numero_controle_pncp` no repositório

Abra `backend/repositories/licitacao_repository.py` e verifique se o método `get_by_numero_controle_pncp` já existe. Se não existir, adicione-o à classe `LicitacaoRepository`:

```python
def get_by_numero_controle_pncp(
    self, db: Session, user_id: int, numero_controle_pncp: str
) -> Optional[Licitacao]:
    """Retorna licitação por numero_controle_pncp para um usuário."""
    return (
        db.query(Licitacao)
        .filter(
            Licitacao.user_id == user_id,
            Licitacao.numero_controle_pncp == numero_controle_pncp,
        )
        .first()
    )
```

> **Nota:** Verifique os imports (`Optional`, `Session`, `Licitacao`) já existentes no arquivo.

### Step 6: Rodar testes do endpoint

```bash
python -m pytest tests/test_pncp_router.py::TestGerenciar -v
```
Esperado: todos passando (ajuste mocks se necessário para `licitacao_repository` e `lembrete_repository`).

### Step 7: Rodar suite completa

```bash
python -m pytest tests/ -x -q --ignore=tests/integration
```
Esperado: todos passando.

### Step 8: Commit

```bash
git add backend/routers/pncp.py backend/repositories/licitacao_repository.py backend/tests/test_pncp_router.py
git commit -m "feat(pncp): add POST /pncp/gerenciar endpoint (Licitacao + Lembrete atomicamente)"
```

---

## Task 3: Backend — Enhanced `GET /pncp/busca`

**Files:**
- Modify: `backend/routers/pncp.py`
- Modify: `backend/tests/test_pncp_router.py`

**Contexto:** O endpoint atual exige `codigo_modalidade` obrigatório e aceita apenas uma UF. Vamos:
1. Tornar `codigo_modalidade` opcional (sem ele, busca nas modalidades padrão: `["4","5","6","7","8"]`)
2. Adicionar `valor_minimo` e `valor_maximo` (filtro client-side)
3. O parâmetro `uf` já existe; sem alteração no filtro de UF por ora

### Step 1: Escrever testes da busca aprimorada (failing)

Adicione ao final de `backend/tests/test_pncp_router.py`:

```python
# ===========================================================================
# GET /busca — enhanced
# ===========================================================================


class TestBuscaEnhanced:
    """Testa a versão aprimorada do endpoint GET /busca."""

    @patch("routers.pncp.pncp_client")
    def test_busca_sem_modalidade_usa_default(self, mock_client, client):
        """Sem codigo_modalidade, deve iterar modalidades padrão."""
        mock_client.buscar_todas_paginas = AsyncMock(return_value=[])

        response = client.get("/pncp/busca?data_inicial=20260301&data_final=20260331")
        assert response.status_code == 200
        # Client deve ter sido chamado múltiplas vezes (1 por modalidade padrão)
        assert mock_client.buscar_todas_paginas.call_count >= 1

    @patch("routers.pncp.pncp_client")
    def test_busca_com_modalidade_especifica(self, mock_client, client):
        """Com codigo_modalidade, deve usar apenas essa modalidade."""
        mock_client.buscar_todas_paginas = AsyncMock(return_value=[])

        response = client.get(
            "/pncp/busca?data_inicial=20260301&data_final=20260331&codigo_modalidade=6"
        )
        assert response.status_code == 200
        assert mock_client.buscar_todas_paginas.call_count == 1

    @patch("routers.pncp.pncp_client")
    def test_busca_filtra_por_valor_minimo(self, mock_client, client):
        """Itens abaixo de valor_minimo devem ser excluídos."""
        mock_client.buscar_todas_paginas = AsyncMock(return_value=[
            {
                "dataAberturaProposta": "2026-03-15T10:00:00",
                "valorTotalEstimado": 10000,
                "numeroControlePNCP": "A",
            },
            {
                "dataAberturaProposta": "2026-03-15T10:00:00",
                "valorTotalEstimado": 200000,
                "numeroControlePNCP": "B",
            },
        ])

        response = client.get(
            "/pncp/busca?data_inicial=20260301&data_final=20260331"
            "&codigo_modalidade=6&valor_minimo=50000"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total_registros"] == 1
        assert data["data"][0]["numeroControlePNCP"] == "B"

    @patch("routers.pncp.pncp_client")
    def test_busca_filtra_por_valor_maximo(self, mock_client, client):
        """Itens acima de valor_maximo devem ser excluídos."""
        mock_client.buscar_todas_paginas = AsyncMock(return_value=[
            {
                "dataAberturaProposta": "2026-03-15T10:00:00",
                "valorTotalEstimado": 100000,
                "numeroControlePNCP": "C",
            },
            {
                "dataAberturaProposta": "2026-03-15T10:00:00",
                "valorTotalEstimado": 2000000,
                "numeroControlePNCP": "D",
            },
        ])

        response = client.get(
            "/pncp/busca?data_inicial=20260301&data_final=20260331"
            "&codigo_modalidade=6&valor_maximo=500000"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total_registros"] == 1
        assert data["data"][0]["numeroControlePNCP"] == "C"
```

### Step 2: Confirmar que `test_busca_sem_modalidade_usa_default` falha

```bash
python -m pytest tests/test_pncp_router.py::TestBuscaEnhanced::test_busca_sem_modalidade_usa_default -v
```
Esperado: `422 Unprocessable Entity` (campo obrigatório faltando).

### Step 3: Atualizar o endpoint `GET /busca` em `backend/routers/pncp.py`

Substitua a assinatura e o corpo do endpoint `buscar_pncp` existente pelo código abaixo:

```python
@router.get("/busca", response_model=PncpBuscaResponse)
async def buscar_pncp(
    data_inicial: str = Query(..., description="Data abertura inicial YYYYMMDD"),
    data_final: str = Query(..., description="Data abertura final YYYYMMDD"),
    codigo_modalidade: Optional[str] = Query(
        None,
        description="Código da modalidade PNCP. Se omitido, busca nas modalidades padrão.",
    ),
    uf: Optional[str] = Query(None),
    valor_minimo: Optional[float] = Query(None, description="Filtro client-side de valor mínimo"),
    valor_maximo: Optional[float] = Query(None, description="Filtro client-side de valor máximo"),
    current_user: Usuario = Depends(get_current_approved_user),
):
    """Busca no PNCP com filtros ricos. Filtragem por valor é client-side."""
    from datetime import datetime, timedelta

    from services.pncp.client import pncp_client

    # Modalidades a iterar
    MODALIDADES_PADRAO = ["4", "5", "6", "7", "8"]
    modalidades = [codigo_modalidade] if codigo_modalidade else MODALIDADES_PADRAO

    try:
        dt_ini = datetime.strptime(data_inicial, "%Y%m%d")
        dt_fim = datetime.strptime(data_final, "%Y%m%d")
        pub_inicial = (dt_ini - timedelta(days=7)).strftime("%Y%m%d")

        todos_items = []
        for modalidade in modalidades:
            kwargs = {"codigo_modalidade": modalidade}
            if uf:
                kwargs["uf"] = uf
            items = await pncp_client.buscar_todas_paginas(
                data_inicial=pub_inicial,
                data_final=data_final,
                max_paginas=3,
                **kwargs,
            )
            todos_items.extend(items)

        # Filtrar por dataAberturaProposta dentro do range
        filtrados = []
        for item in todos_items:
            abertura_str = item.get("dataAberturaProposta")
            if not abertura_str:
                continue
            try:
                abertura = datetime.fromisoformat(abertura_str)
            except (ValueError, TypeError):
                continue
            if not (dt_ini <= abertura <= dt_fim.replace(hour=23, minute=59, second=59)):
                continue

            # Filtrar por valor (client-side)
            valor = item.get("valorTotalEstimado")
            if valor_minimo is not None and valor is not None and float(valor) < valor_minimo:
                continue
            if valor_maximo is not None and valor is not None and float(valor) > valor_maximo:
                continue

            filtrados.append(item)

        # Deduplicar por numeroControlePNCP
        vistos = set()
        unicos = []
        for item in filtrados:
            chave = item.get("numeroControlePNCP", "")
            if chave not in vistos:
                vistos.add(chave)
                unicos.append(item)

        return PncpBuscaResponse(
            data=unicos,
            total_registros=len(unicos),
            total_paginas=1,
            numero_pagina=1,
            paginas_restantes=0,
        )
    except Exception:
        logger.error("Erro na busca PNCP", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=Messages.PNCP_BUSCA_ERRO,
        )
```

### Step 4: Rodar testes da busca aprimorada

```bash
python -m pytest tests/test_pncp_router.py::TestBuscaEnhanced -v
```
Esperado: todos passando.

### Step 5: Rodar suite completa

```bash
python -m pytest tests/ -x -q --ignore=tests/integration
```
Esperado: todos passando.

### Step 6: Commit

```bash
git add backend/routers/pncp.py backend/tests/test_pncp_router.py
git commit -m "feat(pncp): enhance GET /busca with optional modalidade, valor_minimo/maximo filters"
```

---

## Task 4: Frontend HTML — `encontrar.html`

**Files:**
- Create: `frontend/encontrar.html`

**Contexto:** Copiar estrutura do nav de `monitoramento.html` (que tem dropdown Licitações com link ativo para monitoramento). Estrutura da página: barra de busca + filtros + tabs (Busca / Meus Alertas) + área de resultados.

### Step 1: Criar `frontend/encontrar.html`

```html
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>LicitaFácil - Encontrar Licitações</title>
    <link rel="icon" type="image/x-icon" href="/favicon.ico">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="css/style.css">
    <link rel="stylesheet" href="css/encontrar.css">
</head>
<body>
    <!-- Header -->
    <header class="header">
        <a href="dashboard.html" class="header-logo">LicitaFácil</a>
        <button class="nav-toggle" aria-label="Abrir menu" aria-expanded="false">
            <span class="hamburger"></span>
        </button>
        <nav class="header-nav" id="headerNav">
            <a href="dashboard.html">Dashboard</a>
            <div class="nav-dropdown" data-dropdown>
                <button class="nav-dropdown-toggle active" aria-haspopup="true" aria-expanded="false">
                    Licitações
                    <svg class="nav-dropdown-arrow" width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 5l3 3 3-3"/></svg>
                </button>
                <div class="nav-dropdown-menu" role="menu">
                    <a href="licitacoes.html">Gestão</a>
                    <a href="encontrar.html" class="active">Encontrar Licitações</a>
                    <a href="calendario.html">Calendário</a>
                </div>
            </div>
            <div class="nav-dropdown" data-dropdown>
                <button class="nav-dropdown-toggle" aria-haspopup="true" aria-expanded="false">
                    Documentos
                    <svg class="nav-dropdown-arrow" width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 5l3 3 3-3"/></svg>
                </button>
                <div class="nav-dropdown-menu" role="menu">
                    <a href="atestados.html">Atestados</a>
                    <a href="analises.html">Análises</a>
                    <a href="documentos.html">Documentos</a>
                </div>
            </div>
            <div class="nav-utility">
                <a href="admin.html" id="adminLink" class="hidden">Admin</a>
                <a href="perfil.html">Perfil</a>
                <a href="#" class="nav-logout">Sair</a>
            </div>
        </nav>
    </header>

    <div class="container">
        <div id="notificacoesBell"></div>

        <!-- Page Header -->
        <div class="page-header">
            <h1>Encontrar Licitações</h1>
            <p>Busque oportunidades no Portal Nacional de Contratações Públicas (PNCP)</p>
        </div>

        <!-- Search Bar -->
        <div class="encontrar-search-bar">
            <div class="search-input-wrapper">
                <svg class="search-icon" width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="2">
                    <circle cx="9" cy="9" r="7"/><path d="M16 16l-3.5-3.5"/>
                </svg>
                <input
                    type="text"
                    id="searchKeywords"
                    class="search-input"
                    placeholder="Buscar por objeto, palavras-chave..."
                    autocomplete="off"
                />
            </div>
            <button class="btn btn-primary search-btn" data-action="buscar">Buscar</button>
        </div>

        <!-- Quick Filters -->
        <div class="encontrar-filters">
            <div class="filter-group">
                <label class="filter-label">UF</label>
                <select id="filterUF" class="filter-select" multiple size="1">
                    <option value="">Todas</option>
                    <option value="AC">AC</option><option value="AL">AL</option>
                    <option value="AP">AP</option><option value="AM">AM</option>
                    <option value="BA">BA</option><option value="CE">CE</option>
                    <option value="DF">DF</option><option value="ES">ES</option>
                    <option value="GO">GO</option><option value="MA">MA</option>
                    <option value="MT">MT</option><option value="MS">MS</option>
                    <option value="MG">MG</option><option value="PA">PA</option>
                    <option value="PB">PB</option><option value="PR">PR</option>
                    <option value="PE">PE</option><option value="PI">PI</option>
                    <option value="RJ">RJ</option><option value="RN">RN</option>
                    <option value="RS">RS</option><option value="RO">RO</option>
                    <option value="RR">RR</option><option value="SC">SC</option>
                    <option value="SP">SP</option><option value="SE">SE</option>
                    <option value="TO">TO</option>
                </select>
            </div>
            <div class="filter-group">
                <label class="filter-label">Modalidade</label>
                <select id="filterModalidade" class="filter-select">
                    <option value="">Todas</option>
                    <option value="6">Pregão Eletrônico</option>
                    <option value="8">Pregão Presencial</option>
                    <option value="1">Concorrência</option>
                    <option value="4">Concorrência Eletrônica</option>
                    <option value="5">Concurso</option>
                    <option value="2">Diálogo Competitivo</option>
                    <option value="3">Dispensa</option>
                    <option value="7">Inexigibilidade</option>
                    <option value="9">Leilão</option>
                    <option value="10">Manifestação de Interesse</option>
                    <option value="11">Pré-qualificação</option>
                    <option value="12">Credenciamento</option>
                </select>
            </div>
            <!-- Filtros Avançados (collapse) -->
            <button class="btn btn-ghost filter-toggle" data-action="toggleFiltrosAvancados">
                + Mais filtros
            </button>
            <button class="btn btn-ghost filter-clear hidden" data-action="limparFiltros">
                Limpar
            </button>
        </div>

        <!-- Advanced Filters (collapsed by default) -->
        <div class="encontrar-filters-avancados hidden" id="filtrosAvancados">
            <div class="filter-group">
                <label class="filter-label">Valor mínimo (R$)</label>
                <input type="number" id="filterValorMin" class="filter-input" placeholder="0" min="0" step="1000">
            </div>
            <div class="filter-group">
                <label class="filter-label">Valor máximo (R$)</label>
                <input type="number" id="filterValorMax" class="filter-input" placeholder="Sem limite" min="0" step="1000">
            </div>
            <div class="filter-group">
                <label class="filter-label">Abertura de</label>
                <input type="date" id="filterDataIni" class="filter-input">
            </div>
            <div class="filter-group">
                <label class="filter-label">Abertura até</label>
                <input type="date" id="filterDataFim" class="filter-input">
            </div>
        </div>

        <!-- Tabs -->
        <div class="encontrar-tabs">
            <button class="encontrar-tab active" data-action="switchTab" data-tab="busca">
                Busca
                <span class="tab-badge hidden" id="buscaBadge">0</span>
            </button>
            <button class="encontrar-tab" data-action="switchTab" data-tab="alertas">
                Meus Alertas
                <span class="tab-badge tab-badge-blue hidden" id="alertasBadge">0</span>
            </button>
        </div>

        <!-- Tab: Busca -->
        <div id="tabBusca" class="tab-content active">
            <!-- Toolbar -->
            <div class="resultados-toolbar hidden" id="resultadosToolbar">
                <span class="resultados-count" id="resultadosCount"></span>
                <div class="view-toggle">
                    <button class="view-btn active" data-action="setView" data-view="grade" title="Grade">
                        <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
                            <rect x="1" y="1" width="6" height="6" rx="1"/><rect x="9" y="1" width="6" height="6" rx="1"/>
                            <rect x="1" y="9" width="6" height="6" rx="1"/><rect x="9" y="9" width="6" height="6" rx="1"/>
                        </svg>
                    </button>
                    <button class="view-btn" data-action="setView" data-view="lista" title="Lista">
                        <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
                            <rect x="1" y="2" width="14" height="2" rx="1"/>
                            <rect x="1" y="7" width="14" height="2" rx="1"/>
                            <rect x="1" y="12" width="14" height="2" rx="1"/>
                        </svg>
                    </button>
                </div>
            </div>

            <!-- Results area -->
            <div id="resultadosGrid" class="resultados-grid">
                <!-- Empty state inicial -->
                <div class="empty-state" id="emptyStateBusca">
                    <svg width="64" height="64" viewBox="0 0 64 64" fill="none" stroke="var(--text-muted)" stroke-width="1.5">
                        <circle cx="28" cy="28" r="20"/><path d="M44 44l8 8"/>
                    </svg>
                    <h3>Busque licitações no PNCP</h3>
                    <p>Digite palavras-chave, selecione filtros e clique em <strong>Buscar</strong></p>
                </div>
            </div>

            <!-- Pagination -->
            <div class="pagination hidden" id="buscaPaginacao"></div>
        </div>

        <!-- Tab: Meus Alertas -->
        <div id="tabAlertas" class="tab-content hidden">
            <div class="alertas-toolbar">
                <p class="text-muted">Alertas salvos que buscam automaticamente no PNCP</p>
                <button class="btn btn-primary" data-action="novoAlerta">+ Novo Alerta</button>
            </div>
            <div id="alertasGrid" class="alertas-grid">
                <div class="empty-state" id="emptyStateAlertas">
                    <p>Nenhum alerta configurado.</p>
                    <p>Crie alertas para receber novos resultados automaticamente.</p>
                </div>
            </div>
        </div>
    </div>

    <!-- Modal: Gerenciar Licitação -->
    <div class="modal-overlay hidden" id="modalGerenciar" role="dialog" aria-modal="true" aria-labelledby="modalGerenciarTitle">
        <div class="modal-content">
            <div class="modal-header">
                <h2 id="modalGerenciarTitle">Gerenciar Licitação</h2>
                <button class="modal-close" data-action="fecharModalGerenciar" aria-label="Fechar">✕</button>
            </div>
            <div class="modal-body">
                <div class="gerenciar-info" id="gerenciarInfo">
                    <!-- preenchido via JS -->
                </div>
                <div class="form-group">
                    <label class="form-label">Status inicial</label>
                    <select id="gerenciarStatus" class="form-control">
                        <option value="identificada">Identificada</option>
                        <option value="em_analise" selected>Em análise</option>
                        <option value="go_nogo">GO/NO-GO</option>
                    </select>
                </div>
                <div class="form-group" id="lembreteSection">
                    <label class="form-label">
                        <input type="checkbox" id="gerenciarCriarLembrete" checked>
                        Criar lembrete no Calendário
                    </label>
                    <div class="lembrete-config" id="lembreteConfig">
                        <p class="lembrete-data" id="lembreteDataTexto"></p>
                        <div class="form-row">
                            <label class="form-label-inline">Avisar com</label>
                            <select id="gerenciarAntecedencia" class="form-control form-control-sm">
                                <option value="1">1 hora</option>
                                <option value="2">2 horas</option>
                                <option value="6">6 horas</option>
                                <option value="24" selected>24 horas</option>
                                <option value="48">48 horas</option>
                                <option value="72">3 dias</option>
                            </select>
                            <label class="form-label-inline">de antecedência</label>
                        </div>
                    </div>
                </div>
                <div class="form-group">
                    <label class="form-label" for="gerenciarObs">Observações (opcional)</label>
                    <textarea id="gerenciarObs" class="form-control" rows="2" placeholder="Anotações sobre esta licitação..."></textarea>
                </div>
            </div>
            <div class="modal-footer">
                <button class="btn btn-secondary" data-action="fecharModalGerenciar">Cancelar</button>
                <button class="btn btn-primary" data-action="confirmarGerenciar">→ Gerenciar</button>
            </div>
        </div>
    </div>

    <!-- Modal: Novo/Editar Alerta (reutiliza lógica do M3) -->
    <div class="modal-overlay hidden" id="modalAlerta" role="dialog" aria-modal="true" aria-labelledby="modalAlertaTitle">
        <div class="modal-content">
            <div class="modal-header">
                <h2 id="modalAlertaTitle">Novo Alerta</h2>
                <button class="modal-close" data-action="fecharModalAlerta" aria-label="Fechar">✕</button>
            </div>
            <div class="modal-body">
                <div class="form-group">
                    <label class="form-label" for="alertaNome">Nome do alerta *</label>
                    <input type="text" id="alertaNome" class="form-control" placeholder="Ex: TI – São Paulo" maxlength="200">
                </div>
                <div class="form-group">
                    <label class="form-label" for="alertaPalavras">Palavras-chave (separadas por vírgula)</label>
                    <input type="text" id="alertaPalavras" class="form-control" placeholder="tecnologia, informação, suporte">
                </div>
                <div class="form-row">
                    <div class="form-group">
                        <label class="form-label" for="alertaUFs">UF(s)</label>
                        <input type="text" id="alertaUFs" class="form-control" placeholder="SP, RJ, MG">
                    </div>
                    <div class="form-group">
                        <label class="form-label" for="alertaValMin">Valor mín. (R$)</label>
                        <input type="number" id="alertaValMin" class="form-control" min="0" step="1000">
                    </div>
                    <div class="form-group">
                        <label class="form-label" for="alertaValMax">Valor máx. (R$)</label>
                        <input type="number" id="alertaValMax" class="form-control" min="0" step="1000">
                    </div>
                </div>
            </div>
            <div class="modal-footer">
                <button class="btn btn-secondary" data-action="fecharModalAlerta">Cancelar</button>
                <button class="btn btn-primary" data-action="salvarAlerta">Salvar Alerta</button>
            </div>
        </div>
    </div>

    <script src="js/config.js"></script>
    <script src="js/app.js"></script>
    <script src="js/notificacoes.js"></script>
    <script src="js/encontrar.js"></script>
</body>
</html>
```

### Step 2: Verificar o arquivo no browser

Abra `encontrar.html` em um servidor local e confirme que a estrutura carrega sem erros de sintaxe HTML.

### Step 3: Commit

```bash
git add frontend/encontrar.html
git commit -m "feat(encontrar): add encontrar.html structure"
```

---

## Task 5: Frontend CSS — `css/encontrar.css`

**Files:**
- Create: `frontend/css/encontrar.css`

### Step 1: Criar `frontend/css/encontrar.css`

```css
/* === Encontrar Licitações — Estilos === */

/* Variáveis específicas da página */
:root {
    --encontrar-primary: #0D875E;
    --encontrar-primary-hover: #0a6b4a;
    --encontrar-badge-novo: #2563EB;
    --encontrar-card-radius: 12px;
    --encontrar-card-shadow: 0 1px 3px rgba(0, 0, 0, 0.08), 0 1px 2px rgba(0, 0, 0, 0.04);
    --encontrar-card-shadow-hover: 0 4px 12px rgba(0, 0, 0, 0.12);
}

/* === SEARCH BAR === */

.encontrar-search-bar {
    display: flex;
    gap: var(--spacing-sm);
    margin-bottom: var(--spacing-md);
}

.search-input-wrapper {
    position: relative;
    flex: 1;
}

.search-icon {
    position: absolute;
    left: 14px;
    top: 50%;
    transform: translateY(-50%);
    color: var(--text-muted);
    pointer-events: none;
}

.search-input {
    width: 100%;
    padding: 12px 14px 12px 44px;
    border: 1.5px solid var(--border);
    border-radius: 8px;
    font-size: 0.9375rem;
    font-family: inherit;
    background: var(--bg-card);
    color: var(--text-primary);
    transition: border-color 0.15s;
    box-sizing: border-box;
}

.search-input:focus {
    outline: none;
    border-color: var(--encontrar-primary);
    box-shadow: 0 0 0 3px rgba(13, 135, 94, 0.12);
}

.search-btn {
    padding: 12px 24px;
    white-space: nowrap;
    background: var(--encontrar-primary) !important;
    border-color: var(--encontrar-primary) !important;
}

.search-btn:hover {
    background: var(--encontrar-primary-hover) !important;
    border-color: var(--encontrar-primary-hover) !important;
}

/* === FILTERS === */

.encontrar-filters {
    display: flex;
    flex-wrap: wrap;
    align-items: flex-end;
    gap: var(--spacing-sm);
    margin-bottom: var(--spacing-sm);
}

.filter-group {
    display: flex;
    flex-direction: column;
    gap: 4px;
}

.filter-label {
    font-size: 0.75rem;
    font-weight: 500;
    color: var(--text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.04em;
}

.filter-select,
.filter-input {
    padding: 8px 12px;
    border: 1.5px solid var(--border);
    border-radius: 6px;
    font-size: 0.875rem;
    font-family: inherit;
    background: var(--bg-card);
    color: var(--text-primary);
    min-width: 120px;
    transition: border-color 0.15s;
}

.filter-select:focus,
.filter-input:focus {
    outline: none;
    border-color: var(--encontrar-primary);
}

.encontrar-filters-avancados {
    display: flex;
    flex-wrap: wrap;
    gap: var(--spacing-sm);
    margin-bottom: var(--spacing-md);
    padding: var(--spacing-md);
    background: var(--bg-secondary);
    border-radius: 8px;
    border: 1px solid var(--border);
}

.encontrar-filters-avancados.hidden {
    display: none;
}

.filter-toggle {
    color: var(--encontrar-primary);
    font-size: 0.875rem;
}

.filter-clear {
    color: var(--text-muted);
    font-size: 0.875rem;
}

/* === TABS === */

.encontrar-tabs {
    display: flex;
    border-bottom: 2px solid var(--border);
    margin-bottom: var(--spacing-lg);
    gap: 0;
}

.encontrar-tab {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 10px 20px;
    background: none;
    border: none;
    cursor: pointer;
    font-weight: 500;
    font-size: 0.9375rem;
    color: var(--text-secondary);
    border-bottom: 2px solid transparent;
    margin-bottom: -2px;
    transition: var(--transition);
}

.encontrar-tab:hover {
    color: var(--text-primary);
    background: var(--bg-secondary);
}

.encontrar-tab.active {
    color: var(--encontrar-primary);
    border-bottom-color: var(--encontrar-primary);
}

.tab-badge {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-width: 20px;
    height: 20px;
    padding: 0 6px;
    border-radius: 10px;
    font-size: 0.75rem;
    font-weight: 600;
    background: var(--encontrar-primary);
    color: white;
}

.tab-badge-blue {
    background: var(--encontrar-badge-novo);
}

.tab-badge.hidden {
    display: none;
}

/* === TAB CONTENT === */

.tab-content {
    display: block;
}

.tab-content.hidden {
    display: none;
}

/* === RESULTS TOOLBAR === */

.resultados-toolbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: var(--spacing-md);
}

.resultados-toolbar.hidden {
    display: none;
}

.resultados-count {
    font-size: 0.875rem;
    color: var(--text-secondary);
}

.view-toggle {
    display: flex;
    gap: 4px;
}

.view-btn {
    width: 32px;
    height: 32px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: none;
    border: 1.5px solid var(--border);
    border-radius: 6px;
    cursor: pointer;
    color: var(--text-muted);
    transition: var(--transition);
}

.view-btn.active,
.view-btn:hover {
    color: var(--encontrar-primary);
    border-color: var(--encontrar-primary);
    background: rgba(13, 135, 94, 0.06);
}

/* === RESULTS GRID === */

.resultados-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
    gap: var(--spacing-md);
    min-height: 200px;
}

.resultados-grid.view-lista {
    grid-template-columns: 1fr;
}

/* === LICITACAO CARD === */

.licitacao-card {
    background: var(--bg-card);
    border: 1.5px solid var(--border);
    border-radius: var(--encontrar-card-radius);
    padding: var(--spacing-md);
    display: flex;
    flex-direction: column;
    gap: var(--spacing-sm);
    box-shadow: var(--encontrar-card-shadow);
    transition: box-shadow 0.2s, border-color 0.2s;
}

.licitacao-card:hover {
    box-shadow: var(--encontrar-card-shadow-hover);
    border-color: rgba(13, 135, 94, 0.3);
}

.card-header {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 6px;
}

.card-badge-modalidade {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 0.6875rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.03em;
    background: #EFF6FF;
    color: #1D4ED8;
}

.card-badge-modalidade.pregao {
    background: #EFF6FF;
    color: #1D4ED8;
}

.card-badge-modalidade.concorrencia {
    background: #F3E8FF;
    color: #7C3AED;
}

.card-badge-modalidade.dispensa {
    background: #FFF7ED;
    color: #C2410C;
}

.card-badge-uf {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 0.6875rem;
    font-weight: 600;
    background: var(--bg-secondary);
    color: var(--text-secondary);
}

.card-badge-novo {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    font-size: 0.6875rem;
    font-weight: 600;
    color: var(--encontrar-badge-novo);
}

.card-badge-novo::before {
    content: '';
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: var(--encontrar-badge-novo);
    display: inline-block;
}

.card-objeto {
    font-size: 0.9375rem;
    font-weight: 500;
    color: var(--text-primary);
    line-height: 1.4;
    display: -webkit-box;
    -webkit-line-clamp: 3;
    -webkit-box-orient: vertical;
    overflow: hidden;
}

.card-orgao {
    font-size: 0.8125rem;
    color: var(--text-secondary);
}

.card-meta {
    display: flex;
    flex-wrap: wrap;
    gap: var(--spacing-sm);
}

.card-meta-item {
    font-size: 0.8125rem;
    color: var(--text-secondary);
    display: flex;
    align-items: center;
    gap: 4px;
}

.card-meta-item strong {
    color: var(--text-primary);
}

.card-valor {
    font-size: 0.9375rem;
    font-weight: 600;
    color: var(--text-primary);
}

.card-abertura {
    font-size: 0.8125rem;
    color: var(--text-secondary);
}

.card-actions {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--spacing-sm);
    margin-top: auto;
    padding-top: var(--spacing-sm);
    border-top: 1px solid var(--border);
}

.card-btn-edital {
    font-size: 0.8125rem;
    color: var(--text-secondary);
    text-decoration: none;
    display: flex;
    align-items: center;
    gap: 4px;
    transition: color 0.15s;
}

.card-btn-edital:hover {
    color: var(--encontrar-primary);
}

.card-btn-gerenciar {
    padding: 6px 14px;
    font-size: 0.8125rem;
    background: var(--encontrar-primary);
    color: white;
    border: none;
    border-radius: 6px;
    cursor: pointer;
    font-weight: 500;
    transition: background 0.15s;
    white-space: nowrap;
}

.card-btn-gerenciar:hover {
    background: var(--encontrar-primary-hover);
}

.card-btn-gerenciar:disabled {
    background: var(--text-muted);
    cursor: default;
}

.card-btn-gerenciar.gerenciado {
    background: var(--bg-secondary);
    color: var(--text-secondary);
    border: 1.5px solid var(--border);
    cursor: default;
}

/* === LISTA VIEW === */

.licitacao-card.card-lista {
    flex-direction: row;
    align-items: center;
    gap: var(--spacing-md);
    padding: var(--spacing-sm) var(--spacing-md);
}

.licitacao-card.card-lista .card-objeto {
    flex: 1;
    -webkit-line-clamp: 1;
    font-size: 0.875rem;
}

.licitacao-card.card-lista .card-header,
.licitacao-card.card-lista .card-orgao,
.licitacao-card.card-lista .card-meta {
    display: none;
}

/* === ALERTAS === */

.alertas-toolbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: var(--spacing-md);
}

.alertas-grid {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-sm);
}

.alerta-card {
    background: var(--bg-card);
    border: 1.5px solid var(--border);
    border-radius: 10px;
    padding: var(--spacing-md);
    display: flex;
    align-items: center;
    gap: var(--spacing-md);
}

.alerta-icon {
    font-size: 1.5rem;
    flex-shrink: 0;
}

.alerta-info {
    flex: 1;
}

.alerta-nome {
    font-weight: 600;
    font-size: 0.9375rem;
    color: var(--text-primary);
    margin-bottom: 2px;
}

.alerta-criterios {
    font-size: 0.8125rem;
    color: var(--text-secondary);
}

.alerta-novos {
    font-size: 0.8125rem;
    font-weight: 600;
    color: var(--encontrar-badge-novo);
    white-space: nowrap;
}

.alerta-actions {
    display: flex;
    gap: 6px;
    flex-shrink: 0;
}

/* === MODAL GERENCIAR === */

.gerenciar-info {
    background: var(--bg-secondary);
    border-radius: 8px;
    padding: var(--spacing-md);
    margin-bottom: var(--spacing-md);
    font-size: 0.875rem;
    color: var(--text-secondary);
}

.gerenciar-info strong {
    color: var(--text-primary);
    display: block;
    font-size: 0.9375rem;
    margin-bottom: 4px;
}

.lembrete-config {
    margin-top: 8px;
    padding: 12px;
    background: rgba(13, 135, 94, 0.06);
    border-radius: 8px;
    border: 1px solid rgba(13, 135, 94, 0.2);
}

.lembrete-data {
    font-size: 0.875rem;
    font-weight: 500;
    color: var(--encontrar-primary);
    margin: 0 0 8px 0;
}

.form-row {
    display: flex;
    align-items: center;
    gap: var(--spacing-sm);
    flex-wrap: wrap;
}

.form-label-inline {
    font-size: 0.875rem;
    color: var(--text-secondary);
    white-space: nowrap;
}

.form-control-sm {
    padding: 4px 8px;
    font-size: 0.875rem;
}

/* === PAGINATION === */

.pagination {
    display: flex;
    justify-content: center;
    align-items: center;
    gap: 4px;
    margin-top: var(--spacing-lg);
}

.pagination.hidden {
    display: none;
}

.pagination button {
    width: 36px;
    height: 36px;
    border: 1.5px solid var(--border);
    border-radius: 6px;
    background: var(--bg-card);
    cursor: pointer;
    font-size: 0.875rem;
    color: var(--text-secondary);
    transition: var(--transition);
    display: flex;
    align-items: center;
    justify-content: center;
}

.pagination button:hover {
    border-color: var(--encontrar-primary);
    color: var(--encontrar-primary);
}

.pagination button.active {
    background: var(--encontrar-primary);
    border-color: var(--encontrar-primary);
    color: white;
}

.pagination button:disabled {
    opacity: 0.4;
    cursor: default;
}

/* === EMPTY STATE === */

.empty-state {
    grid-column: 1 / -1;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: var(--spacing-xl);
    color: var(--text-muted);
    text-align: center;
    gap: var(--spacing-sm);
}

.empty-state h3 {
    margin: 0;
    font-size: 1rem;
    color: var(--text-secondary);
}

.empty-state p {
    margin: 0;
    font-size: 0.875rem;
}

/* === LOADING === */

.loading-spinner {
    grid-column: 1 / -1;
    display: flex;
    justify-content: center;
    padding: var(--spacing-xl);
}

/* === RESPONSIVE === */

@media (max-width: 768px) {
    .encontrar-search-bar {
        flex-direction: column;
    }

    .search-btn {
        width: 100%;
    }

    .encontrar-filters {
        flex-direction: column;
        align-items: stretch;
    }

    .filter-select,
    .filter-input {
        width: 100%;
    }

    .resultados-grid {
        grid-template-columns: 1fr;
    }

    .alerta-card {
        flex-direction: column;
        align-items: flex-start;
    }
}
```

### Step 2: Verificar visualmente

Abra `encontrar.html` no browser e confirme que os estilos aplicam sem erros no console.

### Step 3: Commit

```bash
git add frontend/css/encontrar.css
git commit -m "feat(encontrar): add encontrar.css styles"
```

---

## Task 6: Frontend JS — `js/encontrar.js` (Busca, Cards, Alertas)

**Files:**
- Create: `frontend/js/encontrar.js`

**Contexto:** Módulo vanilla JS seguindo o mesmo padrão de `monitoramento.js` (object module + setupEventDelegation). Funções: buscar no PNCP, renderizar cards, paginação, tabs, alertas.

### Step 1: Criar `frontend/js/encontrar.js`

```javascript
// LicitaFacil - Modulo Encontrar Licitacoes
// Busca rica no PNCP com integração ao Calendário e Gestão de Licitações

const EncontrarModule = {
    // === ESTADO ===
    resultados: [],
    totalResultados: 0,
    paginaAtual: 1,
    pageSize: 20,
    viewMode: 'grade', // 'grade' | 'lista'
    tabAtiva: 'busca',

    // Item selecionado para gerenciar
    itemParaGerenciar: null,

    // === INICIALIZAÇÃO ===

    init() {
        this.setupEventDelegation();
        this.setupFiltros();
        this.setDefaultDates();
        this.carregarAlertas();
    },

    // === EVENT DELEGATION ===

    setupEventDelegation() {
        const self = this;

        document.addEventListener('click', (e) => {
            const btn = e.target.closest('[data-action]');
            if (!btn) return;
            const action = btn.dataset.action;

            switch (action) {
                case 'buscar':
                    self.buscar(1);
                    break;
                case 'switchTab':
                    self.switchTab(btn.dataset.tab);
                    break;
                case 'setView':
                    self.setView(btn.dataset.view);
                    break;
                case 'toggleFiltrosAvancados':
                    self.toggleFiltrosAvancados();
                    break;
                case 'limparFiltros':
                    self.limparFiltros();
                    break;
                case 'abrirGerenciar':
                    self.abrirGerenciar(btn.dataset.index);
                    break;
                case 'fecharModalGerenciar':
                    self.fecharModalGerenciar();
                    break;
                case 'confirmarGerenciar':
                    self.confirmarGerenciar();
                    break;
                case 'novoAlerta':
                    self.novoAlerta();
                    break;
                case 'fecharModalAlerta':
                    self.fecharModalAlerta();
                    break;
                case 'salvarAlerta':
                    self.salvarAlerta();
                    break;
                case 'editarAlerta':
                    self.editarAlerta(btn.dataset.id);
                    break;
                case 'excluirAlerta':
                    self.excluirAlerta(btn.dataset.id);
                    break;
                case 'toggleAlerta':
                    self.toggleAlerta(btn.dataset.id);
                    break;
                case 'paginaBusca':
                    self.buscar(parseInt(btn.dataset.page));
                    break;
            }
        });

        // Buscar ao pressionar Enter na barra de busca
        document.getElementById('searchKeywords')?.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') self.buscar(1);
        });

        // Toggle checkbox lembrete
        document.getElementById('gerenciarCriarLembrete')?.addEventListener('change', function () {
            const config = document.getElementById('lembreteConfig');
            if (config) config.classList.toggle('hidden', !this.checked);
        });
    },

    // === FILTROS ===

    setupFiltros() {
        // Não precisa de debounce aqui — busca é disparada via botão
    },

    setDefaultDates() {
        const hoje = new Date();
        const em30dias = new Date();
        em30dias.setDate(hoje.getDate() + 30);

        const fmt = (d) => d.toISOString().split('T')[0];

        const ini = document.getElementById('filterDataIni');
        const fim = document.getElementById('filterDataFim');
        if (ini) ini.value = fmt(hoje);
        if (fim) fim.value = fmt(em30dias);
    },

    toggleFiltrosAvancados() {
        const panel = document.getElementById('filtrosAvancados');
        const btn = document.querySelector('[data-action="toggleFiltrosAvancados"]');
        if (!panel) return;
        panel.classList.toggle('hidden');
        if (btn) btn.textContent = panel.classList.contains('hidden') ? '+ Mais filtros' : '− Menos filtros';
    },

    limparFiltros() {
        document.getElementById('searchKeywords').value = '';
        document.getElementById('filterUF').value = '';
        document.getElementById('filterModalidade').value = '';
        document.getElementById('filterValorMin').value = '';
        document.getElementById('filterValorMax').value = '';
        this.setDefaultDates();
        // Limpar resultados
        this.resultados = [];
        this.renderResultados([]);
        document.getElementById('resultadosToolbar')?.classList.add('hidden');
        document.getElementById('buscaPaginacao')?.classList.add('hidden');
        document.getElementById('emptyStateBusca')?.classList.remove('hidden');
        const badge = document.getElementById('buscaBadge');
        if (badge) badge.classList.add('hidden');
    },

    getParams() {
        const keywords = document.getElementById('searchKeywords')?.value.trim() || '';
        const uf = document.getElementById('filterUF')?.value || '';
        const modalidade = document.getElementById('filterModalidade')?.value || '';
        const valorMin = document.getElementById('filterValorMin')?.value || '';
        const valorMax = document.getElementById('filterValorMax')?.value || '';
        const dataIni = document.getElementById('filterDataIni')?.value || '';
        const dataFim = document.getElementById('filterDataFim')?.value || '';

        return { keywords, uf, modalidade, valorMin, valorMax, dataIni, dataFim };
    },

    // === BUSCA ===

    async buscar(pagina = 1) {
        this.paginaAtual = pagina;
        const params = this.getParams();

        // Montar query string para o endpoint
        const qs = new URLSearchParams();
        if (params.dataIni) qs.set('data_inicial', params.dataIni.replace(/-/g, ''));
        if (params.dataFim) qs.set('data_final', params.dataFim.replace(/-/g, ''));
        if (params.modalidade) qs.set('codigo_modalidade', params.modalidade);
        if (params.uf) qs.set('uf', params.uf);
        if (params.valorMin) qs.set('valor_minimo', params.valorMin);
        if (params.valorMax) qs.set('valor_maximo', params.valorMax);

        const container = document.getElementById('resultadosGrid');
        if (!container) return;

        // Loading state
        container.innerHTML = '<div class="loading-spinner"><div class="spinner"></div></div>';
        document.getElementById('resultadosToolbar')?.classList.add('hidden');
        document.getElementById('emptyStateBusca')?.classList.add('hidden');

        try {
            const response = await api.get(`/pncp/busca?${qs}`);
            let items = response.data || [];

            // Filtro client-side por keywords
            if (params.keywords) {
                const kw = params.keywords.toLowerCase();
                items = items.filter(item => {
                    const objeto = (item.objetoCompra || '').toLowerCase();
                    const orgao = (item.orgaoEntidade?.razaoSocial || '').toLowerCase();
                    return objeto.includes(kw) || orgao.includes(kw);
                });
            }

            // Paginação client-side (API retorna tudo de uma vez)
            const total = items.length;
            const inicio = (pagina - 1) * this.pageSize;
            const pagItems = items.slice(inicio, inicio + this.pageSize);
            const totalPaginas = Math.ceil(total / this.pageSize) || 1;

            this.resultados = items; // guarda todos para paginação
            this.renderResultados(pagItems);
            this.renderToolbar(total);
            this.renderPaginacao('buscaPaginacao', pagina, totalPaginas);

            // Badge na tab
            const badge = document.getElementById('buscaBadge');
            if (badge) {
                badge.textContent = total;
                badge.classList.toggle('hidden', total === 0);
            }
        } catch (err) {
            container.innerHTML = `
                <div class="empty-state">
                    <p>Erro ao buscar no PNCP. Verifique sua conexão e tente novamente.</p>
                </div>`;
            console.error('Erro na busca PNCP:', err);
        }
    },

    // === RENDER CARDS ===

    renderResultados(items) {
        const container = document.getElementById('resultadosGrid');
        if (!container) return;

        if (!items || items.length === 0) {
            container.innerHTML = `
                <div class="empty-state" id="emptyStateBusca">
                    <svg width="64" height="64" viewBox="0 0 64 64" fill="none" stroke="var(--text-muted)" stroke-width="1.5">
                        <circle cx="28" cy="28" r="20"/><path d="M44 44l8 8"/>
                    </svg>
                    <h3>Nenhuma licitação encontrada</h3>
                    <p>Tente ampliar o período ou remover alguns filtros.</p>
                </div>`;
            return;
        }

        container.classList.toggle('view-lista', this.viewMode === 'lista');

        const agora = new Date();
        const limite48h = new Date(agora.getTime() - 48 * 60 * 60 * 1000);

        container.innerHTML = items.map((item, idx) => {
            const globalIdx = (this.paginaAtual - 1) * this.pageSize + idx;
            return this.renderCard(item, globalIdx, limite48h);
        }).join('');
    },

    renderCard(item, idx, limite48h) {
        const orgao = item.orgaoEntidade || {};
        const unidade = item.unidadeOrgao || {};
        const objeto = Sanitize.escapeHtml(item.objetoCompra || 'Sem descrição');
        const orgaoNome = Sanitize.escapeHtml(orgao.razaoSocial || 'Órgão não informado');
        const modalidade = Sanitize.escapeHtml(item.modalidadeNome || '');
        const uf = Sanitize.escapeHtml(unidade.ufSigla || '');
        const valor = item.valorTotalEstimado;
        const linkEdital = Sanitize.escapeHtml(item.linkSistemaOrigem || '#');
        const controle = item.numeroControlePNCP || '';

        // Badge "Novo"
        const dataPublicacao = item.dataPublicacao ? new Date(item.dataPublicacao) : null;
        const isNovo = dataPublicacao && dataPublicacao >= limite48h;

        // Formatação de data abertura
        let aberturaTexto = 'Data não informada';
        if (item.dataAberturaProposta) {
            const dt = new Date(item.dataAberturaProposta);
            aberturaTexto = dt.toLocaleString('pt-BR', {
                day: '2-digit', month: '2-digit', year: 'numeric',
                hour: '2-digit', minute: '2-digit',
            });
        }

        // Formatação de valor
        let valorTexto = valor != null
            ? `R$ ${parseFloat(valor).toLocaleString('pt-BR', { minimumFractionDigits: 2 })}`
            : 'Valor não estimado';

        // Classe da badge de modalidade
        const modalidadeLower = modalidade.toLowerCase();
        let modalidadeClass = '';
        if (modalidadeLower.includes('pregão')) modalidadeClass = 'pregao';
        else if (modalidadeLower.includes('concorrência')) modalidadeClass = 'concorrencia';
        else if (modalidadeLower.includes('dispensa') || modalidadeLower.includes('inexigibilidade')) modalidadeClass = 'dispensa';

        if (this.viewMode === 'lista') {
            return `
            <div class="licitacao-card card-lista">
                <div class="card-objeto">${objeto}</div>
                <div class="card-meta-item">${uf}</div>
                <div class="card-meta-item"><strong>${valorTexto}</strong></div>
                <div class="card-meta-item">⏱ ${aberturaTexto}</div>
                <div class="card-actions">
                    ${linkEdital !== '#' ? `<a href="${linkEdital}" target="_blank" rel="noopener noreferrer" class="card-btn-edital">Edital ↗</a>` : ''}
                    <button class="card-btn-gerenciar" data-action="abrirGerenciar" data-index="${idx}">→ Gerenciar</button>
                </div>
            </div>`;
        }

        return `
        <div class="licitacao-card">
            <div class="card-header">
                ${modalidade ? `<span class="card-badge-modalidade ${modalidadeClass}">${modalidade}</span>` : ''}
                ${uf ? `<span class="card-badge-uf">${uf}</span>` : ''}
                ${isNovo ? `<span class="card-badge-novo">Novo</span>` : ''}
            </div>
            <div class="card-objeto">${objeto}</div>
            <div class="card-orgao">${orgaoNome}${orgao.cnpj ? ` — CNPJ ${Sanitize.escapeHtml(orgao.cnpj)}` : ''}</div>
            <div class="card-valor">${valorTexto}</div>
            <div class="card-abertura">⏱ Abertura: <strong>${aberturaTexto}</strong></div>
            <div class="card-actions">
                ${linkEdital !== '#' ? `<a href="${linkEdital}" target="_blank" rel="noopener noreferrer" class="card-btn-edital">Ver Edital ↗</a>` : '<span></span>'}
                <button class="card-btn-gerenciar" data-action="abrirGerenciar" data-index="${idx}">→ Gerenciar</button>
            </div>
        </div>`;
    },

    renderToolbar(total) {
        const toolbar = document.getElementById('resultadosToolbar');
        const count = document.getElementById('resultadosCount');
        if (!toolbar || !count) return;
        toolbar.classList.remove('hidden');
        count.textContent = `${total.toLocaleString('pt-BR')} resultado${total !== 1 ? 's' : ''}`;
    },

    renderPaginacao(containerId, paginaAtual, totalPaginas) {
        const container = document.getElementById(containerId);
        if (!container) return;
        if (totalPaginas <= 1) {
            container.classList.add('hidden');
            return;
        }
        container.classList.remove('hidden');
        const paginas = [];
        paginas.push(`<button ${paginaAtual === 1 ? 'disabled' : ''} data-action="paginaBusca" data-page="${paginaAtual - 1}">‹</button>`);
        for (let i = 1; i <= totalPaginas; i++) {
            if (i === 1 || i === totalPaginas || Math.abs(i - paginaAtual) <= 2) {
                paginas.push(`<button class="${i === paginaAtual ? 'active' : ''}" data-action="paginaBusca" data-page="${i}">${i}</button>`);
            } else if (Math.abs(i - paginaAtual) === 3) {
                paginas.push(`<span style="padding:0 4px;color:var(--text-muted)">…</span>`);
            }
        }
        paginas.push(`<button ${paginaAtual === totalPaginas ? 'disabled' : ''} data-action="paginaBusca" data-page="${paginaAtual + 1}">›</button>`);
        container.innerHTML = paginas.join('');
    },

    // === TABS ===

    switchTab(tab) {
        this.tabAtiva = tab;
        document.querySelectorAll('.encontrar-tab').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.tab === tab);
        });
        document.getElementById('tabBusca').classList.toggle('hidden', tab !== 'busca');
        document.getElementById('tabAlertas').classList.toggle('hidden', tab !== 'alertas');

        if (tab === 'alertas') this.carregarAlertas();
    },

    // === VIEW MODE ===

    setView(mode) {
        this.viewMode = mode;
        document.querySelectorAll('.view-btn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.view === mode);
        });
        // Re-renderizar a página atual
        const inicio = (this.paginaAtual - 1) * this.pageSize;
        const pagItems = this.resultados.slice(inicio, inicio + this.pageSize);
        this.renderResultados(pagItems);
    },

    // === ALERTAS (Monitores PNCP existentes) ===

    async carregarAlertas() {
        const container = document.getElementById('alertasGrid');
        if (!container) return;

        await ErrorHandler.withErrorHandling(async () => {
            const response = await api.get('/pncp/monitoramentos?page_size=50');
            const monitores = response.items || [];
            this.renderAlertas(monitores);

            // Badge na tab
            const badge = document.getElementById('alertasBadge');
            if (badge && monitores.length > 0) {
                badge.textContent = monitores.length;
                badge.classList.remove('hidden');
            }
        }, 'Erro ao carregar alertas', { container: 'alertasGrid' });
    },

    renderAlertas(monitores) {
        const container = document.getElementById('alertasGrid');
        if (!container) return;

        if (!monitores || monitores.length === 0) {
            container.innerHTML = `
                <div class="empty-state" id="emptyStateAlertas">
                    <p>Nenhum alerta configurado.</p>
                    <p>Crie alertas para receber novas licitações automaticamente.</p>
                    <button class="btn btn-primary" data-action="novoAlerta">+ Criar primeiro alerta</button>
                </div>`;
            return;
        }

        container.innerHTML = monitores.map(m => {
            const criterios = [];
            if (m.palavras_chave?.length) criterios.push(`"${m.palavras_chave.slice(0, 3).join(', ')}"`);
            if (m.ufs?.length) criterios.push(m.ufs.join(', '));
            if (m.valor_minimo || m.valor_maximo) {
                const min = m.valor_minimo ? `R$ ${parseFloat(m.valor_minimo).toLocaleString('pt-BR')}` : '';
                const max = m.valor_maximo ? `R$ ${parseFloat(m.valor_maximo).toLocaleString('pt-BR')}` : '';
                criterios.push(min && max ? `${min}–${max}` : min || max);
            }

            return `
            <div class="alerta-card">
                <div class="alerta-icon">${m.ativo ? '🔔' : '🔕'}</div>
                <div class="alerta-info">
                    <div class="alerta-nome">${Sanitize.escapeHtml(m.nome)}</div>
                    <div class="alerta-criterios">${criterios.length ? criterios.join(' | ') : 'Sem critérios específicos'}</div>
                </div>
                ${!m.ativo ? '<span style="font-size:0.75rem;color:var(--text-muted)">Pausado</span>' : ''}
                <div class="alerta-actions">
                    <button class="btn btn-sm btn-ghost" data-action="editarAlerta" data-id="${m.id}" title="Editar">✏</button>
                    <button class="btn btn-sm btn-ghost" data-action="toggleAlerta" data-id="${m.id}" title="${m.ativo ? 'Pausar' : 'Ativar'}">${m.ativo ? '⏸' : '▶'}</button>
                    <button class="btn btn-sm btn-ghost" data-action="excluirAlerta" data-id="${m.id}" title="Excluir">🗑</button>
                </div>
            </div>`;
        }).join('');
    },

    // === MODAL NOVO/EDITAR ALERTA ===

    novoAlerta() {
        this._alertaEditId = null;
        document.getElementById('modalAlertaTitle').textContent = 'Novo Alerta';
        document.getElementById('alertaNome').value = '';
        document.getElementById('alertaPalavras').value = '';
        document.getElementById('alertaUFs').value = '';
        document.getElementById('alertaValMin').value = '';
        document.getElementById('alertaValMax').value = '';
        abrirModal('modalAlerta');
    },

    async editarAlerta(id) {
        this._alertaEditId = id;
        try {
            const monitor = await api.get(`/pncp/monitoramentos/${id}`);
            document.getElementById('modalAlertaTitle').textContent = 'Editar Alerta';
            document.getElementById('alertaNome').value = monitor.nome || '';
            document.getElementById('alertaPalavras').value = (monitor.palavras_chave || []).join(', ');
            document.getElementById('alertaUFs').value = (monitor.ufs || []).join(', ');
            document.getElementById('alertaValMin').value = monitor.valor_minimo || '';
            document.getElementById('alertaValMax').value = monitor.valor_maximo || '';
            abrirModal('modalAlerta');
        } catch (err) {
            ui.showToast('Erro ao carregar alerta', 'error');
        }
    },

    fecharModalAlerta() {
        fecharModal('modalAlerta');
    },

    async salvarAlerta() {
        const nome = document.getElementById('alertaNome')?.value.trim();
        if (!nome) {
            ui.showToast('Informe um nome para o alerta', 'error');
            return;
        }

        const palavrasStr = document.getElementById('alertaPalavras')?.value.trim();
        const ufsStr = document.getElementById('alertaUFs')?.value.trim();
        const valMin = document.getElementById('alertaValMin')?.value;
        const valMax = document.getElementById('alertaValMax')?.value;

        const payload = {
            nome,
            palavras_chave: palavrasStr ? palavrasStr.split(',').map(s => s.trim()).filter(Boolean) : null,
            ufs: ufsStr ? ufsStr.split(',').map(s => s.trim().toUpperCase()).filter(Boolean) : null,
            valor_minimo: valMin ? parseFloat(valMin) : null,
            valor_maximo: valMax ? parseFloat(valMax) : null,
        };

        try {
            if (this._alertaEditId) {
                await api.put(`/pncp/monitoramentos/${this._alertaEditId}`, payload);
                ui.showToast('Alerta atualizado com sucesso!', 'success');
            } else {
                await api.post('/pncp/monitoramentos', payload);
                ui.showToast('Alerta criado com sucesso!', 'success');
            }
            this.fecharModalAlerta();
            this.carregarAlertas();
        } catch (err) {
            ui.showToast('Erro ao salvar alerta', 'error');
        }
    },

    async toggleAlerta(id) {
        try {
            await api.patch(`/pncp/monitoramentos/${id}/toggle`);
            this.carregarAlertas();
        } catch (err) {
            ui.showToast('Erro ao alternar alerta', 'error');
        }
    },

    async excluirAlerta(id) {
        confirmAction('Excluir este alerta permanentemente?', async () => {
            try {
                await api.delete(`/pncp/monitoramentos/${id}`);
                ui.showToast('Alerta removido', 'success');
                this.carregarAlertas();
            } catch (err) {
                ui.showToast('Erro ao excluir alerta', 'error');
            }
        });
    },

    // === MODAL GERENCIAR ===

    abrirGerenciar(idxStr) {
        const idx = parseInt(idxStr, 10);
        const item = this.resultados[idx];
        if (!item) return;
        this.itemParaGerenciar = item;

        // Preencher info
        const orgao = item.orgaoEntidade || {};
        const infoEl = document.getElementById('gerenciarInfo');
        if (infoEl) {
            const objeto = Sanitize.escapeHtml(item.objetoCompra || 'Sem descrição');
            const orgaoNome = Sanitize.escapeHtml(orgao.razaoSocial || 'Não informado');
            const valor = item.valorTotalEstimado
                ? `R$ ${parseFloat(item.valorTotalEstimado).toLocaleString('pt-BR', { minimumFractionDigits: 2 })}`
                : 'Valor não estimado';
            const controle = Sanitize.escapeHtml(item.numeroControlePNCP || '');

            infoEl.innerHTML = `
                <strong>${objeto}</strong>
                ${orgaoNome}<br>
                ${valor}${controle ? ` &nbsp;·&nbsp; PNCP: ${controle}` : ''}
            `;
        }

        // Lembrete section
        const dataAbertura = item.dataAberturaProposta ? new Date(item.dataAberturaProposta) : null;
        const lembreteSection = document.getElementById('lembreteSection');
        const lembreteDataTexto = document.getElementById('lembreteDataTexto');

        if (dataAbertura && lembreteSection) {
            lembreteSection.classList.remove('hidden');
            const antecedencia = parseInt(document.getElementById('gerenciarAntecedencia')?.value || '24', 10);
            const dataLembrete = new Date(dataAbertura.getTime() - antecedencia * 60 * 60 * 1000);
            if (lembreteDataTexto) {
                lembreteDataTexto.textContent = `🗓 Lembrete: ${dataLembrete.toLocaleString('pt-BR', {
                    day: '2-digit', month: '2-digit', year: 'numeric',
                    hour: '2-digit', minute: '2-digit',
                })}`;
            }
        } else if (lembreteSection) {
            lembreteSection.classList.add('hidden');
        }

        // Reset status
        const statusEl = document.getElementById('gerenciarStatus');
        if (statusEl) statusEl.value = 'em_analise';

        document.getElementById('gerenciarObs').value = '';
        abrirModal('modalGerenciar');
    },

    fecharModalGerenciar() {
        fecharModal('modalGerenciar');
        this.itemParaGerenciar = null;
    },

    async confirmarGerenciar() {
        const item = this.itemParaGerenciar;
        if (!item) return;

        const orgao = item.orgaoEntidade || {};
        const unidade = item.unidadeOrgao || {};
        const criarLembrete = document.getElementById('gerenciarCriarLembrete')?.checked ?? true;
        const antecedencia = parseInt(document.getElementById('gerenciarAntecedencia')?.value || '24', 10);
        const statusInicial = document.getElementById('gerenciarStatus')?.value || 'em_analise';
        const observacoes = document.getElementById('gerenciarObs')?.value.trim() || null;

        const payload = {
            numero_controle_pncp: item.numeroControlePNCP || '',
            orgao_razao_social: orgao.razaoSocial || 'Não informado',
            objeto_compra: item.objetoCompra || 'Sem descrição',
            modalidade_nome: item.modalidadeNome || null,
            uf: unidade.ufSigla || null,
            municipio: unidade.municipioNome || null,
            valor_estimado: item.valorTotalEstimado || null,
            data_abertura: item.dataAberturaProposta || null,
            link_sistema_origem: item.linkSistemaOrigem || null,
            dados_completos: item,
            status_inicial: statusInicial,
            observacoes: observacoes,
            criar_lembrete: criarLembrete,
            antecedencia_horas: antecedencia,
        };

        const btnConfirmar = document.querySelector('[data-action="confirmarGerenciar"]');
        if (btnConfirmar) {
            btnConfirmar.disabled = true;
            btnConfirmar.textContent = 'Salvando...';
        }

        try {
            const response = await api.post('/pncp/gerenciar', payload);

            if (response.licitacao_ja_existia) {
                ui.showToast('Esta licitação já está no seu gerenciamento.', 'warning');
            } else {
                const lembreteMsg = response.lembrete_id
                    ? ` Lembrete criado no Calendário.`
                    : '';
                ui.showToast(`Licitação adicionada!${lembreteMsg}`, 'success');

                // Marcar o card como gerenciado
                this._marcarCardGerenciado(item.numeroControlePNCP);
            }
            this.fecharModalGerenciar();
        } catch (err) {
            const msg = err?.detail || 'Erro ao gerenciar licitação. Tente novamente.';
            ui.showToast(Sanitize.escapeHtml(msg), 'error');
        } finally {
            if (btnConfirmar) {
                btnConfirmar.disabled = false;
                btnConfirmar.textContent = '→ Gerenciar';
            }
        }
    },

    _marcarCardGerenciado(numeroControle) {
        // Encontrar o botão do card e marcá-lo como gerenciado
        const cards = document.querySelectorAll('.licitacao-card');
        cards.forEach(card => {
            const btn = card.querySelector('.card-btn-gerenciar');
            if (btn) {
                const idx = parseInt(btn.dataset.index, 10);
                const item = this.resultados[idx];
                if (item && item.numeroControlePNCP === numeroControle) {
                    btn.textContent = '✓ Gerenciado';
                    btn.classList.add('gerenciado');
                    btn.disabled = true;
                    btn.removeAttribute('data-action');
                }
            }
        });
    },
};

// Inicializar quando o DOM estiver pronto
document.addEventListener('DOMContentLoaded', () => {
    if (typeof api !== 'undefined' && typeof ui !== 'undefined') {
        EncontrarModule.init();
    } else {
        console.error('Encontrar: dependências (api, ui) não carregadas');
    }
});
```

### Step 2: Verificar no browser

Abra `encontrar.html`, abra o DevTools (F12) e verifique:
- Sem erros no console ao carregar a página
- Botão "Buscar" responde ao clique
- Tab "Meus Alertas" carrega e mostra lista de alertas

### Step 3: Commit

```bash
git add frontend/js/encontrar.js
git commit -m "feat(encontrar): add encontrar.js with search, cards, alerts, and gerenciar modal"
```

---

## Task 7: Deprecar `monitoramento.html` + Atualizar Nav em todos os HTML

**Files:**
- Modify: `frontend/monitoramento.html`
- Modify: `frontend/admin.html`
- Modify: `frontend/analises.html`
- Modify: `frontend/atestados.html`
- Modify: `frontend/calendario.html`
- Modify: `frontend/dashboard.html`
- Modify: `frontend/documentos.html`
- Modify: `frontend/licitacoes.html`
- Modify: `frontend/perfil.html`

**Contexto:** Todos os arquivos HTML têm um nav dropdown "Licitações" com link `monitoramento.html`. Esse link deve ser atualizado para `encontrar.html` com texto "Encontrar Licitações". O `monitoramento.html` recebe um redirect.

### Step 1: Adicionar redirect em `monitoramento.html`

No `<head>` de `frontend/monitoramento.html`, adicione imediatamente após `<meta charset="UTF-8">`:

```html
<!-- Página migrada para encontrar.html -->
<meta http-equiv="refresh" content="0; url=encontrar.html">
<script>window.location.replace('encontrar.html');</script>
```

### Step 2: Atualizar nav em todos os HTML

Em **cada** arquivo HTML listado acima, localize o trecho:

```html
<a href="monitoramento.html" class="active">Monitoramento PNCP</a>
```
ou (em páginas onde não é ativo):
```html
<a href="monitoramento.html">Monitoramento PNCP</a>
```

E substitua por:

```html
<a href="encontrar.html">Encontrar Licitações</a>
```

> **Nota:** Em `encontrar.html` o link já foi criado com `class="active"`. Nos demais, não deve ter `class="active"`.

### Step 3: Verificar todas as ocorrências

```bash
grep -r "monitoramento.html" d:/Analise\ de\ Capacitade\ Técnica/licitafacil/frontend/
```
Resultado esperado: apenas a referência interna do `monitoramento.html` e o redirect.

### Step 4: Commit

```bash
git add frontend/monitoramento.html frontend/admin.html frontend/analises.html frontend/atestados.html frontend/calendario.html frontend/dashboard.html frontend/documentos.html frontend/licitacoes.html frontend/perfil.html
git commit -m "feat(encontrar): redirect monitoramento.html to encontrar.html, update nav in all pages"
```

---

## Task 8: Teste E2E Manual + Verificação Final

### Checklist de verificação

```
[ ] Backend: POST /api/v1/pncp/gerenciar retorna 201 com licitacao_id e lembrete_id
[ ] Backend: POST /api/v1/pncp/gerenciar com licitação duplicada retorna 200 com licitacao_ja_existia=true
[ ] Backend: GET /api/v1/pncp/busca sem codigo_modalidade retorna resultados (pode ser lista vazia se PNCP offline)
[ ] Backend: GET /api/v1/pncp/busca com valor_minimo filtra corretamente
[ ] Frontend: encontrar.html carrega sem erros no console
[ ] Frontend: Digitar palavras-chave + clicar Buscar → cards aparecem
[ ] Frontend: Badge "Novo" aparece em licitações recentes
[ ] Frontend: Clicar "→ Gerenciar" → modal abre com dados preenchidos
[ ] Frontend: Confirmar gerenciar → licitação aparece em licitacoes.html
[ ] Frontend: Confirmar gerenciar com criar_lembrete=true → lembrete aparece em calendario.html
[ ] Frontend: Tab "Meus Alertas" lista monitores do M3
[ ] Frontend: Criar novo alerta via modal → aparece na lista
[ ] Frontend: monitoramento.html redireciona para encontrar.html
[ ] Frontend: Nav em todos os HTML tem "Encontrar Licitações" linkando para encontrar.html
```

### Rodar suite completa de testes

```bash
cd d:/Analise\ de\ Capacitade\ Técnica/licitafacil/backend
python -m pytest tests/ -x -q --ignore=tests/integration
```
Esperado: todos passando, cobertura ≥ 49%.

### Commit final

```bash
cd d:/Analise\ de\ Capacitade\ Técnica/licitafacil
git add .
git commit -m "feat: complete Encontrar Licitações feature (redesign M3 com integração calendário)"
```
