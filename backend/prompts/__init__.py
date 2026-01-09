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
