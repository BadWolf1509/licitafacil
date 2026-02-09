"""
Serviço de Extração de PDF.

Responsável por:
- Conversão de PDF para imagens
- Extração de texto com fallback para OCR
- Processamento paralelo de OCR
- Detecção de páginas com tabelas
- Manipulação de imagens (crop, resize)
"""

import io
import re
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, List, Optional

import fitz  # PyMuPDF
import pdfplumber
from PIL import Image

from config import OCR_MAX_WORKERS, OCR_PARALLEL_ENABLED
from exceptions import OCRError, PDFError
from logging_config import get_logger

from .extraction import is_garbage_text, normalize_description
from .ocr_service import ocr_service

logger = get_logger('services.pdf_extraction_service')


class ProcessingCancelled(Exception):
    """Processamento cancelado pelo usuario."""


# Type aliases para callbacks
ProgressCallback = Optional[Callable[[int, int, str, str], None]]
CancelCheck = Optional[Callable[[], bool]]


class PDFExtractionService:
    """
    Serviço para extração de conteúdo de arquivos PDF.

    Fornece métodos para:
    - Converter PDF em imagens
    - Extrair texto com fallback automático para OCR
    - Processar OCR em paralelo para melhor performance
    - Detectar páginas que contêm tabelas
    """

    def __init__(self):
        self._min_text_per_page = 200  # Mínimo de caracteres para considerar página como texto
        self._default_dpi = 300  # DPI padrão para conversão

    def pdf_to_images(
        self,
        file_path: str,
        dpi: int = 300,
        progress_callback: ProgressCallback = None,
        cancel_check: CancelCheck = None,
        stage: str = "vision"
    ) -> List[bytes]:
        """
        Converte páginas de PDF em imagens PNG.

        Args:
            file_path: Caminho para o arquivo PDF
            dpi: Resolução em DPI (300 para melhor qualidade de OCR)
            progress_callback: Callback para progresso (current, total, stage, message)
            cancel_check: Função que retorna True se deve cancelar
            stage: Nome do estágio para o callback

        Returns:
            Lista de imagens em bytes (PNG)

        Raises:
            ProcessingCancelled: Se cancelamento solicitado
        """
        images = []
        for img_bytes in self.pdf_to_images_lazy(
            file_path, dpi, progress_callback, cancel_check, stage
        ):
            images.append(img_bytes)
        return images

    def pdf_to_images_lazy(
        self,
        file_path: str,
        dpi: int = 300,
        progress_callback: ProgressCallback = None,
        cancel_check: CancelCheck = None,
        stage: str = "vision"
    ):
        """
        Converte páginas de PDF em imagens PNG usando generator.

        Gera imagens uma por vez para reduzir uso de memoria.
        Ideal para PDFs grandes onde carregar todas as imagens
        simultaneamente excederia a memoria disponivel.

        Args:
            file_path: Caminho para o arquivo PDF
            dpi: Resolução em DPI (300 para melhor qualidade de OCR)
            progress_callback: Callback para progresso
            cancel_check: Função que retorna True se deve cancelar
            stage: Nome do estágio para o callback

        Yields:
            Imagem em bytes (PNG) de cada página

        Raises:
            ProcessingCancelled: Se cancelamento solicitado
        """
        doc = fitz.open(file_path)
        try:
            zoom = dpi / 72
            matrix = fitz.Matrix(zoom, zoom)
            total_pages = doc.page_count

            for page_index in range(total_pages):
                self._check_cancel(cancel_check)
                self._notify_progress(
                    progress_callback,
                    page_index + 1,
                    total_pages,
                    stage,
                    f"Convertendo pagina {page_index + 1} de {total_pages}"
                )
                page = doc[page_index]
                pix = page.get_pixmap(matrix=matrix)
                img_bytes = pix.tobytes("png")
                # Liberar memoria do pixmap imediatamente
                del pix
                yield img_bytes
        finally:
            doc.close()

    def extract_text_with_ocr_fallback(
        self,
        file_path: str,
        progress_callback: ProgressCallback = None,
        cancel_check: CancelCheck = None
    ) -> str:
        """
        Extrai texto de PDF, aplicando OCR em páginas que são imagens.

        Usa pdfplumber para extrair texto nativo. Para páginas com pouco
        texto ou texto "lixo", aplica OCR usando PyMuPDF + EasyOCR.

        Args:
            file_path: Caminho para o arquivo PDF
            progress_callback: Callback para progresso
            cancel_check: Função que retorna True se deve cancelar

        Returns:
            Texto completo extraído (texto nativo + OCR)

        Raises:
            PDFError: Se falhar ao processar o PDF
            ProcessingCancelled: Se cancelamento solicitado
        """
        text_parts = []
        pages_needing_ocr = []

        try:
            # Primeiro, tentar extrair texto de cada página
            with pdfplumber.open(file_path) as pdf:
                total_pages = len(pdf.pages)
                for i, page in enumerate(pdf.pages):
                    self._check_cancel(cancel_check)
                    self._notify_progress(
                        progress_callback,
                        i + 1,
                        total_pages,
                        "texto",
                        f"Extraindo texto da pagina {i + 1} de {total_pages}"
                    )
                    page_text = page.extract_text() or ""
                    text_stripped = page_text.strip()

                    # Se a página tem pouco texto OU texto é lixo/marca d'água, marcar para OCR
                    needs_ocr = len(text_stripped) < self._min_text_per_page or is_garbage_text(text_stripped)

                    if needs_ocr:
                        pages_needing_ocr.append(i)
                        text_parts.append(f"[PÁGINA {i+1} - AGUARDANDO OCR]")
                    else:
                        text_parts.append(f"Página {i+1}/{len(pdf.pages)}\n{page_text}")

            # Se há páginas que precisam de OCR, processar
            if pages_needing_ocr:
                doc = fitz.open(file_path)
                zoom = self._default_dpi / 72
                matrix = fitz.Matrix(zoom, zoom)

                total_ocr = len(pages_needing_ocr)
                for ocr_index, page_idx in enumerate(pages_needing_ocr):
                    self._check_cancel(cancel_check)
                    self._notify_progress(
                        progress_callback,
                        ocr_index + 1,
                        total_ocr,
                        "ocr",
                        f"OCR na pagina {ocr_index + 1} de {total_ocr}"
                    )
                    try:
                        page = doc[page_idx]
                        pix = page.get_pixmap(matrix=matrix)
                        img_bytes = pix.tobytes("png")
                        # Liberar memoria do pixmap imediatamente
                        del pix

                        # Aplicar OCR na página
                        ocr_text = ocr_service.extract_text_from_bytes(img_bytes)
                        # Liberar memoria da imagem apos OCR
                        del img_bytes

                        if ocr_text and len(ocr_text.strip()) > 20:
                            # Substituir placeholder pelo texto do OCR
                            placeholder = f"[PÁGINA {page_idx+1} - AGUARDANDO OCR]"
                            text_parts = [
                                f"Página {page_idx+1}/{len(doc)}\n{ocr_text}" if part == placeholder else part
                                for part in text_parts
                            ]
                    except OCRError as e:
                        logger.warning(f"Erro no OCR da pagina {page_idx+1}: {e}")

                doc.close()

            return "\n\n".join(text_parts)

        except (IOError, ValueError, RuntimeError, PDFError, OCRError) as e:
            raise PDFError("processar", str(e))

    def ocr_image_list(
        self,
        image_list: List[bytes],
        progress_callback: ProgressCallback = None,
        cancel_check: CancelCheck = None
    ) -> str:
        """
        Aplica OCR em uma lista de imagens.

        Usa processamento paralelo se habilitado e houver múltiplas páginas.

        Args:
            image_list: Lista de imagens em bytes
            progress_callback: Callback para progresso
            cancel_check: Função que retorna True se deve cancelar

        Returns:
            Texto concatenado de todas as páginas

        Raises:
            ProcessingCancelled: Se cancelamento solicitado
        """
        total = len(image_list)

        # Usar processamento paralelo se habilitado e houver múltiplas páginas
        if OCR_PARALLEL_ENABLED and total > 1:
            return self._ocr_image_list_parallel(image_list, progress_callback, cancel_check)

        # Processamento sequencial (padrão)
        all_texts = []
        for i, image_bytes in enumerate(image_list):
            self._check_cancel(cancel_check)
            self._notify_progress(
                progress_callback,
                i + 1,
                total,
                "ocr",
                f"OCR na pagina {i + 1} de {total}"
            )
            try:
                page_text = ocr_service.extract_text_from_bytes(image_bytes)
                if page_text.strip():
                    all_texts.append(f"--- Pagina {i + 1} ---\n{page_text}")
            except OCRError as e:
                logger.debug(f"Erro OCR na pagina {i + 1}: {e}")
                all_texts.append(f"--- Pagina {i + 1} ---\n[Erro no OCR: {e}]")

        return "\n\n".join(all_texts)

    def _ocr_image_list_parallel(
        self,
        image_list: List[bytes],
        progress_callback: ProgressCallback = None,
        cancel_check: CancelCheck = None
    ) -> str:
        """
        Processa múltiplas páginas em paralelo.

        Útil quando há muitas páginas e CPU com múltiplos núcleos.

        Args:
            image_list: Lista de imagens em bytes
            progress_callback: Callback para progresso
            cancel_check: Função que retorna True se deve cancelar

        Returns:
            Texto concatenado de todas as páginas
        """
        total = len(image_list)
        results = {}
        completed_count = 0
        lock = threading.Lock()

        def update_progress():
            nonlocal completed_count
            with lock:
                completed_count += 1
                self._notify_progress(
                    progress_callback,
                    completed_count,
                    total,
                    "ocr",
                    f"OCR paralelo: {completed_count} de {total} paginas"
                )

        with ThreadPoolExecutor(max_workers=OCR_MAX_WORKERS) as executor:
            # Submeter todas as páginas para processamento
            futures = {
                executor.submit(self._ocr_single_page, (i, img)): i
                for i, img in enumerate(image_list)
            }

            # Coletar resultados conforme completam
            for future in as_completed(futures):
                self._check_cancel(cancel_check)
                page_index, text = future.result()
                results[page_index] = text
                update_progress()

        # Ordenar resultados por índice de página
        all_texts = [results[i] for i in sorted(results.keys()) if results[i]]
        return "\n\n".join(all_texts)

    def _ocr_single_page(self, args: tuple) -> tuple:
        """
        Processa uma única página para OCR (usado em paralelo).

        Args:
            args: Tupla (page_index, image_bytes)

        Returns:
            Tupla (page_index, texto_extraido)
        """
        page_index, image_bytes = args
        try:
            page_text = ocr_service.extract_text_from_bytes(image_bytes)
            if page_text.strip():
                return (page_index, f"--- Pagina {page_index + 1} ---\n{page_text}")
            return (page_index, "")
        except OCRError as e:
            logger.debug(f"Erro OCR na pagina {page_index + 1}: {e}")
            return (page_index, f"--- Pagina {page_index + 1} ---\n[Erro no OCR: {e}]")

    def detect_table_pages(self, images: List[bytes]) -> List[int]:
        """
        Detecta quais páginas contêm tabelas de serviços.

        Analisa o cabeçalho de cada página procurando por palavras-chave
        típicas de relatórios de serviços executados.

        Args:
            images: Lista de imagens de páginas em bytes

        Returns:
            Lista de índices das páginas que contêm tabelas
        """
        keywords = {"RELATORIO", "SERVICOS", "EXECUTADOS", "ITEM", "DISCRIMINACAO", "UNID", "QUANTIDADE"}
        table_pages = []

        for index, image_bytes in enumerate(images):
            header = self.crop_region(image_bytes, 0.05, 0.0, 0.95, 0.35)
            header = self.resize_image(header, scale=0.5)
            try:
                text = ocr_service.extract_text_from_bytes(header)
            except OCRError as e:
                logger.debug(f"Erro OCR na detecao de pagina de tabela: {e}")
                text = ""
            normalized = normalize_description(text)
            hits = sum(1 for k in keywords if k in normalized)
            if hits >= 2:
                table_pages.append(index)
                continue
            if re.search(r"\b\d{3}\s*\d{2}\s*\d{2}\b", normalized):
                table_pages.append(index)

        # Se encontramos páginas de tabela mas não a última, incluir páginas consecutivas
        # pois tabelas frequentemente continuam em páginas seguintes sem cabeçalho
        if table_pages and len(images) > 1:
            max_detected = max(table_pages)
            # Se há páginas após a última detectada, incluí-las
            for i in range(max_detected + 1, len(images)):
                if i not in table_pages:
                    table_pages.append(i)
            table_pages.sort()

        return table_pages

    def crop_region(
        self,
        image_bytes: bytes,
        left: float,
        top: float,
        right: float,
        bottom: float
    ) -> bytes:
        """
        Recorta uma região da imagem.

        Args:
            image_bytes: Imagem em bytes
            left: Proporção da borda esquerda (0.0 a 1.0)
            top: Proporção da borda superior (0.0 a 1.0)
            right: Proporção da borda direita (0.0 a 1.0)
            bottom: Proporção da borda inferior (0.0 a 1.0)

        Returns:
            Imagem recortada em bytes (PNG)
        """
        try:
            img = Image.open(io.BytesIO(image_bytes))
            width, height = img.size
            crop = img.crop((int(width * left), int(height * top), int(width * right), int(height * bottom)))
            buffer = io.BytesIO()
            crop.save(buffer, format="PNG")
            return buffer.getvalue()
        except (IOError, ValueError, OSError) as e:
            logger.debug(f"Erro ao recortar imagem: {e}")
            return image_bytes

    def resize_image(self, image_bytes: bytes, scale: float = 0.5) -> bytes:
        """
        Redimensiona uma imagem.

        Args:
            image_bytes: Imagem em bytes
            scale: Fator de escala (0.5 = metade do tamanho)

        Returns:
            Imagem redimensionada em bytes (PNG)
        """
        try:
            img = Image.open(io.BytesIO(image_bytes))
            width, height = img.size
            resized = img.resize((max(1, int(width * scale)), max(1, int(height * scale))))
            buffer = io.BytesIO()
            resized.save(buffer, format="PNG")
            return buffer.getvalue()
        except (IOError, ValueError, OSError) as e:
            logger.debug(f"Erro ao redimensionar imagem: {e}")
            return image_bytes

    def _notify_progress(
        self,
        progress_callback: ProgressCallback,
        current: int,
        total: int,
        stage: str,
        message: str
    ):
        """Notifica progresso via callback se disponível."""
        if progress_callback:
            progress_callback(current, total, stage, message)

    def _check_cancel(self, cancel_check: CancelCheck):
        """Verifica se processamento deve ser cancelado."""
        if cancel_check and cancel_check():
            raise ProcessingCancelled("Processamento cancelado.")


# Instância singleton para uso global
pdf_extraction_service = PDFExtractionService()
