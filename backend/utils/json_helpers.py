"""
Utilitários para manipulação de JSON em respostas de IA.
"""
import json
import re
from typing import Any, Optional, Union


def clean_json_response(response: str) -> str:
    """
    Limpa uma resposta de IA removendo marcadores de código markdown.

    Args:
        response: String contendo JSON possivelmente envolta em ```json...```

    Returns:
        String limpa pronta para json.loads()
    """
    if not response:
        return ""

    response = response.strip()

    # Remove ```json no início
    if response.startswith("```json"):
        response = response[7:]
    # Remove ``` genérico no início
    elif response.startswith("```"):
        response = response[3:]

    # Remove ``` no final
    if response.endswith("```"):
        response = response[:-3]

    return response.strip()


def parse_json_response(
    response: str,
    default: Optional[Any] = None
) -> Union[dict, list, Any]:
    """
    Limpa e faz parse de uma resposta JSON de IA.

    Args:
        response: String contendo JSON
        default: Valor padrão a retornar em caso de erro

    Returns:
        Objeto Python parseado do JSON, ou default em caso de erro
    """
    try:
        cleaned = clean_json_response(response)
        return json.loads(cleaned)
    except (json.JSONDecodeError, TypeError):
        return default if default is not None else {}


def extract_json_from_text(text: str) -> Optional[str]:
    """
    Extrai o primeiro bloco JSON válido de um texto.
    Útil quando a IA retorna texto antes/depois do JSON.

    Args:
        text: Texto que pode conter JSON em algum lugar

    Returns:
        String JSON extraída ou None se não encontrado
    """
    if not text:
        return None

    # Primeiro tenta encontrar JSON em bloco de código
    code_block = re.search(r'```(?:json)?\s*([\[\{].*?[\]\}])\s*```', text, re.DOTALL)
    if code_block:
        return code_block.group(1)

    # Tenta encontrar objeto JSON {...}
    obj_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', text, re.DOTALL)
    if obj_match:
        try:
            json.loads(obj_match.group())
            return obj_match.group()
        except json.JSONDecodeError:
            pass

    # Tenta encontrar array JSON [...]
    arr_match = re.search(r'\[[^\[\]]*(?:\[[^\[\]]*\][^\[\]]*)*\]', text, re.DOTALL)
    if arr_match:
        try:
            json.loads(arr_match.group())
            return arr_match.group()
        except json.JSONDecodeError:
            pass

    return None
