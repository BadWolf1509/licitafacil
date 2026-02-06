import json
from pathlib import Path
import pytest

from services.matching_service import (
    matching_service,
    _check_exclusive_qualifiers,
)
from services.extraction import normalize_pt_morphology, extract_keywords


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


# ============================================================
# Melhoria 3: Normalização morfológica (plural/gênero)
# ============================================================

class TestNormalizePtMorphology:
    def test_plural_regular(self):
        assert normalize_pt_morphology("BLOCOS") == "BLOCO"
        assert normalize_pt_morphology("LAJOTAS") == "LAJOTA"
        assert normalize_pt_morphology("CERAMICOS") == "CERAMICO"
        assert normalize_pt_morphology("PISOS") == "PISO"

    def test_plural_oes(self):
        assert normalize_pt_morphology("TUBULACOES") == "TUBULACAO"
        assert normalize_pt_morphology("INSTALACOES") == "INSTALACAO"
        assert normalize_pt_morphology("FUNDACOES") == "FUNDACAO"

    def test_plural_ais(self):
        assert normalize_pt_morphology("MATERIAIS") == "MATERIAL"
        assert normalize_pt_morphology("ESTRUTURAIS") == "ESTRUTURAL"

    def test_plural_eis(self):
        assert normalize_pt_morphology("PAPEIS") == "PAPEL"

    def test_plural_ores(self):
        assert normalize_pt_morphology("CONDUTORES") == "CONDUTOR"
        assert normalize_pt_morphology("DISJUNTORES") == "DISJUNTOR"

    def test_plural_ns(self):
        assert normalize_pt_morphology("ARMAZENS") == "ARMAZEM"

    def test_gender_ada(self):
        assert normalize_pt_morphology("FURADA") == "FURADO"
        assert normalize_pt_morphology("MOLDADA") == "MOLDADO"
        assert normalize_pt_morphology("ARMADA") == "ARMADO"

    def test_gender_ida(self):
        assert normalize_pt_morphology("POLIDA") == "POLIDO"

    def test_gender_ica(self):
        assert normalize_pt_morphology("CERAMICA") == "CERAMICO"
        assert normalize_pt_morphology("METALICA") == "METALICO"

    def test_gender_exceptions(self):
        """Substantivos femininos não devem ser alterados."""
        assert normalize_pt_morphology("LAJOTA") == "LAJOTA"
        assert normalize_pt_morphology("VIGA") == "VIGA"
        assert normalize_pt_morphology("ARGAMASSA") == "ARGAMASSA"
        assert normalize_pt_morphology("TELHA") == "TELHA"
        assert normalize_pt_morphology("PLACA") == "PLACA"
        assert normalize_pt_morphology("CAIXA") == "CAIXA"

    def test_short_words_unchanged(self):
        """Palavras com 2 chars ou menos não devem ser normalizadas."""
        assert normalize_pt_morphology("NA") == "NA"
        assert normalize_pt_morphology("DA") == "DA"
        assert normalize_pt_morphology("OS") == "OS"
        assert normalize_pt_morphology("M") == "M"

    def test_keywords_match_with_plural(self):
        """extract_keywords deve normalizar plurais, permitindo matching."""
        kw1 = extract_keywords("LAJOTAS CERAMICAS PRE MOLDADAS")
        kw2 = extract_keywords("LAJOTA CERAMICA PRE MOLDADA")
        # Ambos devem ter as mesmas keywords após normalização
        assert kw1 & kw2, f"Keywords devem ter interseção: {kw1} vs {kw2}"
        # LAJOTA deve estar em ambos
        assert "LAJOTA" in kw1
        assert "LAJOTA" in kw2


# ============================================================
# Melhoria 1: Qualificadores exclusivos
# ============================================================

