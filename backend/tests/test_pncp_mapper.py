"""Tests for PncpMapper and PncpMatcher."""
from datetime import datetime
from decimal import Decimal
from unittest.mock import MagicMock

from services.pncp.mapper import PncpMapper
from services.pncp.matcher import PncpMatcher

# ===========================================================================
# PncpMapper - parse_pncp_datetime
# ===========================================================================


class TestParsePncpDatetime:

    def test_valid_iso_string(self):
        result = PncpMapper.parse_pncp_datetime("2026-03-15T10:30:00")
        assert isinstance(result, datetime)
        assert result.year == 2026
        assert result.month == 3
        assert result.day == 15
        assert result.hour == 10
        assert result.minute == 30

    def test_valid_iso_with_timezone(self):
        result = PncpMapper.parse_pncp_datetime("2026-03-15T10:30:00-03:00")
        assert isinstance(result, datetime)
        assert result.year == 2026

    def test_none_returns_none(self):
        assert PncpMapper.parse_pncp_datetime(None) is None

    def test_empty_string_returns_none(self):
        assert PncpMapper.parse_pncp_datetime("") is None

    def test_invalid_string_returns_none(self):
        assert PncpMapper.parse_pncp_datetime("not-a-date") is None

    def test_partial_date_string(self):
        # Just a date without time should still parse via fromisoformat
        result = PncpMapper.parse_pncp_datetime("2026-03-15")
        assert isinstance(result, datetime)
        assert result.day == 15


# ===========================================================================
# PncpMapper - parse_decimal
# ===========================================================================


class TestParseDecimal:

    def test_valid_number(self):
        result = PncpMapper.parse_decimal(500000.50)
        assert result == Decimal("500000.5")

    def test_valid_string_number(self):
        result = PncpMapper.parse_decimal("1234567.89")
        assert result == Decimal("1234567.89")

    def test_valid_integer(self):
        result = PncpMapper.parse_decimal(100)
        assert result == Decimal("100")

    def test_none_returns_none(self):
        assert PncpMapper.parse_decimal(None) is None

    def test_invalid_string_returns_none(self):
        assert PncpMapper.parse_decimal("abc") is None

    def test_empty_string_returns_none(self):
        assert PncpMapper.parse_decimal("") is None


# ===========================================================================
# PncpMapper - extrair_resultado
# ===========================================================================


class TestExtrairResultado:

    def test_complete_pncp_data(self):
        item = {
            "numeroControlePNCP": "CTRL-12345678901234",
            "orgaoEntidade": {
                "cnpj": "12345678000100",
                "razaoSocial": "Prefeitura Municipal de Teste",
            },
            "unidadeOrgao": {
                "ufSigla": "SP",
                "municipioNome": "Sao Paulo",
            },
            "objetoCompra": "Pavimentacao asfaltica em CBUQ",
            "modalidadeNome": "Pregao Eletronico",
            "valorTotalEstimado": 500000.00,
            "dataAberturaProposta": "2026-03-15T10:00:00",
            "dataEncerramentoProposta": "2026-04-15T10:00:00",
            "linkSistemaOrigem": "https://comprasnet.gov.br/1234",
        }

        result = PncpMapper.extrair_resultado(item, monitoramento_id=1, user_id=10)

        assert result["monitoramento_id"] == 1
        assert result["user_id"] == 10
        assert result["numero_controle_pncp"] == "CTRL-12345678901234"
        assert result["orgao_cnpj"] == "12345678000100"
        assert result["orgao_razao_social"] == "Prefeitura Municipal de Teste"
        assert result["objeto_compra"] == "Pavimentacao asfaltica em CBUQ"
        assert result["modalidade_nome"] == "Pregao Eletronico"
        assert result["uf"] == "SP"
        assert result["municipio"] == "Sao Paulo"
        assert result["valor_estimado"] == Decimal("500000.0")
        assert isinstance(result["data_abertura"], datetime)
        assert isinstance(result["data_encerramento"], datetime)
        assert result["link_sistema_origem"] == "https://comprasnet.gov.br/1234"
        assert result["dados_completos"] is item

    def test_partial_null_fields(self):
        item = {
            "numeroControlePNCP": "CTRL-MINIMAL",
            "orgaoEntidade": None,
            "unidadeOrgao": None,
            "objetoCompra": None,
            "modalidadeNome": None,
            "valorTotalEstimado": None,
            "dataAberturaProposta": None,
            "dataEncerramentoProposta": None,
            "linkSistemaOrigem": None,
        }

        result = PncpMapper.extrair_resultado(item, monitoramento_id=2, user_id=5)

        assert result["numero_controle_pncp"] == "CTRL-MINIMAL"
        assert result["orgao_cnpj"] is None
        assert result["orgao_razao_social"] is None
        assert result["objeto_compra"] is None
        assert result["valor_estimado"] is None
        assert result["data_abertura"] is None
        assert result["data_encerramento"] is None

    def test_missing_optional_keys(self):
        """Item with minimal keys (no orgaoEntidade, etc.)."""
        item = {"numeroControlePNCP": "CTRL-SPARSE"}

        result = PncpMapper.extrair_resultado(item, monitoramento_id=1, user_id=1)

        assert result["numero_controle_pncp"] == "CTRL-SPARSE"
        assert result["orgao_cnpj"] is None
        assert result["uf"] is None


