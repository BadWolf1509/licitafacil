"""
Serviço de detecção de qualidade de documentos.
Analisa PDFs e imagens para determinar o melhor pipeline de extração.
"""

from typing import Dict, Any, List
from pathlib import Path
from enum import Enum
from dataclasses import dataclass

import pdfplumber
import fitz  # PyMuPDF

from .image_preprocessor import image_preprocessor
from text_utils import is_garbage_text


class DocumentQuality(Enum):
    """Níveis de qualidade do documento."""
    NATIVE = "native"        # PDF nativo com texto selecionável
    EASY = "easy"            # Escaneado com boa qualidade
    MEDIUM = "medium"        # Escaneado com qualidade média
    HARD = "hard"            # Escaneado com baixa qualidade
    VERY_HARD = "very_hard"  # Muito degradado, manuscrito, etc.


class ExtractionPipeline(Enum):
    """Pipelines de extração disponíveis."""
    NATIVE_TEXT = "native_text"      # pdfplumber direto
    LOCAL_OCR = "local_ocr"          # EasyOCR local
    CLOUD_OCR = "cloud_ocr"          # Azure Document Intelligence
    VISION_AI = "vision_ai"          # GPT-4o Vision


@dataclass
class QualityReport:
    """Relatório de qualidade do documento."""
    quality: DocumentQuality
    recommended_pipeline: ExtractionPipeline
    confidence: float  # 0-100
    pages_analysis: List[Dict[str, Any]]
    summary: Dict[str, Any]
    estimated_cost: float  # Em reais


