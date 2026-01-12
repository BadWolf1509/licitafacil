"""
Interface base para estratégias de extração de texto.

Define o contrato que todos os extractors devem implementar,
permitindo fácil adição de novos métodos de extração.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional
from enum import Enum


class ExtractionMethod(str, Enum):
    """Métodos de extração disponíveis."""
    NATIVE_TEXT = "native_text"
    LOCAL_OCR = "local_ocr"
    CLOUD_OCR = "cloud_ocr"
    VISION_AI = "vision_ai"


@dataclass
class ExtractionResult:
    """Resultado de uma extração de texto."""
    text: str
    confidence: float
    method: ExtractionMethod
    success: bool = True
    pages_processed: int = 0
    cost_estimate: float = 0.0
    errors: List[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    @property
    def is_usable(self) -> bool:
        """Verifica se o resultado é utilizável."""
        return self.success and len(self.text.strip()) > 100 and self.confidence > 0.5


class BaseExtractor(ABC):
    """
    Interface abstrata para estratégias de extração.

    Cada implementação encapsula um método específico de extração
    (PDF nativo, OCR local, OCR cloud, Vision AI).
    """

    @property
    @abstractmethod
    def method(self) -> ExtractionMethod:
        """Retorna o método de extração."""
        pass

    @property
    @abstractmethod
    def is_available(self) -> bool:
        """Verifica se o extractor está disponível/configurado."""
        pass

    @property
    def cost_per_page(self) -> float:
        """Custo estimado por página (em R$). Padrão: 0 (gratuito)."""
        return 0.0

    @abstractmethod
    def extract(
        self,
        file_path: str,
        progress_callback: Optional[callable] = None,
        cancel_check: Optional[callable] = None
    ) -> ExtractionResult:
        """
        Extrai texto do documento.

        Args:
            file_path: Caminho para o arquivo
            progress_callback: Callback para progresso (current, total, message)
            cancel_check: Função que retorna True para cancelar

        Returns:
            ExtractionResult com texto e metadados
        """
        pass

    def extract_from_images(
        self,
        images: List[bytes],
        progress_callback: Optional[callable] = None,
        cancel_check: Optional[callable] = None
    ) -> ExtractionResult:
        """
        Extrai texto de lista de imagens.

        Implementação opcional - nem todos os extractors suportam.

        Args:
            images: Lista de imagens em bytes
            progress_callback: Callback para progresso
            cancel_check: Função de cancelamento

        Returns:
            ExtractionResult com texto e metadados
        """
        return ExtractionResult(
            text="",
            confidence=0.0,
            method=self.method,
            success=False,
            errors=["Este extractor não suporta extração de imagens"]
        )

    def get_info(self) -> dict:
        """Retorna informações sobre o extractor."""
        return {
            "method": self.method.value,
            "available": self.is_available,
            "cost_per_page": self.cost_per_page
        }