# ===========================================================================
# PncpMapper - resultado_para_licitacao
# ===========================================================================


class TestResultadoParaLicitacao:

    def _make_resultado(self, **overrides):
        r = MagicMock()
        defaults = {
            "numero_controle_pncp": "12345678901234567890",
            "objeto_compra": "Pavimentacao asfaltica",
            "orgao_razao_social": "Prefeitura Municipal",
            "modalidade_nome": "Pregao Eletronico",
            "valor_estimado": Decimal("500000.00"),
            "data_abertura": datetime(2026, 3, 15),
            "data_encerramento": datetime(2026, 4, 15),
            "uf": "SP",
            "municipio": "Sao Paulo",
            "link_sistema_origem": "https://pncp.gov.br/1234",
        }
        defaults.update(overrides)
        for k, v in defaults.items():
            setattr(r, k, v)
        return r

    def test_numero_starts_with_pncp(self):
        r = self._make_resultado()
        campos = PncpMapper.resultado_para_licitacao(r)
        assert campos["numero"].startswith("PNCP-")

    def test_fonte_is_pncp(self):
        r = self._make_resultado()
        campos = PncpMapper.resultado_para_licitacao(r)
        assert campos["fonte"] == "pncp"

    def test_status_is_identificada(self):
        r = self._make_resultado()
        campos = PncpMapper.resultado_para_licitacao(r)
        assert campos["status"] == "identificada"

    def test_modalidade_present(self):
        r = self._make_resultado()
        campos = PncpMapper.resultado_para_licitacao(r)
        assert campos["modalidade"] == "Pregao Eletronico"

    def test_observacoes_contains_controle(self):
        r = self._make_resultado()
        campos = PncpMapper.resultado_para_licitacao(r)
        assert "12345678901234567890" in campos["observacoes"]
        assert "Importado do PNCP" in campos["observacoes"]

    def test_no_objeto_defaults(self):
        r = self._make_resultado(objeto_compra=None)
        campos = PncpMapper.resultado_para_licitacao(r)
        assert campos["objeto"] == "Sem descrição"

    def test_no_orgao_defaults(self):
        r = self._make_resultado(orgao_razao_social=None)
        campos = PncpMapper.resultado_para_licitacao(r)
        assert campos["orgao"] == "Não informado"

    def test_no_modalidade_defaults(self):
        r = self._make_resultado(modalidade_nome=None)
        campos = PncpMapper.resultado_para_licitacao(r)
        assert campos["modalidade"] == "Não informada"

    def test_short_numero_controle(self):
        """When numero_controle is <= 10 chars, uses full value."""
        r = self._make_resultado(numero_controle_pncp="SHORT123")
        campos = PncpMapper.resultado_para_licitacao(r)
        assert campos["numero"] == "PNCP-SHORT123"

    def test_long_numero_controle_uses_last_10(self):
        """When numero_controle > 10 chars, uses last 10."""
        r = self._make_resultado(numero_controle_pncp="12345678901234567890")
        campos = PncpMapper.resultado_para_licitacao(r)
        assert campos["numero"] == "PNCP-1234567890"


