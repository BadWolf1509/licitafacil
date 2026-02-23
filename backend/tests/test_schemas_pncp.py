"""Tests for PNCP Pydantic schemas."""
from datetime import datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from models.pncp import PncpResultadoStatus
from schemas.pncp import (
    PncpBuscaResponse,
    PncpImportarRequest,
    PncpMonitoramentoCreate,
    PncpMonitoramentoResponse,
    PncpMonitoramentoUpdate,
    PncpResultadoResponse,
    PncpResultadoStatusUpdate,
)

# ==================== PncpMonitoramentoCreate ====================


class TestPncpMonitoramentoCreate:

    def test_valid_minimal(self):
        data = PncpMonitoramentoCreate(nome="Monitor TI")
        assert data.nome == "Monitor TI"
        assert data.ativo is True
        assert data.palavras_chave is None
        assert data.ufs is None
        assert data.modalidades is None
        assert data.esferas is None
        assert data.valor_minimo is None
        assert data.valor_maximo is None

    def test_valid_full(self):
        data = PncpMonitoramentoCreate(
            nome="Monitor Pavimentacao",
            ativo=False,
            palavras_chave=["pavimentacao", "asfalto"],
            ufs=["SP", "RJ"],
            modalidades=["pregao"],
            esferas=["municipal"],
            valor_minimo=Decimal("100000.00"),
            valor_maximo=Decimal("5000000.00"),
        )
        assert data.nome == "Monitor Pavimentacao"
        assert data.ativo is False
        assert data.palavras_chave == ["pavimentacao", "asfalto"]
        assert data.ufs == ["SP", "RJ"]
        assert data.valor_minimo == Decimal("100000.00")
        assert data.valor_maximo == Decimal("5000000.00")

    def test_missing_nome_raises(self):
        with pytest.raises(ValidationError):
            PncpMonitoramentoCreate()

    def test_nome_empty_raises(self):
        with pytest.raises(ValidationError):
            PncpMonitoramentoCreate(nome="")

    def test_nome_max_length(self):
        with pytest.raises(ValidationError):
            PncpMonitoramentoCreate(nome="x" * 201)

    def test_palavras_chave_max_20(self):
        """palavras_chave cannot exceed 20 items."""
        palavras = [f"palavra_{i}" for i in range(21)]
        with pytest.raises(ValidationError, match="20 palavras-chave"):
            PncpMonitoramentoCreate(nome="Monitor", palavras_chave=palavras)

    def test_palavras_chave_exactly_20_ok(self):
        palavras = [f"palavra_{i}" for i in range(20)]
        data = PncpMonitoramentoCreate(nome="Monitor", palavras_chave=palavras)
        assert len(data.palavras_chave) == 20

    def test_ufs_max_27(self):
        """ufs cannot exceed 27 items."""
        ufs = [f"U{i:02d}" for i in range(28)]
        with pytest.raises(ValidationError, match="27 UFs"):
            PncpMonitoramentoCreate(nome="Monitor", ufs=ufs)

    def test_ufs_exactly_27_ok(self):
        ufs = [f"U{i:02d}" for i in range(27)]
        data = PncpMonitoramentoCreate(nome="Monitor", ufs=ufs)
        assert len(data.ufs) == 27

    def test_valor_minimo_negative_raises(self):
        with pytest.raises(ValidationError, match="negativo"):
            PncpMonitoramentoCreate(nome="Monitor", valor_minimo=Decimal("-1"))

    def test_valor_maximo_negative_raises(self):
        with pytest.raises(ValidationError, match="negativo"):
            PncpMonitoramentoCreate(nome="Monitor", valor_maximo=Decimal("-100"))

    def test_valor_minimo_zero_ok(self):
        data = PncpMonitoramentoCreate(nome="Monitor", valor_minimo=Decimal("0"))
        assert data.valor_minimo == Decimal("0")

    def test_valor_maximo_zero_ok(self):
        data = PncpMonitoramentoCreate(nome="Monitor", valor_maximo=Decimal("0"))
        assert data.valor_maximo == Decimal("0")


# ==================== PncpMonitoramentoUpdate ====================


class TestPncpMonitoramentoUpdate:

    def test_partial_update_nome_only(self):
        data = PncpMonitoramentoUpdate(nome="Novo Nome")
        dumped = data.model_dump(exclude_unset=True)
        assert dumped == {"nome": "Novo Nome"}

    def test_partial_update_ativo_only(self):
        data = PncpMonitoramentoUpdate(ativo=False)
        dumped = data.model_dump(exclude_unset=True)
        assert dumped == {"ativo": False}

    def test_empty_update(self):
        data = PncpMonitoramentoUpdate()
        dumped = data.model_dump(exclude_unset=True)
        assert dumped == {}

    def test_update_multiple_fields(self):
        data = PncpMonitoramentoUpdate(
            nome="Atualizado",
            palavras_chave=["nova", "busca"],
            valor_minimo=Decimal("50000"),
        )
        dumped = data.model_dump(exclude_unset=True)
        assert "nome" in dumped
        assert "palavras_chave" in dumped
        assert "valor_minimo" in dumped
        assert "ativo" not in dumped


