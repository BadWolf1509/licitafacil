"""
Script para criar o usuário administrador inicial.
Execute este script após criar o banco de dados.

Uso:
    python seed.py
"""
import os
from dotenv import load_dotenv
from sqlalchemy.orm import Session

from database import engine, SessionLocal, Base
from models import Usuario
from auth import get_password_hash

# Carregar variáveis de ambiente
load_dotenv()


def create_admin():
    """Cria o usuário administrador inicial."""
    # Criar tabelas se não existirem
    Base.metadata.create_all(bind=engine)

    # Obter dados do admin do .env ou usar padrões
    admin_email = os.getenv("ADMIN_EMAIL", "admin@licitafacil.com.br")
    admin_password = os.getenv("ADMIN_PASSWORD", "admin123")
    admin_name = os.getenv("ADMIN_NAME", "Administrador")

    db: Session = SessionLocal()
    try:
        # Verificar se admin já existe
        existing_admin = db.query(Usuario).filter(Usuario.email == admin_email).first()
        if existing_admin:
            print(f"[INFO] Administrador já existe: {admin_email}")
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

        print("=" * 50)
        print("ADMINISTRADOR CRIADO COM SUCESSO!")
        print("=" * 50)
        print(f"Email: {admin_email}")
        print(f"Senha: {admin_password}")
        print("=" * 50)
        print("IMPORTANTE: Altere a senha após o primeiro login!")
        print("=" * 50)

    except Exception as e:
        print(f"[ERRO] Falha ao criar administrador: {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    create_admin()
