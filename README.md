# LicitaFácil

Sistema para extração de dados de atestados de capacidade técnica e análise de exigências de editais de licitação.

## Visão Geral

O LicitaFácil automatiza o processo de análise de qualificação técnica em licitações:

1. **Upload de Atestados** - Extrai serviços, quantidades e metadados de PDFs/imagens
2. **Análise de Editais** - Identifica exigências técnicas quantitativas
3. **Matching Automático** - Compara atestados disponíveis com exigências do edital
4. **Recomendação** - Sugere quais atestados apresentar para cada exigência

## Tecnologias

### Backend
- **Framework:** FastAPI + SQLAlchemy
- **Banco:** SQLite (desenvolvimento) / PostgreSQL (produção)
- **Migrations:** Alembic
- **Extração PDF:** pdfplumber + PyMuPDF
- **OCR:** EasyOCR + Tesseract (fallback)

### Frontend
- HTML5, CSS3, JavaScript (vanilla)
- Design responsivo com menu hamburger mobile
- Tema claro/escuro configurável por usuário

## Funcionalidades

### Atestados
- Upload de PDF e imagens (PNG, JPG, JPEG, WEBP)
- Extração automática de tabela de serviços
- Reprocessamento de documentos
- Edição manual de serviços extraídos

### Análises
- Upload de página de edital com quantitativos
- Matching determinístico por similaridade de descrição
- Soma de atestados para atingir exigências
- Visualização de cobertura por exigência

### Usuários
- Autenticação JWT
- Aprovação de novos usuários por admin
- Página de perfil com alteração de senha
- Preferência de tema (claro/escuro)

## Instalação Rápida

```bash
# Clonar repositório
git clone https://github.com/seu-usuario/licitafacil.git
cd licitafacil

# Criar ambiente virtual
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

# Instalar dependências
pip install -r requirements.txt

# Configurar ambiente
cp .env.example .env
# Editar .env com suas configurações

# Executar migrações de banco
cd backend
alembic upgrade head

# Criar admin inicial
python seed.py

# Iniciar servidor
uvicorn main:app --reload --port 8000
```

**Acesso:** http://localhost:8000

## Variáveis de Ambiente

### Obrigatórias
```env
SECRET_KEY=<gere com: openssl rand -hex 32>
```

### Opcionais
```env
# Banco de dados (default: SQLite local)
DATABASE_URL=sqlite:///./licitafacil.db

# Admin inicial
ADMIN_EMAIL=admin@licitafacil.com.br
ADMIN_PASSWORD=admin123
ADMIN_NAME=Administrador

# JWT
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# OCR
OCR_TESSERACT_FALLBACK=true

# Uploads
UPLOAD_DIR=uploads
MAX_UPLOAD_SIZE=10485760
```

## Estrutura do Projeto

```
licitafacil/
├── backend/
│   ├── alembic/           # Migrations de banco
│   ├── config/            # Configurações
│   ├── docs/              # Documentação técnica
│   ├── prompts/           # Prompts (legado)
│   ├── repositories/      # Repositórios de dados
│   ├── routers/           # Endpoints da API
│   ├── services/          # Lógica de negócio
│   │   ├── aditivo/       # Processamento de aditivos
│   │   ├── atestado/      # Processamento de atestados
│   │   ├── extraction/    # Módulos de extração
│   │   ├── processors/    # Processadores de texto
│   │   └── table_extraction/  # Extração de tabelas
│   ├── tests/             # Testes unitários (341 testes)
│   └── utils/             # Utilitários
├── frontend/
│   ├── css/               # Estilos
│   ├── js/                # JavaScript
│   └── *.html             # Páginas
├── requirements.txt       # Dependências Python
└── .env.example           # Exemplo de configuração
```

## API Endpoints

### Autenticação (`/api/v1/auth`)
| Método | Endpoint | Descrição |
|--------|----------|-----------|
| POST | `/login` | Login (form-data) |
| POST | `/login-json` | Login (JSON) |
| POST | `/registrar` | Novo usuário |
| GET | `/me` | Dados do usuário logado |
| PUT | `/me` | Atualizar perfil |
| POST | `/change-password` | Alterar senha |

### Atestados (`/api/v1/atestados`)
| Método | Endpoint | Descrição |
|--------|----------|-----------|
| GET | `/` | Listar atestados |
| POST | `/` | Criar manualmente |
| POST | `/upload` | Upload de documento |
| GET | `/{id}` | Obter atestado |
| PUT | `/{id}` | Atualizar atestado |
| PATCH | `/{id}/servicos` | Atualizar serviços |
| POST | `/{id}/reprocess` | Reprocessar |
| DELETE | `/{id}` | Excluir |

### Análises (`/api/v1/analises`)
| Método | Endpoint | Descrição |
|--------|----------|-----------|
| GET | `/` | Listar análises |
| POST | `/` | Criar análise |
| GET | `/{id}` | Obter análise |
| POST | `/{id}/processar` | Processar matching |
| DELETE | `/{id}` | Excluir |

### Admin (`/api/v1/admin`)
| Método | Endpoint | Descrição |
|--------|----------|-----------|
| GET | `/usuarios` | Listar usuários |
| POST | `/usuarios/{id}/aprovar` | Aprovar usuário |
| POST | `/usuarios/{id}/toggle-status` | Ativar/desativar |
| POST | `/usuarios/{id}/toggle-admin` | Promover/rebaixar admin |

## Pipeline de Processamento

### Atestados
```
PDF/Imagem
    ↓
Extração de texto (pdfplumber)
    ↓
OCR se necessário (EasyOCR/Tesseract)
    ↓
Extração de tabelas
    ↓
Detecção de aditivos (prefixos S1-, S2-)
    ↓
Normalização e deduplicação
    ↓
Serviços extraídos
```

### Matching
```
Exigências do Edital + Atestados do Usuário
    ↓
Normalização de unidades e descrições
    ↓
Cálculo de similaridade (keywords)
    ↓
Soma de quantidades por exigência
    ↓
Seleção greedy de atestados
    ↓
Resultado: atende/parcial/não_atende
```

## Deploy

### Desenvolvimento Local
Veja instruções acima.

### Produção (Vercel + Supabase)
Consulte [DEPLOY_VERCEL.md](DEPLOY_VERCEL.md) para instruções detalhadas.

## Migrações de Banco de Dados

O projeto usa Alembic para gerenciar migrações do banco de dados.

### Executar migrações pendentes
```bash
cd backend
alembic upgrade head
```

### Verificar status das migrações
```bash
alembic current
alembic history
```

### Migrações recentes
- `c3e7f58106ee` - Adiciona campos de bloqueio de conta (failed_login_attempts, locked_until)
- `d4f8g69217ff` - Adiciona tabela de audit logs para registro de ações administrativas

### Criar nova migração
```bash
alembic revision --autogenerate -m "descricao_da_mudanca"
```

### Reverter última migração
```bash
alembic downgrade -1
```

## Testes

```bash
cd backend
pytest -v
```

**Cobertura:** 341+ testes passando

## Credenciais Padrão

- **Email:** admin@licitafacil.com.br
- **Senha:** admin123

**Altere após o primeiro login!**

## Licença

Proprietário. Todos os direitos reservados.
