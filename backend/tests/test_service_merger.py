"""
Testes para o módulo de mesclagem de planilhas.
"""

from services.processors.service_merger import (
    ServiceMerger,
    merge_planilhas,
    normalize_planilha_prefixes,
)


class TestMergeFragmented:
    """Testes para merge_fragmented."""

    def test_empty_list(self):
        """Lista vazia retorna lista vazia."""
        result = ServiceMerger([]).merge_fragmented()
        assert result == []

    def test_single_planilha(self):
        """Única planilha permanece igual."""
        servicos = [
            {"item": "1.1", "descricao": "Serviço A", "_planilha_id": 1},
            {"item": "1.2", "descricao": "Serviço B", "_planilha_id": 1},
        ]
        result = ServiceMerger(servicos).merge_fragmented()
        assert len(result) == 2
        assert all(s["_planilha_id"] == 1 for s in result)

    def test_merges_fragmented_no_pages(self):
        """Mescla planilhas sem páginas com baixo overlap."""
        servicos = [
            {"item": "1.1", "descricao": "Serviço A", "_planilha_id": 1},
            {"item": "1.2", "descricao": "Serviço B", "_planilha_id": 1},
            {"item": "1.3", "descricao": "Serviço C", "_planilha_id": 1},
            {"item": "2.1", "descricao": "Serviço D", "_planilha_id": 2},  # Códigos diferentes
        ]
        result = ServiceMerger(servicos).merge_fragmented()
        # Planilha 2 deve ser mesclada com planilha 1 (baixo overlap)
        assert len(result) == 4
        # Verifica se foi mesclada
        merged = [s for s in result if s.get("_merged_from")]
        assert len(merged) == 1
        assert merged[0]["_merged_from"] == 2

    def test_does_not_merge_high_overlap(self):
        """Não mescla planilhas com alto overlap."""
        # Cria serviços com mesmo código em planilhas diferentes (alto overlap)
        servicos = [
            {"item": "1.1", "descricao": "Serviço A", "_planilha_id": 1},
            {"item": "1.2", "descricao": "Serviço B", "_planilha_id": 1},
            {"item": "1.3", "descricao": "Serviço C", "_planilha_id": 1},
            {"item": "1.1", "descricao": "Serviço A repetido", "_planilha_id": 2},  # Mesmo código
            {"item": "1.2", "descricao": "Serviço B repetido", "_planilha_id": 2},  # Mesmo código
            {"item": "1.3", "descricao": "Serviço C repetido", "_planilha_id": 2},  # Mesmo código
        ]
        result = ServiceMerger(servicos).merge_fragmented()
        # Deve manter planilhas separadas (alto overlap >= 3)
        planilhas = set(s["_planilha_id"] for s in result)
        assert len(planilhas) == 2

    def test_merges_adjacent_pages(self):
        """Mescla planilhas com páginas adjacentes e baixo overlap."""
        servicos = [
            {"item": "1.1", "_planilha_id": 1, "_page": 1},
            {"item": "1.2", "_planilha_id": 1, "_page": 1},
            {"item": "1.3", "_planilha_id": 1, "_page": 2},
            {"item": "2.1", "_planilha_id": 2, "_page": 2},  # Página adjacente, código diferente
        ]
        result = ServiceMerger(servicos).merge_fragmented()
        # Planilha 2 deve ser mesclada (página adjacente, baixo overlap)
        merged = [s for s in result if s.get("_merged_from")]
        assert len(merged) == 1


class TestNormalizePrefixes:
    """Testes para normalize_prefixes."""

    def test_empty_list(self):
        """Lista vazia retorna lista vazia."""
        result = ServiceMerger([]).normalize_prefixes()
        assert result == []

    def test_single_planilha_removes_prefix(self):
        """Única planilha remove prefixos existentes."""
        servicos = [
            {"item": "S1-1.1", "descricao": "Serviço A", "_planilha_id": 1},
            {"item": "1.2", "descricao": "Serviço B", "_planilha_id": 1},
        ]
        result = ServiceMerger(servicos).normalize_prefixes()
        assert result[0]["item"] == "1.1"
        assert result[1]["item"] == "1.2"

    def test_main_planilha_no_prefix(self):
        """Planilha principal (maior) não recebe prefixo."""
        servicos = [
            {"item": "1.1", "_planilha_id": 1},
            {"item": "1.2", "_planilha_id": 1},
            {"item": "1.3", "_planilha_id": 1},
            {"item": "1.1", "_planilha_id": 2},  # Overlap
            {"item": "1.2", "_planilha_id": 2},  # Overlap
            {"item": "1.3", "_planilha_id": 2},  # Overlap
        ]
        result = ServiceMerger(servicos).normalize_prefixes()
        # Planilha 1 é maior, não recebe prefixo
        p1_items = [s for s in result if s["_planilha_id"] == 1]
        assert all("S" not in s["item"] for s in p1_items)
        # Planilha 2 deve receber prefixo S1
        p2_items = [s for s in result if s["_planilha_id"] == 2]
        assert all(s["item"].startswith("S1-") for s in p2_items)

    def test_no_prefix_when_no_overlap(self):
        """Não adiciona prefixo se não há overlap."""
        servicos = [
            {"item": "1.1", "_planilha_id": 1},
            {"item": "1.2", "_planilha_id": 1},
            {"item": "2.1", "_planilha_id": 2},  # Código diferente
            {"item": "2.2", "_planilha_id": 2},  # Código diferente
        ]
        result = ServiceMerger(servicos).normalize_prefixes()
        # Nenhum prefixo deve ser adicionado (sem overlap)
        assert all("S" not in s["item"] for s in result)

    def test_preserves_ad_prefix_in_single_planilha(self):
        """AD- prefix é preservado em planilha única (não processado)."""
        servicos = [
            {"item": "1.1", "_planilha_id": 1},
            {"item": "AD-1.1", "_planilha_id": 1},  # Prefixo AD- é mantido em planilha única
        ]
        result = ServiceMerger(servicos).normalize_prefixes()
        # Em planilha única, AD- é preservado (só seria processado em multi-planilha)
        ad_item = [s for s in result if "AD" in str(s.get("item", ""))]
        assert len(ad_item) == 1  # AD- é preservado em planilha única


class TestMergeAndNormalize:
    """Testes para merge_and_normalize."""

    def test_combines_operations(self):
        """Executa mesclagem e normalização em sequência."""
        servicos = [
            {"item": "1.1", "_planilha_id": 1},
            {"item": "1.2", "_planilha_id": 1},
        ]
        result = ServiceMerger(servicos).merge_and_normalize()
        assert len(result) == 2


class TestConvenienceFunctions:
    """Testes para funções de conveniência."""

    def test_merge_planilhas(self):
        """Função merge_planilhas funciona."""
        servicos = [
            {"item": "1.1", "_planilha_id": 1},
        ]
        result = merge_planilhas(servicos)
        assert len(result) == 1

    def test_normalize_planilha_prefixes(self):
        """Função normalize_planilha_prefixes funciona."""
        servicos = [
            {"item": "S1-1.1", "_planilha_id": 1},
        ]
        result = normalize_planilha_prefixes(servicos)
        assert result[0]["item"] == "1.1"

    def test_merge_planilhas_empty(self):
        """Função merge_planilhas com lista vazia."""
        result = merge_planilhas([])
        assert result == []

    def test_normalize_planilha_prefixes_empty(self):
        """Função normalize_planilha_prefixes com lista vazia."""
        result = normalize_planilha_prefixes([])
        assert result == []
