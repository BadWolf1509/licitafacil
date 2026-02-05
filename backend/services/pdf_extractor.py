"""
Serviço de extração de texto e tabelas de PDFs.
Utiliza pdfplumber para PDFs digitais e PyMuPDF para renderização.
"""

from exceptions import PDFError
import pdfplumber
import fitz  # PyMuPDF
from typing import List, Dict, Any
from logging_config import get_logger

logger = get_logger('services.pdf_extractor')


class PDFExtractor:
    """Extrai texto e tabelas de arquivos PDF."""

    def __init__(self):
        self.min_text_length = 50  # Mínimo de caracteres para considerar PDF como texto

    def extract_text(self, file_path: str) -> str:
        """
        Extrai todo o texto de um PDF.

        Args:
            file_path: Caminho para o arquivo PDF
            include_page: Se True, inclui numero da pagina por tabela

        Returns:
            Texto extraído do PDF
        """
        text_parts = []
        logger.info(f"Extraindo texto de: {file_path}")

        try:
            with pdfplumber.open(file_path) as pdf:
                logger.debug(f"PDF aberto: {len(pdf.pages)} paginas")
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text_parts.append(page_text)
        except Exception as e:
            logger.error(f"Erro PDF: {e}", exc_info=True)
            raise PDFError("extrair texto", str(e))

        logger.info(f"Texto extraido: {len(text_parts)} paginas com conteudo")
        return "\n\n".join(text_parts)

    def extract_tables(
        self,
        file_path: str,
        include_page: bool = False
    ) -> List[Any]:
        """
        Extrai todas as tabelas de um PDF.

        Args:
            file_path: Caminho para o arquivo PDF

        Returns:
            Lista de tabelas, onde cada tabela é uma lista de linhas
        """
        all_tables: List[Any] = []
        logger.info(f"Extraindo tabelas de: {file_path}")

        try:
            with pdfplumber.open(file_path) as pdf:
                logger.debug(f"PDF aberto: {len(pdf.pages)} paginas")
                for page_index, page in enumerate(pdf.pages, start=1):
                    tables = page.extract_tables()
                    if tables:
                        for table in tables:
                            # Limpar células vazias e None
                            cleaned_table = []
                            for row in table:
                                cleaned_row = [
                                    str(cell).strip() if cell else ""
                                    for cell in row
                                ]
                                # Só adicionar linhas que tenham algum conteúdo
                                if any(cell for cell in cleaned_row):
                                    cleaned_table.append(cleaned_row)

                            if cleaned_table:
                                if include_page:
                                    all_tables.append({
                                        "rows": cleaned_table,
                                        "page": page_index
                                    })
                                else:
                                    all_tables.append(cleaned_table)
        except Exception as e:
            logger.error(f"Erro PDF: {e}", exc_info=True)
            raise PDFError("extrair tabelas", str(e))

        logger.info(f"Tabelas extraidas: {len(all_tables)} tabelas encontradas")
        return all_tables

    def extract_all(self, file_path: str) -> Dict[str, Any]:
        """
        Extrai texto e tabelas de um PDF.

        Args:
            file_path: Caminho para o arquivo PDF

        Returns:
            Dicionário com texto, tabelas e metadados
        """
        result: Dict[str, Any] = {
            "texto": "",
            "tabelas": [],
            "paginas": 0,
            "tem_texto": False,
            "precisa_ocr": False
        }

        logger.info(f"Processando PDF completo: {file_path}")
        try:
            with pdfplumber.open(file_path) as pdf:
                pages = list(pdf.pages)
                result["paginas"] = len(pages)
                logger.debug(f"PDF aberto: {len(pages)} paginas")

                text_parts = []
                all_tables = []

                for page in pages:
                    # Extrair texto
                    page_text = page.extract_text()
                    if page_text:
                        text_parts.append(page_text)

                    # Extrair tabelas
                    tables = page.extract_tables()
                    if tables:
                        for table in tables:
                            cleaned_table = []
                            for row in table:
                                cleaned_row = [
                                    str(cell).strip() if cell else ""
                                    for cell in row
                                ]
                                if any(cell for cell in cleaned_row):
                                    cleaned_table.append(cleaned_row)
                            if cleaned_table:
                                all_tables.append(cleaned_table)

                result["texto"] = "\n\n".join(text_parts)
                result["tabelas"] = all_tables
                result["tem_texto"] = len(result["texto"]) >= self.min_text_length
                result["precisa_ocr"] = not result["tem_texto"]

        except Exception as e:
            logger.error(f"Erro PDF: {e}", exc_info=True)
            raise PDFError("processar", str(e))

        logger.info(f"PDF processado: {result['paginas']} pags, {len(result['tabelas'])} tabelas, tem_texto={result['tem_texto']}")
        return result

    def pdf_to_images(self, file_path: str, dpi: int = 200) -> List[bytes]:
        """
        Converte páginas do PDF em imagens para OCR.

        Args:
            file_path: Caminho para o arquivo PDF
            dpi: Resolução das imagens (default 200)

        Returns:
            Lista de imagens em bytes (PNG)
        """
        images = []
        zoom = dpi / 72  # 72 é o DPI padrão do PDF
        matrix = fitz.Matrix(zoom, zoom)
        logger.info(f"Convertendo PDF para imagens (DPI={dpi}): {file_path}")

        try:
            doc = fitz.open(file_path)
            logger.debug(f"PDF aberto: {len(doc)} paginas")
            for page in doc:
                pix = page.get_pixmap(matrix=matrix)
                img_bytes = pix.tobytes("png")
                images.append(img_bytes)
            doc.close()
        except Exception as e:
            logger.error(f"Erro PDF: {e}", exc_info=True)
            raise PDFError("converter para imagens", str(e))

        logger.info(f"Imagens geradas: {len(images)} paginas")
        return images


# Instância singleton para uso global
pdf_extractor = PDFExtractor()
