# Deploy LicitaFácil na VPS + MCP para Claude Desktop

## Parte 1: Deploy na VPS (Ubuntu/Debian)

### 1.1 Preparar a VPS

```bash
# Conectar via SSH
ssh root@SEU_IP_VPS

# Atualizar sistema
apt update && apt upgrade -y

# Instalar dependências
apt install -y python3.11 python3.11-venv python3-pip nginx git sqlite3 supervisor
```

### 1.2 Criar usuário para a aplicação

```bash
# Criar usuário
useradd -m -s /bin/bash licitafacil
cd /home/licitafacil
```

### 1.3 Clonar/Transferir o projeto

**Opção A - Via Git (se tiver repositório):**
```bash
git clone https://seu-repo.git /home/licitafacil/app
```

**Opção B - Via SCP (transferir arquivos locais):**
```bash
# No seu PC Windows, execute:
scp -r "d:\Analise de Capacitade Técnica\licitafacil" root@SEU_IP_VPS:/home/licitafacil/app
```

### 1.4 Configurar ambiente Python

```bash
cd /home/licitafacil/app

# Criar ambiente virtual
python3.11 -m venv venv
source venv/bin/activate

# Instalar dependências
pip install -r requirements.txt

# Instalar também o uvicorn e gunicorn para produção
pip install gunicorn uvicorn[standard]
```

### 1.5 Configurar variáveis de ambiente

```bash
# Criar arquivo .env
cat > /home/licitafacil/app/backend/.env << 'EOF'
SECRET_KEY=sua_chave_secreta_aqui_gere_com_openssl_rand_hex_32
OPENAI_API_KEY=sua_chave_openai
ANTHROPIC_API_KEY=sua_chave_anthropic
DATABASE_URL=sqlite:///./licitafacil.db
ADMIN_EMAIL=admin@licitafacil.com.br
ADMIN_PASSWORD=SenhaSegura123!
EOF
```

### 1.6 Configurar Supervisor (gerenciador de processos)

```bash
cat > /etc/supervisor/conf.d/licitafacil.conf << 'EOF'
[program:licitafacil]
directory=/home/licitafacil/app/backend
command=/home/licitafacil/app/venv/bin/gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker -b 127.0.0.1:8000
user=licitafacil
autostart=true
autorestart=true
stderr_logfile=/var/log/licitafacil/error.log
stdout_logfile=/var/log/licitafacil/access.log
environment=PATH="/home/licitafacil/app/venv/bin"
EOF

# Criar diretório de logs
mkdir -p /var/log/licitafacil
chown licitafacil:licitafacil /var/log/licitafacil

# Recarregar supervisor
supervisorctl reread
supervisorctl update
supervisorctl start licitafacil
```

### 1.7 Configurar Nginx (proxy reverso)

```bash
cat > /etc/nginx/sites-available/licitafacil << 'EOF'
server {
    listen 80;
    server_name _;  # Aceita qualquer host (IP direto)

    # Frontend estático
    location / {
        root /home/licitafacil/app/frontend;
        index index.html;
        try_files $uri $uri/ /index.html;
    }

    # API Backend
    location /api/ {
        proxy_pass http://127.0.0.1:8000/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
        client_max_body_size 50M;
    }

    # Arquivos de upload
    location /uploads/ {
        alias /home/licitafacil/app/backend/uploads/;
    }
}
EOF

# Ativar site
ln -sf /etc/nginx/sites-available/licitafacil /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default

# Testar e reiniciar nginx
nginx -t
systemctl restart nginx
```

### 1.8 Ajustar permissões

```bash
chown -R licitafacil:licitafacil /home/licitafacil/app
chmod -R 755 /home/licitafacil/app
```

### 1.9 Configurar Firewall

```bash
ufw allow 22    # SSH
ufw allow 80    # HTTP
ufw allow 443   # HTTPS (futuro)
ufw allow 3333  # MCP Server
ufw enable
```

### 1.10 Testar

Acesse no navegador: `http://SEU_IP_VPS`

---

## Parte 2: MCP Server para Claude Desktop

### 2.1 Criar o servidor MCP

Crie o arquivo `/home/licitafacil/app/mcp_server.py`:

