"""
Testes para o módulo de filtragem de serviços.

NOTA: Este teste é para services/processors/validation_filter.py,
não para services/extraction/item_filters.py.
"""

from services.processors.validation_filter import (
    ServiceFilter,
    filter_headers,
    filter_no_code,
    filter_no_quantity,
    filter_servicos,
)


class TestFilterHeaders:
    """Testes para filter_headers."""

    def test_empty_list(self):
        """Lista vazia retorna lista vazia."""
        result = ServiceFilter([]).filter_headers()
        assert result == []

    def test_no_headers(self):
        """Sem cabeçalhos, lista permanece igual."""
        servicos = [
            {"item": "1.1", "descricao": "Fornecimento de material completo para obra"},
            {"item": "1.2", "descricao": "Execução de serviços de pintura externa"},
        ]
        result = ServiceFilter(servicos).filter_headers()
        assert len(result) == 2

    def test_removes_header_with_children(self):
        """Remove cabeçalho que tem filhos."""
        servicos = [
            {"item": "1.4", "descricao": "COBERTURA"},  # Cabeçalho (curto, tem filho)
            {"item": "1.4.1", "descricao": "Instalação de telhas de cerâmica"},
            {"item": "1.4.2", "descricao": "Instalação de cumeeiras"},
        ]
        result = ServiceFilter(servicos).filter_headers()
        assert len(result) == 2
        assert all(s["item"] != "1.4" for s in result)

    def test_keeps_short_desc_without_children(self):
        """Mantém item com descrição curta se não tem filhos."""
        servicos = [
            {"item": "1.1", "descricao": "PINTURA"},  # Curto mas sem filhos
            {"item": "2.1", "descricao": "Serviço de instalação elétrica"},
        ]
        result = ServiceFilter(servicos).filter_headers()
        assert len(result) == 2

    def test_handles_prefixed_codes(self):
        """Lida corretamente com códigos prefixados."""
        servicos = [
            {"item": "S1-1.4", "descricao": "COBERTURA"},  # Cabeçalho com prefixo
            {"item": "S1-1.4.1", "descricao": "Instalação de telhas"},
        ]
        result = ServiceFilter(servicos).filter_headers()
        assert len(result) == 1
        assert result[0]["item"] == "S1-1.4.1"


class TestFilterNoQuantity:
    """Testes para filter_no_quantity."""

    def test_empty_list(self):
        """Lista vazia retorna lista vazia."""
        result = ServiceFilter([]).filter_no_quantity()
        assert result == []

    def test_keeps_items_with_quantity(self):
        """Mantém itens com quantidade válida."""
        servicos = [
            {"item": "1.1", "quantidade": 100},
            {"item": "1.2", "quantidade": 50.5},
            {"item": "1.3", "quantidade": "200"},
        ]
        result = ServiceFilter(servicos).filter_no_quantity()
        assert len(result) == 3

    def test_removes_items_without_quantity(self):
        """Remove itens sem quantidade."""
        servicos = [
            {"item": "1.1", "quantidade": 100},
            {"item": "1.2", "quantidade": None},
            {"item": "1.3"},  # Sem campo quantidade
        ]
        result = ServiceFilter(servicos).filter_no_quantity()
        assert len(result) == 1
        assert result[0]["item"] == "1.1"

    def test_removes_items_with_zero_quantity(self):
        """Remove itens com quantidade zero."""
        servicos = [
            {"item": "1.1", "quantidade": 100},
            {"item": "1.2", "quantidade": 0},
            {"item": "1.3", "quantidade": "0"},
        ]
        result = ServiceFilter(servicos).filter_no_quantity()
        assert len(result) == 1


class TestFilterNoCode:
    """Testes para filter_no_code."""

    def test_empty_list(self):
        """Lista vazia retorna lista vazia."""
        result = ServiceFilter([]).filter_no_code()
        assert result == []

    def test_keeps_all_when_few_with_code(self):
        """Mantém todos se há poucos itens com código."""
        servicos = [
            {"item": "1.1", "descricao": "Serviço A"},
            {"descricao": "Serviço B sem código"},
            {"descricao": "Serviço C sem código"},
        ]
        result = ServiceFilter(servicos).filter_no_code(min_items_with_code=5)
        assert len(result) == 3  # Mantém todos (só 1 com código < 5)

    def test_removes_no_code_when_enough_with_code(self):
        """Remove itens sem código quando há suficientes com código."""
        servicos = [
            {"item": "1.1", "descricao": "Serviço 1"},
            {"item": "1.2", "descricao": "Serviço 2"},
            {"item": "1.3", "descricao": "Serviço 3"},
            {"item": "1.4", "descricao": "Serviço 4"},
            {"item": "1.5", "descricao": "Serviço 5"},
            {"descricao": "Serviço sem código"},  # Será removido
        ]
        result = ServiceFilter(servicos).filter_no_code(min_items_with_code=5)
        assert len(result) == 5
        assert all(s.get("item") for s in result)

    def test_respects_min_items_parameter(self):
        """Respeita parâmetro min_items_with_code."""
        servicos = [
            {"item": "1.1", "descricao": "Serviço 1"},
            {"item": "1.2", "descricao": "Serviço 2"},
            {"descricao": "Serviço sem código"},
        ]
        # Com min=3, não remove (só 2 com código)
        result1 = ServiceFilter(servicos).filter_no_code(min_items_with_code=3)
        assert len(result1) == 3

        # Com min=2, remove (2 com código >= 2)
        result2 = ServiceFilter(servicos).filter_no_code(min_items_with_code=2)
        assert len(result2) == 2