class TestExclusiveQualifiers:
    def test_check_function_blocks_contradiction(self):
        """Qualificadores contraditórios devem retornar False."""
        assert _check_exclusive_qualifiers({"VERTICAL"}, {"HORIZONTAL"}) is False
        assert _check_exclusive_qualifiers({"INTERNO"}, {"EXTERNO"}) is False
        assert _check_exclusive_qualifiers({"VEDACAO"}, {"ESTRUTURAL"}) is False
        assert _check_exclusive_qualifiers({"MANUAL"}, {"MECANIZADO"}) is False

    def test_check_function_allows_same_qualifier(self):
        """Mesmo qualificador deve retornar True."""
        assert _check_exclusive_qualifiers({"VERTICAL"}, {"VERTICAL"}) is True
        assert _check_exclusive_qualifiers({"INTERNO"}, {"INTERNO"}) is True
        assert _check_exclusive_qualifiers({"VEDACAO"}, {"VEDACAO"}) is True

    def test_check_function_allows_no_qualifier(self):
        """Se um lado não tem qualificador do grupo, deve ser compatível."""
        assert _check_exclusive_qualifiers({"VERTICAL"}, {"BLOCO", "CERAMICO"}) is True
        assert _check_exclusive_qualifiers({"BLOCO"}, {"HORIZONTAL"}) is True
        assert _check_exclusive_qualifiers(set(), {"VERTICAL"}) is True

    def test_horizontal_vs_vertical_blocks_match(self):
        """Exigência VERTICAL não deve casar com atestado HORIZONTAL."""
        exigencias = [{
            "descricao": "Alvenaria de vedacao de blocos ceramicos furados na vertical",
            "quantidade_minima": 100,
            "unidade": "M2",
        }]
        atestados = [{
            "id": 1,
            "descricao_servico": "Atestado 1",
            "servicos_json": [{
                "item": "1.1",
                "descricao": "Alvenaria de vedacao de blocos ceramicos furados na horizontal",
                "quantidade": 200,
                "unidade": "M2",
            }],
        }]

        results = matching_service.match_exigencias(exigencias, atestados)
        assert results[0]["status"] == "nao_atende"
        assert results[0]["atestados_recomendados"] == []

    def test_vertical_same_qualifier_matches(self):
        """Exigência VERTICAL deve casar com atestado VERTICAL."""
        exigencias = [{
            "descricao": "Alvenaria de vedacao de blocos ceramicos furados na vertical",
            "quantidade_minima": 100,
            "unidade": "M2",
        }]
        atestados = [{
            "id": 1,
            "descricao_servico": "Atestado 1",
            "servicos_json": [{
                "item": "1.1",
                "descricao": "Alvenaria de vedacao de blocos ceramicos furados na vertical",
                "quantidade": 200,
                "unidade": "M2",
            }],
        }]

        results = matching_service.match_exigencias(exigencias, atestados)
        assert results[0]["status"] == "atende"
        assert results[0]["soma_quantidades"] == pytest.approx(200.0)

    def test_manual_vs_mecanizada_blocks(self):
        """Escavacao manual não deve casar com escavacao mecanizada."""
        exigencias = [{
            "descricao": "Escavacao manual de vala",
            "quantidade_minima": 50,
            "unidade": "M3",
        }]
        atestados = [{
            "id": 1,
            "descricao_servico": "Atestado 1",
            "servicos_json": [{
                "item": "1.1",
                "descricao": "Escavacao mecanizada de vala",
                "quantidade": 100,
                "unidade": "M3",
            }],
        }]

        results = matching_service.match_exigencias(exigencias, atestados)
        assert results[0]["status"] == "nao_atende"

    def test_both_qualifiers_in_requirement_allows_either(self):
        """Se exigência menciona ambos qualificadores (e/ou), qualquer um é aceito."""
        # "flexivel e/ou rigido" → ambos estão na exigência → qualquer é OK
        assert _check_exclusive_qualifiers(
            {"FLEXIVEL", "RIGIDO", "CABO"}, {"FLEXIVEL", "CABO"}
        ) is True
        assert _check_exclusive_qualifiers(
            {"FLEXIVEL", "RIGIDO", "CABO"}, {"RIGIDO", "CABO"}
        ) is True

    def test_vedacao_vs_estrutural_blocks(self):
        """Alvenaria de vedação não deve casar com alvenaria estrutural."""
        exigencias = [{
            "descricao": "Alvenaria de vedacao com blocos ceramicos",
            "quantidade_minima": 100,
            "unidade": "M2",
        }]
        atestados = [{
            "id": 1,
            "descricao_servico": "Atestado 1",
            "servicos_json": [{
                "item": "1.1",
                "descricao": "Alvenaria estrutural com blocos ceramicos",
                "quantidade": 200,
                "unidade": "M2",
            }],
        }]

        results = matching_service.match_exigencias(exigencias, atestados)
        assert results[0]["status"] == "nao_atende"


# ============================================================
# Melhoria 2: Ranking composto (similaridade + quantidade)
# ============================================================

