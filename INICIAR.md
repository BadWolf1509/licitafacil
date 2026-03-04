# LicitaFácil - Guia de Instalação

## Requisitos

- Python 3.13 ou superior
- pip (gerenciador de pacotes Python)
- Acesso a banco PostgreSQL via Supabase (obrigatório)

## Instalação

### 1. Criar ambiente virtual

```bash
cd licitafacil
python -m venv venv
```

### 2. Ativar ambiente virtual

**Windows:**
```bash
venv\Scripts\activate
```

**Linux/Mac:**
```bash
source venv/bin/activate
```

### 3. Instalar dependências

```bash
pip install -r requirements.txt
```

### 4. Configurar variáveis de ambiente

```bash
# Windows
copy .env.example .env

# Linux/Mac
cp .env.example .env
```

Edite o arquivo `.env`:

```env
# Obrigatório - gere uma chave segura
SECRET_KEY=<gere com: openssl rand -hex 32>

# Obrigatório - PostgreSQL via Supabase (Transaction mode, porta 6543)
DATABASE_URL=postgresql://postgres.[ref]:[password]@aws-0-sa-east-1.pooler.supabase.com:6543/postgres

# Admin inicial (opcional - tem valores padrão)
ADMIN_EMAIL=admin@licitafacil.com.br
ADMIN_PASSWORD=admin123
ADMIN_NAME=Administrador
```

### 5. Criar administrador inicial

```bash
cd backend
python seed.py
```

## Execução

### Iniciar o servidor

```bash
cd backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Ou diretamente:
```bash
cd backend
python main.py
```

### Acessar o sistema

| Recurso | URL |
|---------|-----|
| Frontend | http://localhost:8000 |
| API Docs | http://localhost:8000/docs |
| ReDoc | http://localhost:8000/redoc |

## Estrutura do Projeto

```
licitafacil/
├── backend/
│   ├── alembic/       # Migrations
│   ├── models/        # Modelos SQLAlchemy (package)
│   ├── schemas/       # Schemas Pydantic (package)
│   ├── repositories/  # Repositórios de dados
│   ├── routers/       # Endpoints da API
│   ├── services/      # Lógica de negócio
│   ├── tests/         # Testes automatizados (1372+)
│   ├── main.py        # Ponto de entrada
│   ├── auth.py        # Autenticação JWT
│   ├── database.py    # Conexão com banco
│   └── seed.py        # Script para criar admin
├── docs/
│   ├── planos/        # Planos de implementação
│   └── referencias/   # Referências técnicas
├── frontend/
│   ├── css/           # Estilos
│   ├── js/            # JavaScript
│   ├── index.html     # Login/Registro
│   ├── dashboard.html # Dashboard
│   ├── atestados.html # Gestão de atestados
│   ├── analises.html  # Análises
│   ├── licitacoes.html   # Gestão de licitações (M1)
│   ├── calendario.html   # Calendário e lembretes (M2)
│   ├── encontrar.html    # Monitoramento PNCP (M3)
│   ├── documentos.html   # Gestão documental (M4)
│   ├── admin.html     # Painel admin
│   └── perfil.html    # Perfil do usuário
├── requirements.txt   # Dependências
└── .env.example       # Exemplo de config
```

## Credenciais Padrão

- **Email:** admin@licitafacil.com.br
- **Senha:** admin123

**Importante:** Altere a senha após o primeiro login!

## Executar Testes

```bash
cd backend
pytest -v
```

## Migrations (Alembic)

```bash
cd backend

# Verificar status
alembic current

# Aplicar migrations pendentes
alembic upgrade head

# Criar nova migration (após alterar models.py)
alembic revision --autogenerate -m "descricao"
```

## Cores do Sistema

| Elemento | Cor |
|----------|-----|
| Primária (Âmbar) | #F59E0B |
| Secundária (Cinza escuro) | #1F2937 |
| Sucesso | #10B981 |
| Erro | #EF4444 |
