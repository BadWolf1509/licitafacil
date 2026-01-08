"""
Testes para o módulo text_utils.
"""
from text_utils import (
    is_garbage_text,
    count_common_words,
    calculate_letter_ratio,
)


class TestIsGarbageText:
    """Testes para a função is_garbage_text."""

    def test_empty_text_is_garbage(self):
        """Texto vazio deve ser considerado lixo."""
        assert is_garbage_text("") is True
        assert is_garbage_text(None) is True
        assert is_garbage_text("   ") is True

    def test_short_text_is_garbage(self):
        """Texto muito curto deve ser considerado lixo."""
        assert is_garbage_text("Texto curto") is True
        assert is_garbage_text("abc") is True

    def test_valid_portuguese_text(self):
        """Texto válido em português não deve ser lixo."""
        valid_text = """
        Este documento atesta que a empresa realizou os serviços de pavimentação
        asfáltica na cidade de São Paulo, com o fornecimento de materiais e
        mão de obra especializada para a execução do projeto conforme especificações.
        """
        assert is_garbage_text(valid_text) is False

    def test_garbage_with_no_common_words(self):
        """Texto sem palavras comuns em português deve ser lixo."""
        garbage = "xyz123 abc789 qwerty asdfgh zxcvbn mnbvcx poiuyt lkjhgf" * 3
        assert is_garbage_text(garbage) is True

    def test_text_with_low_letter_ratio(self):
        """Texto com baixa proporção de letras deve ser lixo."""
        # Texto com muitos números e poucos caracteres
        garbage = "12345 67890 12345 67890 12345 67890 de da em para com 12345 67890"
        assert is_garbage_text(garbage) is True

    def test_ocr_watermark_is_garbage(self):
        """Marca d'água invertida de OCR deve ser lixo."""
        watermark = "ATESTADO ATESTADO 12345 67890 !@#$%^&*() ATESTADO"
        assert is_garbage_text(watermark) is True

    def test_custom_parameters(self):
        """Testa parâmetros customizados."""
        # Texto válido com palavras comuns suficientes
        valid_text = """
        Este documento de atestado foi emitido para comprovar que a empresa
        realizou os serviços de construção da obra conforme contrato.
        """
        assert is_garbage_text(valid_text, min_length=20) is False

        # Com mais palavras comuns exigidas, texto pode falhar
        short_text = "Este texto é de teste."
        assert is_garbage_text(short_text, min_common_words=10) is True


class TestCountCommonWords:
    """Testes para a função count_common_words."""

    def test_counts_portuguese_words(self):
        """Deve contar palavras comuns em português."""
        text = "O documento de atestado da empresa para o cliente"
        count = count_common_words(text)
        # Palavras encontradas: de, da, para, o
        assert count >= 3

    def test_empty_text_returns_zero(self):
        """Texto vazio deve retornar zero."""
        assert count_common_words("") == 0

    def test_no_common_words(self):
        """Texto sem palavras comuns deve retornar zero."""
        text = "xyz abc qwerty"
        assert count_common_words(text) == 0


class TestCalculateLetterRatio:
    """Testes para a função calculate_letter_ratio."""

    def test_all_letters(self):
        """Texto só com letras deve ter ratio 1.0."""
        text = "abcdefghij"
        assert calculate_letter_ratio(text) == 1.0

    def test_mixed_content(self):
        """Texto misto deve ter ratio entre 0 e 1."""
        text = "abc123def456"
        ratio = calculate_letter_ratio(text)
        assert 0 < ratio < 1

    def test_no_letters(self):
        """Texto sem letras deve ter ratio 0."""
        text = "123456789"
        assert calculate_letter_ratio(text) == 0.0

    def test_empty_text(self):
        """Texto vazio deve retornar 0."""
        assert calculate_letter_ratio("") == 0.0
        assert calculate_letter_ratio("   ") == 0.0