class TestCompositeRanking:
    def test_ranking_prefers_higher_similarity(self):
        """Atestado com maior similaridade deve ser selecionado primeiro,
        mesmo que tenha menor quantidade."""
        exigencias = [{
            "descricao": "Fornecimento e instalacao de piso ceramico",
            "quantidade_minima": 100,
            "unidade": "M2",
        }]
        atestados = [
            {
                "id": 1,
                "descricao_servico": "Atestado genérico",
                "servicos_json": [{
                    "item": "1.1",
                    "descricao": "Fornecimento de material para piso",
                    "quantidade": 1000,
                    "unidade": "M2",
                }],
            },
            {
                "id": 2,
                "descricao_servico": "Atestado específico",
                "servicos_json": [{
                    "item": "2.1",
                    "descricao": "Fornecimento e instalacao de piso ceramico polido",
                    "quantidade": 200,
                    "unidade": "M2",
                }],
            },
        ]

        results = matching_service.match_exigencias(exigencias, atestados)
        recomendados = results[0]["atestados_recomendados"]
        assert len(recomendados) >= 1
        # O atestado 2 (mais similar) deve vir antes do atestado 1 (mais quantidade)
        assert recomendados[0]["atestado_id"] == 2

    def test_ranking_uses_quantity_as_tiebreaker(self):
        """Com mesma similaridade, maior quantidade deve vir primeiro."""
        exigencias = [{
            "descricao": "Pintura acrilica em parede",
            "quantidade_minima": 500,
            "unidade": "M2",
        }]
        atestados = [
            {
                "id": 1,
                "descricao_servico": "Atestado 1",
                "servicos_json": [{
                    "item": "1.1",
                    "descricao": "Pintura acrilica em parede interna",
                    "quantidade": 200,
                    "unidade": "M2",
                }],
            },
            {
                "id": 2,
                "descricao_servico": "Atestado 2",
                "servicos_json": [{
                    "item": "2.1",
                    "descricao": "Pintura acrilica em parede interna",
                    "quantidade": 400,
                    "unidade": "M2",
                }],
            },
        ]

        results = matching_service.match_exigencias(exigencias, atestados)
        recomendados = results[0]["atestados_recomendados"]
        assert len(recomendados) == 2
        # Com mesma similaridade, o de maior quantidade vem primeiro
        assert recomendados[0]["atestado_id"] == 2
        assert recomendados[0]["quantidade"] > recomendados[1]["quantidade"]


# ============================================================
# Teste de integração: as 3 melhorias juntas
# ============================================================

class TestIntegrationAllImprovements:
    def test_alvenaria_vertical_with_plural_and_ranking(self):
        """Cenário real: exigência de alvenaria vertical deve:
        1. Aceitar 'blocos' (plural) via normalização morfológica
        2. Rejeitar 'horizontal' via qualificadores exclusivos
        3. Priorizar match mais similar via ranking composto
        """
        exigencias = [{
            "descricao": "Alvenaria de vedacao de blocos ceramicos furados na vertical",
            "quantidade_minima": 300,
            "unidade": "M2",
        }]
        atestados = [
            {
                "id": 1,
                "descricao_servico": "Horizontal (deve ser rejeitado)",
                "servicos_json": [{
                    "item": "1.1",
                    "descricao": "Alvenaria de vedacao de blocos ceramicos furados na horizontal",
                    "quantidade": 500,
                    "unidade": "M2",
                }],
            },
            {
                "id": 2,
                "descricao_servico": "Vertical exato",
                "servicos_json": [{
                    "item": "2.1",
                    "descricao": "Alvenaria de vedacao de blocos ceramicos furados na vertical",
                    "quantidade": 350,
                    "unidade": "M2",
                }],
            },
            {
                "id": 3,
                "descricao_servico": "Vertical com plural",
                "servicos_json": [{
                    "item": "3.1",
                    "descricao": "Alvenaria de vedacao de blocos ceramicos furados na vertical",
                    "quantidade": 100,
                    "unidade": "M2",
                }],
            },
        ]

        results = matching_service.match_exigencias(exigencias, atestados)

        assert results[0]["status"] == "atende"
        recomendados = results[0]["atestados_recomendados"]
        # Atestado #1 (horizontal) não deve estar nos recomendados
        ids_recomendados = [r["atestado_id"] for r in recomendados]
        assert 1 not in ids_recomendados
        # Atestados #2 e #3 (verticais) devem estar
        assert 2 in ids_recomendados


def test_matching_no_atestados_returns_nao_atende():
    """Quando nao ha atestados, deve retornar nao_atende para cada exigencia."""
    exigencias = [
        {"descricao": "Pavimentacao asfaltica", "quantidade_minima": 500, "unidade": "M2"},
        {"descricao": "Drenagem pluvial", "quantidade_minima": 200, "unidade": "M"},
    ]
    results = matching_service.match_exigencias(exigencias, [])
    assert len(results) == 2
    assert results[0]["status"] == "nao_atende"
    assert results[0]["soma_quantidades"] == 0.0
    assert results[0]["atestados_recomendados"] == []
    assert results[0]["exigencia"]["descricao"] == "Pavimentacao asfaltica"
    assert results[1]["status"] == "nao_atende"
    assert results[1]["exigencia"]["descricao"] == "Drenagem pluvial"


def test_matching_no_exigencias_returns_empty():
    """Quando nao ha exigencias, deve retornar lista vazia."""
    atestados = [{"id": 1, "descricao_servico": "Atestado", "servicos_json": []}]
    results = matching_service.match_exigencias([], atestados)
    assert results == []
