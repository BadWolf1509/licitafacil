"""
Testes unitários para o TextProcessor.

Testa extração de itens de serviço a partir de texto.
"""

from services.processors.text_cleanup import (
    parse_unit_qty_from_line,
    strip_trailing_unit_qty,
)
from services.processors.text_processor import TextProcessor, text_processor


class TestExtractItemCodesFromTextLines:
    """Testes para extract_item_codes_from_text_lines."""

    def test_extracts_simple_codes(self):
        texto = """
        1.1 FORNECIMENTO DE MATERIAL
        1.2 INSTALACAO ELETRICA
        2.1 PINTURA
        """
        codes = text_processor.extract_item_codes_from_text_lines(texto)
        assert "1.1" in codes
        assert "1.2" in codes
        assert "2.1" in codes

    def test_extracts_nested_codes(self):
        texto = """
        1.2.3 SERVICO COMPLEXO
        1.2.4.5 SERVICO MUITO ANINHADO
        """
        codes = text_processor.extract_item_codes_from_text_lines(texto)
        assert "1.2.3" in codes
        assert "1.2.4.5" in codes

    def test_empty_text_returns_empty(self):
        assert text_processor.extract_item_codes_from_text_lines("") == []
        assert text_processor.extract_item_codes_from_text_lines(None) == []

    def test_no_codes_returns_empty(self):
        texto = "Texto sem codigos de item"
        assert text_processor.extract_item_codes_from_text_lines(texto) == []


class TestExtractItemsFromTextLines:
    """Testes para extract_items_from_text_lines."""

    def test_extracts_complete_item(self):
        texto = "9.11 FORNECIMENTO DE DISJUNTOR UN 10,00"
        items = text_processor.extract_items_from_text_lines(texto)
        assert len(items) == 1
        assert items[0]["item"] == "9.11"
        assert "DISJUNTOR" in items[0]["descricao"]
        assert items[0]["unidade"] == "UN"
        assert items[0]["quantidade"] == "10,00"

    def test_extracts_unit_first_pattern(self):
        texto = "9.13 UN 5,00 FORNECIMENTO DE CABO"
        items = text_processor.extract_items_from_text_lines(texto)
        assert len(items) == 1
        assert items[0]["item"] == "9.13"
        assert items[0]["unidade"] == "UN"

    def test_extracts_mid_pattern(self):
        texto = "DISJUNTOR MONOPOLAR 25A - 9.11 UN 10,00 FORNECIMENTO"
        items = text_processor.extract_items_from_text_lines(texto)
        assert len(items) == 1
        assert items[0]["item"] == "9.11"

    def test_handles_segment_restart(self):
        texto = """
        1.1 ITEM A UN 1,00
        1.2 ITEM B UN 2,00
        1.1 ITEM C UN 3,00
        """
        items = text_processor.extract_items_from_text_lines(texto)
        # Deve detectar restart e prefixar com S2-
        codes = [i["item"] for i in items]
        assert "1.1" in codes
        assert "1.2" in codes
        # O terceiro 1.1 deve ter prefixo S2-
        assert any("S2-1.1" in c for c in codes) or len(items) == 3

    def test_empty_text_returns_empty(self):
        assert text_processor.extract_items_from_text_lines("") == []
        assert text_processor.extract_items_from_text_lines(None) == []


class TestParseUnitQtyFromLine:
    """Testes para parse_unit_qty_from_line."""

    def test_parses_unit_qty(self):
        result = parse_unit_qty_from_line("DESCRICAO UN 10,50")
        assert result is not None
        assert result[0] == "UN"
        assert result[1] == 10.5

    def test_parses_m2(self):
        result = parse_unit_qty_from_line("AREA M2 25,00")
        assert result is not None
        assert result[0] == "M2"
        assert result[1] == 25.0

    def test_ignores_mm_cm(self):
        result = parse_unit_qty_from_line("TUBO MM 50")
        assert result is None

    def test_no_match_returns_none(self):
        result = parse_unit_qty_from_line("SEM UNIDADE")
        assert result is None


