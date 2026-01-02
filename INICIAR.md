# LicitaFácil - Instruções de Instalação e Execução

## Requisitos
- Python 3.10 ou superior
- pip (gerenciador de pacotes Python)

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
Copie o arquivo `.env.example` para `.env` e configure:
```bash
cp .env.example .env
```

Edite o arquivo `.env` com suas configurações:
- `SECRET_KEY`: Gere uma chave segura com `openssl rand -hex 32`
- `OPENAI_API_KEY`: Sua chave da API OpenAI
- `ADMIN_EMAIL`: Email do administrador inicial
- `ADMIN_PASSWORD`: Senha do administrador inicial

### 5. Criar administrador inicial
```bash
cd backend
python seed.py
```

## Execução

### Iniciar o servidor
```bash
cd backend
python main.py
```

Ou com uvicorn:
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Acessar o sistema
- **Frontend:** Abra o arquivo `frontend/index.html` no navegador
- **API Docs:** http://localhost:8000/docs
- **API ReDoc:** http://localhost:8000/redoc

## Estrutura do Projeto
```
licitafacil/
├── backend/           # API FastAPI
│   ├── main.py        # Ponto de entrada
│   ├── models.py      # Modelos do banco de dados
│   ├── schemas.py     # Schemas Pydantic
│   ├── auth.py        # Autenticação JWT
│   ├── database.py    # Conexão com banco
│   ├── seed.py        # Script para criar admin
│   ├── routers/       # Rotas da API
│   └── services/      # Serviços (PDF, OCR, IA)
├── frontend/          # Interface web
│   ├── index.html     # Login/Registro
│   ├── dashboard.html # Dashboard
│   ├── atestados.html # Gestão de atestados
│   ├── analises.html  # Análises de licitações
│   ├── admin.html     # Painel administrativo
│   ├── css/           # Estilos
│   └── js/            # JavaScript
├── uploads/           # Arquivos enviados pelos usuários
├── requirements.txt   # Dependências Python
└── .env.example       # Exemplo de variáveis de ambiente
```

## Credenciais Padrão
- **Email:** admin@licitafacil.com.br
- **Senha:** admin123 (altere após o primeiro login!)

## Cores do Sistema
- **Primária (Âmbar):** #F59E0B
- **Secundária (Cinza escuro):** #1F2937