class TestFilterNotInSources:
    """Testes para filter_not_in_sources."""

    def test_empty_list(self):
        """Lista vazia retorna lista vazia."""
        result = ServiceFilter([]).filter_not_in_sources()
        assert result == []

    def test_keeps_items_in_text(self):
        """Mantém itens cujo código aparece no texto."""
        servicos = [
            {"item": "1.1", "descricao": "Serviço A"},
            {"item": "1.2", "descricao": "Serviço B"},
        ]
        texto = "Conforme item 1.1 e item 1.2 do contrato"
        result = ServiceFilter(servicos, texto).filter_not_in_sources()
        assert len(result) == 2

    def test_removes_items_not_in_text(self):
        """Remove itens cujo código não aparece no texto."""
        servicos = [
            {"item": "1.1", "descricao": "Serviço A"},
            {"item": "9.9", "descricao": "Serviço fantasma"},  # Não está no texto
        ]
        texto = "Conforme item 1.1 do contrato"
        result = ServiceFilter(servicos, texto).filter_not_in_sources()
        assert len(result) == 1
        assert result[0]["item"] == "1.1"

    def test_keeps_items_without_code(self):
        """Mantém itens sem código (não pode validar)."""
        servicos = [
            {"item": "1.1", "descricao": "Serviço A"},
            {"descricao": "Serviço sem código"},  # Mantido
        ]
        texto = "Conforme item 1.1 do contrato"
        result = ServiceFilter(servicos, texto).filter_not_in_sources()
        assert len(result) == 2


class TestFilterAll:
    """Testes para filter_all."""

    def test_empty_list(self):
        """Lista vazia retorna lista vazia."""
        result = ServiceFilter([]).filter_all()
        assert result == []

    def test_applies_all_filters(self):
        """Aplica todos os filtros em sequência."""
        servicos = [
            # Cabeçalho (será removido)
            {"item": "1.4", "descricao": "COBERTURA", "quantidade": 100},
            # Filho do cabeçalho (mantido)
            {"item": "1.4.1", "descricao": "Instalação de telhas", "quantidade": 50},
            # Sem quantidade (será removido)
            {"item": "1.5", "descricao": "Serviço sem qty"},
            # Item normal (mantido)
            {"item": "1.6", "descricao": "Serviço normal com quantidade", "quantidade": 10},
        ]
        result = ServiceFilter(servicos).filter_all()
        # Espera: remove header 1.4 e item sem quantidade 1.5
        assert len(result) == 2


class TestConvenienceFunctions:
    """Testes para funções de conveniência."""

    def test_filter_servicos(self):
        """Função filter_servicos aplica todos os filtros."""
        servicos = [
            {"item": "1.1", "descricao": "Serviço completo", "quantidade": 100},
        ]
        result = filter_servicos(servicos)
        assert len(result) == 1

    def test_filter_headers_function(self):
        """Função filter_headers funciona."""
        servicos = [
            {"item": "1.1", "descricao": "HEADER"},
            {"item": "1.1.1", "descricao": "Serviço filho"},
        ]
        result = filter_headers(servicos)
        assert len(result) == 1

    def test_filter_no_quantity_function(self):
        """Função filter_no_quantity funciona."""
        servicos = [
            {"item": "1.1", "quantidade": 100},
            {"item": "1.2"},
        ]
        result = filter_no_quantity(servicos)
        assert len(result) == 1

    def test_filter_no_code_function(self):
        """Função filter_no_code funciona."""
        servicos = [
            {"item": "1.1"},
            {"item": "1.2"},
            {"item": "1.3"},
            {"item": "1.4"},
            {"item": "1.5"},
            {"descricao": "Sem código"},
        ]
        result = filter_no_code(servicos, min_items_with_code=5)
        assert len(result) == 5
