"""
Testes para o servico de autenticacao Supabase.

Testa inicializacao do cliente, validacao de tokens, verificacao de sessao,
extracao de dados do usuario e tratamento de configuracao ausente.
Usa mocking para evitar dependencia de conexao real com Supabase.
"""
import pytest
from unittest.mock import patch, MagicMock


# ============================================================================
# 1. Supabase client initialization
# ============================================================================

class TestSupabaseClientInitialization:
    """Testes para inicializacao do cliente Supabase."""

    def test_get_supabase_client_initializes_when_configured(self):
        """
        Quando SUPABASE_URL e SUPABASE_SERVICE_KEY estao definidos,
        _get_supabase_client deve chamar create_client e retornar o cliente.
        """
        mock_client = MagicMock(name="supabase_client")

        with patch("services.supabase_auth.SUPABASE_URL", "https://example.supabase.co"), \
             patch("services.supabase_auth.SUPABASE_SERVICE_KEY", "service-key-123"), \
             patch("services.supabase_auth._supabase_client", None), \
             patch("supabase.create_client", return_value=mock_client) as mock_create:

            from services.supabase_auth import _get_supabase_client
            client = _get_supabase_client()

            mock_create.assert_called_once_with(
                "https://example.supabase.co",
                "service-key-123",
            )
            assert client is mock_client

    def test_get_supabase_client_returns_cached_client_on_second_call(self):
        """
        Se o cliente ja foi inicializado (nao e None), _get_supabase_client
        deve retornar a instancia existente sem chamar create_client novamente.
        """
        existing_client = MagicMock(name="existing_client")

        with patch("services.supabase_auth._supabase_client", existing_client):
            from services.supabase_auth import _get_supabase_client
            client = _get_supabase_client()

            assert client is existing_client


# ============================================================================
# 2. Missing config handling
# ============================================================================

class TestMissingConfigHandling:
    """Testes para tratamento de configuracao ausente."""

    def test_get_supabase_client_raises_when_url_missing(self):
        """
        Quando SUPABASE_URL esta vazio, _get_supabase_client deve levantar
        ValueError indicando que as variaveis sao obrigatorias.
        """
        with patch("services.supabase_auth.SUPABASE_URL", ""), \
             patch("services.supabase_auth.SUPABASE_SERVICE_KEY", "key"), \
             patch("services.supabase_auth._supabase_client", None):

            from services.supabase_auth import _get_supabase_client

            with pytest.raises(ValueError, match="obrigatórios"):
                _get_supabase_client()

    def test_get_supabase_client_raises_when_service_key_missing(self):
        """
        Quando SUPABASE_SERVICE_KEY esta vazio, _get_supabase_client deve
        levantar ValueError.
        """
        with patch("services.supabase_auth.SUPABASE_URL", "https://example.supabase.co"), \
             patch("services.supabase_auth.SUPABASE_SERVICE_KEY", ""), \
             patch("services.supabase_auth._supabase_client", None):

            from services.supabase_auth import _get_supabase_client

            with pytest.raises(ValueError, match="obrigatórios"):
                _get_supabase_client()

    def test_verify_token_returns_none_when_client_not_configured(self):
        """
        Se o cliente nao esta configurado (_get_supabase_client levanta
        ValueError), verify_supabase_token captura a excecao e retorna None.
        """
        with patch(
            "services.supabase_auth._get_supabase_client",
            side_effect=ValueError("SUPABASE_URL e SUPABASE_SERVICE_KEY são obrigatórios"),
        ):
            from services.supabase_auth import verify_supabase_token

            result = verify_supabase_token("any-token")
            assert result is None

    def test_get_supabase_config_returns_public_config_only(self):
        """
        get_supabase_config deve retornar apenas url e anon_key.
        A service_key NUNCA deve ser exposta.
        """
        with patch("services.supabase_auth.SUPABASE_URL", "https://proj.supabase.co"), \
             patch("services.supabase_auth.SUPABASE_ANON_KEY", "anon-key-456"):

            from services.supabase_auth import get_supabase_config

            config = get_supabase_config()

            assert config["url"] == "https://proj.supabase.co"
            assert config["anon_key"] == "anon-key-456"
            # Garantir que a service key NAO esta presente
            assert "service_key" not in config
            assert "SUPABASE_SERVICE_KEY" not in str(config)