class QualityDetector:
    """Detector de qualidade de documentos."""

    # Limites para classificação
    MIN_TEXT_PER_PAGE = 200  # Caracteres mínimos para considerar texto nativo
    MIN_NATIVE_PAGES_RATIO = 0.7  # 70% das páginas devem ter texto
    QUALITY_THRESHOLD_EASY = 75
    QUALITY_THRESHOLD_MEDIUM = 55
    QUALITY_THRESHOLD_HARD = 35

    # Custos estimados por página (em reais)
    COST_PER_PAGE = {
        ExtractionPipeline.NATIVE_TEXT: 0.002,  # Só GPT-4o-mini
        ExtractionPipeline.LOCAL_OCR: 0.002,    # EasyOCR + GPT-4o-mini
        ExtractionPipeline.CLOUD_OCR: 0.011,    # Azure + GPT-4o-mini
        ExtractionPipeline.VISION_AI: 0.10,     # GPT-4o Vision
    }

    def analyze_document(self, file_path: str) -> QualityReport:
        """
        Analisa um documento e retorna relatório de qualidade.

        Args:
            file_path: Caminho para o arquivo (PDF ou imagem)

        Returns:
            QualityReport com análise completa
        """
        path = Path(file_path)
        extension = path.suffix.lower()

        if extension == '.pdf':
            return self._analyze_pdf(file_path)
        elif extension in ['.png', '.jpg', '.jpeg', '.tiff', '.bmp']:
            return self._analyze_image(file_path)
        else:
            raise ValueError(f"Formato não suportado: {extension}")

    def _analyze_pdf(self, file_path: str) -> QualityReport:
        """Analisa um documento PDF."""
        pages_analysis = []
        native_text_pages = 0
        total_pages = 0

        # Fase 1: Verificar texto nativo com pdfplumber
        try:
            with pdfplumber.open(file_path) as pdf:
                total_pages = len(pdf.pages)

                for i, page in enumerate(pdf.pages):
                    text = page.extract_text() or ""
                    text_length = len(text.strip())

                    page_info: Dict[str, Any] = {
                        'page_number': i + 1,
                        'has_native_text': text_length >= self.MIN_TEXT_PER_PAGE,
                        'text_length': text_length,
                        'is_garbage': is_garbage_text(text),
                        'quality_score': None,
                        'quality_metrics': None
                    }

                    if page_info['has_native_text'] and not page_info['is_garbage']:
                        native_text_pages += 1
                    else:
                        # Fase 2: Analisar qualidade da imagem
                        image_metrics = self._analyze_page_as_image(file_path, i)
                        page_info['quality_score'] = image_metrics.get('quality_score', 0)
                        page_info['quality_metrics'] = image_metrics

                    pages_analysis.append(page_info)

        except Exception as e:
            raise Exception(f"Erro ao analisar PDF: {str(e)}")

        # Determinar qualidade geral e pipeline recomendado
        return self._generate_report(pages_analysis, native_text_pages, total_pages)

    def _analyze_image(self, file_path: str) -> QualityReport:
        """Analisa uma imagem única."""
        with open(file_path, 'rb') as f:
            image_bytes = f.read()

        metrics = image_preprocessor.analyze_quality(image_bytes)

        page_info: Dict[str, Any] = {
            'page_number': 1,
            'has_native_text': False,
            'text_length': 0,
            'is_garbage': False,
            'quality_score': metrics['quality_score'],
            'quality_metrics': metrics
        }

        return self._generate_report([page_info], 0, 1)

    def _analyze_page_as_image(self, pdf_path: str, page_index: int) -> Dict[str, Any]:
        """Renderiza página como imagem e analisa qualidade."""
        try:
            doc = fitz.open(pdf_path)
            page = doc[page_index]

            # Renderizar a 150 DPI para análise (mais rápido)
            zoom = 150 / 72
            matrix = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=matrix)
            image_bytes = pix.tobytes("png")

            doc.close()

            # Analisar qualidade da imagem
            return image_preprocessor.analyze_quality(image_bytes)

        except Exception as e:
            return {
                'quality_score': 0,
                'error': str(e)
            }

    def _generate_report(
        self,
        pages_analysis: List[Dict[str, Any]],
        native_text_pages: int,
        total_pages: int
    ) -> QualityReport:
        """Gera relatório final de qualidade."""

        # Calcular métricas agregadas
        native_ratio = native_text_pages / total_pages if total_pages > 0 else 0

        # Páginas que precisam de processamento de imagem
        image_pages = [p for p in pages_analysis if not p['has_native_text'] or p['is_garbage']]
        image_quality_scores = [p['quality_score'] for p in image_pages if p.get('quality_score')]

        avg_image_quality = (
            sum(image_quality_scores) / len(image_quality_scores)
            if image_quality_scores else 0
        )

        # Determinar qualidade geral
        if native_ratio >= self.MIN_NATIVE_PAGES_RATIO:
            quality = DocumentQuality.NATIVE
            pipeline = ExtractionPipeline.NATIVE_TEXT
            confidence = native_ratio * 100

        elif avg_image_quality >= self.QUALITY_THRESHOLD_EASY:
            quality = DocumentQuality.EASY
            pipeline = ExtractionPipeline.LOCAL_OCR
            confidence = avg_image_quality

        elif avg_image_quality >= self.QUALITY_THRESHOLD_MEDIUM:
            quality = DocumentQuality.MEDIUM
            pipeline = ExtractionPipeline.LOCAL_OCR
            confidence = avg_image_quality

        elif avg_image_quality >= self.QUALITY_THRESHOLD_HARD:
            quality = DocumentQuality.HARD
            pipeline = ExtractionPipeline.CLOUD_OCR
            confidence = avg_image_quality

        else:
            quality = DocumentQuality.VERY_HARD
            pipeline = ExtractionPipeline.VISION_AI
            confidence = max(20, avg_image_quality)

        # Calcular custo estimado
        estimated_cost = self.COST_PER_PAGE[pipeline] * total_pages

        summary = {
            'total_pages': total_pages,
            'native_text_pages': native_text_pages,
            'native_ratio': round(native_ratio * 100, 1),
            'image_pages': len(image_pages),
            'avg_image_quality': round(avg_image_quality, 1),
            'min_image_quality': min(image_quality_scores) if image_quality_scores else None,
            'max_image_quality': max(image_quality_scores) if image_quality_scores else None,
        }

        return QualityReport(
            quality=quality,
            recommended_pipeline=pipeline,
            confidence=round(confidence, 1),
            pages_analysis=pages_analysis,
            summary=summary,
            estimated_cost=round(estimated_cost, 4)
        )

    def get_pipeline_for_quality(self, quality: DocumentQuality) -> ExtractionPipeline:
        """Retorna o pipeline recomendado para um nível de qualidade."""
        mapping = {
            DocumentQuality.NATIVE: ExtractionPipeline.NATIVE_TEXT,
            DocumentQuality.EASY: ExtractionPipeline.LOCAL_OCR,
            DocumentQuality.MEDIUM: ExtractionPipeline.LOCAL_OCR,
            DocumentQuality.HARD: ExtractionPipeline.CLOUD_OCR,
            DocumentQuality.VERY_HARD: ExtractionPipeline.VISION_AI,
        }
        return mapping[quality]

    def should_use_preprocessing(self, quality: DocumentQuality) -> bool:
        """Verifica se deve usar pré-processamento de imagem."""
        return quality in [
            DocumentQuality.MEDIUM,
            DocumentQuality.HARD,
            DocumentQuality.VERY_HARD
        ]

    def get_cost_estimate(
        self,
        pipeline: ExtractionPipeline,
        num_pages: int
    ) -> Dict[str, Any]:
        """Retorna estimativa de custo detalhada."""
        base_cost = self.COST_PER_PAGE[pipeline] * num_pages

        return {
            'pipeline': pipeline.value,
            'num_pages': num_pages,
            'cost_per_page': self.COST_PER_PAGE[pipeline],
            'total_cost_brl': round(base_cost, 4),
            'total_cost_usd': round(base_cost / 5.0, 4),  # Estimativa USD
        }


# Instância singleton
quality_detector = QualityDetector()