```python
#!/usr/bin/env python3
"""
MCP Server para LicitaFácil
Permite que Claude Desktop acesse o banco de dados de atestados
"""

import json
import sqlite3
from typing import Any
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# Inicializar servidor MCP
server = Server("licitafacil-mcp")

DATABASE_PATH = "/home/licitafacil/app/backend/licitafacil.db"

def get_db_connection():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@server.list_tools()
async def list_tools() -> list[Tool]:
    """Lista as ferramentas disponíveis"""
    return [
        Tool(
            name="listar_atestados",
            description="Lista todos os atestados com resumo (id, contratante, descrição)",
            inputSchema={
                "type": "object",
                "properties": {
                    "limite": {
                        "type": "integer",
                        "description": "Número máximo de atestados (default: 50)",
                        "default": 50
                    }
                }
            }
        ),
        Tool(
            name="buscar_atestado",
            description="Busca um atestado específico pelo ID com todos os detalhes",
            inputSchema={
                "type": "object",
                "properties": {
                    "id": {
                        "type": "integer",
                        "description": "ID do atestado"
                    }
                },
                "required": ["id"]
            }
        ),
        Tool(
            name="buscar_servicos",
            description="Busca serviços por palavra-chave na descrição",
            inputSchema={
                "type": "object",
                "properties": {
                    "termo": {
                        "type": "string",
                        "description": "Termo para buscar nos serviços"
                    }
                },
                "required": ["termo"]
            }
        ),
        Tool(
            name="estatisticas",
            description="Retorna estatísticas gerais dos atestados",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="listar_contratantes",
            description="Lista todos os contratantes únicos",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="atestados_por_contratante",
            description="Lista atestados de um contratante específico",
            inputSchema={
                "type": "object",
                "properties": {
                    "contratante": {
                        "type": "string",
                        "description": "Nome (parcial) do contratante"
                    }
                },
                "required": ["contratante"]
            }
        ),
        Tool(
            name="executar_sql",
            description="Executa uma consulta SQL personalizada (somente SELECT)",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Consulta SQL (apenas SELECT)"
                    }
                },
                "required": ["query"]
            }
        )
    ]

@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Executa uma ferramenta"""

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        if name == "listar_atestados":
            limite = arguments.get("limite", 50)
            cursor.execute('''
                SELECT id, contratante, descricao_servico, data_emissao, created_at
                FROM atestados
                ORDER BY id DESC
                LIMIT ?
            ''', (limite,))
            rows = cursor.fetchall()
            result = [dict(row) for row in rows]
            return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]

        elif name == "buscar_atestado":
            atestado_id = arguments["id"]
            cursor.execute('SELECT * FROM atestados WHERE id = ?', (atestado_id,))
            row = cursor.fetchone()
            if row:
                result = dict(row)
                # Parse servicos_json
                if result.get("servicos_json"):
                    try:
                        result["servicos"] = json.loads(result["servicos_json"])
                        del result["servicos_json"]
                    except:
                        pass
                # Remover texto_extraido para não poluir
                if "texto_extraido" in result:
                    result["texto_extraido"] = f"[{len(result['texto_extraido'] or '')} caracteres]"
                return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]
            return [TextContent(type="text", text="Atestado não encontrado")]

        elif name == "buscar_servicos":
            termo = arguments["termo"]
            cursor.execute('SELECT id, contratante, servicos_json FROM atestados WHERE servicos_json IS NOT NULL')
            resultados = []
            for row in cursor.fetchall():
                try:
                    servicos = json.loads(row["servicos_json"])
                    for s in servicos:
                        if termo.lower() in s.get("descricao", "").lower():
                            resultados.append({
                                "atestado_id": row["id"],
                                "contratante": row["contratante"],
                                "item": s.get("item"),
                                "descricao": s.get("descricao"),
                                "quantidade": s.get("quantidade"),
                                "unidade": s.get("unidade")
                            })
                except:
                    pass
            return [TextContent(type="text", text=json.dumps(resultados, ensure_ascii=False, indent=2))]

        elif name == "estatisticas":
            stats = {}
            cursor.execute('SELECT COUNT(*) FROM atestados')
            stats["total_atestados"] = cursor.fetchone()[0]

            cursor.execute('SELECT COUNT(DISTINCT contratante) FROM atestados WHERE contratante IS NOT NULL')
            stats["contratantes_unicos"] = cursor.fetchone()[0]

            # Contar serviços
            cursor.execute('SELECT servicos_json FROM atestados WHERE servicos_json IS NOT NULL')
            total_servicos = 0
            for row in cursor.fetchall():
                try:
                    servicos = json.loads(row[0])
                    if servicos:
                        total_servicos += len(servicos)
                except:
                    pass
            stats["total_servicos"] = total_servicos

            return [TextContent(type="text", text=json.dumps(stats, ensure_ascii=False, indent=2))]

        elif name == "listar_contratantes":
            cursor.execute('''
                SELECT contratante, COUNT(*) as total
                FROM atestados
                WHERE contratante IS NOT NULL
                GROUP BY contratante
                ORDER BY total DESC
            ''')
            result = [{"contratante": row[0], "total_atestados": row[1]} for row in cursor.fetchall()]
            return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]

        elif name == "atestados_por_contratante":
            contratante = arguments["contratante"]
            cursor.execute('''
                SELECT id, contratante, descricao_servico, data_emissao
                FROM atestados
                WHERE contratante LIKE ?
                ORDER BY id
            ''', (f'%{contratante}%',))
            result = [dict(row) for row in cursor.fetchall()]
            return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]

        elif name == "executar_sql":
            query = arguments["query"].strip().upper()
            if not query.startswith("SELECT"):
                return [TextContent(type="text", text="Erro: Apenas consultas SELECT são permitidas")]

            cursor.execute(arguments["query"])
            columns = [description[0] for description in cursor.description]
            rows = cursor.fetchall()
            result = [dict(zip(columns, row)) for row in rows]
            return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]

        else:
            return [TextContent(type="text", text=f"Ferramenta desconhecida: {name}")]

    finally:
        conn.close()

async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```

