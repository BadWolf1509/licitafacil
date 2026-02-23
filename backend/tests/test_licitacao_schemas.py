"""Tests for Licitacao Pydantic schemas."""
from datetime import datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from schemas.licitacao import (
    LicitacaoCreate,
    LicitacaoDetalheResponse,
    LicitacaoEstatisticasResponse,
    LicitacaoHistoricoResponse,
    LicitacaoResponse,
    LicitacaoStatusUpdate,
    LicitacaoTagCreate,
    LicitacaoTagResponse,
    LicitacaoUpdate,
    PaginatedLicitacaoResponse,
)

# ---------- LicitacaoCreate ----------

class TestLicitacaoCreate:

    def test_valid_minimal(self):
        data = LicitacaoCreate(
            numero="PE 001/2026",
            orgao="Prefeitura Municipal de Teste",
            objeto="Pavimentacao asfaltica",
            modalidade="Pregao Eletronico",
        )
        assert data.numero == "PE 001/2026"
        assert data.fonte == "manual"

    def test_valid_full(self):
        data = LicitacaoCreate(
            numero="PE 001/2026",
            orgao="Prefeitura de SP",
            objeto="Obras de drenagem",
            modalidade="Concorrencia",
            valor_estimado=Decimal("1000000.00"),
            uf="SP",
            municipio="Sao Paulo",
            esfera="municipal",
            data_abertura=datetime(2026, 3, 15, 10, 0),
            link_edital="https://exemplo.com/edital.pdf",
            observacoes="Nota importante",
        )
        assert data.valor_estimado == Decimal("1000000.00")
        assert data.uf == "SP"

    def test_missing_required_fields(self):
        with pytest.raises(ValidationError):
            LicitacaoCreate(numero="PE 001/2026")

    def test_numero_max_length(self):
        with pytest.raises(ValidationError):
            LicitacaoCreate(
                numero="x" * 101,
                orgao="Org",
                objeto="Obj",
                modalidade="Mod",
            )

    def test_orgao_max_length(self):
        with pytest.raises(ValidationError):
            LicitacaoCreate(
                numero="PE 001",
                orgao="x" * 501,
                objeto="Obj",
                modalidade="Mod",
            )

    def test_uf_max_length(self):
        with pytest.raises(ValidationError):
            LicitacaoCreate(
                numero="PE 001",
                orgao="Org",
                objeto="Obj",
                modalidade="Mod",
                uf="SPX",
            )


# ---------- LicitacaoUpdate ----------

class TestLicitacaoUpdate:

    def test_all_fields_optional(self):
        data = LicitacaoUpdate()
        assert data.numero is None
        assert data.orgao is None

    def test_partial_update(self):
        data = LicitacaoUpdate(
            valor_estimado=Decimal("500000.00"),
            observacoes="Atualizado",
        )
        assert data.valor_estimado == Decimal("500000.00")
        assert data.numero is None

    def test_decisao_go_field(self):
        data = LicitacaoUpdate(decisao_go=True, motivo_nogo="Razao")
        assert data.decisao_go is True
        assert data.motivo_nogo == "Razao"


# ---------- LicitacaoStatusUpdate ----------

class TestLicitacaoStatusUpdate:

    def test_valid_status(self):
        data = LicitacaoStatusUpdate(status="em_analise")
        assert data.status == "em_analise"

    def test_valid_status_with_observacao(self):
        data = LicitacaoStatusUpdate(status="vencida", observacao="Melhor proposta")
        assert data.observacao == "Melhor proposta"

    def test_invalid_status(self):
        with pytest.raises(ValidationError, match="Status inválido"):
            LicitacaoStatusUpdate(status="status_inexistente")

    def test_all_valid_statuses(self):
        valid = [
            "identificada", "em_analise", "go_nogo", "elaborando_proposta",
            "proposta_enviada", "em_disputa", "vencida", "perdida",
            "contrato_assinado", "em_execucao", "concluida", "desistida", "cancelada",
        ]
        for s in valid:
            data = LicitacaoStatusUpdate(status=s)
            assert data.status == s


# ---------- LicitacaoTagCreate ----------

class TestLicitacaoTagCreate:

    def test_valid_tag(self):
        data = LicitacaoTagCreate(tag="infraestrutura")
        assert data.tag == "infraestrutura"

    def test_tag_max_length(self):
        with pytest.raises(ValidationError):
            LicitacaoTagCreate(tag="x" * 101)

    def test_tag_required(self):
        with pytest.raises(ValidationError):
            LicitacaoTagCreate()


# ---------- LicitacaoTagResponse ----------

class TestLicitacaoTagResponse:

    def test_from_dict(self):
        data = LicitacaoTagResponse(id=1, tag="teste")
        assert data.id == 1
        assert data.tag == "teste"


# ---------- LicitacaoHistoricoResponse ----------

class TestLicitacaoHistoricoResponse:

    def test_from_dict(self):
        now = datetime.now()
        data = LicitacaoHistoricoResponse(
            id=1,
            licitacao_id=10,
            user_id=1,
            status_anterior="identificada",
            status_novo="em_analise",
            observacao="Iniciando analise",
            created_at=now,
        )
        assert data.status_anterior == "identificada"
        assert data.status_novo == "em_analise"

    def test_status_anterior_nullable(self):
        now = datetime.now()
        data = LicitacaoHistoricoResponse(
            id=1, licitacao_id=10, user_id=1,
            status_anterior=None, status_novo="identificada",
            created_at=now,
        )
        assert data.status_anterior is None


# ---------- LicitacaoResponse ----------

class TestLicitacaoResponse:

    def test_from_dict(self):
        now = datetime.now()
        data = LicitacaoResponse(
            id=1, user_id=1, numero="PE 001",
            orgao="Org", objeto="Obj", modalidade="Mod",
            fonte="manual", status="identificada",
            tags=[], created_at=now,
        )
        assert data.id == 1
        assert data.status == "identificada"
        assert data.tags == []


# ---------- LicitacaoDetalheResponse ----------

class TestLicitacaoDetalheResponse:

    def test_includes_historico(self):
        now = datetime.now()
        data = LicitacaoDetalheResponse(
            id=1, user_id=1, numero="PE 001",
            orgao="Org", objeto="Obj", modalidade="Mod",
            fonte="manual", status="identificada",
            tags=[], historico=[], created_at=now,
        )
        assert data.historico == []


# ---------- LicitacaoEstatisticasResponse ----------

class TestLicitacaoEstatisticasResponse:

    def test_valid(self):
        data = LicitacaoEstatisticasResponse(
            total=10,
            por_status={"identificada": 5, "vencida": 3, "perdida": 2},
            por_uf={"SP": 6, "RJ": 4},
            por_modalidade={"Pregao Eletronico": 8, "Concorrencia": 2},
        )
        assert data.total == 10
        assert data.por_status["vencida"] == 3


# ---------- PaginatedLicitacaoResponse ----------

class TestPaginatedLicitacaoResponse:

    def test_create_pagination(self):
        now = datetime.now()
        items = [
            LicitacaoResponse(
                id=i, user_id=1, numero=f"PE {i}",
                orgao="Org", objeto="Obj", modalidade="Mod",
                fonte="manual", status="identificada",
                tags=[], created_at=now,
            )
            for i in range(3)
        ]
        response = PaginatedLicitacaoResponse.create(
            items=items, total=10, page=1, page_size=3,
        )
        assert len(response.items) == 3
        assert response.total == 10
        assert response.total_pages == 4
