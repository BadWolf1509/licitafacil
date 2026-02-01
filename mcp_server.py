#!/usr/bin/env python3
"""
MCP Server para LicitaFácil
Permite que Claude Desktop acesse o banco de dados de atestados
"""

import json
import sqlite3
import os
from typing import Any
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# Inicializar servidor MCP
server = Server("licitafacil-mcp")

# Detectar caminho do banco de dados
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_PATH = os.path.join(SCRIPT_DIR, "backend", "licitafacil.db")

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
            description="Lista todos os atestados com resumo (id, contratante, descrição). Use para ter visão geral.",
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
            description="Busca um atestado específico pelo ID com todos os detalhes incluindo lista de serviços",
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
            description="Busca serviços por palavra-chave na descrição. Útil para encontrar experiência em tipos específicos de serviço.",
            inputSchema={
                "type": "object",
                "properties": {
                    "termo": {
                        "type": "string",
                        "description": "Termo para buscar nos serviços (ex: 'alvenaria', 'concreto', 'pavimentação')"
                    }
                },
                "required": ["termo"]
            }
        ),
        Tool(
            name="estatisticas",
            description="Retorna estatísticas gerais dos atestados (totais, contratantes únicos, etc)",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="listar_contratantes",
            description="Lista todos os contratantes únicos com quantidade de atestados de cada um",
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
                        "description": "Nome (parcial) do contratante (ex: 'CAGEPA', 'Cabedelo')"
                    }
                },
                "required": ["contratante"]
            }
        ),
        Tool(
            name="somar_quantidades",
            description="Soma as quantidades de um tipo de serviço em todos os atestados. Útil para calcular experiência acumulada.",
            inputSchema={
                "type": "object",
                "properties": {
                    "termo": {
                        "type": "string",
                        "description": "Termo para buscar (ex: 'alvenaria', 'm2', 'concreto')"
                    },
                    "unidade": {
                        "type": "string",
                        "description": "Filtrar por unidade específica (ex: 'm2', 'm3', 'KG')"
                    }
                },
                "required": ["termo"]
            }
        ),
        Tool(
            name="executar_sql",
            description="Executa uma consulta SQL personalizada (somente SELECT). Use para consultas avançadas.",
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

        elif name == "somar_quantidades":
            termo = arguments["termo"]
            unidade_filtro = arguments.get("unidade", "").lower()

            cursor.execute('SELECT id, contratante, servicos_json FROM atestados WHERE servicos_json IS NOT NULL')
            soma_por_unidade = {}
            detalhes = []

            for row in cursor.fetchall():
                try:
                    servicos = json.loads(row["servicos_json"])
                    for s in servicos:
                        descricao = s.get("descricao", "").lower()
                        unidade = s.get("unidade", "").lower()

                        if termo.lower() in descricao:
                            if unidade_filtro and unidade != unidade_filtro:
                                continue

                            quantidade = float(s.get("quantidade", 0))
                            unidade_key = s.get("unidade", "UN")

                            if unidade_key not in soma_por_unidade:
                                soma_por_unidade[unidade_key] = 0
                            soma_por_unidade[unidade_key] += quantidade

                            detalhes.append({
                                "atestado_id": row["id"],
                                "contratante": row["contratante"][:40],
                                "descricao": s.get("descricao", "")[:60],
                                "quantidade": quantidade,
                                "unidade": unidade_key
                            })
                except:
                    pass

            result = {
                "termo_buscado": termo,
                "totais_por_unidade": soma_por_unidade,
                "quantidade_ocorrencias": len(detalhes),
                "detalhes": detalhes
            }
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