# ============================================================================
# 3. Token validation - valid token mock
# ============================================================================

class TestTokenValidationValid:
    """Testes para validacao de token valido."""

    def test_verify_token_returns_user_data_for_valid_token(self):
        """
        Quando o token e valido, verify_supabase_token deve retornar
        um dicionario com os dados do usuario extraidos da resposta.
        """
        mock_user = MagicMock()
        mock_user.id = "user-uuid-123"
        mock_user.email = "usuario@teste.com"
        mock_user.email_confirmed_at = "2026-01-01T00:00:00Z"
        mock_user.phone = "+5511999999999"
        mock_user.created_at = "2026-01-01T00:00:00Z"
        mock_user.last_sign_in_at = "2026-02-06T12:00:00Z"
        mock_user.app_metadata = {"provider": "email"}
        mock_user.user_metadata = {"nome": "Teste"}

        mock_response = MagicMock()
        mock_response.user = mock_user

        mock_client = MagicMock(name="supabase_client")
        mock_client.auth.get_user.return_value = mock_response

        with patch("services.supabase_auth._get_supabase_client", return_value=mock_client):
            from services.supabase_auth import verify_supabase_token

            result = verify_supabase_token("valid-jwt-token")

            assert result is not None
            assert result["id"] == "user-uuid-123"
            assert result["email"] == "usuario@teste.com"
            assert result["email_confirmed"] is True
            assert result["phone"] == "+5511999999999"
            assert result["app_metadata"] == {"provider": "email"}
            assert result["user_metadata"] == {"nome": "Teste"}
            mock_client.auth.get_user.assert_called_once_with("valid-jwt-token")

    def test_verify_token_returns_none_when_response_has_no_user(self):
        """
        Se o Supabase retorna uma resposta sem usuario (response.user e None),
        verify_supabase_token deve retornar None.
        """
        mock_response = MagicMock()
        mock_response.user = None

        mock_client = MagicMock(name="supabase_client")
        mock_client.auth.get_user.return_value = mock_response

        with patch("services.supabase_auth._get_supabase_client", return_value=mock_client):
            from services.supabase_auth import verify_supabase_token

            result = verify_supabase_token("some-token")
            assert result is None


# ============================================================================
# 4. Token validation - invalid/expired token
# ============================================================================

class TestTokenValidationInvalid:
    """Testes para rejeicao de tokens invalidos e expirados."""

    def test_verify_token_returns_none_for_empty_token(self):
        """
        Um token vazio deve resultar em retorno None (o cliente Supabase
        lancara excecao internamente, que e capturada e resulta em None).
        """
        mock_client = MagicMock(name="supabase_client")
        mock_client.auth.get_user.side_effect = Exception("Invalid token")

        with patch("services.supabase_auth._get_supabase_client", return_value=mock_client):
            from services.supabase_auth import verify_supabase_token

            result = verify_supabase_token("")
            assert result is None

    def test_verify_token_returns_none_for_invalid_token(self):
        """
        Um token invalido (lixo) deve resultar em retorno None porque o
        Supabase rejeita e a excecao e capturada.
        """
        mock_client = MagicMock(name="supabase_client")
        mock_client.auth.get_user.side_effect = Exception("Invalid JWT")

        with patch("services.supabase_auth._get_supabase_client", return_value=mock_client):
            from services.supabase_auth import verify_supabase_token

            result = verify_supabase_token("not-a-real-jwt-token")
            assert result is None
            mock_client.auth.get_user.assert_called_once_with("not-a-real-jwt-token")

    def test_verify_token_returns_none_for_expired_token(self):
        """
        Um token expirado faz o Supabase lancar excecao, que e capturada
        e resulta em None.
        """
        mock_client = MagicMock(name="supabase_client")
        mock_client.auth.get_user.side_effect = Exception("Token expired")

        with patch("services.supabase_auth._get_supabase_client", return_value=mock_client):
            from services.supabase_auth import verify_supabase_token

            result = verify_supabase_token("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.expired")
            assert result is None


# ============================================================================
# 5. Session verification (sign_in_with_password / refresh_session)
# ============================================================================

