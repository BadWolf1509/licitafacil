"""
Interfaces (Protocols) para quebrar dependências circulares.

Define os contratos que os módulos devem seguir sem criar
imports diretos entre eles.
"""
from typing import Any, Callable, Dict, Optional, Protocol, Tuple


class DocumentProcessorProtocol(Protocol):
    """
    Interface do DocumentProcessor usada por AtestadoPipeline e AtestadoProcessor.

    Define os métodos que os consumidores precisam, sem exigir import direto
    do módulo document_processor (evitando circular dependency).
    """

    def process_atestado(
        self,
        file_path: str,
        use_vision: bool = True,
        progress_callback: Optional[Callable] = None,
        cancel_check: Optional[Callable] = None,
    ) -> Dict[str, Any]:
        """Processa um atestado de capacidade técnica."""
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
        """Aplica pós-processamento nos serviços extraídos."""
        ...

    def _build_restart_prefix_maps(
        self, servicos: list
    ) -> Tuple[Dict[tuple, str], Dict[str, str]]:
        """Constrói mapas de prefixos de restart."""
        ...

    def _build_text_item_map(self, items: list) -> dict:
        """Constrói mapa de itens de texto."""
        ...

    def _apply_text_descriptions(self, servicos: list, text_map: dict) -> int:
        """Aplica descrições de texto aos serviços."""
        ...

    def _should_replace_desc(self, current_desc: str, candidate_desc: str) -> bool:
        """Verifica se a descrição candidata deve substituir a atual."""
        ...
