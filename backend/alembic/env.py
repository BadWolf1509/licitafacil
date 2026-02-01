from logging.config import fileConfig
import os
import sys
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy import pool

from alembic import context  # type: ignore[attr-defined]

# Adicionar o diretório backend ao path para imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Carregar variáveis de ambiente
from dotenv import load_dotenv
env_path = Path(__file__).parent.parent.parent / '.env'
load_dotenv(env_path)

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Obter DATABASE_URL do ambiente (não usar set_main_option devido a caracteres especiais)
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./licitafacil.db")

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Importar models para autogenerate
from database import Base  # noqa: E402
import models  # noqa: E402, F401 - importa para registrar os modelos

# add your model's MetaData object here
# for 'autogenerate' support
target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    context.configure(
        url=DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    # Configuração especial para SQLite
    is_sqlite = DATABASE_URL.startswith("sqlite")

    if is_sqlite:
        connectable = create_engine(
            DATABASE_URL,
            poolclass=pool.NullPool,
            connect_args={"check_same_thread": False},
        )
    else:
        connectable = create_engine(
            DATABASE_URL,
            poolclass=pool.NullPool,
        )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,  # Detectar mudanças de tipo
            compare_server_default=True,  # Detectar mudanças em defaults
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
