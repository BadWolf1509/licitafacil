"""Tests for Pydantic schemas defined in schemas.py."""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from schemas import (
    AnaliseManualCreate,
    AtestadoServicosUpdate,
    ExigenciaEdital,
    PaginatedResponse,
    ServicoAtestado,
)

# ---------- ServicoAtestado ----------


def test_servico_atestado_valid_data():
    """ServicoAtestado accepts a fully-populated, valid payload."""
    servico = ServicoAtestado(
        item="1.1",
        descricao="Fornecimento de cabos de fibra optica",
        quantidade=150.5,
        unidade="metros",
    )
    assert servico.item == "1.1"
    assert servico.descricao == "Fornecimento de cabos de fibra optica"
    assert servico.quantidade == 150.5
    assert servico.unidade == "metros"


def test_servico_atestado_rejects_empty_descricao():
    """Whitespace-only descricao must be rejected by the model validator."""
    with pytest.raises(ValidationError, match="descricao nao pode ser uma string vazia"):
        ServicoAtestado(descricao="   ")


def test_servico_atestado_allows_none_descricao():
    """None descricao is perfectly valid (all fields are optional)."""
    servico = ServicoAtestado(descricao=None)
    assert servico.descricao is None


def test_servico_atestado_max_length_descricao():
    """descricao exceeding 1000 characters must fail validation."""
    long_text = "a" * 1001
    with pytest.raises(ValidationError):
        ServicoAtestado(descricao=long_text)


def test_servico_atestado_max_length_item():
    """item exceeding 50 characters must fail validation."""
    long_item = "x" * 51
    with pytest.raises(ValidationError):
        ServicoAtestado(item=long_item)


def test_servico_atestado_max_length_unidade():
    """unidade exceeding 50 characters must fail validation."""
    long_unidade = "u" * 51
    with pytest.raises(ValidationError):
        ServicoAtestado(unidade=long_unidade)


# ---------- ExigenciaEdital ----------


def test_exigencia_edital_valid_data():
    """ExigenciaEdital accepts a complete, valid payload."""
    exigencia = ExigenciaEdital(
        descricao="Servico de limpeza predial",
        quantidade_minima=Decimal("500.00"),
        unidade="m2",
        permitir_soma=True,
        exige_unico=False,
    )
    assert exigencia.descricao == "Servico de limpeza predial"
    assert exigencia.quantidade_minima == Decimal("500.00")
    assert exigencia.unidade == "m2"
    assert exigencia.permitir_soma is True
    assert exigencia.exige_unico is False


# ---------- AnaliseManualCreate ----------


def test_analise_manual_create_valid_data():
    """AnaliseManualCreate accepts a nome_licitacao and a list of exigencias."""
    analise = AnaliseManualCreate(
        nome_licitacao="Pregao 001/2026",
        exigencias=[
            ExigenciaEdital(
                descricao="Manutencao de ar condicionado",
                quantidade_minima=Decimal("10"),
                unidade="unidades",
            ),
        ],
    )
    assert analise.nome_licitacao == "Pregao 001/2026"
    assert len(analise.exigencias) == 1
    assert analise.exigencias[0].descricao == "Manutencao de ar condicionado"


# ---------- PaginatedResponse ----------


def test_paginated_response_create():
    """PaginatedResponse.create computes total_pages correctly."""
    items = ["a", "b", "c"]
    response = PaginatedResponse.create(
        items=items,
        total=10,
        page=1,
        page_size=3,
    )
    assert response.items == ["a", "b", "c"]
    assert response.total == 10
    assert response.page == 1
    assert response.page_size == 3
    # ceil(10 / 3) == 4
    assert response.total_pages == 4


# ---------- AtestadoServicosUpdate ----------


def test_atestado_servicos_update_validates_list():
    """AtestadoServicosUpdate wraps a list of ServicoAtestado and validates each."""
    update = AtestadoServicosUpdate(
        servicos_json=[
            ServicoAtestado(item="1", descricao="Pintura", quantidade=200, unidade="m2"),
            ServicoAtestado(item="2", descricao="Limpeza", quantidade=50, unidade="m2"),
        ]
    )
    assert len(update.servicos_json) == 2
    assert update.servicos_json[0].descricao == "Pintura"
    assert update.servicos_json[1].quantidade == 50

    # A list containing an invalid ServicoAtestado must be rejected.
    with pytest.raises(ValidationError):
        AtestadoServicosUpdate(
            servicos_json=[
                ServicoAtestado(item="1", descricao="Ok"),
                {"descricao": "   "},  # whitespace-only descricao
            ]
        )
