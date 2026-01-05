"""
Serviço de pré-processamento de imagens para melhorar qualidade do OCR.
Inclui correção de inclinação (deskew), ajuste de contraste e redução de ruído.
"""

import io
import math
from typing import Tuple, Optional
from PIL import Image, ImageFilter, ImageEnhance, ImageOps
import numpy as np


class ImagePreprocessor:
    """Pré-processador de imagens para otimizar OCR."""

    def __init__(self):
        self._deskew_enabled = True
        self._denoise_enabled = True
        self._contrast_enabled = True

    def preprocess(
        self,
        image_bytes: bytes,
        deskew: bool = True,
        denoise: bool = True,
        enhance_contrast: bool = True
    ) -> bytes:
        """
        Aplica pré-processamento completo na imagem.

        Args:
            image_bytes: Imagem em bytes (PNG/JPEG)
            deskew: Corrigir inclinação
            denoise: Reduzir ruído
            enhance_contrast: Melhorar contraste

        Returns:
            Imagem processada em bytes (PNG)
        """
        img = Image.open(io.BytesIO(image_bytes))

        # Converter para RGB se necessário
        if img.mode in ('RGBA', 'LA'):
            background = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'RGBA':
                background.paste(img, mask=img.split()[3])
            else:
                background.paste(img, mask=img.split()[1])
            img = background
        elif img.mode != 'RGB':
            img = img.convert('RGB')

        # 1. Correção de inclinação (deskew)
        if deskew and self._deskew_enabled:
            img = self._deskew_image(img)

        # 2. Redução de ruído
        if denoise and self._denoise_enabled:
            img = self._denoise_image(img)

        # 3. Melhoria de contraste
        if enhance_contrast and self._contrast_enabled:
            img = self._enhance_contrast(img)

        # Converter de volta para bytes
        output = io.BytesIO()
        img.save(output, format='PNG', optimize=True)
        return output.getvalue()

    def _deskew_image(self, img: Image.Image) -> Image.Image:
        """
        Corrige inclinação da imagem usando detecção de ângulo.

        Args:
            img: Imagem PIL

        Returns:
            Imagem com inclinação corrigida
        """
        try:
            # Converter para escala de cinza para análise
            gray = img.convert('L')
            gray_array = np.array(gray)

            # Binarização simples
            threshold = np.mean(gray_array)
            binary = gray_array < threshold

            # Encontrar ângulo de inclinação usando projeção horizontal
            angle = self._detect_skew_angle(binary)

            # Só corrigir se o ângulo for significativo (> 0.5 graus)
            if abs(angle) > 0.5 and abs(angle) < 45:
                # Rotacionar imagem
                img = img.rotate(
                    angle,
                    resample=Image.BICUBIC,
                    expand=True,
                    fillcolor=(255, 255, 255)
                )

            return img
        except Exception:
            # Se falhar, retornar imagem original
            return img

    def _detect_skew_angle(self, binary: np.ndarray) -> float:
        """
        Detecta ângulo de inclinação usando projeção horizontal.

        Args:
            binary: Array binário da imagem

        Returns:
            Ângulo de inclinação em graus
        """
        best_angle = 0
        best_score = 0

        # Testar ângulos de -10 a 10 graus
        for angle in np.arange(-10, 10, 0.5):
            # Rotacionar array
            rotated = self._rotate_array(binary, angle)

            # Calcular projeção horizontal (soma de pixels por linha)
            projection = np.sum(rotated, axis=1)

            # Score baseado na variância da projeção
            # Texto alinhado horizontalmente terá maior variância
            score = np.var(projection)

            if score > best_score:
                best_score = score
                best_angle = angle

        return best_angle

    def _rotate_array(self, arr: np.ndarray, angle: float) -> np.ndarray:
        """Rotaciona array 2D pelo ângulo especificado."""
        from scipy import ndimage
        return ndimage.rotate(arr, angle, reshape=False, order=0)

    def _denoise_image(self, img: Image.Image) -> Image.Image:
        """
        Reduz ruído na imagem usando filtro mediano.

        Args:
            img: Imagem PIL

        Returns:
            Imagem com ruído reduzido
        """
        # Filtro mediano remove ruído salt-and-pepper
        img = img.filter(ImageFilter.MedianFilter(size=3))
        return img

    def _enhance_contrast(self, img: Image.Image) -> Image.Image:
        """
        Melhora contraste da imagem para melhor legibilidade.

        Args:
            img: Imagem PIL

        Returns:
            Imagem com contraste melhorado
        """
        # Auto-contraste (normaliza histograma)
        img = ImageOps.autocontrast(img, cutoff=1)

        # Aumentar contraste levemente
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(1.2)

        # Aumentar nitidez levemente
        enhancer = ImageEnhance.Sharpness(img)
        img = enhancer.enhance(1.3)

        return img

    def analyze_quality(self, image_bytes: bytes) -> dict:
        """
        Analisa a qualidade da imagem e retorna métricas.

        Args:
            image_bytes: Imagem em bytes

        Returns:
            Dicionário com métricas de qualidade
        """
        img = Image.open(io.BytesIO(image_bytes))

        # Converter para escala de cinza
        gray = img.convert('L')
        gray_array = np.array(gray)

        # Calcular métricas
        metrics = {
            'width': img.width,
            'height': img.height,
            'dpi_estimated': self._estimate_dpi(img),
            'contrast': self._calculate_contrast(gray_array),
            'brightness': self._calculate_brightness(gray_array),
            'noise_level': self._estimate_noise(gray_array),
            'skew_angle': self._detect_skew_angle(gray_array < np.mean(gray_array)),
            'quality_score': 0.0  # Será calculado abaixo
        }

        # Calcular score geral de qualidade (0-100)
        quality_score = self._calculate_quality_score(metrics)
        metrics['quality_score'] = quality_score
        metrics['quality_level'] = self._quality_level_from_score(quality_score)

        return metrics

    def _estimate_dpi(self, img: Image.Image) -> int:
        """Estima DPI baseado no tamanho da imagem."""
        # Assumindo documento A4 (210x297mm)
        # Se altura > 3000px, provavelmente 300 DPI
        # Se altura > 2000px, provavelmente 200 DPI
        # Se altura > 1000px, provavelmente 150 DPI
        height = img.height
        if height > 3300:
            return 300
        elif height > 2200:
            return 200
        elif height > 1100:
            return 150
        else:
            return 72

    def _calculate_contrast(self, gray_array: np.ndarray) -> float:
        """Calcula contraste RMS normalizado (0-1)."""
        std = np.std(gray_array)
        # Normalizar para 0-1 (std máximo teórico é ~127.5)
        return min(std / 80.0, 1.0)

    def _calculate_brightness(self, gray_array: np.ndarray) -> float:
        """Calcula brilho médio normalizado (0-1)."""
        return np.mean(gray_array) / 255.0

    def _estimate_noise(self, gray_array: np.ndarray) -> float:
        """
        Estima nível de ruído usando diferença Laplaciana.
        Retorna valor normalizado (0-1), onde menor é melhor.
        """
        from scipy import ndimage

        # Laplaciano detecta variações de alta frequência (ruído)
        laplacian = ndimage.laplace(gray_array.astype(float))
        noise_estimate = np.std(laplacian)

        # Normalizar (valores típicos de 0-50)
        return min(noise_estimate / 50.0, 1.0)

    def _calculate_quality_score(self, metrics: dict) -> float:
        """
        Calcula score de qualidade geral (0-100).

        Fatores considerados:
        - DPI estimado (peso: 30%)
        - Contraste (peso: 25%)
        - Nível de ruído invertido (peso: 25%)
        - Inclinação (peso: 20%)
        """
        # DPI score (72=0, 150=50, 200=75, 300=100)
        dpi = metrics['dpi_estimated']
        if dpi >= 300:
            dpi_score = 100
        elif dpi >= 200:
            dpi_score = 75
        elif dpi >= 150:
            dpi_score = 50
        else:
            dpi_score = max(0, (dpi - 72) / 78 * 50)

        # Contraste score (0-1 -> 0-100)
        contrast_score = metrics['contrast'] * 100

        # Noise score (invertido: menos ruído = melhor)
        noise_score = (1 - metrics['noise_level']) * 100

        # Skew score (0 graus = 100, >10 graus = 0)
        skew = abs(metrics['skew_angle'])
        skew_score = max(0, 100 - skew * 10)

        # Score ponderado
        total_score = (
            dpi_score * 0.30 +
            contrast_score * 0.25 +
            noise_score * 0.25 +
            skew_score * 0.20
        )

        return round(total_score, 2)

    def _quality_level_from_score(self, score: float) -> str:
        """Converte score numérico em nível descritivo."""
        if score >= 80:
            return 'facil'
        elif score >= 60:
            return 'medio'
        elif score >= 40:
            return 'dificil'
        else:
            return 'muito_dificil'


# Instância singleton
image_preprocessor = ImagePreprocessor()
