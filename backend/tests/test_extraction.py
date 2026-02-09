"""
Testes para os módulos de extração (text_normalizer, table_processor, item_filters).
"""
from services.extraction.item_filters import (
    filter_classification_paths,
    is_summary_row,
)
from services.extraction.similarity import (
    descriptions_similar,
    items_similar,
    quantities_similar,
    servico_key,
)
from services.extraction.table_processor import (
    detect_header_row,
    item_tuple_to_str,
    parse_item_tuple,
    parse_quantity,
)
from services.extraction.text_normalizer import (
    description_similarity,
    extract_keywords,
    normalize_description,
    normalize_unit,
)


class TestNormalizeDescription:
    """Testes para normalização de descrições."""

    def test_removes_accents(self):
        """Deve remover acentos."""
        assert "PAVIMENTACAO" in normalize_description("Pavimentação")
        assert "ASFALTICA" in normalize_description("asfáltica")

    def test_uppercase(self):
        """Deve converter para maiúsculas."""
        result = normalize_description("teste minúsculo")
        assert result == result.upper()

    def test_removes_punctuation(self):
        """Deve remover pontuação."""
        result = normalize_description("teste, com; pontuação:")
        assert "," not in result
        assert ";" not in result
        assert ":" not in result

    def test_normalizes_whitespace(self):
        """Deve normalizar espaços extras."""
        result = normalize_description("  teste   com   espacos  ")
        assert "  " not in result  # Sem espaços duplos
        assert result == "TESTE COM ESPACOS"

    def test_empty_input(self):
        """Entrada vazia deve retornar string vazia."""
        assert normalize_description("") == ""
        assert normalize_description(None) == ""


class TestNormalizeUnit:
    """Testes para normalização de unidades."""

    def test_superscript_conversion(self):
        """Deve converter expoentes."""
        assert normalize_unit("m²") == "M2"
        assert normalize_unit("m³") == "M3"

    def test_caret_notation(self):
        """Deve converter notação com ^."""
        assert normalize_unit("M^2") == "M2"
        assert normalize_unit("M^3") == "M3"

    def test_uppercase(self):
        """Deve converter para maiúsculas."""
        assert normalize_unit("kg") == "KG"
        assert normalize_unit("un") == "UN"

    def test_removes_spaces(self):
        """Deve remover espaços."""
        assert normalize_unit("M 2") == "M2"


class TestExtractKeywords:
    """Testes para extração de palavras-chave."""

    def test_removes_stopwords(self):
        """Deve remover stopwords."""
        keywords = extract_keywords("execução de pavimentação para o cliente")
        assert "DE" not in keywords
        assert "PARA" not in keywords
        assert "O" not in keywords

    def test_extracts_significant_words(self):
        """Deve manter palavras significativas."""
        keywords = extract_keywords("execução de pavimentação asfáltica")
        assert "EXECUCAO" in keywords
        assert "PAVIMENTACAO" in keywords


class TestDescriptionSimilarity:
    """Testes para similaridade de descrições."""

    def test_identical_descriptions(self):
        """Descrições idênticas devem ter alta similaridade."""
        desc = "Pavimentação asfáltica em CBUQ"
        assert description_similarity(desc, desc) == 1.0

    def test_similar_descriptions(self):
        """Descrições similares devem ter similaridade > 0."""
        desc1 = "Pavimentação asfáltica"
        desc2 = "Pavimentação em concreto asfáltico"
        sim = description_similarity(desc1, desc2)
        assert sim > 0

    def test_different_descriptions(self):
        """Descrições diferentes devem ter baixa similaridade."""
        desc1 = "Pavimentação asfáltica"
        desc2 = "Instalação elétrica residencial"
        sim = description_similarity(desc1, desc2)
        assert sim < 0.5


class TestParseItemTuple:
    """Testes para parsing de itens."""

    def test_simple_item(self):
        """Deve parsear item simples."""
        assert parse_item_tuple("1.1") == (1, 1)
        assert parse_item_tuple("2.3") == (2, 3)

    def test_nested_item(self):
        """Deve parsear item aninhado."""
        assert parse_item_tuple("1.2.3") == (1, 2, 3)
        assert parse_item_tuple("001.04.09") == (1, 4, 9)

    def test_invalid_item(self):
        """Deve retornar None para item inválido."""
        assert parse_item_tuple("") is None
        assert parse_item_tuple(None) is None
        assert parse_item_tuple("abc") is None
        assert parse_item_tuple("12345678") is None  # muito longo

    def test_item_with_spaces(self):
        """Deve lidar com espaços."""
        assert parse_item_tuple("1 . 2") == (1, 2)
        assert parse_item_tuple(" 1.2 ") == (1, 2)


class TestItemTupleToStr:
    """Testes para conversão de tupla para string."""

    def test_simple_tuple(self):
        """Deve converter tupla simples."""
        assert item_tuple_to_str((1, 2)) == "1.2"
        assert item_tuple_to_str((1, 2, 3)) == "1.2.3"


