# Roteiro de Finalização de Sessão - LicitaFacil

## Checklist Rápido

```bash
# 1. Rodar testes
cd backend && python -m pytest tests/ -q

# 2. Verificar código
python -m mypy . --ignore-missing-imports
python -m ruff check .

# 3. Commit
git status
git add <arquivos>
git commit -m "descrição"
```

---

## Checklist Detalhado

### 1. Verificar Backend

```bash
cd licitafacil/backend

# Testes
python -m pytest tests/ -q

# Type check
python -m mypy . --ignore-missing-imports

# Lint
python -m ruff check .
```

### 2. Verificar Frontend (se houve alterações)

- Verificar se não há erros de sintaxe nos arquivos JS
- Testar manualmente as páginas alteradas no navegador

### 3. Banco de Dados

- Se houve alterações em models, verificar se migrations estão atualizadas
- Comando: `alembic revision --autogenerate -m "descricao"`

### 4. Git - Commit das Alterações

```bash
# Ver status
git status

# Adicionar arquivos específicos (evitar git add .)
git add <arquivos>

# Commit com mensagem clara
git commit -m "feat/fix/refactor: descrição clara da alteração"

# Push (se necessário)
git push origin main
```

### 5. Documentar Pendências

Ao final de cada sessão, anotar:

- [ ] Bugs conhecidos não resolvidos
- [ ] Features incompletas
- [ ] Decisões técnicas tomadas
- [ ] Próximos passos sugeridos

### 6. Estado do Ambiente

- [ ] Parar servidor de desenvolvimento (`Ctrl+C`)
- [ ] Verificar se não há processos Python órfãos
- [ ] Fechar conexões de banco se necessário

---

## Comandos Úteis

| Ação | Comando |
|------|---------|
| Rodar servidor | `cd backend && uvicorn main:app --reload` |
| Rodar testes | `python -m pytest tests/ -q` |
| Rodar teste específico | `python -m pytest tests/test_arquivo.py -v` |
| Type check | `python -m mypy . --ignore-missing-imports` |
| Lint | `python -m ruff check .` |
| Lint com fix | `python -m ruff check . --fix` |
| Ver migrations | `alembic history` |
| Aplicar migrations | `alembic upgrade head` |

---

## Estrutura do Projeto

```
licitafacil/
├── backend/           # API FastAPI
│   ├── routers/       # Endpoints
│   ├── services/      # Lógica de negócio
│   ├── models.py      # Modelos SQLAlchemy
│   ├── schemas.py     # Schemas Pydantic
│   └── tests/         # Testes pytest
├── frontend/          # Interface web
│   ├── js/            # JavaScript
│   ├── css/           # Estilos
│   └── *.html         # Páginas
└── .env               # Configurações (não commitar)
```

---

## Contatos e Recursos

- **Banco de Dados**: Supabase PostgreSQL
- **Deploy Backend**: Render
- **Deploy Frontend**: Vercel