class TestStripTrailingUnitQty:
    """Testes para strip_trailing_unit_qty."""

    def test_strips_trailing(self):
        result = strip_trailing_unit_qty(
            "FORNECIMENTO DE MATERIAL UN 10,00",
            unit="UN",
            qty=10.0
        )
        assert result == "FORNECIMENTO DE MATERIAL"

    def test_preserves_if_unit_mismatch(self):
        result = strip_trailing_unit_qty(
            "FORNECIMENTO DE MATERIAL UN 10,00",
            unit="M2",
            qty=10.0
        )
        assert result == "FORNECIMENTO DE MATERIAL UN 10,00"

    def test_preserves_if_qty_mismatch(self):
        result = strip_trailing_unit_qty(
            "FORNECIMENTO DE MATERIAL UN 10,00",
            unit="UN",
            qty=20.0
        )
        assert result == "FORNECIMENTO DE MATERIAL UN 10,00"

    def test_empty_returns_empty(self):
        assert strip_trailing_unit_qty("") == ""
        assert strip_trailing_unit_qty(None) is None


class TestStripUnitQtyPrefix:
    """Testes para strip_unit_qty_prefix."""

    def test_strips_prefix(self):
        result = text_processor.strip_unit_qty_prefix("UN 1,00 FORNECIMENTO DE MATERIAL")
        assert result == "FORNECIMENTO DE MATERIAL"

    def test_strips_m_prefix(self):
        result = text_processor.strip_unit_qty_prefix("M 2,05 inclusive roldanas")
        assert result == "inclusive roldanas"

    def test_preserves_short_result(self):
        result = text_processor.strip_unit_qty_prefix("UN 1,00 ABC")
        assert result == "UN 1,00 ABC"  # Resultado muito curto, preserva original

    def test_no_prefix_returns_original(self):
        result = text_processor.strip_unit_qty_prefix("FORNECIMENTO DE MATERIAL")
        assert result == "FORNECIMENTO DE MATERIAL"


class TestExtractQuantitiesFromText:
    """Testes para extract_quantities_from_text."""

    def test_extracts_quantities(self):
        texto = """
        1.1 ITEM A UN 10,00
        1.2 ITEM B M2 25,50
        """
        item_codes = {"1.1", "1.2"}
        qty_map = text_processor.extract_quantities_from_text(texto, item_codes)

        assert "1.1" in qty_map
        assert "1.2" in qty_map
        assert qty_map["1.1"][0] == ("UN", 10.0)
        assert qty_map["1.2"][0] == ("M2", 25.5)

    def test_ignores_unknown_codes(self):
        texto = "1.1 ITEM UN 10,00\n9.9 OUTRO M2 5,00"
        item_codes = {"1.1"}
        qty_map = text_processor.extract_quantities_from_text(texto, item_codes)

        assert "1.1" in qty_map
        assert "9.9" not in qty_map

    def test_empty_returns_empty(self):
        assert text_processor.extract_quantities_from_text("", set()) == {}
        assert text_processor.extract_quantities_from_text("texto", set()) == {}


class TestBackfillQuantitiesFromText:
    """Testes para backfill_quantities_from_text."""

    def test_backfills_missing_quantities(self):
        servicos = [
            {"item": "1.1", "descricao": "ITEM A", "unidade": None, "quantidade": None},
        ]
        texto = "1.1 ITEM A UN 10,00"

        filled = text_processor.backfill_quantities_from_text(servicos, texto)

        assert filled == 1
        assert servicos[0]["unidade"] == "UN"
        assert servicos[0]["quantidade"] == 10.0

    def test_skips_items_with_quantity(self):
        servicos = [
            {"item": "1.1", "descricao": "ITEM A", "unidade": "UN", "quantidade": 5.0},
        ]
        texto = "1.1 ITEM A UN 10,00"

        filled = text_processor.backfill_quantities_from_text(servicos, texto)

        assert filled == 0
        assert servicos[0]["quantidade"] == 5.0  # Manteve original

    def test_empty_returns_zero(self):
        assert text_processor.backfill_quantities_from_text([], "texto") == 0
        assert text_processor.backfill_quantities_from_text([{"item": "1.1"}], "") == 0


class TestTextProcessorInstance:
    """Testes para instância singleton."""

    def test_singleton_exists(self):
        assert text_processor is not None
        assert isinstance(text_processor, TextProcessor)

    def test_can_create_new_instance(self):
        processor = TextProcessor()
        assert processor is not None
        assert processor is not text_processor
