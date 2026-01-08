"""
Gerenciador de prompts para IA.

Este módulo carrega prompts de arquivos externos para facilitar manutenção.
"""
from functools import lru_cache
from pathlib import Path


PROMPTS_DIR = Path(__file__).parent


@lru_cache(maxsize=32)
def load_prompt(name: str) -> str:
    """
    Carrega um prompt de arquivo.

    Args:
        name: Nome do prompt (sem extensão .txt)

    Returns:
        Conteúdo do prompt

    Raises:
        FileNotFoundError: Se o arquivo não existir
    """
    prompt_path = PROMPTS_DIR / f"{name}.txt"
    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt não encontrado: {name}")

    with open(prompt_path, 'r', encoding='utf-8') as f:
        return f.read().strip()


def get_prompt(name: str, **kwargs) -> str:
    """
    Carrega um prompt e aplica substituições de variáveis.

    Args:
        name: Nome do prompt
        **kwargs: Variáveis para substituir no formato {variavel}

    Returns:
        Prompt com variáveis substituídas
    """
    prompt = load_prompt(name)
    if kwargs:
        prompt = prompt.format(**kwargs)
    return prompt


# Constantes para nomes de prompts
class PromptNames:
    ATESTADO_VISION = "atestado_vision"
    ATESTADO_TEXT = "atestado_text"
    EDITAL_EXIGENCIAS = "edital_exigencias"
    ANALISE_MATCHING = "analise_matching"


# Alias para acesso mais fácil
PROMPTS = PromptNames()
