"""
Testes para utils.retry - decorators de retry com backoff exponencial.

Cobre retry sincrono, async_retry assincrono e casos de borda.
"""

import asyncio
import time
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

from utils.retry import retry, async_retry


# ============================================================
# Sync retry decorator
# ============================================================


class TestRetrySyncSuccess:
    """Testes de sucesso para o decorator retry sincrono."""

    def test_retry_success_first_attempt(self):
        """Funcao que nunca falha nao dispara retry."""
        call_count = 0

        @retry(max_attempts=3, delay=1.0)
        def succeed():
            nonlocal call_count
            call_count += 1
            return "ok"

        result = succeed()
        assert result == "ok"
        assert call_count == 1

    @patch("utils.retry.time.sleep")
    def test_retry_success_after_failures(self, mock_sleep):
        """Funcao que falha na 1a tentativa mas acerta na 2a."""
        call_count = 0

        @retry(max_attempts=3, delay=0.1)
        def flaky():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ConnectionError("transient")
            return "recovered"

        result = flaky()
        assert result == "recovered"
        assert call_count == 2
        mock_sleep.assert_called_once()

    @patch("utils.retry.time.sleep")
    def test_retry_exhausts_max_attempts(self, mock_sleep):
        """Levanta excecao apos esgotar todas as tentativas."""
        @retry(max_attempts=3, delay=0.1)
        def always_fails():
            raise RuntimeError("persistent")

        with pytest.raises(RuntimeError, match="persistent"):
            always_fails()

        # 3 tentativas -> 2 sleeps (entre tentativa 1-2 e 2-3)
        assert mock_sleep.call_count == 2


class TestRetrySyncBackoff:
    """Testes de backoff exponencial para o decorator retry sincrono."""

    @patch("utils.retry.time.sleep")
    def test_retry_exponential_backoff(self, mock_sleep):
        """Verifica que delay aumenta exponencialmente entre tentativas."""
        call_count = 0

        @retry(max_attempts=4, delay=1.0, backoff=2.0)
        def fail_thrice():
            nonlocal call_count
            call_count += 1
            if call_count < 4:
                raise ValueError("boom")
            return "ok"

        result = fail_thrice()
        assert result == "ok"

        # Delays esperados: 1.0, 2.0, 4.0
        delays = [call[0][0] for call in mock_sleep.call_args_list]
        assert delays == pytest.approx([1.0, 2.0, 4.0])


class TestRetrySyncExceptions:
    """Testes de filtragem de excecoes."""

    @patch("utils.retry.time.sleep")
    def test_retry_custom_exceptions(self, mock_sleep):
        """Retry so captura excecoes especificadas."""
        call_count = 0

        @retry(max_attempts=3, delay=0.1, exceptions=(ConnectionError,))
        def flaky():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ConnectionError("net")
            return "ok"

        result = flaky()
        assert result == "ok"
        assert call_count == 2

    def test_retry_unmatched_exception_propagates(self):
        """Excecao nao listada propaga imediatamente sem retry."""
        call_count = 0

        @retry(max_attempts=3, delay=0.1, exceptions=(ConnectionError,))
        def bad():
            nonlocal call_count
            call_count += 1
            raise TypeError("wrong type")

        with pytest.raises(TypeError, match="wrong type"):
            bad()

        # So chamou 1 vez - nao fez retry
        assert call_count == 1


class TestRetrySyncCallback:
    """Testes do callback on_retry."""

    @patch("utils.retry.time.sleep")
    def test_retry_on_retry_callback_called(self, mock_sleep):
        """Callback on_retry e invocado com attempt, exception e delay."""
        callback = MagicMock()
        call_count = 0

        @retry(max_attempts=3, delay=1.0, backoff=2.0, on_retry=callback)
        def flaky():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise RuntimeError(f"fail-{call_count}")
            return "ok"

        result = flaky()
        assert result == "ok"
        assert callback.call_count == 2

        # Primeira chamada: attempt=1, exception, delay=1.0
        args1 = callback.call_args_list[0][0]
        assert args1[0] == 1
        assert isinstance(args1[1], RuntimeError)
        assert args1[2] == pytest.approx(1.0)

        # Segunda chamada: attempt=2, exception, delay=2.0
        args2 = callback.call_args_list[1][0]
        assert args2[0] == 2
        assert isinstance(args2[1], RuntimeError)
        assert args2[2] == pytest.approx(2.0)


class TestRetrySyncMetadata:
    """Testes de preservacao de metadados da funcao decorada."""

    def test_retry_preserves_function_metadata(self):
        """@wraps preserva __name__ e __doc__ da funcao original."""
        @retry()
        def my_function():
            """Docstring original."""
            pass

        assert my_function.__name__ == "my_function"
        assert my_function.__doc__ == "Docstring original."

    def test_retry_default_parameters(self):
        """Parametros default: 3 tentativas, 1.0s delay, 2.0 backoff."""
        # Testa indiretamente verificando que com defaults, 3 falhas = excecao
        call_count = 0

        @retry()
        def always_fail():
            nonlocal call_count
            call_count += 1
            raise Exception("fail")

        with patch("utils.retry.time.sleep") as mock_sleep:
            with pytest.raises(Exception):
                always_fail()

        assert call_count == 3
        # 2 sleeps com delays 1.0 e 2.0 (backoff=2.0)
        delays = [call[0][0] for call in mock_sleep.call_args_list]
        assert delays == pytest.approx([1.0, 2.0])


