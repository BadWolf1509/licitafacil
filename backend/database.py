from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

# Carregar .env do diretório raiz do projeto (um nível acima do backend)
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(env_path)

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./licitafacil.db")

# Detectar tipo de banco de dados
IS_SQLITE = DATABASE_URL.startswith("sqlite")
IS_POSTGRES = DATABASE_URL.startswith("postgresql")

if IS_SQLITE:
    # SQLite: check_same_thread=False e timeout para evitar locks
    engine = create_engine(
        DATABASE_URL,
        connect_args={
            "check_same_thread": False,
            "timeout": 30.0
        },
        pool_pre_ping=True
    )

    # Habilitar WAL mode para melhor concorrência em SQLite
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()

elif IS_POSTGRES:
    # PostgreSQL (Supabase): connection pooling otimizado
    engine = create_engine(
        DATABASE_URL,
        pool_size=5,
        max_overflow=10,
        pool_timeout=30,
        pool_recycle=1800,  # Reconectar a cada 30 min
        pool_pre_ping=True,
        echo=False
    )

else:
    # Outros bancos
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)

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
