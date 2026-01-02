from sqlalchemy import Boolean, Column, Integer, String, DateTime, ForeignKey, Text, Numeric, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base


class Usuario(Base):
    """Modelo de usuário do sistema."""
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    senha_hash = Column(String(255), nullable=False)
    nome = Column(String(255), nullable=False)

    is_admin = Column(Boolean, default=False)
    is_approved = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)

    tema_preferido = Column(String(10), default="light")  # light ou dark

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    approved_at = Column(DateTime(timezone=True), nullable=True)
    approved_by = Column(Integer, ForeignKey("usuarios.id"), nullable=True)

    # Relacionamentos
    atestados = relationship("Atestado", back_populates="usuario")
    analises = relationship("Analise", back_populates="usuario")
    aprovador = relationship("Usuario", remote_side=[id], foreign_keys=[approved_by])


class Atestado(Base):
    """Modelo de atestado de capacidade técnica."""
    __tablename__ = "atestados"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)

    descricao_servico = Column(Text, nullable=False)
    quantidade = Column(Numeric(15, 4), nullable=False)
    unidade = Column(String(20), nullable=False)

    contratante = Column(String(255), nullable=True)
    data_emissao = Column(DateTime, nullable=True)

    arquivo_path = Column(String(500), nullable=True)
    texto_extraido = Column(Text, nullable=True)
    servicos_json = Column(JSON, nullable=True)  # Lista de serviços detalhados

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relacionamentos
    usuario = relationship("Usuario", back_populates="atestados")


class Analise(Base):
    """Modelo de análise de licitação."""
    __tablename__ = "analises"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)

    nome_licitacao = Column(String(255), nullable=False)
    arquivo_path = Column(String(500), nullable=True)

    exigencias_json = Column(JSON, nullable=True)
    resultado_json = Column(JSON, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relacionamentos
    usuario = relationship("Usuario", back_populates="analises")
