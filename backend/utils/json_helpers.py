"""
Utilitários para manipulação de JSON em respostas de IA.
"""


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
