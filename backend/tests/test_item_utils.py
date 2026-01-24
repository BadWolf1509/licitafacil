"""
Testes unitários para item_utils.

Testa funções de manipulação de códigos de item.
"""

import pytest
from services.extraction.item_utils import (
    normalize_item_code,
    strip_restart_prefix,
    split_restart_prefix,
    item_code_in_text,
    max_restart_prefix_index,
)


class TestNormalizeItemCode:
    """Testes para normalize_item_code."""

    def test_simple_code(self):
        assert normalize_item_code("1.2.3") == "1.2.3"

    def test_removes_ad_prefix(self):
        assert normalize_item_code("AD-1.2.3") == "1.2.3"
        assert normalize_item_code("ad-1.2.3") == "1.2.3"

    def test_removes_s_prefix(self):
        assert normalize_item_code("S1-1.2.3") == "1.2.3"
        assert normalize_item_code("S2-1.2") == "1.2"

    def test_handles_spaces(self):
        # parse_item_tuple handles spaces
        assert normalize_item_code("1 2 3") == "1.2.3"

    def test_none_returns_none(self):
        assert normalize_item_code(None) is None

    def test_empty_returns_none(self):
        assert normalize_item_code("") is None
        assert normalize_item_code("  ") is None

    def test_invalid_returns_none(self):
        assert normalize_item_code("invalid") is None
        assert normalize_item_code("abc") is None

    def test_deep_nesting(self):
        assert normalize_item_code("1.2.3.4.5") == "1.2.3.4.5"


class TestStripRestartPrefix:
    """Testes para strip_restart_prefix."""

    def test_removes_s_prefix(self):
        assert strip_restart_prefix("S1-1.2.3") == "1.2.3"
        assert strip_restart_prefix("S2-1.2") == "1.2"
        assert strip_restart_prefix("S10-1.1") == "1.1"

    def test_removes_ad_prefix(self):
        assert strip_restart_prefix("AD-1.2.3") == "1.2.3"
        assert strip_restart_prefix("ad-1.2") == "1.2"

    def test_no_prefix_unchanged(self):
        assert strip_restart_prefix("1.2.3") == "1.2.3"

    def test_empty_returns_empty(self):
        assert strip_restart_prefix("") == ""
        assert strip_restart_prefix(None) == ""


class TestSplitRestartPrefix:
    """Testes para split_restart_prefix."""

    def test_splits_s_prefix(self):
        prefix, code = split_restart_prefix("S1-1.2.3")
        assert prefix == "S1"
        assert code == "1.2.3"

    def test_splits_higher_prefix(self):
        prefix, code = split_restart_prefix("S10-1.2")
        assert prefix == "S10"
        assert code == "1.2"

    def test_no_prefix(self):
        prefix, code = split_restart_prefix("1.2.3")
        assert prefix is None
        assert code == "1.2.3"

    def test_empty_input(self):
        prefix, code = split_restart_prefix("")
        assert prefix is None
        assert code == ""

    def test_none_input(self):
        prefix, code = split_restart_prefix(None)
        assert prefix is None
        assert code == ""

    def test_case_insensitive(self):
        prefix, code = split_restart_prefix("s1-1.2.3")
        assert prefix == "S1"  # Normalizado para maiúsculo


class TestItemCodeInText:
    """Testes para item_code_in_text."""

    def test_finds_exact_match(self):
        assert item_code_in_text("1.2.3", "Item 1.2.3 descrição")

    def test_finds_with_spaces(self):
        assert item_code_in_text("1.2.3", "Item 1. 2. 3 descrição")

    def test_not_part_of_larger_number(self):
        # 1.2.3 não deve casar com 11.2.3 ou 1.2.34
        assert not item_code_in_text("1.2.3", "Item 11.2.3 descrição")

    def test_empty_code(self):
        assert not item_code_in_text("", "texto")

    def test_empty_text(self):
        assert not item_code_in_text("1.2.3", "")

    def test_none_values(self):
        assert not item_code_in_text(None, "texto")
        assert not item_code_in_text("1.2.3", None)


class TestMaxRestartPrefixIndex:
    """Testes para max_restart_prefix_index."""

    def test_finds_max_index(self):
        items = [
            {"item": "S1-1.1"},
            {"item": "S2-1.2"},
            {"item": "S3-1.3"},
        ]
        assert max_restart_prefix_index(items) == 3

    def test_mixed_items(self):
        items = [
            {"item": "1.1"},
            {"item": "S2-1.2"},
            {"item": "1.3"},
        ]
        assert max_restart_prefix_index(items) == 2

    def test_no_prefixes(self):
        items = [
            {"item": "1.1"},
            {"item": "1.2"},
        ]
        assert max_restart_prefix_index(items) == 0

    def test_empty_list(self):
        assert max_restart_prefix_index([]) == 0

    def test_missing_item_key(self):
        items = [
            {"descricao": "test"},
            {"item": "S1-1.1"},
        ]
        assert max_restart_prefix_index(items) == 1
