"""
Fixtures compartilhadas para testes do LicitaFacil.
"""
import os
import sys
import pytest
from datetime import date
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from fastapi.testclient import TestClient

# Adicionar o diretório backend ao path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import Base
from models import Usuario, Atestado, Analise
from auth import get_password_hash


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
    """Sessão de banco de dados para cada teste."""
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


# === Fixtures de Usuário ===

@pytest.fixture
def test_user(db_session: Session) -> Usuario:
    """Cria um usuário de teste."""
    user = Usuario(
        email="teste@exemplo.com",
        nome="Usuário Teste",
        empresa="Empresa Teste LTDA",
        hashed_password=get_password_hash("senha123"),
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
        empresa="Admin Corp",
        hashed_password=get_password_hash("admin123"),
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
        empresa="Empresa Inativa",
        hashed_password=get_password_hash("senha123"),
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
        edital_arquivo="uploads/edital_teste.pdf",
        atestados_usados="[1, 2, 3]",
        resultado_analise={
            "exigencias": [
                {
                    "descricao": "Pavimentacao asfaltica",
                    "quantidade_exigida": 5000.0,
                    "unidade": "m2",
                    "status": "atende"
                }
            ],
            "resumo": "Atende todas as exigencias"
        }
    )
    db_session.add(analise)
    db_session.commit()
    db_session.refresh(analise)
    return analise


# === Fixtures de Cliente HTTP ===

@pytest.fixture
def client(test_engine) -> Generator[TestClient, None, None]:
    """Cliente de teste FastAPI."""
    from main import app
    from database import get_db

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
def auth_headers(client: TestClient, test_user: Usuario) -> dict:
    """Headers de autenticacao para um usuario de teste."""
    response = client.post(
        "/auth/login",
        data={"username": "teste@exemplo.com", "password": "senha123"}
    )
    token = response.json().get("access_token")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_auth_headers(client: TestClient, admin_user: Usuario) -> dict:
    """Headers de autenticacao para um usuario admin."""
    response = client.post(
        "/auth/login",
        data={"username": "admin@exemplo.com", "password": "admin123"}
    )
    token = response.json().get("access_token")
    return {"Authorization": f"Bearer {token}"}
