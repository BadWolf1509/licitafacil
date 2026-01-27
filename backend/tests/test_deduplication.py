"""
Testes para o módulo de deduplicação de serviços.
"""

from services.processors.deduplication import ServiceDeduplicator, dedupe_servicos


class TestRemoveDuplicatePairs:
    """Testes para remove_duplicate_pairs."""

    def test_empty_list(self):
        """Lista vazia retorna lista vazia."""
        result = ServiceDeduplicator([]).remove_duplicate_pairs()
        assert result == []

    def test_no_duplicates(self):
        """Sem duplicatas, lista permanece igual."""
        servicos = [
            {"item": "1.1", "descricao": "Serviço A", "quantidade": 10},
            {"item": "1.2", "descricao": "Serviço B", "quantidade": 20},
        ]
        result = ServiceDeduplicator(servicos).remove_duplicate_pairs()
        assert len(result) == 2

    def test_removes_child_when_parent_has_good_desc(self):
        """Remove filho quando pai tem boa descrição."""
        servicos = [
            {"item": "1.1", "descricao": "Fornecimento de material para construção civil", "quantidade": 100},
            {"item": "1.1.1", "descricao": "Fornecimento de material para construção civil completo", "quantidade": 100},
        ]
        result = ServiceDeduplicator(servicos).remove_duplicate_pairs()
        assert len(result) == 1
        assert result[0]["item"] == "1.1"

    def test_removes_parent_when_short_desc(self):
        """Remove pai quando descrição é curta (header) e keywords similares."""
        # Descrições com keywords significativamente sobrepostas (>= 50%)
        servicos = [
            {"item": "1.1", "descricao": "pintura geral", "quantidade": 100},
            {"item": "1.1.1", "descricao": "pintura geral interna externa", "quantidade": 100},
        ]
        result = ServiceDeduplicator(servicos).remove_duplicate_pairs()
        assert len(result) == 1
        assert result[0]["item"] == "1.1.1"

    def test_different_quantities_not_duplicates(self):
        """Quantidades diferentes não são duplicatas."""
        servicos = [
            {"item": "1.1", "descricao": "Serviço de pintura geral", "quantidade": 100},
            {"item": "1.1.1", "descricao": "Serviço de pintura geral", "quantidade": 200},
        ]
        result = ServiceDeduplicator(servicos).remove_duplicate_pairs()
        assert len(result) == 2

    def test_respects_planilha_id(self):
        """Duplicatas só são removidas na mesma planilha."""
        servicos = [
            {"item": "1.1", "descricao": "Serviço de pintura", "quantidade": 100, "_planilha_id": 1},
            {"item": "1.1.1", "descricao": "Serviço de pintura", "quantidade": 100, "_planilha_id": 2},
        ]
        result = ServiceDeduplicator(servicos).remove_duplicate_pairs()
        assert len(result) == 2


class TestDedupeByRestartPrefix:
    """Testes para dedupe_by_restart_prefix."""

    def test_empty_list(self):
        """Lista vazia retorna lista vazia."""
        result = ServiceDeduplicator([]).dedupe_by_restart_prefix()
        assert result == []

    def test_no_prefixes(self):
        """Sem prefixos, lista permanece igual."""
        servicos = [
            {"item": "1.1", "descricao": "Serviço A", "quantidade": 10, "unidade": "UN"},
            {"item": "1.2", "descricao": "Serviço B", "quantidade": 20, "unidade": "M2"},
        ]
        result = ServiceDeduplicator(servicos).dedupe_by_restart_prefix()
        assert len(result) == 2

    def test_removes_duplicate_with_s_prefix(self):
        """Remove duplicata com prefixo S1-, S2-."""
        servicos = [
            {"item": "1.1", "descricao": "Fornecimento de material completo", "quantidade": 100, "unidade": "UN"},
            {"item": "S1-1.1", "descricao": "Material", "quantidade": 100, "unidade": "UN"},
        ]
        result = ServiceDeduplicator(servicos).dedupe_by_restart_prefix()
        assert len(result) == 1
        # Mantém o com melhor descrição
        assert "completo" in result[0]["descricao"].lower() or result[0]["item"] == "1.1"

    def test_keeps_ad_prefix(self):
        """Itens com AD- não são removidos."""
        servicos = [
            {"item": "1.1", "descricao": "Serviço original", "quantidade": 100, "unidade": "UN"},
            {"item": "AD-1.1", "descricao": "Serviço aditivo", "quantidade": 100, "unidade": "UN"},
        ]
        result = ServiceDeduplicator(servicos).dedupe_by_restart_prefix()
        assert len(result) == 2

    def test_requires_same_unit_qty(self):
        """Só agrupa itens com mesma unidade e quantidade."""
        servicos = [
            {"item": "1.1", "descricao": "Serviço A", "quantidade": 100, "unidade": "UN"},
            {"item": "S1-1.1", "descricao": "Serviço A", "quantidade": 200, "unidade": "UN"},
        ]
        result = ServiceDeduplicator(servicos).dedupe_by_restart_prefix()
        assert len(result) == 2