# ===========================================================================
# PncpMatcher - match_palavras_chave
# ===========================================================================


class TestMatchPalavrasChave:

    def test_match_found(self):
        assert PncpMatcher.match_palavras_chave(
            "Pavimentacao asfaltica em CBUQ", ["pavimentacao"],
        ) is True

    def test_no_match(self):
        assert PncpMatcher.match_palavras_chave(
            "Servico de limpeza urbana", ["pavimentacao", "asfalto"],
        ) is False

    def test_empty_list_returns_true(self):
        """Empty palavras list means no filter applied."""
        assert PncpMatcher.match_palavras_chave("Qualquer texto", []) is True

    def test_none_text_returns_false(self):
        assert PncpMatcher.match_palavras_chave(None, ["asfalto"]) is False

    def test_case_insensitive(self):
        assert PncpMatcher.match_palavras_chave(
            "PAVIMENTACAO ASFALTICA", ["pavimentacao"],
        ) is True


# ===========================================================================
# PncpMatcher - match_ufs
# ===========================================================================


class TestMatchUfs:

    def test_match(self):
        assert PncpMatcher.match_ufs("SP", ["SP", "RJ"]) is True

    def test_no_match(self):
        assert PncpMatcher.match_ufs("MG", ["SP", "RJ"]) is False

    def test_empty_list_returns_true(self):
        assert PncpMatcher.match_ufs("SP", []) is True

    def test_none_uf_returns_false(self):
        assert PncpMatcher.match_ufs(None, ["SP"]) is False

    def test_case_insensitive(self):
        assert PncpMatcher.match_ufs("sp", ["SP"]) is True


# ===========================================================================
# PncpMatcher - match_valor
# ===========================================================================


class TestMatchValor:

    def test_within_range(self):
        assert PncpMatcher.match_valor(
            500000, Decimal("100000"), Decimal("1000000"),
        ) is True

    def test_below_min(self):
        assert PncpMatcher.match_valor(
            50000, Decimal("100000"), Decimal("1000000"),
        ) is False

    def test_above_max(self):
        assert PncpMatcher.match_valor(
            2000000, Decimal("100000"), Decimal("1000000"),
        ) is False

    def test_no_limits(self):
        """No min and no max always matches."""
        assert PncpMatcher.match_valor(500000, None, None) is True

    def test_only_min(self):
        assert PncpMatcher.match_valor(500000, Decimal("100000"), None) is True
        assert PncpMatcher.match_valor(50, Decimal("100000"), None) is False

    def test_only_max(self):
        assert PncpMatcher.match_valor(500, None, Decimal("1000")) is True
        assert PncpMatcher.match_valor(2000, None, Decimal("1000")) is False

    def test_none_valor_returns_true(self):
        """None valor is not filtered out."""
        assert PncpMatcher.match_valor(None, Decimal("100"), Decimal("1000")) is True

    def test_exact_min_boundary(self):
        assert PncpMatcher.match_valor(
            100000, Decimal("100000"), Decimal("1000000"),
        ) is True

    def test_exact_max_boundary(self):
        assert PncpMatcher.match_valor(
            1000000, Decimal("100000"), Decimal("1000000"),
        ) is True


# ===========================================================================
# PncpMatcher - filtrar_resultados
# ===========================================================================


