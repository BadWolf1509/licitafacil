"""
Serviço integrado de processamento de documentos.
Combina extração de PDF, OCR e análise com IA.
Suporta GPT-4o Vision para análise direta de imagens.
"""

from typing import Dict, Any, List
from pathlib import Path
import pdfplumber
import fitz  # PyMuPDF

from .pdf_extractor import pdf_extractor
from .ocr_service import ocr_service
from .ai_provider import ai_provider


class DocumentProcessor:
    """Processador integrado de documentos."""

    def _pdf_to_images(self, file_path: str, dpi: int = 200) -> List[bytes]:
        """
        Converte páginas de PDF em imagens PNG.

        Args:
            file_path: Caminho para o arquivo PDF
            dpi: Resolução em DPI (200 é bom equilíbrio entre qualidade e tamanho)

        Returns:
            Lista de imagens em bytes (PNG)
        """
        images = []
        doc = fitz.open(file_path)
        zoom = dpi / 72
        matrix = fitz.Matrix(zoom, zoom)

        for page in doc:
            pix = page.get_pixmap(matrix=matrix)
            img_bytes = pix.tobytes("png")
            images.append(img_bytes)

        doc.close()
        return images

    def _is_garbage_text(self, text: str) -> bool:
        """
        Verifica se o texto é lixo (marca d'água invertida, etc).

        Args:
            text: Texto a verificar

        Returns:
            True se o texto parecer ser lixo/marca d'água
        """
        if not text or len(text.strip()) < 50:
            return True

        # Verificar se tem palavras comuns em português
        palavras_comuns = ['de', 'do', 'da', 'em', 'para', 'que', 'com', 'os', 'as', 'um', 'uma',
                          'no', 'na', 'ao', 'pela', 'pelo', 'este', 'esta', 'esse', 'essa']
        text_lower = text.lower()
        palavras_encontradas = sum(1 for p in palavras_comuns if f' {p} ' in text_lower)

        # Se não encontrar pelo menos 5 palavras comuns, provavelmente é lixo
        if palavras_encontradas < 5:
            return True

        # Verificar proporção de caracteres válidos vs especiais/números
        letras = sum(1 for c in text if c.isalpha())
        total = len(text.replace(' ', '').replace('\n', ''))

        if total > 0 and letras / total < 0.5:  # Menos de 50% letras = lixo
            return True

        return False

    def _extract_pdf_with_ocr_fallback(self, file_path: str) -> str:
        """
        Extrai texto de PDF, aplicando OCR em páginas que são imagens.

        Args:
            file_path: Caminho para o arquivo PDF

        Returns:
            Texto completo extraído (texto + OCR)
        """
        MIN_TEXT_PER_PAGE = 200  # Mínimo de caracteres para considerar página como texto
        text_parts = []
        pages_needing_ocr = []

        try:
            # Primeiro, tentar extrair texto de cada página
            with pdfplumber.open(file_path) as pdf:
                for i, page in enumerate(pdf.pages):
                    page_text = page.extract_text() or ""
                    text_stripped = page_text.strip()

                    # Se a página tem pouco texto OU texto é lixo/marca d'água, marcar para OCR
                    needs_ocr = len(text_stripped) < MIN_TEXT_PER_PAGE or self._is_garbage_text(text_stripped)

                    if needs_ocr:
                        pages_needing_ocr.append(i)
                        text_parts.append(f"[PÁGINA {i+1} - AGUARDANDO OCR]")
                    else:
                        text_parts.append(f"Página {i+1}/{len(pdf.pages)}\n{page_text}")

            # Se há páginas que precisam de OCR, processar
            if pages_needing_ocr:
                import fitz
                doc = fitz.open(file_path)
                zoom = 300 / 72  # 300 DPI para melhor qualidade de OCR
                matrix = fitz.Matrix(zoom, zoom)

                for page_idx in pages_needing_ocr:
                    try:
                        page = doc[page_idx]
                        pix = page.get_pixmap(matrix=matrix)
                        img_bytes = pix.tobytes("png")

                        # Aplicar OCR na página
                        ocr_text = ocr_service.extract_text_from_bytes(img_bytes)

                        if ocr_text and len(ocr_text.strip()) > 20:
                            # Substituir placeholder pelo texto do OCR
                            placeholder = f"[PÁGINA {page_idx+1} - AGUARDANDO OCR]"
                            text_parts = [
                                f"Página {page_idx+1}/{len(doc)}\n{ocr_text}" if part == placeholder else part
                                for part in text_parts
                            ]
                    except Exception as e:
                        print(f"Erro no OCR da página {page_idx+1}: {str(e)}")

                doc.close()

            return "\n\n".join(text_parts)

        except Exception as e:
            raise Exception(f"Erro ao processar PDF: {str(e)}")

    def _normalize_description(self, desc: str) -> str:
        """
        Normaliza descrição para comparação.
        Remove acentos, espaços extras e converte para maiúsculas.
        """
        import unicodedata
        # Remover acentos
        nfkd = unicodedata.normalize('NFKD', desc)
        ascii_text = nfkd.encode('ASCII', 'ignore').decode('ASCII')
        # Remover espaços extras e converter para maiúsculas
        return ' '.join(ascii_text.upper().split())

    def _extract_keywords(self, desc: str) -> set:
        """
        Extrai palavras-chave significativas da descrição.
        """
        normalized = self._normalize_description(desc)
        # Palavras a ignorar
        stopwords = {'DE', 'DO', 'DA', 'EM', 'PARA', 'COM', 'E', 'A', 'O', 'AS', 'OS',
                     'UN', 'M2', 'M3', 'ML', 'M', 'VB', 'KG', 'INCLUSIVE', 'INCLUSIV',
                     'TIPO', 'MODELO', 'TRACO'}
        words = set(normalized.split())
        return words - stopwords

    def _extract_item_code(self, desc: str) -> str:
        """
        Extrai código do item da descrição (ex: "001.03.01" de "001.03.01 MOBILIZAÇÃO").
        """
        import re
        match = re.match(r'^(\d{3}[\.\s]+\d{2}[\.\s]+\d{2})', desc)
        if match:
            return re.sub(r'[\s]+', '.', match.group(1))
        return ""

    def _merge_servicos(self, servicos1: list, servicos2: list) -> list:
        """
        Faz merge inteligente de duas listas de serviços.

        Estratégia:
        1. Priorizar itens COM código (mais precisos)
        2. Para itens SEM código, verificar se são duplicatas de itens com código
        3. Itens de séries diferentes (001.03.xx vs 001.04.xx) NÃO são duplicatas

        Args:
            servicos1: Primeira lista de serviços (OCR - geralmente sem código)
            servicos2: Segunda lista de serviços (Vision - geralmente com código)

        Returns:
            Lista combinada sem duplicatas reais
        """
        # Primeiro, separar itens com código e sem código
        items_with_code = {}
        items_without_code = []

        # Processar ambas as listas
        for s in servicos1 + servicos2:
            desc = s.get('descricao', '')
            qtd = s.get('quantidade', 0)
            un = s.get('unidade', '').upper().strip()
            code = self._extract_item_code(desc)

            if code:
                key = f"{code}"
                if key not in items_with_code:
                    items_with_code[key] = s
                else:
                    # Se já existe, manter o com descrição mais completa
                    if len(desc) > len(items_with_code[key].get('descricao', '')):
                        items_with_code[key] = s
            else:
                items_without_code.append(s)

        # Agora, processar itens sem código
        # Verificar se são duplicatas de itens com código
        final_items = list(items_with_code.values())
        qty_set = set()

        # Criar índice de quantidades dos itens com código
        for item in final_items:
            qtd = item.get('quantidade', 0)
            un = item.get('unidade', '').upper().strip()
            qty_set.add(f"{qtd}|{un}")

        # Adicionar itens sem código que não são duplicatas
        added_without_code = {}
        for s in items_without_code:
            desc = s.get('descricao', '')
            qtd = s.get('quantidade', 0)
            un = s.get('unidade', '').upper().strip()

            qty_key = f"{qtd}|{un}"

            # Se a quantidade já existe nos itens com código, provavelmente é duplicata
            if qty_key in qty_set:
                # Verificar se a descrição é similar a algum item com código
                is_duplicate = False
                new_kw = self._extract_keywords(desc)

                for item in final_items:
                    item_qtd = item.get('quantidade', 0)
                    item_un = item.get('unidade', '').upper()

                    if abs(qtd - item_qtd) < 0.01 and un == item_un:
                        old_kw = self._extract_keywords(item.get('descricao', ''))
                        if len(new_kw & old_kw) >= 1:  # Pelo menos 1 palavra em comum
                            is_duplicate = True
                            break

                if is_duplicate:
                    continue

            # Verificar duplicatas entre itens sem código
            desc_key = self._normalize_description(desc)[:25]
            check_key = f"{desc_key}|{qtd}|{un}"

            if check_key not in added_without_code:
                added_without_code[check_key] = s
                qty_set.add(qty_key)

        final_items.extend(added_without_code.values())
        return final_items

    def process_atestado(self, file_path: str, use_vision: bool = True) -> Dict[str, Any]:
        """
        Processa um atestado de capacidade técnica usando abordagem híbrida.

        Combina GPT-4o Vision (para precisão) com OCR+texto (para completude).

        Args:
            file_path: Caminho para o arquivo (PDF ou imagem)
            use_vision: Se True, usa abordagem híbrida Vision+OCR; se False, apenas OCR+texto

        Returns:
            Dicionário com dados extraídos do atestado
        """
        file_ext = Path(file_path).suffix.lower()
        texto = ""
        dados_vision = None
        dados_ocr = None

        # Extrair texto com OCR (sempre necessário para referência)
        if file_ext == ".pdf":
            try:
                texto = self._extract_pdf_with_ocr_fallback(file_path)
            except Exception as e:
                try:
                    images = pdf_extractor.pdf_to_images(file_path)
                    texto = ocr_service.extract_from_pdf_images(images)
                except Exception as e2:
                    raise Exception(f"Erro ao processar PDF: {str(e)} / OCR: {str(e2)}")
        elif file_ext in [".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif"]:
            try:
                texto = ocr_service.extract_text_from_image(file_path)
            except Exception as e:
                raise Exception(f"Erro no OCR da imagem: {str(e)}")
        else:
            raise Exception(f"Formato de arquivo não suportado: {file_ext}")

        if not texto.strip():
            raise Exception("Não foi possível extrair texto do documento")

        # Se IA está configurada, processar com ambos os métodos
        if ai_provider.is_configured:
            # Método 1: OCR + análise de texto
            dados_ocr = ai_provider.extract_atestado_info(texto)

            # Método 2: Vision (GPT-4o ou Gemini) (se habilitado)
            if use_vision:
                try:
                    if file_ext == ".pdf":
                        images = self._pdf_to_images(file_path, dpi=150)
                    else:
                        with open(file_path, "rb") as f:
                            images = [f.read()]

                    dados_vision = ai_provider.extract_atestado_from_images(images)
                except Exception as e:
                    print(f"Erro no Vision: {str(e)}")
                    dados_vision = None

            # Combinar resultados
            if dados_vision and dados_ocr:
                # Usar descrição e contratante do Vision (mais preciso)
                dados = {
                    "descricao_servico": dados_vision.get("descricao_servico") or dados_ocr.get("descricao_servico"),
                    "contratante": dados_vision.get("contratante") or dados_ocr.get("contratante"),
                    "data_emissao": dados_vision.get("data_emissao") or dados_ocr.get("data_emissao"),
                    "quantidade": dados_vision.get("quantidade") or dados_ocr.get("quantidade"),
                    "unidade": dados_vision.get("unidade") or dados_ocr.get("unidade"),
                }

                # Fazer merge dos serviços (Vision tem precisão, OCR tem completude)
                servicos_vision = dados_vision.get("servicos", [])
                servicos_ocr = dados_ocr.get("servicos", [])
                dados["servicos"] = self._merge_servicos(servicos_ocr, servicos_vision)
            else:
                dados = dados_ocr or {
                    "descricao_servico": None,
                    "quantidade": None,
                    "unidade": None,
                    "contratante": None,
                    "data_emissao": None,
                    "servicos": []
                }
        else:
            dados = {
                "descricao_servico": None,
                "quantidade": None,
                "unidade": None,
                "contratante": None,
                "data_emissao": None,
                "servicos": []
            }

        dados["texto_extraido"] = texto
        return dados

    def process_edital(self, file_path: str) -> Dict[str, Any]:
        """
        Processa uma página de edital com quantitativos mínimos.

        Args:
            file_path: Caminho para o arquivo PDF

        Returns:
            Dicionário com exigências extraídas
        """
        file_ext = Path(file_path).suffix.lower()
        texto = ""
        tabelas = []

        if file_ext != ".pdf":
            raise Exception("O arquivo do edital deve ser um PDF")

        # Extrair conteúdo do PDF
        resultado = pdf_extractor.extract_all(file_path)

        if resultado["tem_texto"]:
            texto = resultado["texto"]
            tabelas = resultado["tabelas"]
        else:
            # PDF escaneado - usar OCR
            try:
                images = pdf_extractor.pdf_to_images(file_path)
                texto = ocr_service.extract_from_pdf_images(images)
            except Exception as e:
                raise Exception(f"Erro no OCR do edital: {str(e)}")

        if not texto.strip():
            raise Exception("Não foi possível extrair texto do edital")

        # Combinar texto e tabelas para análise
        texto_completo = texto
        if tabelas:
            texto_completo += "\n\nTABELAS ENCONTRADAS:\n"
            for i, tabela in enumerate(tabelas):
                texto_completo += f"\nTabela {i + 1}:\n"
                for linha in tabela:
                    texto_completo += " | ".join(linha) + "\n"

        # Extrair exigências com IA
        if ai_provider.is_configured:
            # Usar OpenAI diretamente para exigências (mais maduro)
            from .ai_analyzer import ai_analyzer
            if ai_analyzer.is_configured:
                exigencias = ai_analyzer.extract_edital_requirements(texto_completo)
            else:
                # Tentar com Gemini
                from .gemini_analyzer import gemini_analyzer
                exigencias = gemini_analyzer.extract_edital_requirements(texto_completo) if gemini_analyzer.is_configured else []
        else:
            exigencias = []

        return {
            "texto_extraido": texto,
            "tabelas": tabelas,
            "exigencias": exigencias,
            "paginas": resultado.get("paginas", 1)
        }

    def analyze_qualification(
        self,
        exigencias: List[Dict[str, Any]],
        atestados: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Analisa a qualificação técnica comparando exigências e atestados.

        Args:
            exigencias: Lista de exigências do edital
            atestados: Lista de atestados do usuário

        Returns:
            Resultado da análise com status de atendimento
        """
        return ai_provider.match_atestados(exigencias, atestados)

    def get_status(self) -> Dict[str, Any]:
        """
        Retorna o status dos serviços de processamento.

        Returns:
            Dicionário com status de cada serviço
        """
        provider_status = ai_provider.get_status()
        return {
            "pdf_extractor": True,
            "ocr_service": True,
            "ai_provider": provider_status,
            "is_configured": ai_provider.is_configured,
            "mensagem": f"IA configurada ({', '.join(ai_provider.available_providers)})" if ai_provider.is_configured else "Configure OPENAI_API_KEY ou GOOGLE_API_KEY para análise inteligente"
        }


# Instância singleton para uso global
document_processor = DocumentProcessor()
