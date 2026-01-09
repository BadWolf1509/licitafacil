"""
Pipeline de extração em cascata para documentos.
Otimiza custo-benefício usando a ferramenta mais barata que funcione para cada documento.

Níveis:
1. NATIVE_TEXT: pdfplumber para PDFs nativos (GRÁTIS)
2. LOCAL_OCR: EasyOCR com pré-processamento (GRÁTIS)
3. CLOUD_OCR: Azure Document Intelligence (~R$0.01/página)
4. VISION_AI: GPT-4o Vision (~R$0.10/página)
"""

import time
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from pathlib import Path
from enum import Enum

import pdfplumber
import fitz  # PyMuPDF

from .quality_detector import (
    quality_detector,
    QualityReport,
    ExtractionPipeline
)
from .image_preprocessor import image_preprocessor
from .ocr_service import ocr_service
from .azure_document_service import azure_document_service
from .ai_analyzer import ai_analyzer
from .ai_provider import ai_provider
from exceptions import (
    ProcessingCancelledError,
    AzureNotConfiguredError,
    AINotConfiguredError
)
from .text_utils import is_garbage_text
from config import PipelineConfig, OCRConfig


class PipelineStage(Enum):
    """Estágios do pipeline."""
    QUALITY_CHECK = "quality_check"
    NATIVE_EXTRACTION = "native_extraction"
    PREPROCESSING = "preprocessing"
    LOCAL_OCR = "local_ocr"
    CLOUD_OCR = "cloud_ocr"
    VISION_AI = "vision_ai"
    AI_ANALYSIS = "ai_analysis"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class PipelineResult:
    """Resultado do pipeline de extração."""
    success: bool
    text: str
    data: Dict[str, Any]
    pipeline_used: ExtractionPipeline
    stages_executed: List[str]
    quality_report: Optional[QualityReport]
    processing_time: float
    cost_estimate: float
    errors: List[str] = field(default_factory=list)
    debug_info: Dict[str, Any] = field(default_factory=dict)


