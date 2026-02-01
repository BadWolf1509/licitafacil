# Deploy na Vercel + Supabase

Guia para deploy do LicitaFácil usando **apenas Vercel e Supabase**, sem necessidade de Railway ou outro serviço de backend.

## Arquitetura

```
┌─────────────────────────────────────────┐     ┌─────────────────┐
│              Vercel                      │     │    Supabase     │
│  ┌──────────────┐  ┌──────────────────┐ │     │                 │
│  │   Frontend   │  │ Serverless Funcs │ │────▶│  PostgreSQL     │
│  │  HTML/CSS/JS │  │  FastAPI/Python  │ │     │  Storage        │
│  └──────────────┘  └──────────────────┘ │     │                 │
└─────────────────────────────────────────┘     └─────────────────┘
```

## Limitações do Modo Serverless

| Aspecto | Limite |
|---------|--------|
| Timeout | 10s (Hobby) / 60s (Pro) |
| Memória | 1024 MB |
| Pacote | ~50 MB |
| Cold Start | 1-3 segundos |

**Nota:** Documentos complexos podem exceder o timeout. Para casos assim, considere:
- Usar plano Pro da Vercel (60s timeout)
- Usar OCR externo via API (Google Vision, AWS Textract)

---

## Passo 1: Configurar Supabase

### 1.1 Criar Projeto

1. Acesse [supabase.com](https://supabase.com) e crie um projeto
2. Anote as credenciais em **Settings > API**:
   - `Project URL` → `SUPABASE_URL`
   - `anon public` → `SUPABASE_ANON_KEY`
   - `service_role` → `SUPABASE_SERVICE_KEY`

### 1.2 Configurar Banco de Dados

No **SQL Editor** do Supabase, execute:

```sql
-- Cole o conteúdo de supabase_migration.sql
```

### 1.3 Configurar Connection String

Em **Settings > Database**, copie a **Connection string (URI)** em modo `Transaction`:

```
postgresql://postgres.[ref]:[password]@aws-0-sa-east-1.pooler.supabase.com:6543/postgres
```

---

## Passo 2: Deploy na Vercel

### 2.1 Via CLI (Recomendado)

```bash
# Instalar Vercel CLI
npm i -g vercel

# Login
vercel login

# Deploy (na raiz do projeto)
cd licitafacil
vercel
```

### 2.2 Configurar Variáveis de Ambiente

No painel Vercel (**Settings > Environment Variables**):

```env
# Banco de dados (obrigatório)
DATABASE_URL=postgresql://postgres.[ref]:[password]@aws-0-sa-east-1.pooler.supabase.com:6543/postgres

# Supabase (obrigatório)
SUPABASE_URL=https://[ref].supabase.co
SUPABASE_ANON_KEY=eyJ...
SUPABASE_SERVICE_KEY=eyJ...

# Autenticação (obrigatório)
SECRET_KEY=<gere-com: openssl rand -hex 32>
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# Admin inicial (primeira execução)
ADMIN_EMAIL=admin@seudominio.com
ADMIN_PASSWORD=SenhaSegura123!
ADMIN_NAME=Administrador

# Ambiente
ENVIRONMENT=production
PROCESSING_MODE=sync

# OCR
OCR_PREFER_TESSERACT=true
```

### 2.3 Deploy para Produção

```bash
vercel --prod
```

---

## Passo 3: Verificar Deploy

### 3.1 Testar Health Check

```bash
curl https://seu-projeto.vercel.app/api/v1/health
```

Resposta esperada:
```json
{"status": "healthy", "mode": "serverless"}
```

### 3.2 Testar Login

```bash
curl -X POST https://seu-projeto.vercel.app/api/v1/auth/login \
  -d "username=admin@seudominio.com&password=SenhaSegura123!"
```

### 3.3 Testar no Browser

1. Acesse `https://seu-projeto.vercel.app`
2. Faça login com credenciais de admin
3. Teste upload de um atestado simples (PDF pequeno)

---

## Estrutura do Projeto

```
licitafacil/
├── api/
│   ├── index.py           # Entry point serverless
│   └── requirements.txt   # Deps otimizadas (sem EasyOCR)
├── frontend/              # Arquivos estáticos
├── backend/               # Código Python
├── vercel.json            # Configuração Vercel
└── .vercel/
    └── project.json       # Link do projeto
```

---

## Configuração vercel.json

```json
{
  "builds": [
    {"src": "api/index.py", "use": "@vercel/python"},
    {"src": "frontend/**", "use": "@vercel/static"}
  ],
  "routes": [
    {"src": "/api/(.*)", "dest": "/api/index.py"},
    {"src": "/(.*)", "dest": "/frontend/$1"}
  ],
  "functions": {
    "api/index.py": {
      "memory": 1024,
      "maxDuration": 60
    }
  }
}
```

---

## Diferenças do Modo Serverless

### Upload de Atestados

**Modo Tradicional (VPS):**
1. Usuário faz upload
2. Sistema retorna `job_id`
3. Usuário consulta status
4. Quando pronto, atestado aparece na lista

**Modo Serverless (Vercel):**
1. Usuário faz upload
2. Sistema processa **imediatamente**
3. Retorna atestado completo ou erro
4. Tempo limite: 60 segundos

### Código do Frontend

O frontend detecta automaticamente o modo e se adapta:
- Em serverless: aguarda resposta completa
- Em tradicional: faz polling do status

---

## Troubleshooting

### Erro: Function Timeout

**Causa:** Documento muito complexo para processar em 60s.

**Soluções:**
1. Usar documentos mais simples
2. Upgrade para Vercel Pro
3. Integrar OCR externo (Google Vision API)

### Erro: Module Not Found

**Causa:** Dependência pesada não incluída.

**Solução:** Verificar `api/requirements.txt` - EasyOCR foi removido intencionalmente.

### Erro: Database Connection

**Causa:** `DATABASE_URL` incorreta ou Supabase inacessível.

**Solução:**
1. Verificar string de conexão
2. Usar modo `Transaction` (porta 6543)
3. Verificar se IP da Vercel está permitido

### CORS Error

**Causa:** Origem não permitida.

**Solução:** Verificar se a URL do frontend está em `CORS_ORIGINS`.

---

## Custos

| Serviço | Plano | Custo |
|---------|-------|-------|
| Vercel | Hobby | Grátis |
| Vercel | Pro | $20/mês |
| Supabase | Free | Grátis |
| Supabase | Pro | $25/mês |

**Recomendação:**
- Desenvolvimento/teste: Grátis
- Produção pequena: Vercel Pro + Supabase Free = $20/mês
- Produção maior: Vercel Pro + Supabase Pro = $45/mês

---

## Comandos Úteis

```bash
# Deploy preview (branch)
vercel

# Deploy produção
vercel --prod

# Ver logs
vercel logs

# Listar variáveis
vercel env ls

# Adicionar variável
vercel env add DATABASE_URL

# Remover projeto do link local
rm -rf .vercel
```

---

## Migração de VPS para Vercel

Se você já tem dados em um VPS:

1. **Exportar dados do banco atual:**
   ```bash
   pg_dump -h localhost -U user dbname > backup.sql
   ```

2. **Importar no Supabase:**
   - SQL Editor > Run SQL > Cole o backup

3. **Migrar arquivos:**
   - Upload para Supabase Storage
   - Atualizar paths no banco

4. **Testar no Vercel preview** antes de migrar DNS

---

## Próximos Passos

1. Configurar domínio customizado na Vercel
2. Habilitar SSL automático
3. Configurar monitoramento (Vercel Analytics)
4. Configurar backups automáticos do Supabase
