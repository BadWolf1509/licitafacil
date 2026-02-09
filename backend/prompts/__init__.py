"""
Gerenciador de prompts para IA.

Este modulo carrega prompts de arquivos externos para facilitar manutencao.
"""
from functools import lru_cache
from pathlib import Path
from typing import Dict

PROMPTS_DIR = Path(__file__).parent


@lru_cache(maxsize=32)
def load_prompt(name: str) -> str:
    """
    Carrega um prompt de arquivo.

    Args:
        name: Nome do prompt (sem extensao .txt)

    Returns:
        Conteudo do prompt

    Raises:
        FileNotFoundError: Se o arquivo nao existir
    """
    prompt_path = PROMPTS_DIR / f"{name}.txt"
    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt nao encontrado: {name}")

    with open(prompt_path, 'r', encoding='utf-8') as f:
        return f.read().strip()


def get_atestado_vision_prompts() -> Dict[str, str]:
    """
    Retorna os prompts para extracao de atestado via vision.

    Returns:
        Dicionario com 'system' e 'user' prompts
    """
    return {
        "system": load_prompt("atestado_vision_system"),
        "user": load_prompt("atestado_vision_user"),
    }


def get_atestado_text_prompt() -> str:
    """
    Retorna o prompt para extracao de atestado via texto.

    Returns:
        Prompt de sistema para extracao de texto
    """
    return load_prompt("atestado_text")


def get_edital_prompt() -> str:
    """
    Retorna o prompt para extracao de exigencias de edital.

    Returns:
        Prompt de sistema para extracao de edital
    """
    return load_prompt("edital_exigencias")


def get_matching_prompt() -> str:
    """
    Retorna o prompt para analise de matching.

    Returns:
        Prompt de sistema para matching
    """
    return load_prompt("analise_matching")