class TestDedupeWithinPlanilha:
    """Testes para dedupe_within_planilha."""

    def test_empty_list(self):
        """Lista vazia retorna lista vazia."""
        result = ServiceDeduplicator([]).dedupe_within_planilha()
        assert result == []

    def test_no_duplicates(self):
        """Sem duplicatas, lista permanece igual."""
        servicos = [
            {"item": "1.1", "descricao": "Serviço A", "_planilha_id": 1},
            {"item": "1.2", "descricao": "Serviço B", "_planilha_id": 1},
        ]
        result = ServiceDeduplicator(servicos).dedupe_within_planilha()
        assert len(result) == 2

    def test_removes_duplicate_same_code(self):
        """Remove duplicata com mesmo código na mesma planilha."""
        servicos = [
            {"item": "1.1", "descricao": "Serviço A curto", "_planilha_id": 1},
            {"item": "1.1", "descricao": "Serviço A com descrição mais completa", "_planilha_id": 1},
        ]
        result = ServiceDeduplicator(servicos).dedupe_within_planilha()
        assert len(result) == 1
        assert "completa" in result[0]["descricao"]

    def test_different_planilhas_not_duplicates(self):
        """Mesmo código em planilhas diferentes não são duplicatas."""
        servicos = [
            {"item": "1.1", "descricao": "Serviço A", "_planilha_id": 1},
            {"item": "1.1", "descricao": "Serviço A", "_planilha_id": 2},
        ]
        result = ServiceDeduplicator(servicos).dedupe_within_planilha()
        assert len(result) == 2

    def test_prefers_item_with_quantity(self):
        """Prefere item com quantidade."""
        servicos = [
            {"item": "1.1", "descricao": "Serviço A completo", "_planilha_id": 1},
            {"item": "1.1", "descricao": "Serviço A", "quantidade": 100, "_planilha_id": 1},
        ]
        result = ServiceDeduplicator(servicos).dedupe_within_planilha()
        assert len(result) == 1
        assert result[0].get("quantidade") == 100


class TestDedupeByDescUnit:
    """Testes para dedupe_by_desc_unit."""

    def test_empty_list(self):
        """Lista vazia retorna lista vazia."""
        result = ServiceDeduplicator([]).dedupe_by_desc_unit()
        assert result == []

    def test_no_duplicates(self):
        """Sem duplicatas, lista permanece igual."""
        servicos = [
            {"descricao": "Serviço A", "unidade": "UN"},
            {"descricao": "Serviço B", "unidade": "M2"},
        ]
        result = ServiceDeduplicator(servicos).dedupe_by_desc_unit()
        assert len(result) == 2

    def test_removes_duplicate_desc_unit(self):
        """Remove duplicata com mesma descrição e unidade."""
        servicos = [
            {"descricao": "Fornecimento de material", "unidade": "UN"},
            {"descricao": "fornecimento de material", "unidade": "UN", "quantidade": 100},
        ]
        result = ServiceDeduplicator(servicos).dedupe_by_desc_unit()
        assert len(result) == 1
        assert result[0].get("quantidade") == 100  # Mantém o com quantidade

    def test_different_units_not_duplicates(self):
        """Mesma descrição com unidades diferentes não são duplicatas."""
        servicos = [
            {"descricao": "Fornecimento de material", "unidade": "UN"},
            {"descricao": "Fornecimento de material", "unidade": "M2"},
        ]
        result = ServiceDeduplicator(servicos).dedupe_by_desc_unit()
        assert len(result) == 2

    def test_keeps_items_without_desc(self):
        """Itens sem descrição são mantidos em extras."""
        servicos = [
            {"descricao": "Serviço A", "unidade": "UN"},
            {"unidade": "M2"},  # Sem descrição
            {"descricao": "", "unidade": "KG"},  # Descrição vazia
        ]
        result = ServiceDeduplicator(servicos).dedupe_by_desc_unit()
        assert len(result) == 3


class TestCleanupOrphanSuffixes:
    """Testes para cleanup_orphan_suffixes."""

    def test_removes_orphan_suffix_same_planilha(self):
        servicos = [
            {"item": "S2-9.13-A", "_planilha_id": 3},
            {"item": "S1-9.13", "_planilha_id": 2},
        ]
        result = ServiceDeduplicator(servicos).cleanup_orphan_suffixes()
        assert result[0]["item"] == "S2-9.13"

    def test_keeps_suffix_when_base_exists(self):
        servicos = [
            {"item": "S2-9.13", "_planilha_id": 3},
            {"item": "S2-9.13-A", "_planilha_id": 3},
        ]
        result = ServiceDeduplicator(servicos).cleanup_orphan_suffixes()
        assert result[1]["item"] == "S2-9.13-A"


class TestDedupeAll:
    """Testes para dedupe_all."""

    def test_empty_list(self):
        """Lista vazia retorna lista vazia."""
        result = ServiceDeduplicator([]).dedupe_all()
        assert result == []

    def test_applies_all_strategies(self):
        """Aplica todas as estratégias de deduplicação."""
        servicos = [
            # Par pai/filho com keywords similares (>= 50%)
            {"item": "1.1", "descricao": "pintura geral", "quantidade": 100},
            {"item": "1.1.1", "descricao": "pintura geral interna", "quantidade": 100},
            # Duplicata por código na planilha
            {"item": "2.1", "descricao": "Serviço B", "_planilha_id": 1},
            {"item": "2.1", "descricao": "Serviço B com descrição completa", "_planilha_id": 1},
        ]
        result = ServiceDeduplicator(servicos).dedupe_all()
        # Deve remover o header 1.1 e uma das duplicatas 2.1
        assert len(result) == 2


class TestConvenienceFunction:
    """Testes para função de conveniência."""

    def test_dedupe_servicos(self):
        """Função dedupe_servicos aplica todas as deduplicações."""
        servicos = [
            {"item": "1.1", "descricao": "Serviço A", "quantidade": 10},
        ]
        result = dedupe_servicos(servicos)
        assert len(result) == 1
        assert result[0]["item"] == "1.1"

    def test_dedupe_servicos_empty(self):
        """Função dedupe_servicos com lista vazia."""
        result = dedupe_servicos([])
        assert result == []

    def test_dedupe_servicos_none(self):
        """Função dedupe_servicos com None."""
        result = dedupe_servicos(None)
        assert result == []
