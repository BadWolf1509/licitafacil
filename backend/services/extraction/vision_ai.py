"""
Extrator usando GPT-4o Vision.

Utiliza GPT-4o Vision para extrair texto e dados estruturados
diretamente de imagens. Mais caro mas mais preciso para documentos complexos.
"""

from pathlib import Path
from typing import Optional, List, Dict, Any

import fitz  # PyMuPDF

from .base_extractor import BaseExtractor, ExtractionMethod, ExtractionResult
from exceptions import AINotConfiguredError

from logging_config import get_logger
logger = get_logger('services.extraction.vision_ai')


class VisionAIExtractor(BaseExtractor):
    """
    Extrator usando GPT-4o Vision.

    Ideal para documentos muito complexos ou com baixa qualidade
    onde OCR tradicional falha. Retorna dados já estruturados.
    """

    @property
    def method(self) -> ExtractionMethod:
        return ExtractionMethod.VISION_AI

    @property
    def is_available(self) -> bool:
        """Verifica se OpenAI está configurado."""
        from services.ai_analyzer import ai_analyzer
        return ai_analyzer.is_configured

    def _get_analyzer(self):
        """Obtém o ai_analyzer (lazy import para evitar circular)."""
        from services.ai_analyzer import ai_analyzer
        return ai_analyzer

    @property
    def cost_per_page(self) -> float:
        """Custo aproximado por página em R$."""
        return 0.10

    def _convert_pdf_to_images(
        self,
        file_path: str,
        dpi: int = 200  # DPI menor para economizar tokens
    ) -> List[bytes]:
        """
        Converte PDF para lista de imagens.

        Args:
            file_path: Caminho do PDF
            dpi: Resolução em DPI

        Returns:
            Lista de imagens em bytes (PNG)
        """
        images = []
        doc = fitz.open(file_path)
        zoom = dpi / 72
        matrix = fitz.Matrix(zoom, zoom)

        for page in doc:
            pix = page.get_pixmap(matrix=matrix)
            images.append(pix.tobytes("png"))

        doc.close()
        return images

    def extract(
        self,
        file_path: str,
        progress_callback: Optional[callable] = None,
        cancel_check: Optional[callable] = None
    ) -> ExtractionResult:
        """
        Extrai texto e dados usando GPT-4o Vision.

        Args:
            file_path: Caminho para o arquivo
            progress_callback: Callback para progresso
            cancel_check: Função de cancelamento

        Returns:
            ExtractionResult com texto e metadados (incluindo dados estruturados)
        """
        if not self.is_available:
            return ExtractionResult(
                text="",
                confidence=0.0,
                method=self.method,
                success=False,
                errors=["OpenAI não está configurado"]
            )

        try:
            path = Path(file_path)
            ext = path.suffix.lower()

            # Converter para imagens
            if ext == '.pdf':
                if progress_callback:
                    progress_callback(1, 3, "Convertendo PDF para imagens...")

                images = self._convert_pdf_to_images(file_path)
            else:
                with open(file_path, 'rb') as f:
                    images = [f.read()]

            # Verificar cancelamento
            if cancel_check and cancel_check():
                return ExtractionResult(
                    text="",
                    confidence=0.0,
                    method=self.method,
                    success=False,
                    errors=["Processamento cancelado pelo usuário"]
                )

            # Enviar para GPT-4o Vision
            if progress_callback:
                progress_callback(2, 3, "Analisando com GPT-4o Vision...")

            data = self._get_analyzer().extract_atestado_from_images(images)

            # Extrair texto do resultado
            text = data.get('texto_extraido', '')
            if not text:
                # Tentar construir texto a partir dos dados estruturados
                parts = []
                if data.get('contratante'):
                    parts.append(f"Contratante: {data['contratante']}")
                if data.get('contratada'):
                    parts.append(f"Contratada: {data['contratada']}")
                if data.get('objeto'):
                    parts.append(f"Objeto: {data['objeto']}")
                if data.get('servicos'):
                    parts.append("Serviços:")
                    for s in data['servicos']:
                        desc = s.get('descricao', '')
                        qtd = s.get('quantidade', '')
                        un = s.get('unidade', '')
                        parts.append(f"  - {desc} ({qtd} {un})")
                text = "\n".join(parts)

            if progress_callback:
                progress_callback(3, 3, "Análise concluída")

            cost_estimate = len(images) * self.cost_per_page

            return ExtractionResult(
                text=text,
                confidence=0.95,  # GPT-4o Vision tem alta confiança
                method=self.method,
                success=True,
                pages_processed=len(images),
                cost_estimate=cost_estimate,
                metadata={
                    "structured_data": data,
                    "num_servicos": len(data.get('servicos', [])),
                    "has_contratante": bool(data.get('contratante')),
                    "has_contratada": bool(data.get('contratada'))
                }
            )

        except AINotConfiguredError:
            return ExtractionResult(
                text="",
                confidence=0.0,
                method=self.method,
                success=False,
                errors=["OpenAI não está configurado"]
            )
        except Exception as e:
            logger.error(f"Erro no GPT-4o Vision: {e}")
            return ExtractionResult(
                text="",
                confidence=0.0,
                method=self.method,
                success=False,
                errors=[f"Erro no GPT-4o Vision: {str(e)}"]
            )

    def extract_from_images(
        self,
        images: List[bytes],
        progress_callback: Optional[callable] = None,
        cancel_check: Optional[callable] = None
    ) -> ExtractionResult:
        """
        Extrai texto e dados de lista de imagens.

        Args:
            images: Lista de imagens em bytes
            progress_callback: Callback para progresso
            cancel_check: Função de cancelamento

        Returns:
            ExtractionResult com texto e metadados
        """
        if not self.is_available:
            return ExtractionResult(
                text="",
                confidence=0.0,
                method=self.method,
                success=False,
                errors=["OpenAI não está configurado"]
            )

        try:
            if cancel_check and cancel_check():
                return ExtractionResult(
                    text="",
                    confidence=0.0,
                    method=self.method,
                    success=False,
                    errors=["Processamento cancelado"]
                )

            if progress_callback:
                progress_callback(1, 2, "Enviando para GPT-4o Vision...")

            data = self._get_analyzer().extract_atestado_from_images(images)

            if progress_callback:
                progress_callback(2, 2, "Análise concluída")

            text = data.get('texto_extraido', '')
            cost_estimate = len(images) * self.cost_per_page

            return ExtractionResult(
                text=text,
                confidence=0.95,
                method=self.method,
                success=True,
                pages_processed=len(images),
                cost_estimate=cost_estimate,
                metadata={"structured_data": data}
            )

        except Exception as e:
            logger.error(f"Erro no GPT-4o Vision: {e}")
            return ExtractionResult(
                text="",
                confidence=0.0,
                method=self.method,
                success=False,
                errors=[f"Erro no GPT-4o Vision: {str(e)}"]
            )

    def extract_structured_data(
        self,
        images: List[bytes]
    ) -> Dict[str, Any]:
        """
        Extrai dados estruturados diretamente das imagens.

        Este método retorna os dados já parseados pelo GPT-4o Vision,
        útil quando se precisa dos dados estruturados em vez de texto.

        Args:
            images: Lista de imagens em bytes

        Returns:
            Dicionário com dados estruturados do atestado
        """
        if not self.is_available:
            raise AINotConfiguredError("OpenAI")

        return self._get_analyzer().extract_atestado_from_images(images)
