import json
from pathlib import Path
import pytest

from services.matching_service import matching_service


def test_matching_sums_across_atestados():
    exigencias = [{
        "descricao": "Pavimentacao asfaltica em CBUQ",
        "quantidade_minima": 1000,
        "unidade": "M2",
    }]
    atestados = [
        {
            "id": 1,
            "descricao_servico": "Atestado 1",
            "servicos_json": [
                {"item": "1.1", "descricao": "Pavimentacao asfaltica em CBUQ", "quantidade": 600, "unidade": "M2"}
            ],
        },
        {
            "id": 2,
            "descricao_servico": "Atestado 2",
            "servicos_json": [
                {"item": "2.1", "descricao": "Pavimentacao asfaltica", "quantidade": 500, "unidade": "M2"}
            ],
        },
    ]

    results = matching_service.match_exigencias(exigencias, atestados)

    assert results
    assert results[0]["status"] == "atende"
    assert results[0]["soma_quantidades"] == pytest.approx(1100.0)
    assert len(results[0]["atestados_recomendados"]) == 2


def test_matching_respects_unit():
    exigencias = [{
        "descricao": "Escavacao manual",
        "quantidade_minima": 10,
        "unidade": "M3",
    }]
    atestados = [{
        "id": 1,
        "descricao_servico": "Atestado 1",
        "servicos_json": [
            {"item": "1.1", "descricao": "Escavacao manual", "quantidade": 20, "unidade": "M2"}
        ],
    }]

    results = matching_service.match_exigencias(exigencias, atestados)

    assert results[0]["status"] == "nao_atende"
    assert results[0]["atestados_recomendados"] == []


def test_matching_exige_unico():
    exigencias = [{
        "descricao": "Pavimentacao asfaltica",
        "quantidade_minima": 1000,
        "unidade": "M2",
        "exige_unico": True,
    }]
    atestados = [
        {
            "id": 1,
            "descricao_servico": "Atestado 1",
            "servicos_json": [
                {"item": "1.1", "descricao": "Pavimentacao asfaltica", "quantidade": 600, "unidade": "M2"}
            ],
        },
        {
            "id": 2,
            "descricao_servico": "Atestado 2",
            "servicos_json": [
                {"item": "2.1", "descricao": "Pavimentacao asfaltica", "quantidade": 500, "unidade": "M2"}
            ],
        },
    ]

    results = matching_service.match_exigencias(exigencias, atestados)

    assert results[0]["status"] == "parcial"
    assert len(results[0]["atestados_recomendados"]) == 1
    assert results[0]["soma_quantidades"] == pytest.approx(600.0)


def test_matching_fallback_to_atestado_fields():
    exigencias = [{
        "descricao": "Execucao de meio fio",
        "quantidade_minima": 100,
        "unidade": "M",
    }]
    atestados = [{
        "id": 1,
        "descricao_servico": "Execucao de meio fio",
        "quantidade": 120,
        "unidade": "M",
    }]

    results = matching_service.match_exigencias(exigencias, atestados)

    assert results[0]["status"] == "atende"
    assert results[0]["soma_quantidades"] == pytest.approx(120.0)


def test_matching_coverage_with_long_description():
    exigencias = [{
        "descricao": "Fornecimento e instalacao de cabo de cobre flexivel e/ou rigido isolado",
        "quantidade_minima": 100,
        "unidade": "M",
    }]
    atestados = [{
        "id": 1,
        "descricao_servico": "Atestado 1",
        "servicos_json": [
            {
                "item": "1.1",
                "descricao": "CABO DE COBRE FLEXIVEL ISOLADO, 2,5 MM2, ANTI-CHAMA 450/750 V, PARA CIRCUITOS TERMINAIS - FORNECIMENTO E INSTALACAO",
                "quantidade": 150,
                "unidade": "M",
            }
        ],
    }]

    results = matching_service.match_exigencias(exigencias, atestados)

    assert results[0]["status"] == "atende"
    assert results[0]["soma_quantidades"] == pytest.approx(150.0)


def test_activity_gate_blocks_mismatched_activity():
    exigencias = [{
        "descricao": "Revestimento ceramico para piso",
        "quantidade_minima": 10,
        "unidade": "M2",
    }]
    atestados = [{
        "id": 1,
        "descricao_servico": "Atestado 1",
        "servicos_json": [
            {
                "item": "1.1",
                "descricao": "Limpeza de piso ceramico com pano umido",
                "quantidade": 20,
                "unidade": "M2",
            }
        ],
    }]

    results = matching_service.match_exigencias(exigencias, atestados)

    assert results[0]["status"] == "nao_atende"
    assert results[0]["atestados_recomendados"] == []


def test_mandatory_tokens_block_incorrect_material():
    exigencias = [{
        "descricao": "Fornecimento e instalacao de vidro laminado",
        "quantidade_minima": 10,
        "unidade": "M2",
    }]
    atestados = [{
        "id": 1,
        "descricao_servico": "Atestado 1",
        "servicos_json": [
            {
                "item": "1.1",
                "descricao": "Fornecimento e instalacao de placa em ACM",
                "quantidade": 20,
                "unidade": "M2",
            }
        ],
    }]

    results = matching_service.match_exigencias(exigencias, atestados)

    assert results[0]["status"] == "nao_atende"
    assert results[0]["atestados_recomendados"] == []


def test_matching_fixture_file():
    fixture_path = Path(__file__).parent / "fixtures" / "matching_fixture.json"
    data = json.loads(fixture_path.read_text(encoding="utf-8"))

    results = matching_service.match_exigencias(
        data["exigencias"],
        data["atestados"]
    )

    assert len(results) == 2
    status_map = {r["exigencia"]["descricao"]: r["status"] for r in results}
    assert status_map["Fornecimento e instalacao de cabo de cobre flexivel isolado"] == "atende"
    assert status_map["Forro em placas de gesso"] == "atende"
