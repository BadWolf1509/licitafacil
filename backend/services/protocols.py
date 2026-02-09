"""
Protocolos (Interfaces) para servicos do LicitaFacil.
Define contratos que os servicos devem implementar.
Permite injecao de dependencia e facilita testes.
"""
from typing import Any, Dict, List, Optional, Protocol


class PDFExtractorProtocol(Protocol):
    """Protocolo para extracao de dados de PDF."""

    def extract_all(self, file_path: str) -> Dict[str, Any]:
        """
        Extrai todos os dados de um PDF.

        Args:
            file_path: Caminho do arquivo PDF

        Returns:
            Dicionario com texto, imagens e metadados extraidos
        """
        ...


class OCRServiceProtocol(Protocol):
    """Protocolo para servico de OCR."""

    def initialize(self) -> None:
        """Inicializa o servico de OCR."""
        ...

    def ocr_images(self, images: List[bytes]) -> str:
        """
        Executa OCR em lista de imagens.

        Args:
            images: Lista de imagens em bytes

        Returns:
            Texto extraido das imagens
        """
        ...

    def is_available(self) -> bool:
        """Verifica se o servico esta disponivel."""
        ...


class AIServiceProtocol(Protocol):
    """Protocolo para servico de IA/LLM."""

    def process_text(self, text: str, prompt: str) -> Dict[str, Any]:
        """
        Processa texto com IA usando um prompt.

        Args:
            text: Texto a processar
            prompt: Instrucoes para a IA

        Returns:
            Resultado do processamento
        """
        ...

    def is_available(self) -> bool:
        """Verifica se o servico esta disponivel."""
        ...


class DocumentProcessorProtocol(Protocol):
    """
    Protocolo completo do DocumentProcessor.

    Inclui metodos publicos e internos usados por AtestadoPipeline e AtestadoProcessor.
    """

    def process_atestado(
        self,
        file_path: str,
        use_vision: bool = True,
        progress_callback: Optional[Any] = None,
        cancel_check: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Processa um atestado de capacidade tecnica."""
        ...

    def process_edital(
        self,
        file_path: str,
        **kwargs
    ) -> Dict[str, Any]:
        """Processa um edital de licitacao."""
        ...

    def analyze_qualification(
        self,
        exigencias: List[Dict],
        atestados: List[Dict]
    ) -> List[Dict]:
        """Analisa qualificacao tecnica."""
        ...

    def get_status(self) -> Dict[str, Any]:
        """Retorna status dos servicos de processamento."""
        ...

    def _postprocess_servicos(
        self,
        servicos: list,
        use_ai: bool,
        table_used: bool,
        servicos_table: list,
        texto: str,
        strict_item_gate: bool = False,
        skip_no_code_dedupe: bool = False,
    ) -> list:
        """Aplica pos-processamento nos servicos extraidos."""
        ...

    def _build_restart_prefix_maps(
        self, servicos: list
    ) -> tuple:
        """Constroi mapas de prefixos de restart."""
        ...

    def _build_text_item_map(self, items: list) -> dict:
        """Constroi mapa de itens de texto."""
        ...

    def _apply_text_descriptions(self, servicos: list, text_map: dict) -> int:
        """Aplica descricoes de texto aos servicos."""
        ...

    def _should_replace_desc(self, current_desc: str, candidate_desc: str) -> bool:
        """Verifica se a descricao candidata deve substituir a atual."""
        ...


class ProcessingQueueProtocol(Protocol):
    """Protocolo para fila de processamento."""

    async def start(self) -> None:
        """Inicia a fila de processamento."""
        ...

    async def stop(self) -> None:
        """Para a fila de processamento."""
        ...

    async def enqueue(
        self,
        job_type: str,
        file_path: str,
        user_id: int,
        **kwargs
    ) -> str:
        """
        Adiciona job na fila.

        Args:
            job_type: Tipo do job (atestado, edital)
            file_path: Caminho do arquivo
            user_id: ID do usuario
            **kwargs: Dados adicionais

        Returns:
            ID do job criado
        """
        ...

    def get_job(self, job_id: str) -> Optional[Dict]:
        """Retorna dados de um job."""
        ...

    def get_user_jobs(self, user_id: int, limit: int = 20) -> List[Dict]:
        """Retorna jobs de um usuario."""
        ...


class AtestadoServiceProtocol(Protocol):
    """Protocolo para servico de atestados."""

    def atestados_to_dict(self, atestados: list) -> List[Dict]:
        """Converte atestados ORM para dicionarios."""
        ...

    def ordenar_servicos(self, servicos: List[Dict]) -> List[Dict]:
        """Ordena servicos pelo numero do item."""
        ...

    def parse_date(self, date_str: Optional[str]) -> Optional[Any]:
        """Converte string de data para objeto date."""
        ...
