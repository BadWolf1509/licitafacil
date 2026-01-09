"""
Serviço de extração de texto e tabelas de PDFs.
Utiliza pdfplumber para PDFs digitais e PyMuPDF para renderização.
"""

from exceptions import PDFError
import pdfplumber
import fitz  # PyMuPDF
from typing import List, Dict, Any


class PDFExtractor:
    """Extrai texto e tabelas de arquivos PDF."""

    def __init__(self):
        self.min_text_length = 50  # Mínimo de caracteres para considerar PDF como texto

    def extract_text(self, file_path: str) -> str:
        """
        Extrai todo o texto de um PDF.

        Args:
            file_path: Caminho para o arquivo PDF

        Returns:
            Texto extraído do PDF
        """
        text_parts = []

        try:
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text_parts.append(page_text)
        except Exception as e:
            raise PDFError("extrair texto", str(e))

        return "\n\n".join(text_parts)

    def extract_tables(self, file_path: str) -> List[List[List[str]]]:
        """
        Extrai todas as tabelas de um PDF.

        Args:
            file_path: Caminho para o arquivo PDF

        Returns:
            Lista de tabelas, onde cada tabela é uma lista de linhas
        """
        all_tables = []

        try:
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
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
                                all_tables.append(cleaned_table)
        except Exception as e:
            raise PDFError("extrair tabelas", str(e))

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

        try:
            with pdfplumber.open(file_path) as pdf:
                pages = list(pdf.pages)
                result["paginas"] = len(pages)

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
            raise PDFError("processar", str(e))

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

        try:
            doc = fitz.open(file_path)
            for page in doc:
                pix = page.get_pixmap(matrix=matrix)
                img_bytes = pix.tobytes("png")
                images.append(img_bytes)
            doc.close()
        except Exception as e:
            raise PDFError("converter para imagens", str(e))

        return images


# Instância singleton para uso global
pdf_extractor = PDFExtractor()
