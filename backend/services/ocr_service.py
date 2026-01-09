"""
Serviço de OCR (Reconhecimento Óptico de Caracteres).
Utiliza EasyOCR para extrair texto de imagens e PDFs escaneados.
Inclui pré-processamento de imagem para melhorar qualidade.
Suporta Tesseract como fallback opcional.
"""

from exceptions import OCRError
import easyocr
from typing import List, Optional, Dict, Any
import io
import os
from PIL import Image
import numpy as np
import cv2

# Tesseract é opcional - só usa se estiver instalado
try:
    import pytesseract
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False


class OCRService:
    """Serviço de OCR usando EasyOCR com pré-processamento de imagem e Tesseract fallback."""

    def __init__(self):
        self._reader: Optional[easyocr.Reader] = None
        self._languages = ['pt', 'en']  # Português e inglês
        self._preprocess_enabled = os.getenv("OCR_PREPROCESS", "1").lower() in {"1", "true", "yes"}
        self._tesseract_enabled = os.getenv("OCR_TESSERACT_FALLBACK", "1").lower() in {"1", "true", "yes"}
        self._tesseract_available = TESSERACT_AVAILABLE and self._check_tesseract()

    def _check_tesseract(self) -> bool:
        """Verifica se o Tesseract está instalado e acessível."""
        if not TESSERACT_AVAILABLE:
            return False
        try:
            pytesseract.get_tesseract_version()
            return True
        except Exception:
            return False

    @property
    def tesseract_available(self) -> bool:
        """Retorna se Tesseract está disponível."""
        return self._tesseract_available

    def _deskew_image(self, image: np.ndarray) -> np.ndarray:
        """
        Corrige inclinação (skew) da imagem.

        Args:
            image: Imagem em formato numpy array (BGR ou grayscale)

        Returns:
            Imagem corrigida
        """
        try:
            # Converter para grayscale se necessário
            if len(image.shape) == 3:
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            else:
                gray = image.copy()

            # Aplicar threshold binário invertido
            _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

            # Encontrar coordenadas de pixels não-zero
            coords = np.column_stack(np.where(thresh > 0))

            if len(coords) < 100:
                return image  # Sem pixels suficientes para calcular ângulo

            # Calcular ângulo usando minAreaRect
            angle = cv2.minAreaRect(coords)[-1]

            # Ajustar ângulo
            if angle < -45:
                angle = -(90 + angle)
            else:
                angle = -angle

            # Limitar correção a ±15 graus (evitar rotações erradas)
            if abs(angle) > 15:
                return image

            # Aplicar rotação se ângulo significativo (> 0.5 grau)
            if abs(angle) > 0.5:
                (h, w) = image.shape[:2]
                center = (w // 2, h // 2)
                M = cv2.getRotationMatrix2D(center, angle, 1.0)
                rotated = cv2.warpAffine(
                    image, M, (w, h),
                    flags=cv2.INTER_CUBIC,
                    borderMode=cv2.BORDER_REPLICATE
                )
                return rotated

            return image
        except Exception:
            return image  # Em caso de erro, retornar imagem original

    def _adaptive_binarization(self, image: np.ndarray) -> np.ndarray:
        """
        Aplica binarização adaptativa para melhorar contraste.

        Args:
            image: Imagem em formato numpy array

        Returns:
            Imagem binarizada
        """
        try:
            # Converter para grayscale se necessário
            if len(image.shape) == 3:
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            else:
                gray = image.copy()

            # Aplicar denoising leve
            denoised = cv2.fastNlMeansDenoising(gray, h=10)

            # Binarização adaptativa (Gaussian) - melhor para texto
            binary = cv2.adaptiveThreshold(
                denoised,
                255,
                cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY,
                blockSize=15,  # Tamanho do bloco (deve ser ímpar)
                C=8  # Constante subtraída da média
            )

            return binary
        except Exception:
            return image  # Em caso de erro, retornar imagem original

    def _preprocess_image(self, image: np.ndarray, use_binarization: bool = False) -> np.ndarray:
        """
        Aplica pré-processamento completo na imagem.

        Args:
            image: Imagem em formato numpy array
            use_binarization: Se True, aplica binarização adaptativa

        Returns:
            Imagem pré-processada
        """
        if not self._preprocess_enabled:
            return image

        # 1. Deskewing (correção de inclinação)
        processed = self._deskew_image(image)

        # 2. Binarização adaptativa (opcional - pode ajudar em alguns casos)
        if use_binarization:
            processed = self._adaptive_binarization(processed)

        return processed

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
            raise OCRError(str(e))

    def extract_text_from_bytes(self, image_bytes: bytes, use_binarization: bool = False) -> str:
        """
        Extrai texto de uma imagem em bytes.

        Args:
            image_bytes: Imagem em bytes (PNG, JPG, etc.)
            use_binarization: Se True, aplica binarização adaptativa

        Returns:
            Texto extraído
        """
        try:
            # Converter bytes para array numpy via PIL
            image = Image.open(io.BytesIO(image_bytes))
            image_array = np.array(image)

            # Aplicar pré-processamento (deskewing + opcionalmente binarização)
            processed = self._preprocess_image(image_array, use_binarization=use_binarization)

            results = self.reader.readtext(processed)
            texts = [result[1] for result in results]
            return " ".join(texts)
        except Exception as e:
            raise OCRError(str(e))

    def extract_words_from_bytes(self, image_bytes: bytes, min_confidence: float = 0.3, use_binarization: bool = False) -> List[Dict[str, Any]]:
        """
        Extrai palavras com bounding boxes.

        Args:
            image_bytes: Imagem em bytes
            min_confidence: Confiança mínima (0-1)
            use_binarization: Se True, aplica binarização adaptativa
        """
        try:
            image = Image.open(io.BytesIO(image_bytes))
            image_array = np.array(image)

            # Aplicar pré-processamento
            processed = self._preprocess_image(image_array, use_binarization=use_binarization)

            results = self.reader.readtext(processed)
            words = []
            for bbox, text, conf in results:
                if conf is None or conf < min_confidence:
                    continue
                if not text or not str(text).strip():
                    continue
                xs = [point[0] for point in bbox]
                ys = [point[1] for point in bbox]
                x0, x1 = min(xs), max(xs)
                y0, y1 = min(ys), max(ys)
                words.append({
                    "text": str(text).strip(),
                    "conf": float(conf),
                    "x0": x0,
                    "y0": y0,
                    "x1": x1,
                    "y1": y1,
                    "x_center": (x0 + x1) / 2,
                    "y_center": (y0 + y1) / 2,
                    "width": x1 - x0,
                    "height": y1 - y0
                })
            return words
        except Exception as e:
            raise OCRError(str(e))


# Instância singleton para uso global
# Nota: O reader é inicializado sob demanda para economizar memória
ocr_service = OCRService()
