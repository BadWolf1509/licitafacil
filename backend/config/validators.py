"""
Validadores de configuração do LicitaFácil.

Fornece funções para validar valores de configuração
e garantir que estão dentro de limites aceitáveis.
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from logging_config import get_logger

logger = get_logger('config.validators')


@dataclass
class ConfigValidationError:
    """Erro de validação de configuração."""
    config_name: str
    value: Any
    message: str
    severity: str = "error"  # "error" ou "warning"


@dataclass
class ValidationResult:
    """Resultado da validação de configurações."""
    is_valid: bool
    errors: List[ConfigValidationError] = field(default_factory=list)
    warnings: List[ConfigValidationError] = field(default_factory=list)

    def add_error(self, config_name: str, value: Any, message: str):
        """Adiciona um erro de validação."""
        self.errors.append(ConfigValidationError(
            config_name=config_name,
            value=value,
            message=message,
            severity="error"
        ))
        self.is_valid = False

    def add_warning(self, config_name: str, value: Any, message: str):
        """Adiciona um warning de validação."""
        self.warnings.append(ConfigValidationError(
            config_name=config_name,
            value=value,
            message=message,
            severity="warning"
        ))


def validate_range(
    value: float,
    name: str,
    min_val: Optional[float] = None,
    max_val: Optional[float] = None,
    result: Optional[ValidationResult] = None
) -> bool:
    """
    Valida se um valor está dentro de um range.

    Args:
        value: Valor a validar
        name: Nome da configuração
        min_val: Valor mínimo (inclusive)
        max_val: Valor máximo (inclusive)
        result: ValidationResult para adicionar erros

    Returns:
        True se válido, False caso contrário
    """
    if min_val is not None and value < min_val:
        if result:
            result.add_error(name, value, f"Deve ser >= {min_val}")
        return False

    if max_val is not None and value > max_val:
        if result:
            result.add_error(name, value, f"Deve ser <= {max_val}")
        return False

    return True


def validate_positive(
    value: float,
    name: str,
    allow_zero: bool = False,
    result: Optional[ValidationResult] = None
) -> bool:
    """
    Valida se um valor é positivo.

    Args:
        value: Valor a validar
        name: Nome da configuração
        allow_zero: Se True, permite zero
        result: ValidationResult para adicionar erros

    Returns:
        True se válido, False caso contrário
    """
    if allow_zero and value < 0:
        if result:
            result.add_error(name, value, "Deve ser >= 0")
        return False

    if not allow_zero and value <= 0:
        if result:
            result.add_error(name, value, "Deve ser > 0")
        return False

    return True


def validate_percentage(
    value: float,
    name: str,
    result: Optional[ValidationResult] = None
) -> bool:
    """
    Valida se um valor é uma porcentagem válida (0 a 1).

    Args:
        value: Valor a validar
        name: Nome da configuração
        result: ValidationResult para adicionar erros

    Returns:
        True se válido, False caso contrário
    """
    return validate_range(value, name, 0.0, 1.0, result)


def validate_atestado_config() -> ValidationResult:
    """
    Valida todas as configurações de processamento de atestados.

    Returns:
        ValidationResult com erros e warnings encontrados
    """
    from .atestado import AtestadoProcessingConfig as APC

    result = ValidationResult(is_valid=True)

    # Validar OCR Layout
    validate_percentage(APC.ocr_layout.CONFIDENCE, "OCR_LAYOUT_CONFIDENCE", result)
    validate_positive(APC.ocr_layout.DPI, "OCR_LAYOUT_DPI", result=result)
    validate_percentage(APC.ocr_layout.RETRY_CONFIDENCE, "OCR_LAYOUT_RETRY_CONFIDENCE", result)

    # Validar Cascade thresholds
    validate_percentage(APC.cascade.STAGE1_QTY_THRESHOLD, "STAGE1_QTY_THRESHOLD", result)
    validate_percentage(APC.cascade.STAGE2_QTY_THRESHOLD, "STAGE2_QTY_THRESHOLD", result)
    validate_percentage(APC.cascade.STAGE3_QTY_THRESHOLD, "STAGE3_QTY_THRESHOLD", result)

    # Verificar ordem dos thresholds (Stage1 > Stage2 > Stage3)
    if APC.cascade.STAGE1_QTY_THRESHOLD < APC.cascade.STAGE2_QTY_THRESHOLD:
        result.add_warning(
            "STAGE_THRESHOLDS",
            f"{APC.cascade.STAGE1_QTY_THRESHOLD} < {APC.cascade.STAGE2_QTY_THRESHOLD}",
            "STAGE1_QTY_THRESHOLD deve ser >= STAGE2_QTY_THRESHOLD"
        )

    if APC.cascade.STAGE2_QTY_THRESHOLD < APC.cascade.STAGE3_QTY_THRESHOLD:
        result.add_warning(
            "STAGE_THRESHOLDS",
            f"{APC.cascade.STAGE2_QTY_THRESHOLD} < {APC.cascade.STAGE3_QTY_THRESHOLD}",
            "STAGE2_QTY_THRESHOLD deve ser >= STAGE3_QTY_THRESHOLD"
        )

    # Validar Table config
    validate_percentage(APC.table.CONFIDENCE_THRESHOLD, "TABLE_CONFIDENCE_THRESHOLD", result)
    validate_positive(APC.table.MIN_ITEMS, "TABLE_MIN_ITEMS", result=result)

    # Validar Similarity config
    validate_percentage(APC.similarity.DESC_THRESHOLD, "DESC_SIM_THRESHOLD", result)

    # Log results
    if not result.is_valid:
        for error in result.errors:
            logger.error(f"[CONFIG] {error.config_name}={error.value}: {error.message}")

    for warning in result.warnings:
        logger.warning(f"[CONFIG] {warning.config_name}={warning.value}: {warning.message}")

    return result


def get_config_summary() -> Dict[str, Any]:
    """
    Retorna um resumo das configurações atuais.

    Returns:
        Dict com valores de configuração principais
    """
    from .atestado import AtestadoProcessingConfig as APC
    from .base import PAID_SERVICES_ENABLED

    return {
        "paid_services_enabled": PAID_SERVICES_ENABLED,
        "ocr": {
            "dpi": APC.ocr_layout.DPI,
            "confidence": APC.ocr_layout.CONFIDENCE,
            "retry_dpi": APC.ocr_layout.RETRY_DPI,
        },
        "cascade": {
            "stage1_threshold": APC.cascade.STAGE1_QTY_THRESHOLD,
            "stage2_threshold": APC.cascade.STAGE2_QTY_THRESHOLD,
            "stage3_threshold": APC.cascade.STAGE3_QTY_THRESHOLD,
        },
        "table": {
            "confidence_threshold": APC.table.CONFIDENCE_THRESHOLD,
            "min_items": APC.table.MIN_ITEMS,
        },
        "vision": {
            "pagewise_enabled": APC.vision.PAGEWISE_ENABLED,
            "llm_fallback_only": APC.vision.LLM_FALLBACK_ONLY,
        },
        "document_ai": {
            "enabled": APC.document_ai.ENABLED,
            "fallback_only": APC.document_ai.FALLBACK_ONLY,
        }
    }
