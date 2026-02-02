"""
Testes para o validador de senha.
"""
import pytest
from utils.password_validator import PasswordValidator, validate_password, get_password_requirements


class TestPasswordValidator:
    """Testes da classe PasswordValidator."""

    def test_valid_password_passes(self):
        """Senha que atende todos os requisitos deve passar."""
        validator = PasswordValidator(
            min_length=8,
            require_uppercase=True,
            require_lowercase=True,
            require_digit=True,
            require_special=False
        )
        is_valid, errors = validator.validate("Senha123")
        assert is_valid is True
        assert len(errors) == 0

    def test_password_too_short(self):
        """Senha muito curta deve falhar."""
        validator = PasswordValidator(min_length=8)
        is_valid, errors = validator.validate("Abc123")
        assert is_valid is False
        assert any("minimo" in e.lower() for e in errors)

    def test_password_missing_uppercase(self):
        """Senha sem maiuscula deve falhar quando exigido."""
        validator = PasswordValidator(
            min_length=8,
            require_uppercase=True
        )
        is_valid, errors = validator.validate("senha123")
        assert is_valid is False
        assert any("maiuscula" in e.lower() for e in errors)

    def test_password_missing_lowercase(self):
        """Senha sem minuscula deve falhar quando exigido."""
        validator = PasswordValidator(
            min_length=8,
            require_lowercase=True
        )
        is_valid, errors = validator.validate("SENHA123")
        assert is_valid is False
        assert any("minuscula" in e.lower() for e in errors)

    def test_password_missing_digit(self):
        """Senha sem digito deve falhar quando exigido."""
        validator = PasswordValidator(
            min_length=8,
            require_digit=True
        )
        is_valid, errors = validator.validate("SenhaABC")
        assert is_valid is False
        assert any("numero" in e.lower() for e in errors)

    def test_password_missing_special(self):
        """Senha sem caractere especial deve falhar quando exigido."""
        validator = PasswordValidator(
            min_length=8,
            require_special=True
        )
        is_valid, errors = validator.validate("Senha123")
        assert is_valid is False
        assert any("especial" in e.lower() for e in errors)

    def test_password_with_special_passes(self):
        """Senha com caractere especial deve passar."""
        validator = PasswordValidator(
            min_length=8,
            require_special=True
        )
        is_valid, errors = validator.validate("Senha123!")
        assert is_valid is True
        assert len(errors) == 0

    def test_multiple_errors_returned(self):
        """Multiplos erros devem ser retornados."""
        validator = PasswordValidator(
            min_length=8,
            require_uppercase=True,
            require_lowercase=True,
            require_digit=True
        )
        is_valid, errors = validator.validate("a")
        assert is_valid is False
        assert len(errors) >= 2  # Muito curta e falta maiuscula e digito

    def test_empty_password_fails(self):
        """Senha vazia deve falhar."""
        validator = PasswordValidator(min_length=8)
        is_valid, errors = validator.validate("")
        assert is_valid is False

    def test_get_requirements(self):
        """Deve retornar lista de requisitos."""
        validator = PasswordValidator(
            min_length=8,
            require_uppercase=True,
            require_lowercase=True,
            require_digit=True,
            require_special=False
        )
        requirements = validator.get_requirements()
        assert len(requirements) == 4
        assert any("8" in r for r in requirements)


class TestValidatePasswordFunction:
    """Testes da funcao validate_password."""

    def test_convenience_function_works(self):
        """Funcao de conveniencia deve funcionar."""
        is_valid, errors = validate_password("SenhaForte123")
        # Depende da configuracao padrao
        assert isinstance(is_valid, bool)
        assert isinstance(errors, list)

    def test_get_requirements_function_works(self):
        """Funcao get_password_requirements deve funcionar."""
        requirements = get_password_requirements()
        assert isinstance(requirements, list)
        assert len(requirements) > 0


class TestSpecialCharacters:
    """Testes de caracteres especiais."""

    @pytest.mark.parametrize("special_char", [
        "!", "@", "#", "$", "%", "^", "&", "*", "(", ")",
        ",", ".", "?", ":", "{", "}", "|", "<", ">",
        "_", "-", "+", "=", "[", "]", "\\", ";", "'", "`", "~"
    ])
    def test_various_special_characters(self, special_char):
        """Diversos caracteres especiais devem ser aceitos."""
        validator = PasswordValidator(
            min_length=8,
            require_uppercase=True,
            require_lowercase=True,
            require_digit=True,
            require_special=True
        )
        password = f"Senha12{special_char}"
        is_valid, errors = validator.validate(password)
        assert is_valid is True, f"Char {special_char} should be accepted. Errors: {errors}"
