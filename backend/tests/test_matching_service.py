import json
from pathlib import Path

import pytest

from services.extraction import extract_keywords, normalize_pt_morphology
from services.matching_service import (
    _check_exclusive_qualifiers,
    matching_service,
)


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


# ============================================================
# Ajuste: Stopwords (OU, numeros curtos)
# ============================================================

class TestStopwordsOuAndNumbers:
    def test_ou_nao_gera_match_espurio(self):
        """Palavra OU nao deve contribuir para similaridade."""
        kw = extract_keywords("PISO EM GRANILITE, MARMORITE OU GRANITINA")
        assert "OU" not in kw

    def test_numeros_curtos_removidos(self):
        """Numeros de 1-2 digitos nao devem ser keywords."""
        kw = extract_keywords("ARGAMASSA TRACO 1:2:8 PREPARO MANUAL")
        assert "1" not in kw
        assert "2" not in kw
        assert "8" not in kw
        assert "ARGAMASSA" in kw
        assert "MANUAL" in kw

    def test_numeros_longos_preservados(self):
        """Numeros de 3+ digitos devem ser preservados como keywords."""
        kw = extract_keywords("BETONEIRA 400L")
        assert "400L" in kw

    def test_granilite_nao_casa_com_lastro_via_ou(self):
        """Lastro de concreto nao deve casar com piso em granilite."""
        exigencias = [{
            "descricao": "Piso em granilite, marmorite ou granitina",
            "quantidade_minima": 100,
            "unidade": "M2",
        }]
        atestados = [{
            "id": 1,
            "descricao_servico": "Atestado 1",
            "servicos_json": [{
                "item": "1.1",
                "descricao": "Lastro de concreto magro, aplicado em pisos ou radiers",
                "quantidade": 200,
                "unidade": "M2",
            }],
        }]
        results = matching_service.match_exigencias(exigencias, atestados)
        assert results[0]["status"] == "nao_atende"


# ============================================================
# Ajuste: Siglas preservadas (EPS, ABS)
# ============================================================

class TestSiglaExceptions:
    def test_eps_preservado(self):
        """EPS nao deve ser normalizado para EP."""
        assert normalize_pt_morphology("EPS") == "EPS"

    def test_abs_preservado(self):
        """ABS nao deve ser normalizado para AB."""
        assert normalize_pt_morphology("ABS") == "ABS"

    def test_eps_keyword_preservada(self):
        """EPS deve aparecer como keyword, nao EP."""
        kw = extract_keywords("MOLDURA EM EPS PARA FACHADA")
        assert "EPS" in kw
        assert "EP" not in kw


# ============================================================
# Ajuste: MECANICO no grupo de qualifiers
# ============================================================

class TestMecanicoQualifier:
    def test_manual_vs_mecanico_blocks(self):
        """Preparo manual nao deve casar com preparo mecanico."""
        assert _check_exclusive_qualifiers({"MANUAL"}, {"MECANICO"}) is False

    def test_mecanico_vs_manual_blocks(self):
        """Preparo mecanico nao deve casar com preparo manual."""
        assert _check_exclusive_qualifiers({"MECANICO"}, {"MANUAL"}) is False

    def test_mecanico_vs_mecanico_passes(self):
        """Mecanico vs mecanico deve passar."""
        assert _check_exclusive_qualifiers({"MECANICO"}, {"MECANICO"}) is True

    def test_emboco_manual_vs_reboco_mecanico(self):
        """Emboco manual nao deve casar com reboco mecanico."""
        exigencias = [{
            "descricao": "Emboco em argamassa preparo manual aplicado manualmente em paredes",
            "quantidade_minima": 100,
            "unidade": "M2",
        }]
        atestados = [{
            "id": 1,
            "descricao_servico": "Atestado 1",
            "servicos_json": [{
                "item": "1.1",
                "descricao": "Reboco vertical em argamassa preparo mecanico com betoneira",
                "quantidade": 200,
                "unidade": "M2",
            }],
        }]
        results = matching_service.match_exigencias(exigencias, atestados)
        assert results[0]["status"] == "nao_atende"


# ============================================================
# Ajuste: Grupo exclusivo PISO/PAREDE/TETO/FORRO/MURO
# ============================================================

class TestElementoQualifier:
    def test_piso_vs_parede_blocks(self):
        """Piso nao deve casar com parede."""
        assert _check_exclusive_qualifiers({"PISO"}, {"PAREDE"}) is False

    def test_piso_vs_teto_blocks(self):
        """Piso nao deve casar com teto."""
        assert _check_exclusive_qualifiers({"PISO"}, {"TETO"}) is False

    def test_piso_vs_piso_passes(self):
        """Piso vs piso deve passar."""
        assert _check_exclusive_qualifiers({"PISO"}, {"PISO"}) is True

    def test_servico_com_multiplos_elementos_passa(self):
        """Item que menciona piso e parede deve casar com exigencia de piso."""
        assert _check_exclusive_qualifiers({"PISO"}, {"PISO", "PAREDE"}) is True

    def test_parede_concreto_nao_casa_com_piso_concreto(self):
        """Parede de concreto nao deve casar com piso em concreto."""
        exigencias = [{
            "descricao": "Piso em concreto 20 MPA preparo mecanico",
            "quantidade_minima": 100,
            "unidade": "M2",
        }]
        atestados = [{
            "id": 1,
            "descricao_servico": "Atestado 1",
            "servicos_json": [{
                "item": "1.1",
                "descricao": "Parede de placa pre-moldada de concreto preparo mecanico com betoneira",
                "quantidade": 200,
                "unidade": "M2",
            }],
        }]
        results = matching_service.match_exigencias(exigencias, atestados)
        assert results[0]["status"] == "nao_atende"


