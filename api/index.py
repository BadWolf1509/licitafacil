"""
Vercel Serverless Function - Entry point para FastAPI.

Este arquivo permite rodar o backend FastAPI como Serverless Function na Vercel.
"""
import sys
from pathlib import Path

# Adicionar backend ao path
backend_path = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_path))

# Importar app FastAPI
from main import app

# Vercel espera um handler chamado 'app' ou 'handler'
# FastAPI é compatível diretamente