# ==================== PncpResultadoStatusUpdate ====================


class TestPncpResultadoStatusUpdate:

    def test_valid_status_novo(self):
        data = PncpResultadoStatusUpdate(status="novo")
        assert data.status == "novo"

    def test_valid_status_interessante(self):
        data = PncpResultadoStatusUpdate(status="interessante")
        assert data.status == "interessante"

    def test_valid_status_descartado(self):
        data = PncpResultadoStatusUpdate(status="descartado")
        assert data.status == "descartado"

    def test_valid_status_importado(self):
        data = PncpResultadoStatusUpdate(status="importado")
        assert data.status == "importado"

    def test_invalid_status_raises(self):
        with pytest.raises(ValidationError, match="Status inválido"):
            PncpResultadoStatusUpdate(status="invalido")

    def test_empty_status_raises(self):
        with pytest.raises(ValidationError):
            PncpResultadoStatusUpdate(status="")


# ==================== PncpBuscaResponse ====================


class TestPncpBuscaResponse:

    def test_busca_response_parsing(self):
        data = PncpBuscaResponse(
            data=[{"id": 1, "objeto": "teste"}],
            total_registros=100,
            total_paginas=5,
            numero_pagina=1,
            paginas_restantes=4,
        )
        assert len(data.data) == 1
        assert data.total_registros == 100
        assert data.total_paginas == 5
        assert data.numero_pagina == 1
        assert data.paginas_restantes == 4

    def test_busca_response_defaults(self):
        data = PncpBuscaResponse(data=[])
        assert data.total_registros == 0
        assert data.total_paginas == 0
        assert data.numero_pagina == 1
        assert data.paginas_restantes == 0


# ==================== PncpImportarRequest ====================


class TestPncpImportarRequest:

    def test_importar_with_observacoes(self):
        data = PncpImportarRequest(observacoes="Resultado interessante")
        assert data.observacoes == "Resultado interessante"

    def test_importar_without_observacoes(self):
        data = PncpImportarRequest()
        assert data.observacoes is None

    def test_importar_empty_body(self):
        data = PncpImportarRequest.model_validate({})
        assert data.observacoes is None


# ==================== PncpMonitoramentoResponse ====================


class TestPncpMonitoramentoResponse:

    def test_from_attributes(self):
        """from_attributes allows creation from ORM-like objects."""

        class FakeMonitor:
            id = 1
            user_id = 10
            nome = "Monitor Test"
            ativo = True
            palavras_chave = ["asfalto"]
            ufs = ["SP"]
            modalidades = None
            esferas = None
            valor_minimo = Decimal("1000")
            valor_maximo = None
            ultimo_check = None
            created_at = datetime(2026, 1, 15, 10, 0)

        resp = PncpMonitoramentoResponse.model_validate(FakeMonitor(), from_attributes=True)
        assert resp.id == 1
        assert resp.user_id == 10
        assert resp.nome == "Monitor Test"
        assert resp.palavras_chave == ["asfalto"]
        assert resp.created_at == datetime(2026, 1, 15, 10, 0)


# ==================== PncpResultadoResponse ====================


class TestPncpResultadoResponse:

    def test_from_attributes(self):
        class FakeResultado:
            id = 5
            monitoramento_id = 1
            user_id = 10
            numero_controle_pncp = "12345678901234567890"
            orgao_cnpj = "12345678000100"
            orgao_razao_social = "Prefeitura Municipal"
            objeto_compra = "Pavimentacao asfaltica"
            modalidade_nome = "Pregao Eletronico"
            uf = "SP"
            municipio = "Sao Paulo"
            valor_estimado = Decimal("500000.00")
            data_abertura = datetime(2026, 3, 15)
            data_encerramento = datetime(2026, 4, 15)
            link_sistema_origem = "https://pncp.gov.br/1234"
            status = "novo"
            licitacao_id = None
            encontrado_em = datetime(2026, 1, 10)

        resp = PncpResultadoResponse.model_validate(FakeResultado(), from_attributes=True)
        assert resp.id == 5
        assert resp.numero_controle_pncp == "12345678901234567890"
        assert resp.status == "novo"
        assert resp.valor_estimado == Decimal("500000.00")


# ==================== PncpResultadoStatus Constants ====================


class TestPncpResultadoStatusConstants:

    def test_all_statuses_present(self):
        assert PncpResultadoStatus.NOVO == "novo"
        assert PncpResultadoStatus.INTERESSANTE == "interessante"
        assert PncpResultadoStatus.DESCARTADO == "descartado"
        assert PncpResultadoStatus.IMPORTADO == "importado"
        assert len(PncpResultadoStatus.ALL) == 4
        assert set(PncpResultadoStatus.ALL) == {"novo", "interessante", "descartado", "importado"}
