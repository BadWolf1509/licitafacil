"""Tests for Documento/Checklist Pydantic schemas."""
from datetime import datetime

import pytest
from pydantic import ValidationError

from models.documento import DocumentoTipo
from schemas.documento import (
    ChecklistItemCreate,
    ChecklistItemToggle,
    ChecklistItemUpdate,
    ChecklistResumoResponse,
    DocumentoCreate,
    DocumentoResponse,
    DocumentoResumoResponse,
    DocumentoUpdate,
    PaginatedDocumentoResponse,
)

# ---------- DocumentoCreate ----------

class TestDocumentoCreate:

    def test_valid_minimal(self):
        data = DocumentoCreate(
            nome="Certidao Negativa Federal",
            tipo_documento="certidao_federal",
        )
        assert data.nome == "Certidao Negativa Federal"
        assert data.tipo_documento == "certidao_federal"
        assert data.licitacao_id is None
        assert data.obrigatorio is False

    def test_valid_full(self):
        now = datetime.now()
        data = DocumentoCreate(
            nome="Balanco Patrimonial 2025",
            tipo_documento="balanco",
            licitacao_id=42,
            data_emissao=now,
            data_validade=now,
            obrigatorio=True,
            observacoes="Auditado",
        )
        assert data.tipo_documento == "balanco"
        assert data.licitacao_id == 42
        assert data.obrigatorio is True
        assert data.observacoes == "Auditado"

    def test_all_valid_tipos(self):
        """All 15 valid document types should be accepted."""
        for tipo in DocumentoTipo.ALL:
            data = DocumentoCreate(nome="Doc", tipo_documento=tipo)
            assert data.tipo_documento == tipo

    def test_invalid_tipo_documento_raises(self):
        with pytest.raises(ValidationError, match="Tipo de documento inválido"):
            DocumentoCreate(nome="Doc", tipo_documento="tipo_inexistente")

    def test_missing_required_nome(self):
        with pytest.raises(ValidationError):
            DocumentoCreate(tipo_documento="edital")

    def test_missing_required_tipo_documento(self):
        with pytest.raises(ValidationError):
            DocumentoCreate(nome="Doc")

    def test_nome_max_length(self):
        with pytest.raises(ValidationError):
            DocumentoCreate(nome="x" * 256, tipo_documento="edital")

    def test_tipo_documento_max_length(self):
        """tipo_documento exceeding 100 chars should fail (before validator)."""
        with pytest.raises(ValidationError):
            DocumentoCreate(nome="Doc", tipo_documento="x" * 101)

    def test_licitacao_id_optional(self):
        data = DocumentoCreate(nome="Doc", tipo_documento="edital")
        assert data.licitacao_id is None

    def test_data_emissao_optional(self):
        data = DocumentoCreate(nome="Doc", tipo_documento="edital")
        assert data.data_emissao is None

    def test_data_validade_optional(self):
        data = DocumentoCreate(nome="Doc", tipo_documento="edital")
        assert data.data_validade is None


# ---------- DocumentoUpdate ----------

class TestDocumentoUpdate:

    def test_all_fields_optional(self):
        data = DocumentoUpdate()
        assert data.nome is None
        assert data.tipo_documento is None
        assert data.licitacao_id is None
        assert data.obrigatorio is None

    def test_partial_update(self):
        data = DocumentoUpdate(nome="Novo nome", obrigatorio=True)
        assert data.nome == "Novo nome"
        assert data.obrigatorio is True
        assert data.tipo_documento is None

    def test_exclude_unset(self):
        data = DocumentoUpdate(nome="Atualizado")
        dumped = data.model_dump(exclude_unset=True)
        assert "nome" in dumped
        assert "tipo_documento" not in dumped
        assert "licitacao_id" not in dumped

    def test_invalid_tipo_documento_raises(self):
        with pytest.raises(ValidationError, match="Tipo de documento inválido"):
            DocumentoUpdate(tipo_documento="invalido")

    def test_none_tipo_documento_is_ok(self):
        data = DocumentoUpdate(tipo_documento=None)
        assert data.tipo_documento is None

    def test_valid_tipo_documento(self):
        data = DocumentoUpdate(tipo_documento="certidao_fgts")
        assert data.tipo_documento == "certidao_fgts"


# ---------- DocumentoResponse ----------

class TestDocumentoResponse:

    def test_from_dict(self):
        now = datetime.now()
        data = DocumentoResponse(
            id=1,
            user_id=10,
            nome="Certidao Federal",
            tipo_documento="certidao_federal",
            status="valido",
            created_at=now,
        )
        assert data.id == 1
        assert data.user_id == 10
        assert data.status == "valido"
        assert data.arquivo_path is None
        assert data.tamanho_bytes is None
        assert data.updated_at is None

    def test_with_all_fields(self):
        now = datetime.now()
        data = DocumentoResponse(
            id=2,
            user_id=10,
            nome="Balanco",
            tipo_documento="balanco",
            licitacao_id=5,
            data_emissao=now,
            data_validade=now,
            obrigatorio=True,
            observacoes="Nota",
            arquivo_path="users/10/documentos/abc.pdf",
            tamanho_bytes=102400,
            status="vencendo",
            created_at=now,
            updated_at=now,
        )
        assert data.arquivo_path == "users/10/documentos/abc.pdf"
        assert data.tamanho_bytes == 102400
        assert data.status == "vencendo"
        assert data.licitacao_id == 5

    def test_from_attributes_config(self):
        assert DocumentoResponse.model_config.get("from_attributes") is True