class TestSessionVerification:
    """Testes para verificacao de sessao via login e refresh."""

    def test_sign_in_with_password_returns_tokens_on_success(self):
        """
        sign_in_with_password com credenciais validas deve retornar
        dicionario com access_token, refresh_token, expires_in e user.
        """
        mock_user = MagicMock()
        mock_user.id = "user-uuid-456"
        mock_user.email = "login@teste.com"

        mock_session = MagicMock()
        mock_session.access_token = "access-token-xyz"
        mock_session.refresh_token = "refresh-token-abc"
        mock_session.expires_in = 3600

        mock_response = MagicMock()
        mock_response.session = mock_session
        mock_response.user = mock_user

        mock_anon_client = MagicMock(name="anon_client")
        mock_anon_client.auth.sign_in_with_password.return_value = mock_response

        with patch("services.supabase_auth.SUPABASE_URL", "https://proj.supabase.co"), \
             patch("services.supabase_auth.SUPABASE_ANON_KEY", "anon-key"), \
             patch("supabase.create_client", return_value=mock_anon_client):

            from services.supabase_auth import sign_in_with_password

            result = sign_in_with_password("login@teste.com", "senha123")

            assert result is not None
            assert result["access_token"] == "access-token-xyz"
            assert result["refresh_token"] == "refresh-token-abc"
            assert result["expires_in"] == 3600
            assert result["user"]["id"] == "user-uuid-456"
            assert result["user"]["email"] == "login@teste.com"

            mock_anon_client.auth.sign_in_with_password.assert_called_once_with({
                "email": "login@teste.com",
                "password": "senha123",
            })

    def test_sign_in_with_password_returns_none_on_invalid_credentials(self):
        """
        sign_in_with_password com credenciais invalidas deve retornar None
        (excecao capturada internamente).
        """
        mock_anon_client = MagicMock(name="anon_client")
        mock_anon_client.auth.sign_in_with_password.side_effect = Exception(
            "Invalid login credentials"
        )

        with patch("services.supabase_auth.SUPABASE_URL", "https://proj.supabase.co"), \
             patch("services.supabase_auth.SUPABASE_ANON_KEY", "anon-key"), \
             patch("supabase.create_client", return_value=mock_anon_client):

            from services.supabase_auth import sign_in_with_password

            result = sign_in_with_password("wrong@teste.com", "wrongpass")
            assert result is None

    def test_sign_in_returns_none_when_no_session(self):
        """
        Se o Supabase retorna resposta sem sessao, sign_in_with_password
        deve retornar None.
        """
        mock_response = MagicMock()
        mock_response.session = None
        mock_response.user = MagicMock()

        mock_anon_client = MagicMock(name="anon_client")
        mock_anon_client.auth.sign_in_with_password.return_value = mock_response

        with patch("services.supabase_auth.SUPABASE_URL", "https://proj.supabase.co"), \
             patch("services.supabase_auth.SUPABASE_ANON_KEY", "anon-key"), \
             patch("supabase.create_client", return_value=mock_anon_client):

            from services.supabase_auth import sign_in_with_password

            result = sign_in_with_password("user@teste.com", "pass123")
            assert result is None

    def test_refresh_session_returns_new_tokens_on_success(self):
        """
        refresh_session com refresh_token valido deve retornar novos tokens.
        """
        mock_session = MagicMock()
        mock_session.access_token = "new-access-token"
        mock_session.refresh_token = "new-refresh-token"
        mock_session.expires_in = 3600

        mock_response = MagicMock()
        mock_response.session = mock_session

        mock_anon_client = MagicMock(name="anon_client")
        mock_anon_client.auth.refresh_session.return_value = mock_response

        with patch("services.supabase_auth.SUPABASE_URL", "https://proj.supabase.co"), \
             patch("services.supabase_auth.SUPABASE_ANON_KEY", "anon-key"), \
             patch("supabase.create_client", return_value=mock_anon_client):

            from services.supabase_auth import refresh_session

            result = refresh_session("old-refresh-token")

            assert result is not None
            assert result["access_token"] == "new-access-token"
            assert result["refresh_token"] == "new-refresh-token"
            assert result["expires_in"] == 3600
            mock_anon_client.auth.refresh_session.assert_called_once_with("old-refresh-token")

    def test_refresh_session_returns_none_on_failure(self):
        """
        refresh_session com refresh_token invalido deve retornar None.
        """
        mock_anon_client = MagicMock(name="anon_client")
        mock_anon_client.auth.refresh_session.side_effect = Exception("Invalid refresh token")

        with patch("services.supabase_auth.SUPABASE_URL", "https://proj.supabase.co"), \
             patch("services.supabase_auth.SUPABASE_ANON_KEY", "anon-key"), \
             patch("supabase.create_client", return_value=mock_anon_client):

            from services.supabase_auth import refresh_session

            result = refresh_session("expired-refresh-token")
            assert result is None