class TestParseQuantity:
    """Testes para parsing de quantidade."""

    def test_integer(self):
        """Deve parsear inteiro."""
        assert parse_quantity(100) == 100.0
        assert parse_quantity("100") == 100.0

    def test_decimal_with_comma(self):
        """Deve parsear decimal com vírgula (formato BR)."""
        assert parse_quantity("100,50") == 100.5

    def test_thousands_separator(self):
        """Deve lidar com separador de milhares no formato brasileiro."""
        # Formato brasileiro: ponto é separador de milhar, vírgula é decimal
        assert parse_quantity("1.234,56") == 1234.56
        # Sem vírgula, ponto é tratado como separador de milhar
        assert parse_quantity("1.234") == 1234.0

    def test_invalid_quantity(self):
        """Deve retornar None para quantidade inválida."""
        assert parse_quantity("") is None
        assert parse_quantity(None) is None
        assert parse_quantity("abc") is None


class TestDetectHeaderRow:
    """Testes para detecção de linha de cabeçalho."""

    def test_finds_header(self):
        """Deve encontrar cabeçalho."""
        rows = [
            ["ITEM", "DESCRICAO", "UNIDADE", "QUANTIDADE"],
            ["1.1", "Serviço A", "M2", "100"],
        ]
        assert detect_header_row(rows) == 0

    def test_no_header(self):
        """Deve retornar None se não encontrar cabeçalho."""
        rows = [
            ["1.1", "Serviço A", "M2", "100"],
            ["1.2", "Serviço B", "M3", "200"],
        ]
        assert detect_header_row(rows) is None


class TestFilterClassificationPaths:
    """Testes para filtro de caminhos de classificação."""

    def test_removes_classification_paths(self):
        """Deve remover caminhos de classificação."""
        servicos = [
            {"descricao": "EXECUÇÃO > OBRAS > CONSTRUÇÃO"},
            {"descricao": "Pavimentação asfáltica"},
        ]
        filtered = filter_classification_paths(servicos)
        assert len(filtered) == 1
        assert "Pavimentação" in filtered[0]["descricao"]

    def test_removes_invalid_prefixes(self):
        """Deve remover prefixos inválidos."""
        servicos = [
            {"descricao": "DIRETA OBRAS - Classificação"},
            {"descricao": "Instalação elétrica"},
        ]
        filtered = filter_classification_paths(servicos)
        assert len(filtered) == 1

    def test_keeps_valid_services(self):
        """Deve manter serviços válidos."""
        servicos = [
            {"descricao": "EXECUÇÃO DE PAVIMENTAÇÃO"},  # válido
            {"descricao": "Fundação em estacas"},
        ]
        filtered = filter_classification_paths(servicos)
        assert len(filtered) == 2


class TestIsSummaryRow:
    """Testes para detecção de linha de resumo."""

    def test_detects_total(self):
        """Deve detectar linhas de total."""
        assert is_summary_row("TOTAL DA ETAPA") is True
        assert is_summary_row("TOTAL DO CONTRATO") is True
        assert is_summary_row("SUBTOTAL") is True

    def test_valid_service_not_summary(self):
        """Serviço válido não deve ser detectado como resumo."""
        assert is_summary_row("Pavimentação asfáltica") is False


class TestQuantitiesSimilar:
    """Testes para similaridade de quantidades."""

    def test_equal_quantities(self):
        """Quantidades iguais devem ser similares."""
        assert quantities_similar(100.0, 100.0) is True

    def test_similar_quantities(self):
        """Quantidades com menos de 20% de diferença devem ser similares."""
        assert quantities_similar(100.0, 110.0) is True
        assert quantities_similar(100.0, 119.0) is True

    def test_different_quantities(self):
        """Quantidades muito diferentes não devem ser similares."""
        assert quantities_similar(100.0, 150.0) is False

    def test_none_quantities(self):
        """Quantidades None devem ser consideradas similares."""
        assert quantities_similar(None, 100.0) is True
        assert quantities_similar(100.0, None) is True


class TestDescriptionsSimilar:
    """Testes para similaridade de descrições."""

    def test_identical(self):
        """Descrições idênticas devem ser similares."""
        assert descriptions_similar("Pavimentação", "Pavimentação") is True

    def test_substring(self):
        """Uma descrição contida na outra deve ser similar."""
        assert descriptions_similar("Pavimentação", "Pavimentação asfáltica") is True


class TestItemsSimilar:
    """Testes para similaridade de itens."""

    def test_similar_items(self):
        """Itens similares devem ser detectados."""
        item_a = {"descricao": "Pavimentação asfáltica", "unidade": "M2", "quantidade": 100}
        item_b = {"descricao": "Pavimentação em asfalto", "unidade": "M2", "quantidade": 105}
        assert items_similar(item_a, item_b) is True

    def test_different_units(self):
        """Itens com unidades diferentes não devem ser similares."""
        item_a = {"descricao": "Pavimentação", "unidade": "M2", "quantidade": 100}
        item_b = {"descricao": "Pavimentação", "unidade": "M3", "quantidade": 100}
        assert items_similar(item_a, item_b) is False


class TestServicoKey:
    """Testes para geração de chave de serviço."""

    def test_generates_key(self):
        """Deve gerar chave única."""
        servico = {"item": "1.1", "descricao": "Pavimentação asfáltica"}
        key = servico_key(servico)
        assert key[0] == "1.1"
        assert "PAVIMENTACAO" in key[1]