# ---------- ChecklistItemCreate ----------

class TestChecklistItemCreate:

    def test_valid_minimal(self):
        data = ChecklistItemCreate(descricao="Certidao FGTS")
        assert data.descricao == "Certidao FGTS"
        assert data.tipo_documento is None
        assert data.obrigatorio is True
        assert data.ordem == 0

    def test_valid_full(self):
        data = ChecklistItemCreate(
            descricao="Balanco patrimonial dos ultimos 3 anos",
            tipo_documento="balanco",
            obrigatorio=True,
            observacao="Deve ser auditado",
            ordem=5,
        )
        assert data.tipo_documento == "balanco"
        assert data.observacao == "Deve ser auditado"
        assert data.ordem == 5

    def test_invalid_tipo_documento(self):
        with pytest.raises(ValidationError, match="Tipo de documento inválido"):
            ChecklistItemCreate(
                descricao="Item",
                tipo_documento="tipo_invalido",
            )

    def test_none_tipo_documento_is_ok(self):
        data = ChecklistItemCreate(
            descricao="Item sem tipo",
            tipo_documento=None,
        )
        assert data.tipo_documento is None

    def test_all_valid_tipos(self):
        for tipo in DocumentoTipo.ALL:
            data = ChecklistItemCreate(descricao="Item", tipo_documento=tipo)
            assert data.tipo_documento == tipo


# ---------- ChecklistItemUpdate ----------

class TestChecklistItemUpdate:

    def test_all_fields_optional(self):
        data = ChecklistItemUpdate()
        assert data.descricao is None
        assert data.tipo_documento is None
        assert data.obrigatorio is None
        assert data.cumprido is None
        assert data.documento_id is None
        assert data.observacao is None
        assert data.ordem is None

    def test_partial_update(self):
        data = ChecklistItemUpdate(cumprido=True, documento_id=5)
        dumped = data.model_dump(exclude_unset=True)
        assert dumped == {"cumprido": True, "documento_id": 5}

    def test_descricao_update(self):
        data = ChecklistItemUpdate(descricao="Descricao atualizada")
        assert data.descricao == "Descricao atualizada"


# ---------- ChecklistItemToggle ----------

class TestChecklistItemToggle:

    def test_cumprido_true(self):
        data = ChecklistItemToggle(cumprido=True)
        assert data.cumprido is True
        assert data.documento_id is None

    def test_cumprido_false_with_documento_id(self):
        data = ChecklistItemToggle(cumprido=False, documento_id=42)
        assert data.cumprido is False
        assert data.documento_id == 42

    def test_cumprido_required(self):
        with pytest.raises(ValidationError):
            ChecklistItemToggle()


# ---------- ChecklistResumoResponse ----------

class TestChecklistResumoResponse:

    def test_valid(self):
        data = ChecklistResumoResponse(
            licitacao_id=10,
            total=8,
            cumpridos=5,
            pendentes=3,
            obrigatorios_pendentes=2,
            percentual=62.5,
        )
        assert data.licitacao_id == 10
        assert data.percentual == 62.5
        assert data.cumpridos == 5

    def test_zero_total(self):
        data = ChecklistResumoResponse(
            licitacao_id=1,
            total=0,
            cumpridos=0,
            pendentes=0,
            obrigatorios_pendentes=0,
            percentual=0.0,
        )
        assert data.total == 0
        assert data.percentual == 0.0


# ---------- DocumentoResumoResponse ----------

class TestDocumentoResumoResponse:

    def test_valid(self):
        data = DocumentoResumoResponse(
            total=20,
            validos=12,
            vencendo=3,
            vencidos=2,
            nao_aplicavel=3,
        )
        assert data.total == 20
        assert data.validos == 12
        assert data.vencendo == 3
        assert data.vencidos == 2
        assert data.nao_aplicavel == 3

    def test_all_zeros(self):
        data = DocumentoResumoResponse(
            total=0,
            validos=0,
            vencendo=0,
            vencidos=0,
            nao_aplicavel=0,
        )
        assert data.total == 0


# ---------- PaginatedDocumentoResponse ----------

class TestPaginatedDocumentoResponse:

    def test_create_pagination(self):
        now = datetime.now()
        items = [
            DocumentoResponse(
                id=i,
                user_id=1,
                nome=f"Doc {i}",
                tipo_documento="edital",
                status="valido",
                created_at=now,
            )
            for i in range(3)
        ]
        response = PaginatedDocumentoResponse.create(
            items=items, total=10, page=1, page_size=3,
        )
        assert len(response.items) == 3
        assert response.total == 10
        assert response.page == 1
        assert response.page_size == 3
        assert response.total_pages == 4

    def test_empty_pagination(self):
        response = PaginatedDocumentoResponse.create(
            items=[], total=0, page=1, page_size=10,
        )
        assert len(response.items) == 0
        assert response.total == 0
        assert response.total_pages == 0
