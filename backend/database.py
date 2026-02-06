"""
Configuração do banco de dados PostgreSQL (Supabase).

O LicitaFácil usa exclusivamente PostgreSQL via Supabase.
"""

from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
import os
import sys
from dotenv import load_dotenv

# Carregar .env do diretório raiz do projeto (um nível acima do backend)
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(env_path)

DATABASE_URL = os.getenv("DATABASE_URL", "")

# Em modo de teste (pytest), usar SQLite em memoria
_TESTING = os.getenv("TESTING", "").lower() in ("1", "true", "yes") or "pytest" in sys.modules

if not DATABASE_URL and not _TESTING:
    raise ValueError(
        "DATABASE_URL não configurada. "
        "Configure com uma URL PostgreSQL do Supabase no arquivo .env"
    )

if DATABASE_URL and not DATABASE_URL.startswith("postgresql") and not _TESTING:
    raise ValueError(
        f"DATABASE_URL inválida: deve ser PostgreSQL. "
        f"Recebido: {DATABASE_URL[:20]}..."
    )

# Fallback para SQLite em testes quando DATABASE_URL nao esta configurada
if not DATABASE_URL and _TESTING:
    DATABASE_URL = "sqlite:///./test_licitafacil.db"

# Detectar tipo de banco
_is_sqlite = DATABASE_URL.startswith("sqlite")
_is_supabase_pooler = ":6543/" in DATABASE_URL or "pooler.supabase.com" in DATABASE_URL

if _is_sqlite:
    # SQLite para testes locais
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        echo=False
    )
elif _is_supabase_pooler:
    # Supabase Pooler (transaction mode): NullPool obrigatório
    # para evitar double-pooling que causa problemas de commit/rollback
    engine = create_engine(
        DATABASE_URL,
        poolclass=NullPool,
        echo=False
    )
else:
    # PostgreSQL direto (sem pooler externo)
    _pool_size = int(os.getenv("DB_POOL_SIZE", "5"))
    _max_overflow = int(os.getenv("DB_MAX_OVERFLOW", "10"))
    engine = create_engine(
        DATABASE_URL,
        pool_size=_pool_size,
        max_overflow=_max_overflow,
        pool_timeout=30,
        pool_recycle=1800,
        pool_pre_ping=True,
        echo=False
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """Dependency para obter sessão do banco de dados."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_session():
    """
    Context manager para obter sessão do banco de dados.

    Uso em callbacks, services ou código fora de rotas FastAPI:
        with get_db_session() as db:
            db.query(Model).filter(...)
            db.commit()

    O commit deve ser feito manualmente se necessário.
    Rollback é automático em caso de exceção.
    """
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
