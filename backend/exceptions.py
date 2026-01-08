"""
Exceções específicas do LicitaFacil.

Este módulo define exceções customizadas para melhor tratamento de erros
e mensagens mais claras para o usuário.
"""

from typing import Any, Optional


class LicitaFacilError(Exception):
    """Exceção base para todas as exceções do LicitaFacil."""

    def __init__(self, message: str, details: Optional[str] = None):
        self.message = message
        self.details = details
        super().__init__(self.message)


# === Exceções de Configuração ===

class ConfigurationError(LicitaFacilError):
    """Erro de configuração do sistema (API keys, serviços não configurados)."""
    pass


class AINotConfiguredError(ConfigurationError):
    """Nenhum provedor de IA está configurado."""

    def __init__(self, provider: Optional[str] = None):
        if provider:
            message = f"API {provider} não configurada. Verifique as variáveis de ambiente."
        else:
            message = "Nenhum provedor de IA configurado. Configure OPENAI_API_KEY ou GOOGLE_API_KEY."
        super().__init__(message)


class AzureNotConfiguredError(ConfigurationError):
    """Azure Document Intelligence não está configurado."""

    def __init__(self):
        super().__init__(
            "Azure Document Intelligence não configurado. "
            "Defina AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT e AZURE_DOCUMENT_INTELLIGENCE_KEY."
        )


class DependencyNotInstalledError(ConfigurationError):
    """Dependência Python não está instalada."""

    def __init__(self, package: str):
        super().__init__(f"Pacote '{package}' não está instalado. Execute: pip install {package}")


# === Exceções de Processamento ===

class ProcessingError(LicitaFacilError):
    """Erro durante o processamento de documentos."""
    pass


class ProcessingCancelledError(ProcessingError):
    """Processamento foi cancelado pelo usuário."""

    def __init__(self):
        super().__init__("Processamento cancelado pelo usuário")


class OCRError(ProcessingError):
    """Erro durante o processamento OCR."""

    def __init__(self, message: str = "Erro no OCR", details: Optional[str] = None):
        super().__init__(f"Erro no OCR: {message}", details)


class PDFError(ProcessingError):
    """Erro ao processar arquivo PDF."""

    def __init__(self, operation: str, details: Optional[str] = None):
        super().__init__(f"Erro ao {operation} PDF", details)


class TextExtractionError(ProcessingError):
    """Não foi possível extrair texto do documento."""

    def __init__(self, file_type: str = "documento"):
        super().__init__(f"Não foi possível extrair texto do {file_type}")


# === Exceções de Validação ===

class ValidationError(LicitaFacilError):
    """Erro de validação de dados ou arquivos."""
    pass


class UnsupportedFileError(ValidationError):
    """Formato de arquivo não suportado."""

    def __init__(self, extension: str, supported: Optional[list] = None):
        supported_str = ", ".join(supported) if supported else "PDF, JPG, PNG"
        super().__init__(
            f"Formato de arquivo '{extension}' não suportado. "
            f"Formatos aceitos: {supported_str}"
        )


class InvalidFileError(ValidationError):
    """Arquivo inválido ou corrompido."""

    def __init__(self, message: str = "Arquivo inválido ou corrompido"):
        super().__init__(message)


# === Exceções de API Externa ===

class ExternalAPIError(LicitaFacilError):
    """Erro ao comunicar com API externa."""
    pass


class OpenAIError(ExternalAPIError):
    """Erro na API da OpenAI."""

    def __init__(self, details: Optional[str] = None):
        super().__init__("Erro na API OpenAI", details)


class GeminiError(ExternalAPIError):
    """Erro na API do Google Gemini."""

    def __init__(self, details: Optional[str] = None):
        super().__init__("Erro na API Google Gemini", details)


class AzureAPIError(ExternalAPIError):
    """Erro na API do Azure."""

    def __init__(self, details: Optional[str] = None):
        super().__init__("Erro na API Azure", details)


# === Exceções de Banco de Dados ===

class DatabaseError(LicitaFacilError):
    """Erro base para operações de banco de dados."""
    pass


class RecordNotFoundError(DatabaseError):
    """Registro não encontrado no banco de dados."""

    def __init__(self, entity: str, identifier: Any = None):
        if identifier:
            message = f"{entity} com ID '{identifier}' não encontrado"
        else:
            message = f"{entity} não encontrado"
        super().__init__(message)


class DuplicateRecordError(DatabaseError):
    """Tentativa de inserir registro duplicado."""

    def __init__(self, entity: str, field: Optional[str] = None):
        if field:
            message = f"{entity} com este {field} já existe"
        else:
            message = f"{entity} já existe no sistema"
        super().__init__(message)


class IntegrityError(DatabaseError):
    """Violação de integridade referencial."""

    def __init__(self, message: str = "Violação de integridade referencial"):
        super().__init__(message)


class ConnectionError(DatabaseError):
    """Erro de conexão com o banco de dados."""

    def __init__(self, details: Optional[str] = None):
        super().__init__("Não foi possível conectar ao banco de dados", details)
