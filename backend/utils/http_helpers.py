"""
Funções auxiliares para HTTP/routers.

Centraliza padrões comuns de resposta HTTP, tratamento de erros
e validação de recursos.
"""
from typing import Optional, Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from config import Messages


def get_resource_or_404(
    db: Session,
    model: Any,
    resource_id: int,
    user_id: Optional[int] = None,
    error_message: str = Messages.NOT_FOUND
) -> Any:
    """
    Busca um recurso por ID ou levanta HTTPException 404.

    Args:
        db: Sessão do banco de dados
        model: Classe do modelo SQLAlchemy
        resource_id: ID do recurso a buscar
        user_id: Se informado, filtra também por user_id
        error_message: Mensagem de erro personalizada

    Returns:
        O recurso encontrado

    Raises:
        HTTPException: 404 se o recurso não for encontrado
    """
    query = db.query(model).filter(model.id == resource_id)

    if user_id is not None:
        query = query.filter(model.user_id == user_id)

    resource = query.first()

    if not resource:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=error_message
        )

    return resource


def get_user_resource_or_404(
    db: Session,
    model: Any,
    resource_id: int,
    user_id: int,
    error_message: str = Messages.NOT_FOUND
) -> Any:
    """
    Busca recurso pertencente ao usuário ou levanta 404.

    Wrapper conveniente para get_resource_or_404 com user_id obrigatório.

    Args:
        db: Sessão do banco de dados
        model: Classe do modelo SQLAlchemy
        resource_id: ID do recurso
        user_id: ID do usuário proprietário
        error_message: Mensagem de erro personalizada

    Returns:
        O recurso encontrado

    Raises:
        HTTPException: 404 se o recurso não for encontrado
    """
    return get_resource_or_404(db, model, resource_id, user_id, error_message)
