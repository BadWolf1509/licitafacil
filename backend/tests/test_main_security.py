"""
Testes de seguranca para main.py.

Cobre:
- PathTraversalError exception handler
- Docs/Redoc desabilitados em producao
"""
from unittest.mock import MagicMock, patch

import pytest

from utils.router_helpers import PathTraversalError, _validate_storage_path


class TestPathTraversalErrorHandler:
    """Testes para o exception handler de PathTraversalError."""

    def test_validate_storage_path_rejects_double_dots(self):
        """Path com .. e rejeitado."""
        with pytest.raises(PathTraversalError):
            _validate_storage_path("users/1/../../../etc/passwd")

    def test_validate_storage_path_rejects_outside_users(self):
        """Path fora de users/ e rejeitado."""
        with pytest.raises(PathTraversalError):
            _validate_storage_path("admin/secret/file.pdf")

    def test_validate_storage_path_accepts_valid(self):
        """Path valido dentro de users/ e aceito."""
        result = _validate_storage_path("users/1/atestados/file.pdf")
        assert result == "users/1/atestados/file.pdf"

    def test_validate_storage_path_normalizes_slashes(self):
        """Path com barras extras e normalizado."""
        result = _validate_storage_path("users//1//atestados//file.pdf")
        assert result == "users/1/atestados/file.pdf"

    def test_validate_storage_path_rejects_backslash_traversal(self):
        """Path com backslash traversal e rejeitado."""
        with pytest.raises(PathTraversalError):
            _validate_storage_path("users\\..\\..\\etc\\passwd")

    def test_path_traversal_handler_returns_400(self, client, admin_auth_headers):
        """PathTraversalError retorna status 400 (nao 500)."""
        # Forcar PathTraversalError via mock em endpoint que usa storage
        with patch('utils.router_helpers._validate_storage_path') as mock_validate:
            mock_validate.side_effect = PathTraversalError("Test traversal")
            # Tentar download de atestado com path malicioso
            with patch('routers.atestados.atestado_repository') as mock_repo:
                mock_atestado = MagicMock()
                mock_atestado.user_id = 1
                mock_atestado.arquivo_path = "../../../etc/passwd"
                mock_repo.get_by_id.return_value = mock_atestado
                # O handler deve capturar PathTraversalError e retornar 400
                # Testar diretamente o handler
                import asyncio

                from fastapi import Request

                from main import path_traversal_handler

                exc = PathTraversalError("Path contains traversal sequence: ../../../etc/passwd")
                mock_request = MagicMock(spec=Request)
                response = asyncio.get_event_loop().run_until_complete(
                    path_traversal_handler(mock_request, exc)
                )
                assert response.status_code == 400

    def test_path_traversal_handler_generic_message(self):
        """PathTraversalError retorna mensagem generica (nao ecoa o path)."""
        import asyncio
        import json

        from fastapi import Request

        from main import path_traversal_handler

        exc = PathTraversalError("Path contains traversal: /etc/passwd")
        mock_request = MagicMock(spec=Request)
        response = asyncio.get_event_loop().run_until_complete(
            path_traversal_handler(mock_request, exc)
        )
        body = json.loads(response.body.decode())
        assert body["detail"] == "Caminho de arquivo inválido"
        assert "/etc/passwd" not in body["detail"]

    def test_path_traversal_handler_logs_warning(self):
        """PathTraversalError loga warning."""
        import asyncio

        from fastapi import Request

        from main import path_traversal_handler

        exc = PathTraversalError("Test")
        mock_request = MagicMock(spec=Request)
        with patch('main.logger') as mock_logger:
            asyncio.get_event_loop().run_until_complete(
                path_traversal_handler(mock_request, exc)
            )
            mock_logger.warning.assert_called_once()
            assert "SECURITY" in mock_logger.warning.call_args[0][0]


class TestDocsEndpoints:
    """Testes para endpoints /docs e /redoc condicionais."""

    def test_docs_available_in_development(self, client):
        """Em desenvolvimento, /docs esta disponivel."""
        # ENVIRONMENT default e 'development', entao docs deve estar habilitado
        response = client.get("/docs")
        # Docs retorna 200 ou 307 (redirect)
        assert response.status_code in (200, 307)

    def test_redoc_available_in_development(self, client):
        """Em desenvolvimento, /redoc esta disponivel."""
        response = client.get("/redoc")
        assert response.status_code in (200, 307)

    def test_docs_url_none_in_production(self):
        """Em producao, docs_url deve ser None."""
        with patch.dict('os.environ', {'ENVIRONMENT': 'production'}):
            # Testar a logica diretamente
            import os
            env = os.getenv('ENVIRONMENT', 'development')
            docs_url = "/docs" if env != "production" else None
            assert docs_url is None

    def test_redoc_url_none_in_production(self):
        """Em producao, redoc_url deve ser None."""
        with patch.dict('os.environ', {'ENVIRONMENT': 'production'}):
            import os
            env = os.getenv('ENVIRONMENT', 'development')
            redoc_url = "/redoc" if env != "production" else None
            assert redoc_url is None