class TestFiltrarResultados:

    def _make_monitor(self, **overrides):
        m = MagicMock()
        defaults = {
            "palavras_chave": None,
            "ufs": None,
            "valor_minimo": None,
            "valor_maximo": None,
        }
        defaults.update(overrides)
        for k, v in defaults.items():
            setattr(m, k, v)
        return m

    def test_no_filters_returns_all(self):
        monitor = self._make_monitor()
        items = [
            {"objetoCompra": "Item 1", "unidadeOrgao": {"ufSigla": "SP"}, "valorTotalEstimado": 100},
            {"objetoCompra": "Item 2", "unidadeOrgao": {"ufSigla": "RJ"}, "valorTotalEstimado": 200},
        ]
        result = PncpMatcher.filtrar_resultados(items, monitor)
        assert len(result) == 2

    def test_filter_by_palavras_chave(self):
        monitor = self._make_monitor(palavras_chave=["asfalto"])
        items = [
            {"objetoCompra": "Asfalto CBUQ", "unidadeOrgao": {}, "valorTotalEstimado": 100},
            {"objetoCompra": "Limpeza urbana", "unidadeOrgao": {}, "valorTotalEstimado": 200},
        ]
        result = PncpMatcher.filtrar_resultados(items, monitor)
        assert len(result) == 1
        assert result[0]["objetoCompra"] == "Asfalto CBUQ"

    def test_filter_by_ufs(self):
        monitor = self._make_monitor(ufs=["SP"])
        items = [
            {"objetoCompra": "Item SP", "unidadeOrgao": {"ufSigla": "SP"}, "valorTotalEstimado": 100},
            {"objetoCompra": "Item RJ", "unidadeOrgao": {"ufSigla": "RJ"}, "valorTotalEstimado": 200},
        ]
        result = PncpMatcher.filtrar_resultados(items, monitor)
        assert len(result) == 1
        assert result[0]["objetoCompra"] == "Item SP"

    def test_filter_by_valor_range(self):
        monitor = self._make_monitor(
            valor_minimo=Decimal("150"),
            valor_maximo=Decimal("250"),
        )
        items = [
            {"objetoCompra": "Cheap", "unidadeOrgao": {}, "valorTotalEstimado": 100},
            {"objetoCompra": "Mid", "unidadeOrgao": {}, "valorTotalEstimado": 200},
            {"objetoCompra": "Expensive", "unidadeOrgao": {}, "valorTotalEstimado": 300},
        ]
        result = PncpMatcher.filtrar_resultados(items, monitor)
        assert len(result) == 1
        assert result[0]["objetoCompra"] == "Mid"

    def test_combination_of_all_filters(self):
        monitor = self._make_monitor(
            palavras_chave=["pavimentacao"],
            ufs=["SP"],
            valor_minimo=Decimal("100000"),
            valor_maximo=Decimal("1000000"),
        )
        items = [
            # Matches all filters
            {
                "objetoCompra": "Pavimentacao asfaltica",
                "unidadeOrgao": {"ufSigla": "SP"},
                "valorTotalEstimado": 500000,
            },
            # Wrong UF
            {
                "objetoCompra": "Pavimentacao asfaltica",
                "unidadeOrgao": {"ufSigla": "RJ"},
                "valorTotalEstimado": 500000,
            },
            # Wrong keyword
            {
                "objetoCompra": "Servico de limpeza",
                "unidadeOrgao": {"ufSigla": "SP"},
                "valorTotalEstimado": 500000,
            },
            # Value too low
            {
                "objetoCompra": "Pavimentacao pequena",
                "unidadeOrgao": {"ufSigla": "SP"},
                "valorTotalEstimado": 50000,
            },
        ]
        result = PncpMatcher.filtrar_resultados(items, monitor)
        assert len(result) == 1
        assert result[0]["objetoCompra"] == "Pavimentacao asfaltica"

    def test_empty_items_list(self):
        monitor = self._make_monitor(palavras_chave=["asfalto"])
        result = PncpMatcher.filtrar_resultados([], monitor)
        assert result == []
