#!/usr/bin/env python3
"""
Script para migrar usuários existentes para o Supabase Auth.

Este script:
1. Lê todos os usuários que possuem senha_hash mas não têm supabase_id
2. Cria esses usuários no Supabase Auth
3. Atualiza o supabase_id no banco local
4. Opcionalmente remove a senha_hash local

Uso:
    python migrate_users_to_supabase.py [--dry-run] [--remove-passwords]

Opções:
    --dry-run           Mostra o que seria feito sem executar
    --remove-passwords  Remove senha_hash dos usuários migrados
"""
import os
import sys
import argparse
from pathlib import Path

# Adicionar o diretório backend ao path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from config import SUPABASE_URL, SUPABASE_SERVICE_KEY
from models import Usuario


def get_database_url():
    """Obtém a URL do banco de dados."""
    url = os.getenv("DATABASE_URL")
    if not url:
        raise ValueError("DATABASE_URL não configurada")
    return url


def create_supabase_user(email: str, password_placeholder: str) -> dict:
    """
    Cria usuário no Supabase Auth.

    NOTA: Como não temos a senha original (apenas o hash),
    criamos o usuário com uma senha temporária.
    O usuário deverá usar "Esqueci minha senha" para redefinir.
    """
    from supabase import create_client

    client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

    # Criar usuário com senha temporária
    # O usuário precisará resetar a senha
    response = client.auth.admin.create_user({
        "email": email,
        "password": password_placeholder,
        "email_confirm": True,  # Marcar email como confirmado
        "user_metadata": {"migrated_from_legacy": True}
    })

    if response.user:
        return {
            "id": response.user.id,
            "email": response.user.email
        }

    return None


def generate_temp_password(email: str) -> str:
    """
    Gera uma senha temporária segura.
    NOTA: Esta senha não será usada - o usuário vai resetar via Supabase.
    """
    import hashlib
    import secrets

    # Gerar senha aleatória que o usuário não saberá
    # Forçar uso de "Esqueci minha senha"
    random_part = secrets.token_hex(16)
    hash_part = hashlib.sha256(f"{email}{random_part}".encode()).hexdigest()[:8]
    return f"Temp_{hash_part}_{random_part[:8]}!Aa1"


def migrate_users(dry_run: bool = True, remove_passwords: bool = False):
    """
    Migra usuários existentes para o Supabase Auth.

    Args:
        dry_run: Se True, apenas mostra o que seria feito
        remove_passwords: Se True, remove senha_hash dos usuários migrados
    """
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        print("ERRO: SUPABASE_URL e SUPABASE_SERVICE_KEY são obrigatórios")
        print("Configure as variáveis de ambiente e tente novamente.")
        return

    # Conectar ao banco
    database_url = get_database_url()
    engine = create_engine(database_url)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        # Buscar usuários que têm senha_hash mas não têm supabase_id
        users_to_migrate = session.query(Usuario).filter(
            Usuario.senha_hash.isnot(None),
            Usuario.supabase_id.is_(None)
        ).all()

        print(f"\n{'='*60}")
        print(f"MIGRAÇÃO DE USUÁRIOS PARA SUPABASE AUTH")
        print(f"{'='*60}")
        print(f"Modo: {'DRY RUN (simulação)' if dry_run else 'EXECUÇÃO REAL'}")
        print(f"Remover senhas locais: {'Sim' if remove_passwords else 'Não'}")
        print(f"Usuários a migrar: {len(users_to_migrate)}")
        print(f"{'='*60}\n")

        if len(users_to_migrate) == 0:
            print("Nenhum usuário para migrar.")
            return

        migrated = 0
        errors = 0

        for user in users_to_migrate:
            print(f"[{user.id}] {user.email}...")

            if dry_run:
                print(f"    -> [DRY RUN] Seria criado no Supabase")
                migrated += 1
                continue

            try:
                # Gerar senha temporária
                temp_password = generate_temp_password(user.email)

                # Criar no Supabase
                supabase_user = create_supabase_user(user.email, temp_password)

                if supabase_user:
                    # Atualizar banco local
                    user.supabase_id = supabase_user["id"]

                    if remove_passwords:
                        user.senha_hash = None
                        print(f"    -> Criado no Supabase (id: {supabase_user['id'][:8]}...), senha local removida")
                    else:
                        print(f"    -> Criado no Supabase (id: {supabase_user['id'][:8]}...)")

                    session.commit()
                    migrated += 1
                else:
                    print(f"    -> ERRO: Falha ao criar no Supabase")
                    errors += 1

            except Exception as e:
                print(f"    -> ERRO: {e}")
                errors += 1
                session.rollback()

        print(f"\n{'='*60}")
        print(f"RESULTADO:")
        print(f"  Migrados com sucesso: {migrated}")
        print(f"  Erros: {errors}")
        print(f"{'='*60}")

        if not dry_run and migrated > 0:
            print("\nIMPORTANTE:")
            print("Os usuários migrados receberam uma senha temporária.")
            print("Eles devem usar 'Esqueci minha senha' no Supabase para")
            print("definir uma nova senha antes de fazer login.")

    finally:
        session.close()


def main():
    parser = argparse.ArgumentParser(
        description="Migra usuários existentes para Supabase Auth"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Simula a migração sem executar (padrão)"
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Executa a migração de verdade"
    )
    parser.add_argument(
        "--remove-passwords",
        action="store_true",
        help="Remove senha_hash dos usuários migrados"
    )

    args = parser.parse_args()

    # Se --execute foi passado, desabilita dry_run
    dry_run = not args.execute

    if not dry_run:
        print("\n" + "!"*60)
        print("ATENÇÃO: Você está prestes a migrar usuários para o Supabase!")
        print("Esta ação criará contas no Supabase Auth.")
        print("!"*60)
        resposta = input("\nDigite 'SIM' para continuar: ")
        if resposta != "SIM":
            print("Operação cancelada.")
            return

    migrate_users(dry_run=dry_run, remove_passwords=args.remove_passwords)


if __name__ == "__main__":
    main()
