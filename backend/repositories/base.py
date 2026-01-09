"""
Repositório base com operações CRUD genéricas.
"""
from typing import TypeVar, Generic, Type, Optional, List, Any
from sqlalchemy.orm import Session

ModelType = TypeVar("ModelType")


class BaseRepository(Generic[ModelType]):
    """
    Repositório genérico com operações CRUD comuns.

    Uso:
        class AtestadoRepository(BaseRepository[Atestado]):
            def __init__(self):
                super().__init__(Atestado)
    """

    def __init__(self, model: Type[ModelType]):
        """
        Inicializa o repositório com o modelo.

        Args:
            model: Classe do modelo SQLAlchemy
        """
        self.model = model

    def get_by_id(self, db: Session, id: int) -> Optional[ModelType]:
        """
        Busca entidade por ID.

        Args:
            db: Sessão do banco
            id: ID da entidade

        Returns:
            Entidade ou None
        """
        return db.query(self.model).filter(self.model.id == id).first()  # type: ignore[attr-defined]

    def get_by_id_for_user(
        self, db: Session, id: int, user_id: int
    ) -> Optional[ModelType]:
        """
        Busca entidade por ID, filtrada por usuário.

        Args:
            db: Sessão do banco
            id: ID da entidade
            user_id: ID do usuário dono

        Returns:
            Entidade ou None
        """
        return db.query(self.model).filter(
            self.model.id == id,  # type: ignore[attr-defined]
            self.model.user_id == user_id  # type: ignore[attr-defined]
        ).first()

    def get_all_for_user(
        self,
        db: Session,
        user_id: int,
        order_by: Any = None,
        offset: int = 0,
        limit: int = 100
    ) -> List[ModelType]:
        """
        Busca todas as entidades de um usuário com paginação.

        Args:
            db: Sessão do banco
            user_id: ID do usuário
            order_by: Coluna para ordenação
            offset: Posição inicial
            limit: Quantidade máxima

        Returns:
            Lista de entidades
        """
        query = db.query(self.model).filter(self.model.user_id == user_id)  # type: ignore[attr-defined]
        if order_by is not None:
            query = query.order_by(order_by)
        return query.offset(offset).limit(limit).all()

    def count_for_user(self, db: Session, user_id: int) -> int:
        """
        Conta entidades de um usuário.

        Args:
            db: Sessão do banco
            user_id: ID do usuário

        Returns:
            Contagem
        """
        return db.query(self.model).filter(
            self.model.user_id == user_id  # type: ignore[attr-defined]
        ).count()

    def create(self, db: Session, entity: ModelType) -> ModelType:
        """
        Cria nova entidade.

        Args:
            db: Sessão do banco
            entity: Entidade a criar

        Returns:
            Entidade criada
        """
        db.add(entity)
        db.commit()
        db.refresh(entity)
        return entity

    def update(self, db: Session, entity: ModelType) -> ModelType:
        """
        Atualiza entidade existente.

        Args:
            db: Sessão do banco
            entity: Entidade a atualizar

        Returns:
            Entidade atualizada
        """
        db.commit()
        db.refresh(entity)
        return entity

    def delete(self, db: Session, entity: ModelType) -> None:
        """
        Remove entidade.

        Args:
            db: Sessão do banco
            entity: Entidade a remover
        """
        db.delete(entity)
        db.commit()

    def delete_by_id_for_user(
        self, db: Session, id: int, user_id: int
    ) -> bool:
        """
        Remove entidade por ID, filtrada por usuário.

        Args:
            db: Sessão do banco
            id: ID da entidade
            user_id: ID do usuário dono

        Returns:
            True se removido, False se não encontrado
        """
        entity = self.get_by_id_for_user(db, id, user_id)
        if entity:
            self.delete(db, entity)
            return True
        return False
