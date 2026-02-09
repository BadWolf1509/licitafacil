"""
Script para criar o usuário administrador inicial.
Execute este script após criar o banco de dados.

Uso:
    python seed.py
"""
import os

from dotenv import load_dotenv
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from config.defaults import DEFAULT_ADMIN_EMAIL, DEFAULT_ADMIN_NAME, MIN_PASSWORD_LENGTH
from database import Base, SessionLocal, engine
from logging_config import get_logger
from models import Usuario
from utils.password_validator import validate_password

logger = get_logger('seed')

# Contexto de criptografia para senhas
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def get_password_hash(password: str) -> str:
    """Gera hash de senha usando bcrypt."""
    return pwd_context.hash(password)

# Carregar variáveis de ambiente
load_dotenv()


def create_admin():
    """Cria o usuário administrador inicial."""
    # Criar tabelas se não existirem
    Base.metadata.create_all(bind=engine)

    # Obter dados do admin do .env
    admin_email = os.getenv("ADMIN_EMAIL", DEFAULT_ADMIN_EMAIL)
    admin_password = os.getenv("ADMIN_PASSWORD")
    admin_name = os.getenv("ADMIN_NAME", DEFAULT_ADMIN_NAME)

    # Validar senha - não aceitar default fraco
    if not admin_password:
        logger.error("ADMIN_PASSWORD não definida no .env")
        logger.info(f"Defina uma senha forte com pelo menos {MIN_PASSWORD_LENGTH} caracteres.")
        return

    # Validar complexidade da senha (não apenas tamanho)
    is_valid, errors = validate_password(admin_password)
    if not is_valid:
        logger.error(f"ADMIN_PASSWORD inválida: {'; '.join(errors)}")
        logger.info("A senha deve atender aos requisitos de complexidade.")
        return

    db: Session = SessionLocal()
    try:
        # Verificar se admin já existe
        existing_admin = db.query(Usuario).filter(Usuario.email == admin_email).first()
        if existing_admin:
            logger.info(f"Administrador ja existe: {admin_email}")
            return

        # Criar admin
        admin = Usuario(
            email=admin_email,
            nome=admin_name,
            senha_hash=get_password_hash(admin_password),
            is_admin=True,
            is_approved=True,
            is_active=True
        )
        db.add(admin)
        db.commit()

        # Log seguro - NUNCA expor senha
        logger.info(f"Administrador criado com sucesso: {admin_email}")
        logger.warning("IMPORTANTE: Altere a senha apos o primeiro login!")

    except Exception as e:
        logger.error(f"Falha ao criar administrador: {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    create_admin()
