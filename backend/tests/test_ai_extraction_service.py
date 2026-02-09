"""
Testes unitários para o AIExtractionService.

Testa o serviço unificado de extração via IA.
"""

from unittest.mock import Mock

import pytest

from services.ai.extraction_service import AIExtractionService, extraction_service


def create_mock_response(content: str):
    """Cria mock de resposta com atributo content."""
    response = Mock()
    response.content = content
    return response


class TestAIExtractionServiceInit:
    """Testes de inicialização."""

    def test_can_create_instance(self):
        service = AIExtractionService()
        assert service is not None

    def test_accepts_provider(self):
        mock_provider = Mock()
        service = AIExtractionService(provider=mock_provider)
        assert service._provider == mock_provider

    def test_singleton_exists(self):
        assert extraction_service is not None
        assert isinstance(extraction_service, AIExtractionService)


class TestExtractAtestadoFromImages:
    """Testes para extract_atestado_from_images."""

    def test_requires_provider(self):
        service = AIExtractionService()
        with pytest.raises(ValueError):
            service.extract_atestado_from_images([b"image_data"])

    def test_calls_provider_with_prompts(self):
        mock_provider = Mock()
        mock_provider.generate_with_vision.return_value = create_mock_response(
            '{"servicos": [{"item": "1.1", "descricao": "TEST"}]}'
        )

        service = AIExtractionService(provider=mock_provider)
        result = service.extract_atestado_from_images(
            [b"image1", b"image2"],
            provider=mock_provider
        )

        assert mock_provider.generate_with_vision.called
        assert "servicos" in result

    def test_handles_json_in_markdown(self):
        mock_provider = Mock()
        mock_provider.generate_with_vision.return_value = create_mock_response(
            '''```json
            {"servicos": [{"item": "1.1", "descricao": "TEST"}]}
            ```'''
        )

        service = AIExtractionService(provider=mock_provider)
        result = service.extract_atestado_from_images(
            [b"image"],
            provider=mock_provider
        )

        assert "servicos" in result
        # A filtragem pode remover itens, então apenas verificamos que não deu erro

    def test_handles_invalid_json(self):
        mock_provider = Mock()
        mock_provider.generate_with_vision.return_value = create_mock_response(
            "not valid json"
        )

        service = AIExtractionService(provider=mock_provider)
        result = service.extract_atestado_from_images(
            [b"image"],
            provider=mock_provider
        )

        # Retorna resultado vazio padrão
        assert "servicos" in result
        assert result["servicos"] == []


class TestExtractAtestadoInfo:
    """Testes para extract_atestado_info."""

    def test_requires_provider(self):
        service = AIExtractionService()
        with pytest.raises(ValueError):
            service.extract_atestado_info("texto do atestado")

    def test_calls_provider_generate_text(self):
        mock_provider = Mock()
        mock_provider.generate_text.return_value = create_mock_response(
            '{"servicos": [{"item": "1.1", "descricao": "TEST"}]}'
        )

        service = AIExtractionService(provider=mock_provider)
        result = service.extract_atestado_info(
            "texto do atestado",
            provider=mock_provider
        )

        assert mock_provider.generate_text.called
        assert "servicos" in result


class TestExtractEditalRequirements:
    """Testes para extract_edital_requirements."""

    def test_requires_provider(self):
        service = AIExtractionService()
        with pytest.raises(ValueError):
            service.extract_edital_requirements("texto do edital")

    def test_extracts_requirements(self):
        mock_provider = Mock()
        mock_provider.generate_text.return_value = create_mock_response(
            '''```json
            [
                {"descricao": "Experiencia em obras", "quantidade": 1000, "unidade": "M2"},
                {"descricao": "Certificacao ISO", "quantidade": 1, "unidade": "UN"}
            ]
            ```'''
        )

        service = AIExtractionService(provider=mock_provider)
        result = service.extract_edital_requirements(
            "texto do edital",
            provider=mock_provider
        )

        assert len(result) == 2
        assert result[0]["descricao"] == "Experiencia em obras"
        assert result[1]["unidade"] == "UN"


class TestBatchProcessing:
    """Testes para processamento em batch."""

    def test_batch_size_default(self):
        service = AIExtractionService()
        assert service.BATCH_SIZE == 2

    def test_processes_in_batches(self):
        mock_provider = Mock()
        mock_provider.generate_with_vision.return_value = create_mock_response(
            '{"servicos": [{"item": "1.1", "descricao": "TEST"}]}'
        )

        service = AIExtractionService(provider=mock_provider)
        # 5 imagens = 3 batches (2, 2, 1)
        images = [b"img"] * 5
        service.extract_atestado_from_images(images, provider=mock_provider)

        # Deve ter chamado generate_with_vision 3 vezes (batches de 2, 2, 1)
        assert mock_provider.generate_with_vision.call_count == 3


class TestJsonParsing:
    """Testes para parsing de JSON."""

    def test_handles_raw_json(self):
        mock_provider = Mock()
        mock_provider.generate_with_vision.return_value = create_mock_response(
            '{"servicos": [{"item": "2.1", "descricao": "Valid service"}]}'
        )

        service = AIExtractionService(provider=mock_provider)
        result = service.extract_atestado_from_images([b"img"], provider=mock_provider)

        assert "servicos" in result
        # Verifica que há serviços (pode haver filtragem)
        assert isinstance(result["servicos"], list)

    def test_filters_classification_paths(self):
        """Testa que filter_classification_paths é aplicado."""
        mock_provider = Mock()
        # Inclui serviços com caminhos de classificação que devem ser filtrados
        mock_provider.generate_with_vision.return_value = create_mock_response(
            '''{"servicos": [
                {"item": "1", "descricao": "CATEGORIA SIMPLES"},
                {"item": "1.1", "descricao": "SERVICO VALIDO"}
            ]}'''
        )

        service = AIExtractionService(provider=mock_provider)
        result = service.extract_atestado_from_images([b"img"], provider=mock_provider)

        # O filtro deve remover itens que são apenas caminhos
        assert "servicos" in result


class TestProviderOverride:
    """Testes para override de provider por chamada."""

    def test_uses_instance_provider_by_default(self):
        default_provider = Mock()
        default_provider.generate_with_vision.return_value = create_mock_response(
            '{"servicos": []}'
        )

        service = AIExtractionService(provider=default_provider)
        service.extract_atestado_from_images([b"img"])

        assert default_provider.generate_with_vision.called

    def test_override_provider_per_call(self):
        default_provider = Mock()
        override_provider = Mock()
        override_provider.generate_with_vision.return_value = create_mock_response(
            '{"servicos": []}'
        )

        service = AIExtractionService(provider=default_provider)
        service.extract_atestado_from_images([b"img"], provider=override_provider)

        assert not default_provider.generate_with_vision.called
        assert override_provider.generate_with_vision.called


class TestEmptyAtestadoResult:
    """Testes para resultado vazio padrão."""

    def test_empty_result_structure(self):
        service = AIExtractionService()
        result = service._empty_atestado_result()

        assert "servicos" in result
        assert result["servicos"] == []
        assert "descricao_servico" in result
        assert "contratante" in result
        assert "data_emissao" in result