# ============================================================
# Async retry decorator
# ============================================================


class TestAsyncRetrySuccess:
    """Testes de sucesso para o decorator async_retry."""

    @pytest.mark.asyncio
    async def test_async_retry_success_first_attempt(self):
        """Funcao async que nunca falha nao dispara retry."""
        call_count = 0

        decorator = await async_retry(max_attempts=3, delay=0.1)

        @decorator
        async def succeed():
            nonlocal call_count
            call_count += 1
            return "async_ok"

        result = await succeed()
        assert result == "async_ok"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_async_retry_success_after_failures(self):
        """Funcao async que falha na 1a tentativa mas acerta na 2a."""
        call_count = 0

        decorator = await async_retry(max_attempts=3, delay=0.01)

        @decorator
        async def flaky():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ConnectionError("transient")
            return "recovered"

        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            result = await flaky()

        assert result == "recovered"
        assert call_count == 2


class TestAsyncRetryFailure:
    """Testes de falha para async_retry."""

    @pytest.mark.asyncio
    async def test_async_retry_exhausts_max_attempts(self):
        """Levanta excecao apos esgotar tentativas async."""
        decorator = await async_retry(max_attempts=3, delay=0.01)

        @decorator
        async def always_fails():
            raise RuntimeError("persistent")

        with patch("asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(RuntimeError, match="persistent"):
                await always_fails()


class TestAsyncRetryBackoff:
    """Testes de backoff exponencial para async_retry."""

    @pytest.mark.asyncio
    async def test_async_retry_exponential_backoff(self):
        """Verifica delays exponenciais nas chamadas a asyncio.sleep."""
        call_count = 0

        decorator = await async_retry(max_attempts=4, delay=1.0, backoff=2.0)

        @decorator
        async def fail_thrice():
            nonlocal call_count
            call_count += 1
            if call_count < 4:
                raise ValueError("boom")
            return "ok"

        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            result = await fail_thrice()

        assert result == "ok"
        delays = [call[0][0] for call in mock_sleep.call_args_list]
        assert delays == pytest.approx([1.0, 2.0, 4.0])


class TestAsyncRetryExceptionsAndCallback:
    """Testes de filtragem de excecoes e callback para async_retry."""

    @pytest.mark.asyncio
    async def test_async_retry_custom_exceptions(self):
        """Async retry so captura excecoes especificadas."""
        call_count = 0

        decorator = await async_retry(
            max_attempts=3, delay=0.01, exceptions=(ConnectionError,)
        )

        @decorator
        async def bad():
            nonlocal call_count
            call_count += 1
            raise TypeError("wrong")

        with pytest.raises(TypeError, match="wrong"):
            await bad()

        assert call_count == 1

    @pytest.mark.asyncio
    async def test_async_retry_on_retry_callback(self):
        """Callback on_retry e invocado em async retry."""
        callback = MagicMock()
        call_count = 0

        decorator = await async_retry(
            max_attempts=3, delay=1.0, backoff=3.0, on_retry=callback
        )

        @decorator
        async def flaky():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise RuntimeError("fail")
            return "ok"

        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await flaky()

        assert result == "ok"
        assert callback.call_count == 1

        args = callback.call_args[0]
        assert args[0] == 1
        assert isinstance(args[1], RuntimeError)
        assert args[2] == pytest.approx(1.0)


# ============================================================
# Edge cases
# ============================================================


class TestRetryEdgeCases:
    """Testes de casos de borda."""

    def test_retry_max_attempts_one(self):
        """Com max_attempts=1 nao ha retry, falha imediatamente."""
        call_count = 0

        @retry(max_attempts=1, delay=0.1)
        def fail_once():
            nonlocal call_count
            call_count += 1
            raise RuntimeError("only once")

        with pytest.raises(RuntimeError, match="only once"):
            fail_once()

        assert call_count == 1

    @patch("utils.retry.time.sleep")
    def test_retry_zero_delay(self, mock_sleep):
        """Com delay=0 nao ha espera entre tentativas."""
        call_count = 0

        @retry(max_attempts=3, delay=0.0)
        def flaky():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise RuntimeError("retry me")
            return "done"

        result = flaky()
        assert result == "done"
        assert call_count == 3

        # sleep chamado com 0.0 (delay * backoff = 0)
        for call in mock_sleep.call_args_list:
            assert call[0][0] == pytest.approx(0.0)

    @patch("utils.retry.time.sleep")
    def test_retry_returns_correct_value(self, mock_sleep):
        """Valor de retorno da funcao original e preservado apos retries."""
        call_count = 0

        @retry(max_attempts=3, delay=0.1)
        def compute():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise RuntimeError("not yet")
            return {"key": "value", "list": [1, 2, 3]}

        result = compute()
        assert result == {"key": "value", "list": [1, 2, 3]}
