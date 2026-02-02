# Deploy na Vercel + Supabase

Guia para deploy do LicitaFácil usando Vercel (frontend + serverless functions) e Supabase (PostgreSQL).

## Arquitetura

```
┌─────────────────────────────────────────┐     ┌─────────────────┐
│              Vercel                      │     │    Supabase     │
│  ┌──────────────┐  ┌──────────────────┐ │     │                 │
│  │   Frontend   │  │ Serverless Funcs │ │────▶│  PostgreSQL     │
│  │  HTML/CSS/JS │  │  FastAPI/Python  │ │     │                 │
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

**Nota:** O sistema usa processamento local (OCR, pdfplumber). Documentos complexos podem exceder o timeout em planos gratuitos.

---

## Passo 1: Configurar Supabase

### 1.1 Criar Projeto

1. Acesse [supabase.com](https://supabase.com) e crie um projeto
2. Anote as credenciais em **Settings > API**:
   - `Project URL` → `SUPABASE_URL`
   - `service_role` → `SUPABASE_SERVICE_KEY`

### 1.2 Configurar Connection String

Em **Settings > Database**, copie a **Connection string (URI)** em modo `Transaction`:

```
postgresql://postgres.[ref]:[password]@aws-0-sa-east-1.pooler.supabase.com:6543/postgres
```

---

## Passo 2: Deploy na Vercel

### 2.1 Via CLI

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

# Autenticação (obrigatório)
SECRET_KEY=<gere-com: openssl rand -hex 32>

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

---

## Estrutura do Projeto

```
licitafacil/
├── api/
│   └── index.py           # Entry point serverless
├── frontend/              # Arquivos estáticos
├── backend/               # Código Python
├── vercel.json            # Configuração Vercel
└── .vercelignore          # Arquivos ignorados
```

---

## Diferenças do Modo Serverless

### Upload de Atestados

| Modo | Comportamento |
|------|---------------|
| Tradicional (VPS) | Retorna `job_id`, polling de status |
| Serverless (Vercel) | Processa imediatamente, retorna resultado |

O frontend detecta automaticamente o modo e se adapta.

---

## Troubleshooting

### Erro: Function Timeout

**Causa:** Documento muito complexo para processar em 60s.

**Soluções:**
1. Usar documentos mais simples
2. Upgrade para Vercel Pro (60s timeout)

### Erro: Database Connection

**Causa:** `DATABASE_URL` incorreta.

**Solução:**
1. Verificar string de conexão
2. Usar modo `Transaction` (porta 6543)

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
# Deploy preview
vercel

# Deploy produção
vercel --prod

# Ver logs
vercel logs

# Listar variáveis
vercel env ls

# Adicionar variável
vercel env add DATABASE_URL
```

---

## Migração de VPS para Vercel

1. **Exportar dados do banco atual:**
   ```bash
   pg_dump -h localhost -U user dbname > backup.sql
   ```

2. **Importar no Supabase:**
   - SQL Editor > Run SQL > Cole o backup

3. **Testar no Vercel preview** antes de migrar DNS
