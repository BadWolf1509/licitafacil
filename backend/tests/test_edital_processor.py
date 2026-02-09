"""
Testes para o processador de editais (EditalProcessor).

Testa services/edital_processor.py: extracao de texto de PDF,
fallback OCR para PDFs escaneados, rejeicao de formatos invalidos,
cancelamento e delegacao ao matching_service.

Todos os servicos externos (pdf_extractor, pdf_extraction_service,
matching_service) sao mockados para evitar dependencias reais.
"""
from typing import Any, Optional
from unittest.mock import MagicMock, patch

import pytest

from exceptions import OCRError, TextExtractionError, UnsupportedFileError
from services.edital_processor import EditalProcessor, edital_processor

# === Helpers ===

def _make_extract_result(
    tem_texto: bool = True,
    texto: str = "Texto do edital de licitacao",
    tabelas: Optional[list[Any]] = None,
    paginas: int = 3,
) -> dict:
    """Cria resultado simulado de pdf_extractor.extract_all."""
    return {
        "tem_texto": tem_texto,
        "texto": texto,
        "tabelas": tabelas or [],
        "paginas": paginas,
    }


# === Tests ===


def test_rejects_non_pdf_file():
    """Arquivo nao-PDF deve levantar UnsupportedFileError."""
    processor = EditalProcessor()

    with patch("services.edital_processor.pdf_extraction_service"):
        with pytest.raises(UnsupportedFileError):
            processor.process("/tmp/documento.docx")


def test_rejects_non_pdf_various_extensions():
    """Varias extensoes nao-PDF devem ser rejeitadas."""
    processor = EditalProcessor()

    for ext in [".txt", ".jpg", ".png", ".xlsx", ".doc"]:
        with patch("services.edital_processor.pdf_extraction_service"):
            with pytest.raises(UnsupportedFileError):
                processor.process(f"/tmp/arquivo{ext}")


@patch("services.edital_processor.pdf_extraction_service")
@patch("services.edital_processor.pdf_extractor")
def test_process_pdf_with_text(mock_extractor, mock_extraction_svc):
    """PDF com texto embutido deve extrair texto e retornar resultado correto."""
    mock_extractor.extract_all.return_value = _make_extract_result(
        tem_texto=True,
        texto="Exigencia: 500m de pavimentacao asfaltica",
        paginas=5,
    )

    processor = EditalProcessor()
    result = processor.process("/tmp/edital.pdf")

    assert result["texto_extraido"] == "Exigencia: 500m de pavimentacao asfaltica"
    assert result["tabelas"] == []
    assert result["exigencias"] == []
    assert result["paginas"] == 5
    mock_extractor.extract_all.assert_called_once_with("/tmp/edital.pdf")


@patch("services.edital_processor.pdf_extraction_service")
@patch("services.edital_processor.pdf_extractor")
def test_process_pdf_scanned_falls_back_to_ocr(mock_extractor, mock_extraction_svc):
    """PDF escaneado (sem texto) deve usar OCR como fallback."""
    mock_extractor.extract_all.return_value = _make_extract_result(
        tem_texto=False, texto=""
    )
    mock_extractor.pdf_to_images.return_value = ["img1.png", "img2.png"]
    mock_extraction_svc.ocr_image_list.return_value = "Texto extraido via OCR"

    processor = EditalProcessor()
    progress_cb = MagicMock()
    cancel_ck = MagicMock(return_value=False)

    result = processor.process("/tmp/scan.pdf", progress_cb, cancel_ck)

    assert result["texto_extraido"] == "Texto extraido via OCR"
    mock_extractor.pdf_to_images.assert_called_once_with("/tmp/scan.pdf")
    mock_extraction_svc.ocr_image_list.assert_called_once_with(
        ["img1.png", "img2.png"],
        progress_callback=progress_cb,
        cancel_check=cancel_ck,
    )


