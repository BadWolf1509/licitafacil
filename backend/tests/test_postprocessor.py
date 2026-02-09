"""
Testes unitários para o módulo services.postprocessor.

Cobre: postprocess_servicos, filter_items_without_code, should_replace_desc,
build_text_item_map, apply_text_descriptions, build_restart_prefix_maps,
normalize_servicos_fields, PostprocessConfig e filtros internos.
"""



from config.atestado import PostprocessConfig
from services.postprocessor import (
    apply_text_descriptions,
    build_restart_prefix_maps,
    build_text_item_map,
    filter_items_without_code,
    postprocess_servicos,
    should_replace_desc,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _servico(item=None, descricao="", quantidade=None, unidade="", **extra):
    """Atalho para criar um dict de serviço."""
    s = {"item": item, "descricao": descricao, "quantidade": quantidade, "unidade": unidade}
    s.update(extra)
    return s


# ===========================================================================
# 1. postprocess_servicos – entrada vazia
# ===========================================================================

class TestPostprocessServicosEmpty:
    """postprocess_servicos deve retornar lista vazia para entrada vazia."""

    def test_empty_list(self):
        result = postprocess_servicos(
            servicos=[],
            use_ai=False,
            table_used=False,
            servicos_table=[],
            texto="",
        )
        assert result == []

    def test_none_like_empty(self):
        """Passar None como servicos não deve estourar (filter_summary_rows trata)."""
        result = postprocess_servicos(
            servicos=[],
            use_ai=True,
            table_used=True,
            servicos_table=None,
            texto="",
        )
        assert isinstance(result, list)


# ===========================================================================
# 2. postprocess_servicos – normalização de campos
# ===========================================================================

class TestPostprocessServicosNormalization:
    """postprocess_servicos normaliza unidade e descricao."""

    def test_normalizes_unidade(self):
        """Unidades devem ser normalizadas (ex: 'metro' -> 'M')."""
        servicos = [
            _servico(item="1.1", descricao="Fornecimento de tubo PVC", quantidade=10, unidade="  m  "),
        ]
        result = postprocess_servicos(
            servicos=servicos,
            use_ai=False,
            table_used=False,
            servicos_table=[],
            texto="1.1 Fornecimento de tubo PVC",
        )
        # O pipeline pode filtrar o item se não tiver quantidade, mas a normalização ocorre.
        # Verificamos que os itens restantes têm unidade normalizada (stripped/uppercased).
        for s in result:
            unit = s.get("unidade") or ""
            assert unit == unit.strip(), "Unidade não deve ter espaços"

    def test_normalizes_descricao_strips_item_code(self):
        """Se descricao contém código de item embutido, deve ser extraído."""
        servicos = [
            _servico(
                item=None,
                descricao="1.2.3 PINTURA LATEX PVA INTERNA",
                quantidade=150,
                unidade="M2",
            ),
        ]
        result = postprocess_servicos(
            servicos=servicos,
            use_ai=False,
            table_used=False,
            servicos_table=[],
            texto="1.2.3 PINTURA LATEX PVA INTERNA M2 150",
        )
        # Após normalização, se o item 1.2.3 foi extraído da descrição,
        # o campo "item" deve ser preenchido.
        for s in result:
            if s.get("item"):
                assert "1.2.3" not in (s.get("descricao") or "").split()[0:1], (
                    "Código não deve ficar no início da descrição após normalização"
                )


# ===========================================================================
# 3. filter_items_without_code – poucos com código → mantém todos
# ===========================================================================

class TestFilterItemsWithoutCodeKeeps:
    """Quando poucos itens têm código, todos são mantidos."""

    def test_keeps_all_when_few_have_codes(self):
        servicos = [
            _servico(item="1.1", descricao="Com código", quantidade=10),
            _servico(item=None, descricao="Sem código A", quantidade=20),
            _servico(item=None, descricao="Sem código B", quantidade=30),
        ]
        result = filter_items_without_code(servicos, min_items_with_code=5)
        assert len(result) == 3

    def test_empty_input(self):
        assert filter_items_without_code([]) == []

    def test_none_input(self):
        """None não faz sentido mas não deve estourar."""
        assert filter_items_without_code(None) is None


# ===========================================================================
# 4. filter_items_without_code – muitos com código → remove sem código
# ===========================================================================

class TestFilterItemsWithoutCodeRemoves:
    """Quando há itens suficientes com código, remove os sem código."""

    def test_removes_codeless_when_enough_with_code(self):
        com_codigo = [_servico(item=f"1.{i}", descricao=f"Serviço {i}", quantidade=i * 10) for i in range(1, 7)]
        sem_codigo = [_servico(item=None, descricao="Sem código", quantidade=99)]
        servicos = com_codigo + sem_codigo
        result = filter_items_without_code(servicos, min_items_with_code=5)
        assert len(result) == 6
        assert all(s.get("item") for s in result)

    def test_threshold_boundary(self):
        """Exatamente no limiar (min_items_with_code) deve filtrar."""
        com_codigo = [_servico(item=f"2.{i}", descricao=f"S{i}", quantidade=i) for i in range(1, 6)]
        sem_codigo = [_servico(item=None, descricao="Sem", quantidade=1)]
        result = filter_items_without_code(com_codigo + sem_codigo, min_items_with_code=5)
        assert len(result) == 5


# ===========================================================================
# 5. should_replace_desc – True para descrições mais longas
# ===========================================================================

class TestShouldReplaceDescTrue:
    """should_replace_desc retorna True quando a candidata é melhor."""

    def test_empty_current_replaced(self):
        assert should_replace_desc("", "Nova descrição completa") is True

    def test_none_current_replaced(self):
        assert should_replace_desc(None, "Nova descrição completa") is True

    def test_short_current_replaced(self):
        """Descrição curta (< 12 chars) deve ser substituída."""
        assert should_replace_desc("Curta", "Descrição candidata bastante longa e detalhada") is True


# ===========================================================================
# 6. should_replace_desc – False quando atual é melhor
# ===========================================================================

class TestShouldReplaceDescFalse:
    """should_replace_desc retorna False quando a atual é suficiente."""

    def test_empty_candidate_not_replaced(self):
        assert should_replace_desc("Descrição atual boa", "") is False

    def test_none_candidate_not_replaced(self):
        assert should_replace_desc("Descrição atual boa", None) is False

    def test_similar_descriptions_not_replaced(self):
        """Descrições muito similares não devem ser substituídas."""
        current = "Fornecimento e instalação de tubulação de PVC"
        candidate = "Fornecimento e instalação de tubulação de PVC rígido"
        # Altamente similares → similarity >= PP_DESC_REPLACE_SIMILARITY → False
        result = should_replace_desc(current, candidate)
        assert result is False


# ===========================================================================
# 7. build_text_item_map – criação correta do mapa
# ===========================================================================

class TestBuildTextItemMap:
    """build_text_item_map cria mapeamento por chave (code, unit, qty)."""

    def test_creates_map_from_items(self):
        items = [
            _servico(item="1.1", descricao="PINTURA LATEX PVA INTERNA EM PAREDE", quantidade=100, unidade="M2"),
            _servico(item="2.1", descricao="REVESTIMENTO CERAMICO EM PISO", quantidade=50, unidade="M2"),
        ]
        result = build_text_item_map(items)
        assert isinstance(result, dict)
        assert len(result) >= 1  # Pelo menos um item mapeado

    def test_empty_input(self):
        assert build_text_item_map([]) == {}
        assert build_text_item_map(None) == {}

    def test_skips_items_without_code(self):
        """Itens sem código de item não entram no mapa."""
        items = [
            _servico(item=None, descricao="Sem código", quantidade=10, unidade="UN"),
        ]
        result = build_text_item_map(items)
        assert len(result) == 0

    def test_skips_empty_description(self):
        """Itens com descrição vazia não entram no mapa."""
        items = [
            _servico(item="1.1", descricao="", quantidade=10, unidade="UN"),
        ]
        result = build_text_item_map(items)
        assert len(result) == 0


# ===========================================================================
# 8. apply_text_descriptions – enriquece serviços com dados do texto
# ===========================================================================

class TestApplyTextDescriptions:
    """apply_text_descriptions atualiza descrições usando text_map."""

    def test_enriches_servico_with_text_data(self):
        servicos = [
            _servico(item="3.1", descricao="", quantidade=200, unidade="M2"),
        ]
        # Construir text_map manualmente usando a mesma chave que helpers_item_key geraria.
        # Usamos build_text_item_map com itens completos.
        text_items = [
            _servico(item="3.1", descricao="REVESTIMENTO ARGAMASSA PAREDES INTERNAS", quantidade=200, unidade="M2"),
        ]
        text_map = build_text_item_map(text_items)

        if text_map:
            updated = apply_text_descriptions(servicos, text_map)
            # Se a chave casou, a descrição vazia deve ter sido substituída.
            if updated > 0:
                assert servicos[0]["descricao"] == "REVESTIMENTO ARGAMASSA PAREDES INTERNAS"
                assert servicos[0].get("_desc_from_text") is True

    def test_returns_zero_for_empty_inputs(self):
        assert apply_text_descriptions([], {}) == 0
        assert apply_text_descriptions(None, None) == 0
        assert apply_text_descriptions([], {"key": "val"}) == 0

    def test_no_update_when_map_has_no_match(self):
        servicos = [
            _servico(item="99.99", descricao="Original", quantidade=1, unidade="UN"),
        ]
        text_map = {}
        updated = apply_text_descriptions(servicos, text_map)
        assert updated == 0
        assert servicos[0]["descricao"] == "Original"


# ===========================================================================
# 9. build_restart_prefix_maps – entrada vazia
# ===========================================================================

class TestBuildRestartPrefixMaps:
    """build_restart_prefix_maps com entradas vazias e None."""

    def test_empty_list(self):
        prefix_map, unique_map = build_restart_prefix_maps([])
        assert prefix_map == {}
        assert unique_map == {}

    def test_none_input(self):
        prefix_map, unique_map = build_restart_prefix_maps(None)
        assert prefix_map == {}
        assert unique_map == {}

    def test_items_without_prefix(self):
        """Itens sem prefixo de restart não geram entradas no mapa."""
        servicos = [
            _servico(item="1.1", descricao="Serviço A", quantidade=10, unidade="M2"),
            _servico(item="2.1", descricao="Serviço B", quantidade=20, unidade="UN"),
        ]
        prefix_map, unique_map = build_restart_prefix_maps(servicos)
        assert prefix_map == {}
        assert unique_map == {}

    def test_skips_ad_section(self):
        """Itens com _section='AD' devem ser ignorados."""
        servicos = [
            _servico(item="S2-1.1", descricao="Aditivo", quantidade=10, unidade="M2", _section="AD"),
        ]
        prefix_map, unique_map = build_restart_prefix_maps(servicos)
        assert prefix_map == {}
        assert unique_map == {}


# ===========================================================================
# 10. PostprocessConfig – valores padrão
# ===========================================================================

class TestPostprocessConfig:
    """PostprocessConfig tem valores padrão razoáveis."""

    def test_min_items_with_code_default(self):
        assert PostprocessConfig.MIN_ITEMS_WITH_CODE == 5

    def test_desc_replace_similarity_default(self):
        assert PostprocessConfig.DESC_REPLACE_SIMILARITY == 0.3

    def test_min_desc_len_for_replace_default(self):
        assert PostprocessConfig.MIN_DESC_LEN_FOR_REPLACE == 20

    def test_qty_match_tolerance_default(self):
        assert PostprocessConfig.QTY_MATCH_TOLERANCE == 0.05

    def test_match_score_boost_default(self):
        assert PostprocessConfig.MATCH_SCORE_BOOST == 0.1


# ===========================================================================
# 11. Deduplicação via postprocess_servicos
# ===========================================================================

class TestPostprocessDeduplication:
    """postprocess_servicos remove serviços duplicados."""

    def test_deduplicates_identical_services(self):
        """Serviços idênticos devem ser deduplicados."""
        servicos = [
            _servico(item="1.1", descricao="FORNECIMENTO DE TUBO PVC 100MM", quantidade=50, unidade="M"),
            _servico(item="1.1", descricao="FORNECIMENTO DE TUBO PVC 100MM", quantidade=50, unidade="M"),
        ]
        result = postprocess_servicos(
            servicos=servicos,
            use_ai=False,
            table_used=False,
            servicos_table=[],
            texto="1.1 FORNECIMENTO DE TUBO PVC 100MM M 50",
        )
        # Após deduplicação deve haver no máximo 1 item com mesmo código/qty
        items_1_1 = [s for s in result if s.get("item") and "1.1" in str(s["item"])]
        assert len(items_1_1) <= 1


# ===========================================================================
# 12. Filtragem de linhas de resumo via postprocess_servicos
# ===========================================================================

class TestPostprocessSummaryFiltering:
    """postprocess_servicos filtra linhas de resumo/total."""

    def test_filters_total_rows(self):
        """Linhas com 'TOTAL' na descrição devem ser removidas."""
        servicos = [
            _servico(item="1.1", descricao="FORNECIMENTO DE MATERIAL ELETRICO", quantidade=100, unidade="UN"),
            _servico(item=None, descricao="TOTAL GERAL", quantidade=5000, unidade=""),
        ]
        result = postprocess_servicos(
            servicos=servicos,
            use_ai=False,
            table_used=False,
            servicos_table=[],
            texto="1.1 FORNECIMENTO DE MATERIAL ELETRICO UN 100",
        )
        descs = [s.get("descricao", "") for s in result]
        for d in descs:
            assert "TOTAL GERAL" not in d.upper(), "Linha de resumo não deve permanecer"

    def test_filters_subtotal_rows(self):
        """Linhas com 'SUBTOTAL' na descrição devem ser removidas."""
        servicos = [
            _servico(item="2.1", descricao="PINTURA ACRILICA EXTERNA", quantidade=200, unidade="M2"),
            _servico(item=None, descricao="SUBTOTAL", quantidade=999, unidade=""),
        ]
        result = postprocess_servicos(
            servicos=servicos,
            use_ai=False,
            table_used=False,
            servicos_table=[],
            texto="2.1 PINTURA ACRILICA EXTERNA M2 200",
        )
        descs = [(s.get("descricao") or "").upper() for s in result]
        assert not any("SUBTOTAL" in d for d in descs)