### 2.2 Instalar dependência MCP

```bash
cd /home/licitafacil/app
source venv/bin/activate
pip install mcp
```

### 2.3 Testar o servidor MCP localmente

```bash
python mcp_server.py
```

---

## Parte 3: Configurar Claude Desktop

### 3.1 Localizar arquivo de configuração

**Windows:**
```
%APPDATA%\Claude\claude_desktop_config.json
```

**Mac:**
```
~/Library/Application Support/Claude/claude_desktop_config.json
```

### 3.2 Configuração para conexão LOCAL (mesmo PC)

Se o banco está no seu PC Windows, edite o `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "licitafacil": {
      "command": "python",
      "args": ["d:\\Analise de Capacitade Técnica\\licitafacil\\mcp_server.py"],
      "env": {}
    }
  }
}
```

### 3.3 Configuração para conexão REMOTA (VPS)

Para acessar a VPS remotamente, você precisa de um wrapper SSH:

**Opção A - Via SSH direto:**

```json
{
  "mcpServers": {
    "licitafacil": {
      "command": "ssh",
      "args": [
        "-i", "C:\\Users\\SEU_USER\\.ssh\\id_rsa",
        "licitafacil@SEU_IP_VPS",
        "/home/licitafacil/app/venv/bin/python",
        "/home/licitafacil/app/mcp_server.py"
      ]
    }
  }
}
```

**Opção B - Via túnel SSH (mais seguro):**

1. Criar túnel SSH permanente:
```bash
ssh -N -L 3333:localhost:3333 licitafacil@SEU_IP_VPS
```

2. Configurar MCP via HTTP (requer modificação do servidor)

---

## Parte 4: Criar MCP Server Local (Windows)

Se preferir rodar o MCP localmente no Windows, crie o arquivo:

`d:\Analise de Capacitade Técnica\licitafacil\mcp_server.py`

E ajuste o DATABASE_PATH:

```python
DATABASE_PATH = r"d:\Analise de Capacitade Técnica\licitafacil\backend\licitafacil.db"
```

Depois configure o Claude Desktop:

```json
{
  "mcpServers": {
    "licitafacil": {
      "command": "d:\\Analise de Capacitade Técnica\\licitafacil\\venv\\Scripts\\python.exe",
      "args": ["d:\\Analise de Capacitade Técnica\\licitafacil\\mcp_server.py"]
    }
  }
}
```

---

## Comandos Úteis

### VPS
```bash
# Ver status do servidor
supervisorctl status licitafacil

# Reiniciar aplicação
supervisorctl restart licitafacil

# Ver logs
tail -f /var/log/licitafacil/error.log

# Reiniciar nginx
systemctl restart nginx
```

### Backup do banco
```bash
# Na VPS
sqlite3 /home/licitafacil/app/backend/licitafacil.db ".backup backup_$(date +%Y%m%d).db"
```
