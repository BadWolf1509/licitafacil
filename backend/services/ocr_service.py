"""
Serviço de OCR (Reconhecimento Óptico de Caracteres).
Utiliza EasyOCR para extrair texto de imagens e PDFs escaneados.
"""

import easyocr
from typing import List, Optional, Tuple
from pathlib import Path
import io
from PIL import Image
import numpy as np


class OCRService:
    """Serviço de OCR usando EasyOCR."""

    def __init__(self):
        self._reader: Optional[easyocr.Reader] = None
        self._languages = ['pt', 'en']  # Português e inglês

    @property
    def reader(self) -> easyocr.Reader:
        """Inicializa o leitor OCR de forma lazy (sob demanda)."""
        if self._reader is None:
            # gpu=False para compatibilidade (usar True se tiver GPU CUDA)
            self._reader = easyocr.Reader(
                self._languages,
                gpu=False,
                verbose=False
            )
        return self._reader

    def extract_text_from_image(self, image_path: str) -> str:
        """
        Extrai texto de uma imagem.

        Args:
            image_path: Caminho para a imagem

        Returns:
            Texto extraído
        """
        try:
            results = self.reader.readtext(image_path)
            # Concatenar todos os textos detectados
            texts = [result[1] for result in results]
            return " ".join(texts)
        except Exception as e:
            raise Exception(f"Erro no OCR da imagem: {str(e)}")

    def extract_text_from_bytes(self, image_bytes: bytes) -> str:
        """
        Extrai texto de uma imagem em bytes.

        Args:
            image_bytes: Imagem em bytes (PNG, JPG, etc.)

        Returns:
            Texto extraído
        """
        try:
            # Converter bytes para array numpy via PIL
            image = Image.open(io.BytesIO(image_bytes))
            image_array = np.array(image)

            results = self.reader.readtext(image_array)
            texts = [result[1] for result in results]
            return " ".join(texts)
        except Exception as e:
            raise Exception(f"Erro no OCR: {str(e)}")

    def extract_with_confidence(
        self,
        image_path: str,
        min_confidence: float = 0.5
    ) -> List[Tuple[str, float]]:
        """
        Extrai texto com níveis de confiança.

        Args:
            image_path: Caminho para a imagem
            min_confidence: Confiança mínima para incluir (0-1)

        Returns:
            Lista de tuplas (texto, confiança)
        """
        try:
            results = self.reader.readtext(image_path)
            filtered = [
                (result[1], result[2])
                for result in results
                if result[2] >= min_confidence
            ]
            return filtered
        except Exception as e:
            raise Exception(f"Erro no OCR: {str(e)}")

    def extract_from_pdf_images(self, image_list: List[bytes]) -> str:
        """
        Extrai texto de múltiplas imagens (páginas de PDF).

        Args:
            image_list: Lista de imagens em bytes

        Returns:
            Texto completo concatenado
        """
        all_texts = []

        for i, image_bytes in enumerate(image_list):
            try:
                page_text = self.extract_text_from_bytes(image_bytes)
                if page_text.strip():
                    all_texts.append(f"--- Página {i + 1} ---\n{page_text}")
            except Exception as e:
                all_texts.append(f"--- Página {i + 1} ---\n[Erro no OCR: {str(e)}]")

        return "\n\n".join(all_texts)

    def is_image_readable(self, image_path: str) -> bool:
        """
        Verifica se a imagem tem texto legível.

        Args:
            image_path: Caminho para a imagem

        Returns:
            True se encontrou texto significativo
        """
        try:
            results = self.reader.readtext(image_path)
            # Considerar legível se tiver pelo menos 3 palavras com boa confiança
            confident_texts = [r for r in results if r[2] >= 0.5]
            total_chars = sum(len(r[1]) for r in confident_texts)
            return total_chars >= 20
        except:
            return False


# Instância singleton para uso global
# Nota: O reader é inicializado sob demanda para economizar memória
ocr_service = OCRService()