class CascadePipeline:
    """
    Pipeline de extração em cascata.

    Tenta métodos mais baratos primeiro e escala para mais caros
    apenas quando necessário.
    """

    # Configurações carregadas de config.py (podem ser sobrescritas via env vars)
    MIN_CONFIDENCE_LOCAL_OCR = PipelineConfig.MIN_CONFIDENCE_LOCAL_OCR
    MIN_CONFIDENCE_CLOUD_OCR = PipelineConfig.MIN_CONFIDENCE_CLOUD_OCR
    MIN_TEXT_LENGTH = OCRConfig.MIN_TEXT_LENGTH

    def __init__(self):
        self._force_pipeline: Optional[ExtractionPipeline] = None
        self._enable_preprocessing = True
        self._enable_azure = True
        self._enable_vision = True

    def configure(
        self,
        force_pipeline: Optional[ExtractionPipeline] = None,
        enable_preprocessing: bool = True,
        enable_azure: bool = True,
        enable_vision: bool = True
    ):
        """
        Configura o comportamento do pipeline.

        Args:
            force_pipeline: Forçar uso de um pipeline específico
            enable_preprocessing: Habilitar pré-processamento de imagem
            enable_azure: Habilitar fallback para Azure
            enable_vision: Habilitar fallback para GPT-4o Vision
        """
        self._force_pipeline = force_pipeline
        self._enable_preprocessing = enable_preprocessing
        self._enable_azure = enable_azure and azure_document_service.is_configured
        self._enable_vision = enable_vision and ai_analyzer.is_configured

    def process(
        self,
        file_path: str,
        progress_callback: Optional[Callable] = None,
        cancel_check: Optional[Callable] = None
    ) -> PipelineResult:
        """
        Processa documento usando pipeline em cascata.

        Args:
            file_path: Caminho para o arquivo
            progress_callback: Callback para progresso (current, total, stage, message)
            cancel_check: Função que retorna True para cancelar

        Returns:
            PipelineResult com dados extraídos
        """
        start_time = time.time()
        stages_executed = []
        errors: List[str] = []
        debug_info: Dict[str, Any] = {}
        text = ""
        data = {}

        def notify(current: int, total: int, stage: str, message: str):
            if progress_callback:
                progress_callback(current, total, stage, message)

        def check_cancel():
            if cancel_check and cancel_check():
                raise ProcessingCancelledError()

        try:
            # Estágio 1: Análise de qualidade
            notify(1, 5, "quality", "Analisando qualidade do documento...")
            check_cancel()
            stages_executed.append(PipelineStage.QUALITY_CHECK.value)

            quality_report = quality_detector.analyze_document(file_path)
            debug_info['quality_report'] = {
                'quality': quality_report.quality.value,
                'recommended_pipeline': quality_report.recommended_pipeline.value,
                'confidence': quality_report.confidence,
                'summary': quality_report.summary
            }

            # Determinar pipeline a usar
            if self._force_pipeline:
                pipeline = self._force_pipeline
            else:
                pipeline = quality_report.recommended_pipeline

            # Estágio 2: Extração baseada no pipeline escolhido
            notify(2, 5, "extraction", f"Extraindo texto ({pipeline.value})...")
            check_cancel()

            if pipeline == ExtractionPipeline.NATIVE_TEXT:
                text, extraction_ok = self._extract_native(file_path)
                stages_executed.append(PipelineStage.NATIVE_EXTRACTION.value)

                if not extraction_ok:
                    # Fallback para OCR local
                    pipeline = ExtractionPipeline.LOCAL_OCR

            if pipeline == ExtractionPipeline.LOCAL_OCR:
                notify(3, 5, "ocr", "Aplicando OCR local...")
                check_cancel()

                text, ocr_confidence = self._extract_local_ocr(
                    file_path,
                    use_preprocessing=self._enable_preprocessing,
                    progress_callback=progress_callback,
                    cancel_check=cancel_check
                )
                stages_executed.append(PipelineStage.LOCAL_OCR.value)
                debug_info['ocr_confidence'] = ocr_confidence

                # Verificar se OCR local foi suficiente
                if ocr_confidence < self.MIN_CONFIDENCE_LOCAL_OCR and self._enable_azure:
                    pipeline = ExtractionPipeline.CLOUD_OCR

            if pipeline == ExtractionPipeline.CLOUD_OCR:
                notify(3, 5, "cloud_ocr", "Usando OCR na nuvem (Azure)...")
                check_cancel()

                text, cloud_confidence = self._extract_cloud_ocr(file_path)
                stages_executed.append(PipelineStage.CLOUD_OCR.value)
                debug_info['cloud_confidence'] = cloud_confidence

                # Verificar se Azure foi suficiente
                if cloud_confidence < self.MIN_CONFIDENCE_CLOUD_OCR and self._enable_vision:
                    pipeline = ExtractionPipeline.VISION_AI

            if pipeline == ExtractionPipeline.VISION_AI:
                notify(4, 5, "vision", "Usando GPT-4o Vision...")
                check_cancel()

                data = self._extract_vision(
                    file_path,
                    progress_callback=progress_callback,
                    cancel_check=cancel_check
                )
                stages_executed.append(PipelineStage.VISION_AI.value)
                text = data.get('texto_extraido', '')

            # Estágio 3: Análise com IA (se temos texto mas não dados estruturados)
            if text and not data.get('servicos'):
                notify(5, 5, "analysis", "Analisando com IA...")
                check_cancel()
                stages_executed.append(PipelineStage.AI_ANALYSIS.value)

                data = self._analyze_with_ai(text)

            # Calcular custo
            num_pages = quality_report.summary.get('total_pages', 1)
            cost = quality_detector.get_cost_estimate(pipeline, num_pages)

            stages_executed.append(PipelineStage.COMPLETED.value)

            return PipelineResult(
                success=True,
                text=text,
                data=data,
                pipeline_used=pipeline,
                stages_executed=stages_executed,
                quality_report=quality_report,
                processing_time=time.time() - start_time,
                cost_estimate=cost['total_cost_brl'],
                errors=errors,
                debug_info=debug_info
            )

        except Exception as e:
            stages_executed.append(PipelineStage.FAILED.value)
            errors.append(str(e))

            return PipelineResult(
                success=False,
                text=text,
                data=data,
                pipeline_used=pipeline if 'pipeline' in dir() else ExtractionPipeline.NATIVE_TEXT,
                stages_executed=stages_executed,
                quality_report=quality_report if 'quality_report' in dir() else None,
                processing_time=time.time() - start_time,
                cost_estimate=0,
                errors=errors,
                debug_info=debug_info
            )

    def _extract_native(self, file_path: str) -> tuple[str, bool]:
        """
        Extrai texto nativo de PDF usando pdfplumber.

        Returns:
            Tuple de (texto, sucesso)
        """
        try:
            text_parts = []
            with pdfplumber.open(file_path) as pdf:
                for i, page in enumerate(pdf.pages):
                    page_text = page.extract_text() or ""
                    if page_text.strip():
                        text_parts.append(f"--- Página {i+1} ---\n{page_text}")

            text = "\n\n".join(text_parts)

            # Verificar se texto é válido (não é lixo)
            if len(text) < self.MIN_TEXT_LENGTH:
                return text, False

            if is_garbage_text(text):
                return text, False

            return text, True

        except Exception as e:
            return f"Erro na extração nativa: {e}", False

    def _extract_local_ocr(
        self,
        file_path: str,
        use_preprocessing: bool = True,
        progress_callback: Optional[Callable] = None,
        cancel_check: Optional[Callable] = None
    ) -> tuple[str, float]:
        """
        Extrai texto usando OCR local (EasyOCR).

        Returns:
            Tuple de (texto, confiança)
        """
        path = Path(file_path)
        ext = path.suffix.lower()

        images = []
        if ext == '.pdf':
            # Converter PDF para imagens
            doc = fitz.open(file_path)
            zoom = 300 / 72  # 300 DPI
            matrix = fitz.Matrix(zoom, zoom)

            for page in doc:
                pix = page.get_pixmap(matrix=matrix)
                images.append(pix.tobytes("png"))

            doc.close()
        else:
            # Ler imagem diretamente
            with open(file_path, 'rb') as f:
                images.append(f.read())

        # Aplicar pré-processamento se habilitado
        if use_preprocessing:
            preprocessed = []
            for img_bytes in images:
                try:
                    processed = image_preprocessor.preprocess(
                        img_bytes,
                        deskew=True,
                        denoise=True,
                        enhance_contrast=True
                    )
                    preprocessed.append(processed)
                except Exception:
                    preprocessed.append(img_bytes)
            images = preprocessed

        # Aplicar OCR
        text_parts = []
        total_confidence: float = 0.0
        num_words = 0

        for i, img_bytes in enumerate(images):
            if cancel_check and cancel_check():
                raise ProcessingCancelledError()

            if progress_callback:
                progress_callback(i + 1, len(images), "ocr", f"OCR página {i+1}/{len(images)}")

            try:
                # EasyOCR retorna lista de (bbox, text, confidence)
                result = ocr_service.extract_text_from_bytes(img_bytes)

                if isinstance(result, tuple):
                    page_text, page_confidence = result
                else:
                    page_text = result
                    page_confidence = 0.8  # Estimativa padrão

                if page_text.strip():
                    text_parts.append(f"--- Página {i+1} ---\n{page_text}")
                    total_confidence += page_confidence
                    num_words += 1

            except Exception as e:
                text_parts.append(f"--- Página {i+1} ---\n[Erro OCR: {e}]")

        text = "\n\n".join(text_parts)
        avg_confidence = total_confidence / num_words if num_words > 0 else 0

        return text, avg_confidence

    def _extract_cloud_ocr(self, file_path: str) -> tuple[str, float]:
        """
        Extrai texto usando Azure Document Intelligence.

        Returns:
            Tuple de (texto, confiança)
        """
        if not azure_document_service.is_configured:
            raise AzureNotConfiguredError()

        result = azure_document_service.extract_text_from_file(file_path)
        return result.text, result.confidence

    def _extract_vision(
        self,
        file_path: str,
        progress_callback: Optional[Callable] = None,
        cancel_check: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """
        Extrai dados usando GPT-4o Vision.

        Returns:
            Dicionário com dados estruturados
        """
        if not ai_analyzer.is_configured:
            raise AINotConfiguredError("OpenAI")

        path = Path(file_path)
        ext = path.suffix.lower()

        # Converter para imagens
        images = []
        if ext == '.pdf':
            doc = fitz.open(file_path)
            zoom = 200 / 72  # 200 DPI (menor que OCR para economizar tokens)
            matrix = fitz.Matrix(zoom, zoom)

            for i, page in enumerate(doc):
                if cancel_check and cancel_check():
                    raise ProcessingCancelledError()

                if progress_callback:
                    progress_callback(i + 1, len(doc), "vision", f"Preparando página {i+1}")

                pix = page.get_pixmap(matrix=matrix)
                images.append(pix.tobytes("png"))

            doc.close()
        else:
            with open(file_path, 'rb') as f:
                images.append(f.read())

        # Chamar GPT-4o Vision
        return ai_analyzer.extract_atestado_from_images(images)

    def _analyze_with_ai(self, text: str) -> Dict[str, Any]:
        """
        Analisa texto extraído com IA (GPT-4o-mini).

        Returns:
            Dicionário com dados estruturados
        """
        if not ai_provider.is_configured:
            # Fallback: retornar texto sem análise
            return {
                'descricao_servico': text[:500] if text else None,
                'texto_extraido': text,
                'servicos': []
            }

        data = ai_analyzer.extract_atestado_info(text)
        data['texto_extraido'] = text
        return data

    def get_status(self) -> Dict[str, Any]:
        """Retorna status do pipeline e serviços disponíveis."""
        return {
            'preprocessing_enabled': self._enable_preprocessing,
            'services': {
                'pdfplumber': True,
                'easyocr': ocr_service.is_available if hasattr(ocr_service, 'is_available') else True,
                'azure': azure_document_service.is_configured,
                'openai_vision': ai_analyzer.is_configured,
                'openai_text': ai_provider.is_configured
            },
            'costs': {
                'native_text': 0.002,
                'local_ocr': 0.002,
                'cloud_ocr': 0.011,
                'vision_ai': 0.10
            }
        }


# Instância singleton
cascade_pipeline = CascadePipeline()
