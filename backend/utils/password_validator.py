"""
Validacao de complexidade de senha.

Implementa regras configuraveis para garantir senhas seguras.
"""
import re
from typing import List, Tuple

from config.security import (
    PASSWORD_MIN_LENGTH,
    PASSWORD_REQUIRE_DIGIT,
    PASSWORD_REQUIRE_LOWERCASE,
    PASSWORD_REQUIRE_SPECIAL,
    PASSWORD_REQUIRE_UPPERCASE,
)


class PasswordValidator:
    """
    Validador de complexidade de senha.

    Verifica se a senha atende aos requisitos minimos de seguranca.
    """

    def __init__(
        self,
        min_length: int = PASSWORD_MIN_LENGTH,
        require_uppercase: bool = PASSWORD_REQUIRE_UPPERCASE,
        require_lowercase: bool = PASSWORD_REQUIRE_LOWERCASE,
        require_digit: bool = PASSWORD_REQUIRE_DIGIT,
        require_special: bool = PASSWORD_REQUIRE_SPECIAL,
    ):
        """
        Inicializa o validador com as regras especificadas.

        Args:
            min_length: Comprimento minimo da senha
            require_uppercase: Exigir pelo menos uma letra maiuscula
            require_lowercase: Exigir pelo menos uma letra minuscula
            require_digit: Exigir pelo menos um digito
            require_special: Exigir pelo menos um caractere especial
        """
        self.min_length = min_length
        self.require_uppercase = require_uppercase
        self.require_lowercase = require_lowercase
        self.require_digit = require_digit
        self.require_special = require_special

    def validate(self, password: str) -> Tuple[bool, List[str]]:
        """
        Valida a senha contra as regras de complexidade.

        Args:
            password: Senha a ser validada

        Returns:
            Tupla (is_valid, lista_de_erros)
        """
        errors = []

        if len(password) < self.min_length:
            errors.append(
                f"Senha deve ter no minimo {self.min_length} caracteres"
            )

        if self.require_uppercase and not re.search(r'[A-Z]', password):
            errors.append("Senha deve conter pelo menos uma letra maiuscula")

        if self.require_lowercase and not re.search(r'[a-z]', password):
            errors.append("Senha deve conter pelo menos uma letra minuscula")

        if self.require_digit and not re.search(r'\d', password):
            errors.append("Senha deve conter pelo menos um numero")

        if self.require_special and not re.search(r'[!@#$%^&*(),.?":{}|<>_\-+=\[\]\\;\'`~]', password):
            errors.append("Senha deve conter pelo menos um caractere especial")

        return len(errors) == 0, errors

    def get_requirements(self) -> List[str]:
        """
        Retorna lista de requisitos de senha para exibicao ao usuario.

        Returns:
            Lista de strings descrevendo os requisitos
        """
        requirements = [f"Minimo {self.min_length} caracteres"]

        if self.require_uppercase:
            requirements.append("Pelo menos uma letra maiuscula")

        if self.require_lowercase:
            requirements.append("Pelo menos uma letra minuscula")

        if self.require_digit:
            requirements.append("Pelo menos um numero")

        if self.require_special:
            requirements.append("Pelo menos um caractere especial (!@#$%^&*...)")

        return requirements

    def get_policy(self) -> dict:
        """Retorna politica de senha em formato estruturado para clientes."""
        return {
            "min_length": self.min_length,
            "require_uppercase": self.require_uppercase,
            "require_lowercase": self.require_lowercase,
            "require_digit": self.require_digit,
            "require_special": self.require_special,
        }


# Instancia padrao do validador com configuracoes do ambiente
password_validator = PasswordValidator()


def validate_password(password: str) -> Tuple[bool, List[str]]:
    """
    Funcao de conveniencia para validar senha.

    Args:
        password: Senha a ser validada

    Returns:
        Tupla (is_valid, lista_de_erros)
    """
    return password_validator.validate(password)


def get_password_requirements() -> List[str]:
    """
    Funcao de conveniencia para obter requisitos de senha.

    Returns:
        Lista de strings descrevendo os requisitos
    """
    return password_validator.get_requirements()


def get_password_policy() -> dict:
    """
    Funcao de conveniencia para obter politica de senha estruturada.

    Returns:
        Dicionario com regras de validacao de senha
    """
    return password_validator.get_policy()