# ============================================================================
# 6. User extraction from token
# ============================================================================

class TestUserExtractionFromToken:
    """Testes para extracao correta dos dados do usuario a partir do token."""

    def test_user_extraction_includes_all_expected_fields(self):
        """
        O dicionario retornado deve conter todos os campos esperados:
        id, email, email_confirmed, phone, created_at, last_sign_in,
        app_metadata e user_metadata.
        """
        mock_user = MagicMock()
        mock_user.id = "abc-123"
        mock_user.email = "completo@teste.com"
        mock_user.email_confirmed_at = "2026-01-15T10:00:00Z"
        mock_user.phone = None
        mock_user.created_at = "2026-01-15T10:00:00Z"
        mock_user.last_sign_in_at = "2026-02-01T08:30:00Z"
        mock_user.app_metadata = {"provider": "email", "providers": ["email"]}
        mock_user.user_metadata = {"nome": "Completo", "empresa": "Teste LTDA"}

        mock_response = MagicMock()
        mock_response.user = mock_user

        mock_client = MagicMock(name="supabase_client")
        mock_client.auth.get_user.return_value = mock_response

        with patch("services.supabase_auth._get_supabase_client", return_value=mock_client):
            from services.supabase_auth import verify_supabase_token

            result = verify_supabase_token("valid-token")

            expected_keys = {
                "id", "email", "email_confirmed", "phone",
                "created_at", "last_sign_in", "app_metadata", "user_metadata",
            }
            assert set(result.keys()) == expected_keys

    def test_user_extraction_email_not_confirmed(self):
        """
        Quando email_confirmed_at e None, email_confirmed deve ser False.
        """
        mock_user = MagicMock()
        mock_user.id = "unconfirmed-uuid"
        mock_user.email = "naoconfirmado@teste.com"
        mock_user.email_confirmed_at = None
        mock_user.phone = None
        mock_user.created_at = None
        mock_user.last_sign_in_at = None
        mock_user.app_metadata = {}
        mock_user.user_metadata = {}

        mock_response = MagicMock()
        mock_response.user = mock_user

        mock_client = MagicMock(name="supabase_client")
        mock_client.auth.get_user.return_value = mock_response

        with patch("services.supabase_auth._get_supabase_client", return_value=mock_client):
            from services.supabase_auth import verify_supabase_token

            result = verify_supabase_token("unconfirmed-token")

            assert result["email_confirmed"] is False
            assert result["created_at"] is None
            assert result["last_sign_in"] is None

    def test_user_extraction_preserves_metadata(self):
        """
        Os metadados do usuario (app_metadata e user_metadata) devem ser
        preservados integralmente na resposta.
        """
        app_meta = {"provider": "google", "providers": ["google", "email"]}
        user_meta = {"nome": "Maria", "empresa": "Corp SA", "cargo": "Engenheira"}

        mock_user = MagicMock()
        mock_user.id = "meta-uuid"
        mock_user.email = "meta@teste.com"
        mock_user.email_confirmed_at = "2026-01-01T00:00:00Z"
        mock_user.phone = "+5521988887777"
        mock_user.created_at = "2026-01-01T00:00:00Z"
        mock_user.last_sign_in_at = "2026-02-06T14:00:00Z"
        mock_user.app_metadata = app_meta
        mock_user.user_metadata = user_meta

        mock_response = MagicMock()
        mock_response.user = mock_user

        mock_client = MagicMock(name="supabase_client")
        mock_client.auth.get_user.return_value = mock_response

        with patch("services.supabase_auth._get_supabase_client", return_value=mock_client):
            from services.supabase_auth import verify_supabase_token

            result = verify_supabase_token("meta-token")

            assert result["app_metadata"] == app_meta
            assert result["user_metadata"] == user_meta
            assert result["phone"] == "+5521988887777"
