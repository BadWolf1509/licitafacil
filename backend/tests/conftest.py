"""
Fixtures compartilhadas para testes do LicitaFacil.

Usa mocking para autenticação já que o Supabase não está disponível em testes.
"""
import os
import sys
import uuid
from datetime import date
from typing import Generator
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

# Adicionar o diretório backend ao path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import Base
from models import (
    Analise,
    Atestado,
    AuditLog,
    ChecklistEdital,
    DocumentoLicitacao,
    Lembrete,
    Licitacao,
    LicitacaoHistorico,
    LicitacaoTag,
    Notificacao,
    PreferenciaNotificacao,
    ProcessingJobModel,
    Usuario,
)

# === Configuração do Banco de Dados de Teste ===

TEST_DATABASE_URL = "sqlite:///./test_licitafacil.db"

@pytest.fixture(scope="session")
def test_engine():
    """Engine do banco de dados de teste."""
    engine = create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    # Cleanup: remover banco de teste após todos os testes
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def db_session(test_engine) -> Generator[Session, None, None]:
    """Sessão de banco de dados para cada teste com cleanup."""
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        # Limpar dados de teste
        session.execute(PreferenciaNotificacao.__table__.delete())
        session.execute(Notificacao.__table__.delete())
        session.execute(Lembrete.__table__.delete())
        session.execute(AuditLog.__table__.delete())
        session.execute(ProcessingJobModel.__table__.delete())
        session.execute(ChecklistEdital.__table__.delete())
        session.execute(DocumentoLicitacao.__table__.delete())
        session.execute(LicitacaoHistorico.__table__.delete())
        session.execute(LicitacaoTag.__table__.delete())
        session.execute(Analise.__table__.delete())
        session.execute(Licitacao.__table__.delete())
        session.execute(Atestado.__table__.delete())
        session.execute(Usuario.__table__.delete())
        session.commit()
        session.close()


# === Fixtures de Usuário ===

def generate_supabase_id() -> str:
    """Gera um UUID simulando supabase_id."""
    return str(uuid.uuid4())


@pytest.fixture
def test_user(db_session: Session) -> Usuario:
    """Cria um usuário de teste."""
    user = Usuario(
        email="teste@exemplo.com",
        nome="Usuário Teste",
        supabase_id=generate_supabase_id(),
        is_active=True,
        is_approved=True,
        is_admin=False
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def admin_user(db_session: Session) -> Usuario:
    """Cria um usuário admin de teste."""
    user = Usuario(
        email="admin@exemplo.com",
        nome="Admin Teste",
        supabase_id=generate_supabase_id(),
        is_active=True,
        is_approved=True,
        is_admin=True
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def inactive_user(db_session: Session) -> Usuario:
    """Cria um usuário inativo de teste."""
    user = Usuario(
        email="inativo@exemplo.com",
        nome="Usuário Inativo",
        supabase_id=generate_supabase_id(),
        is_active=False,
        is_approved=False,
        is_admin=False
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


# === Fixtures de Atestado ===

@pytest.fixture
def sample_atestado(db_session: Session, test_user: Usuario) -> Atestado:
    """Cria um atestado de teste."""
    atestado = Atestado(
        user_id=test_user.id,
        descricao_servico="Pavimentacao asfaltica em CBUQ",
        quantidade=2500.0,
        unidade="m2",
        contratante="Prefeitura Municipal de Teste",
        data_emissao=date(2023, 6, 15),
        arquivo_path="uploads/teste_atestado.pdf",
        servicos_json=[
            {"item": "1.1", "descricao": "Pavimentacao asfaltica", "quantidade": 2500.0, "unidade": "M2"},
            {"item": "1.2", "descricao": "Meio-fio", "quantidade": 500.0, "unidade": "ML"}
        ]
    )
    db_session.add(atestado)
    db_session.commit()
    db_session.refresh(atestado)
    return atestado


@pytest.fixture
def multiple_atestados(db_session: Session, test_user: Usuario) -> list[Atestado]:
    """Cria multiplos atestados de teste."""
    atestados = []
    for i in range(3):
        atestado = Atestado(
            user_id=test_user.id,
            descricao_servico=f"Servico de teste {i+1}",
            quantidade=1000.0 * (i + 1),
            unidade="m2",
            contratante=f"Contratante {i+1}",
            data_emissao=date(2023, 1 + i, 15),
            arquivo_path=f"uploads/atestado_{i+1}.pdf"
        )
        db_session.add(atestado)
        atestados.append(atestado)
    db_session.commit()
    for a in atestados:
        db_session.refresh(a)
    return atestados


# === Fixtures de Analise ===

@pytest.fixture
def sample_analise(db_session: Session, test_user: Usuario) -> Analise:
    """Cria uma analise de teste."""
    analise = Analise(
        user_id=test_user.id,
        nome_licitacao="Edital de Teste",
        arquivo_path="uploads/edital_teste.pdf",
        exigencias_json=[
            {
                "descricao": "Pavimentacao asfaltica",
                "quantidade_minima": 5000.0,
                "unidade": "m2"
            }
        ],
        resultado_json=[
            {
                "exigencia": {"descricao": "Pavimentacao asfaltica", "quantidade_minima": 5000.0, "unidade": "m2"},
                "status": "atende",
                "atestados_recomendados": [],
                "soma_quantidades": 5500.0,
                "percentual_total": 110.0
            }
        ]
    )
    db_session.add(analise)
    db_session.commit()
    db_session.refresh(analise)
    return analise


# === Fixtures de Cliente HTTP ===

@pytest.fixture
def client(test_engine) -> Generator[TestClient, None, None]:
    """Cliente de teste FastAPI."""
    from database import get_db
    from main import app

    # Override da dependencia de banco
    def override_get_db():
        TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture
def mock_supabase_verify():
    """Mock para verificação de token Supabase."""
    with patch('services.supabase_auth.verify_supabase_token') as mock:
        yield mock


def create_mock_auth_headers(user: Usuario, mock_verify: MagicMock) -> dict:
    """
    Cria headers de autenticação mockando a verificação Supabase.

    Args:
        user: Usuário para autenticar
        mock_verify: Mock da função verify_supabase_token

    Returns:
        Headers dict com Authorization
    """
    # Configura o mock para retornar dados do usuário
    mock_verify.return_value = {
        "id": user.supabase_id,
        "email": user.email
    }

    # Token fake (será ignorado pois mock retorna diretamente)
    return {"Authorization": f"Bearer mock_token_{user.id}"}


@pytest.fixture
def auth_headers(test_user: Usuario, mock_supabase_verify: MagicMock) -> dict:
    """Headers de autenticacao para um usuario de teste."""
    return create_mock_auth_headers(test_user, mock_supabase_verify)


@pytest.fixture
def admin_auth_headers(admin_user: Usuario, mock_supabase_verify: MagicMock) -> dict:
    """Headers de autenticacao para um usuario admin."""
    return create_mock_auth_headers(admin_user, mock_supabase_verify)