# ============================================================
# Ajuste: Novos mandatory patterns
# ============================================================

class TestNewMandatoryPatterns:
    def test_texturizada_bloqueia_selador(self):
        """Selador acrilico nao deve casar com pintura texturizada."""
        exigencias = [{
            "descricao": "Aplicacao manual de pintura com tinta texturizada acrilica",
            "quantidade_minima": 100,
            "unidade": "M2",
        }]
        atestados = [{
            "id": 1,
            "descricao_servico": "Atestado 1",
            "servicos_json": [{
                "item": "1.1",
                "descricao": "Fundo selador acrilico, aplicacao manual em parede",
                "quantidade": 200,
                "unidade": "M2",
            }],
        }]
        results = matching_service.match_exigencias(exigencias, atestados)
        assert results[0]["status"] == "nao_atende"

    def test_texturizada_casa_com_texturizada(self):
        """Pintura texturizada deve casar com pintura texturizada."""
        exigencias = [{
            "descricao": "Aplicacao manual de pintura com tinta texturizada acrilica",
            "quantidade_minima": 100,
            "unidade": "M2",
        }]
        atestados = [{
            "id": 1,
            "descricao_servico": "Atestado 1",
            "servicos_json": [{
                "item": "1.1",
                "descricao": "Aplicacao manual de pintura com tinta texturizada acrilica em fachada",
                "quantidade": 200,
                "unidade": "M2",
            }],
        }]
        results = matching_service.match_exigencias(exigencias, atestados)
        assert results[0]["status"] == "atende"

    def test_emboco_mandatory_bloqueia_alvenaria(self):
        """Alvenaria com argamassa nao deve casar com emboco."""
        exigencias = [{
            "descricao": "Emboco em argamassa preparo manual em paredes",
            "quantidade_minima": 100,
            "unidade": "M2",
        }]
        atestados = [{
            "id": 1,
            "descricao_servico": "Atestado 1",
            "servicos_json": [{
                "item": "1.1",
                "descricao": "Alvenaria de vedacao com blocos ceramicos e argamassa preparo manual",
                "quantidade": 200,
                "unidade": "M2",
            }],
        }]
        results = matching_service.match_exigencias(exigencias, atestados)
        assert results[0]["status"] == "nao_atende"

    def test_revisao_cobertura_bloqueia_telhamento(self):
        """Telhamento novo nao deve casar com revisao de cobertura."""
        exigencias = [{
            "descricao": "Revisao de cobertura em telha ceramica",
            "quantidade_minima": 100,
            "unidade": "M2",
        }]
        atestados = [{
            "id": 1,
            "descricao_servico": "Atestado 1",
            "servicos_json": [{
                "item": "1.1",
                "descricao": "Telhamento com telha ceramica capa-canal tipo colonial",
                "quantidade": 200,
                "unidade": "M2",
            }],
        }]
        results = matching_service.match_exigencias(exigencias, atestados)
        assert results[0]["status"] == "nao_atende"

    def test_revisao_cobertura_casa_com_revisao(self):
        """Revisao de cobertura deve casar com revisao de cobertura."""
        exigencias = [{
            "descricao": "Revisao de cobertura em telha ceramica",
            "quantidade_minima": 100,
            "unidade": "M2",
        }]
        atestados = [{
            "id": 1,
            "descricao_servico": "Atestado 1",
            "servicos_json": [{
                "item": "1.1",
                "descricao": "Revisao em cobertura com telha ceramica tipo canal, com reposicao de 10 porcento",
                "quantidade": 200,
                "unidade": "M2",
            }],
        }]
        results = matching_service.match_exigencias(exigencias, atestados)
        assert results[0]["status"] == "atende"


# ============================================================
# Ajuste: Atividade COMPACTACAO
# ============================================================

class TestCompactacaoActivity:
    def test_compactacao_nao_casa_com_execucao_piso(self):
        """Compactacao de solo nao deve casar com execucao de piso."""
        exigencias = [{
            "descricao": "Execucao de piso em concreto armado",
            "quantidade_minima": 100,
            "unidade": "M2",
        }]
        atestados = [{
            "id": 1,
            "descricao_servico": "Atestado 1",
            "servicos_json": [{
                "item": "1.1",
                "descricao": "Compactacao mecanica de solo para piso de concreto",
                "quantidade": 200,
                "unidade": "M2",
            }],
        }]
        results = matching_service.match_exigencias(exigencias, atestados)
        assert results[0]["status"] == "nao_atende"