@patch("services.edital_processor.pdf_extraction_service")
@patch("services.edital_processor.pdf_extractor")
def test_raises_text_extraction_error_when_no_text(mock_extractor, mock_extraction_svc):
    """Deve levantar TextExtractionError se nenhum texto for extraido."""
    mock_extractor.extract_all.return_value = _make_extract_result(
        tem_texto=True, texto="   "
    )

    processor = EditalProcessor()

    with pytest.raises(TextExtractionError):
        processor.process("/tmp/edital_vazio.pdf")


@patch("services.edital_processor.pdf_extraction_service")
@patch("services.edital_processor.pdf_extractor")
def test_cancel_check_called_before_processing(mock_extractor, mock_extraction_svc):
    """cancel_check deve ser verificado no inicio do processamento."""
    from services.pdf_extraction_service import ProcessingCancelled

    mock_extraction_svc._check_cancel.side_effect = ProcessingCancelled(
        "Processamento cancelado."
    )

    processor = EditalProcessor()
    cancel_ck = MagicMock(return_value=True)

    with pytest.raises(ProcessingCancelled):
        processor.process("/tmp/edital.pdf", cancel_check=cancel_ck)

    mock_extraction_svc._check_cancel.assert_called_once_with(cancel_ck)
    # pdf_extractor nunca deve ser chamado se cancelamento detectado
    mock_extractor.extract_all.assert_not_called()


@patch("services.edital_processor.matching_service")
def test_analyze_qualification_delegates_to_matching_service(mock_matching):
    """analyze_qualification deve delegar ao matching_service.match_exigencias."""
    exigencias = [{"descricao": "500m pavimentacao", "quantidade": 500}]
    atestados = [{"descricao": "600m pavimentacao asfaltica", "quantidade": 600}]
    expected = [{"descricao": "500m pavimentacao", "atendido": True, "atestado_id": 1}]
    mock_matching.match_exigencias.return_value = expected

    processor = EditalProcessor()
    result = processor.analyze_qualification(exigencias, atestados)

    assert result == expected
    mock_matching.match_exigencias.assert_called_once_with(exigencias, atestados)


@patch("services.edital_processor.pdf_extraction_service")
@patch("services.edital_processor.pdf_extractor")
def test_process_pdf_with_tables(mock_extractor, mock_extraction_svc):
    """Tabelas extraidas devem ser incluidas no texto_completo e retornadas."""
    tabelas = [
        [["Item", "Qtd"], ["Pavimentacao", "500"]],
        [["Servico", "Unid"], ["Drenagem", "200"]],
    ]
    mock_extractor.extract_all.return_value = _make_extract_result(
        tem_texto=True,
        texto="Edital com tabelas",
        tabelas=tabelas,
        paginas=2,
    )

    processor = EditalProcessor()
    result = processor.process("/tmp/edital_tabelas.pdf")

    assert result["texto_extraido"] == "Edital com tabelas"
    assert result["tabelas"] == tabelas
    assert result["paginas"] == 2
    # Verifica que progress_callback foi notificado com etapa "final"
    final_calls = [
        c for c in mock_extraction_svc._notify_progress.call_args_list
        if len(c.args) >= 4 and c.args[3] == "final"
    ]
    assert len(final_calls) == 1


@patch("services.edital_processor.pdf_extraction_service")
@patch("services.edital_processor.pdf_extractor")
def test_ocr_error_during_fallback_raises_ocr_error(mock_extractor, mock_extraction_svc):
    """Erro de OCR durante fallback deve ser re-levantado como OCRError."""
    mock_extractor.extract_all.return_value = _make_extract_result(
        tem_texto=False, texto=""
    )
    mock_extractor.pdf_to_images.return_value = ["img.png"]
    mock_extraction_svc.ocr_image_list.side_effect = IOError("Falha no OCR")

    processor = EditalProcessor()

    with pytest.raises(OCRError):
        processor.process("/tmp/scan_ruim.pdf")


def test_singleton_instance_exists():
    """Modulo deve exportar instancia singleton edital_processor."""
    assert isinstance(edital_processor, EditalProcessor)
