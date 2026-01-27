"""
Testes unitários para patterns.py.

Testa os padrões regex compilados usados na extração.
"""

from services.extraction.patterns import Patterns


class TestItemCodePatterns:
    """Testes para padrões de código de item."""

    def test_item_code_simple(self):
        assert Patterns.ITEM_CODE.match("1.2.3")
        assert Patterns.ITEM_CODE.match("1.2")
        assert Patterns.ITEM_CODE.match("12.34.56")

    def test_item_code_deep_nesting(self):
        assert Patterns.ITEM_CODE.match("1.2.3.4.5")

    def test_item_code_rejects_invalid(self):
        assert not Patterns.ITEM_CODE.match("abc")
        assert not Patterns.ITEM_CODE.match("1234")
        assert not Patterns.ITEM_CODE.match("S1-1.2.3")

    def test_item_with_prefix(self):
        assert Patterns.ITEM_WITH_PREFIX.match("1.2.3")
        assert Patterns.ITEM_WITH_PREFIX.match("S1-1.2.3")
        assert Patterns.ITEM_WITH_PREFIX.match("AD-1.2.3")
        assert Patterns.ITEM_WITH_PREFIX.match("s2-1.2")

    def test_restart_prefix_extraction(self):
        match = Patterns.RESTART_PREFIX.match("S1-1.2.3")
        assert match
        assert match.group(1) == "S1-"

        match = Patterns.RESTART_PREFIX.match("AD-1.2.3")
        assert match
        assert match.group(1) == "AD-"

    def test_restart_index_extraction(self):
        match = Patterns.RESTART_INDEX.match("S1-1.2.3")
        assert match
        assert match.group(1) == "1"

        match = Patterns.RESTART_INDEX.match("S10-1.2")
        assert match
        assert match.group(1) == "10"


class TestPageMetadataPatterns:
    """Testes para padrões de metadados de página."""

    def test_page_number(self):
        assert Patterns.PAGE_NUMBER.match("PÁGINA 5/10")
        assert Patterns.PAGE_NUMBER.match("Pagina 1 / 20")
        assert Patterns.PAGE_NUMBER.match("PAGINA 99/100")

    def test_page_abbrev(self):
        assert Patterns.PAGE_ABBREV.match("Pág. 5/10")
        assert Patterns.PAGE_ABBREV.match("PAG 1/20")

    def test_page_bare(self):
        assert Patterns.PAGE_BARE.match("5/10")
        assert Patterns.PAGE_BARE.match("1 / 20")
        assert not Patterns.PAGE_BARE.match("texto 5/10")

    def test_print_datetime(self):
        assert Patterns.PRINT_DATETIME.match("10/10/2025, 17:50")
        assert Patterns.PRINT_DATETIME.match("01/01/2020 10:30")


class TestSectionHeaderPatterns:
    """Testes para padrões de cabeçalho de seção."""

    def test_section_header(self):
        match = Patterns.SECTION_HEADER.match("8 INSTALAÇÕES HIDROSSANITÁRIAS")
        assert match
        assert match.group(1) == "8"
        assert match.group(2) == "INSTALAÇÕES HIDROSSANITÁRIAS"

    def test_section_number(self):
        assert Patterns.SECTION_NUMBER.match("8")
        assert Patterns.SECTION_NUMBER.match("12")
        assert not Patterns.SECTION_NUMBER.match("123")


class TestUnitQtyPatterns:
    """Testes para padrões de unidade e quantidade."""

    def test_unit_qty_end(self):
        match = Patterns.UNIT_QTY_END.search("Serviço de pintura UN 10,50")
        assert match
        assert match.group(1).upper() == "UN"
        assert match.group(2) == "10,50"

    def test_unit_qty_m2(self):
        match = Patterns.UNIT_QTY_END.search("Piso cerâmico M2 25,00")
        assert match
        assert match.group(1).upper() == "M2"

    def test_unit_qty_m3(self):
        match = Patterns.UNIT_QTY_END.search("Concreto M³ 100")
        assert match
        assert match.group(1) == "M³"


class TestInstitutionalPatterns:
    """Testes para padrões de dados institucionais."""

    def test_cnpj(self):
        match = Patterns.CNPJ.search("CNPJ: 12.345.678/0001-90")
        assert match
        assert match.group(0) == "12.345.678/0001-90"

    def test_cpf(self):
        match = Patterns.CPF.search("CPF: 123.456.789-00")
        assert match
        assert match.group(0) == "123.456.789-00"

    def test_crea(self):
        assert Patterns.CREA.search("CREA-SP 123456")
        assert Patterns.CREA.search("CREA: MG 789012")
