"""
Testes unitários para sanitize_description.

Testa sanitização de descrições extraídas de documentos.
"""

import pytest
from utils.text_utils import sanitize_description


class TestSanitizeDescription:
    """Testes para sanitize_description."""

    def test_preserves_ascii(self):
        result = sanitize_description("FORNECIMENTO DE MATERIAL")
        assert result == "FORNECIMENTO DE MATERIAL"

    def test_preserves_latin1_accents(self):
        # Acentos em Latin-1 Supplement (0x00C0-0x00FF)
        result = sanitize_description("INSTALAÇÃO ELÉTRICA")
        assert result == "INSTALAÇÃO ELÉTRICA"

    def test_removes_heavy_minus_sign(self):
        # U+2796 HEAVY MINUS SIGN
        result = sanitize_description("ITEM\u2796DESCRICAO")
        assert "\u2796" not in result
        assert "ITEM" in result
        assert "DESCRICAO" in result

    def test_removes_special_unicode(self):
        # Vários caracteres Unicode especiais
        result = sanitize_description("TEST\u2022BULLET\u2013DASH\u201Cquote\u201D")
        assert "\u2022" not in result  # bullet
        assert "\u2013" not in result  # en dash
        assert "\u201C" not in result  # left quote
        assert "\u201D" not in result  # right quote

    def test_normalizes_multiple_spaces(self):
        result = sanitize_description("ITEM    COM     ESPACOS")
        assert result == "ITEM COM ESPACOS"

    def test_empty_string_returns_empty(self):
        assert sanitize_description("") == ""

    def test_none_returns_empty(self):
        # A função trata None como falsy e retorna ""
        assert sanitize_description(None) == ""

    def test_preserves_numbers(self):
        result = sanitize_description("ITEM 1.2.3 COM 10,50 QUANTIDADE")
        assert "1.2.3" in result
        assert "10,50" in result

    def test_preserves_common_punctuation(self):
        result = sanitize_description("ITEM, COM (PARENTESES) E [COLCHETES].")
        assert "," in result
        assert "(" in result
        assert ")" in result
        assert "[" in result
        assert "]" in result
        assert "." in result

    def test_handles_mixed_content(self):
        # Texto real com problemas de OCR
        # U+2796 é removido, espaço é inserido
        result = sanitize_description("FORNEC\u2796 DE TUBO 50mm")
        assert "FORNEC" in result
        assert "TUBO" in result
        assert "50mm" in result

    def test_trims_whitespace(self):
        result = sanitize_description("  TEXTO COM ESPACOS  ")
        assert result == "TEXTO COM ESPACOS"

    def test_handles_cedilla(self):
        # Ç (0x00C7) e Ã (0x00C3) estão em Latin-1 Supplement (0x00C0-0x00FF)
        result = sanitize_description("INSTALAÇÃO CONEXÃO FUNDAÇÃO")
        assert "Ç" in result
        assert "Ã" in result

    def test_removes_degree_symbol(self):
        # ° (0x00B0) está fora do range 0x00C0-0x00FF, é removido
        result = sanitize_description("TEMPERATURA 25°C")
        # O ° é substituído por espaço
        assert "°" not in result
        assert "TEMPERATURA" in result
        assert "25" in result
        assert "C" in result

    def test_removes_superscript_numbers(self):
        # ² (0x00B2) e ³ (0x00B3) estão fora do range 0x00C0-0x00FF, são removidos
        result = sanitize_description("AREA 100M² VOLUME 50M³")
        assert "²" not in result
        assert "³" not in result
        # Números e letras são preservados
        assert "AREA" in result
        assert "100M" in result
        assert "50M" in result


class TestSanitizeDescriptionEdgeCases:
    """Testes para casos extremos."""

    def test_only_unicode_returns_empty(self):
        # Apenas caracteres Unicode especiais
        result = sanitize_description("\u2796\u2022\u2013")
        assert result == ""

    def test_very_long_text(self):
        long_text = "A" * 10000
        result = sanitize_description(long_text)
        assert len(result) == 10000

    def test_newlines_normalized(self):
        result = sanitize_description("LINHA1\nLINHA2\nLINHA3")
        # Newlines são preservados pelo loop, mas split() os normaliza
        assert "LINHA1" in result
        assert "LINHA2" in result
        assert "LINHA3" in result

    def test_tabs_normalized(self):
        result = sanitize_description("COL1\tCOL2\tCOL3")
        # Tabs são normalizados por split()
        assert "COL1" in result
        assert "COL2" in result
        assert "COL3" in result

    def test_preserves_o_with_slash(self):
        # Ø (0x00D8) está em Latin-1 Supplement (0x00C0-0x00FF)
        result = sanitize_description("TUBO Ø 50mm")
        assert "Ø" in result

    def test_preserves_tilde_n(self):
        # Ñ (0x00D1) está em Latin-1 Supplement
        result = sanitize_description("SEÑOR")
        assert "Ñ" in result
