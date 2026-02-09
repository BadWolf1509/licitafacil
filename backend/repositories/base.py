"""
Repositório base com operações CRUD genéricas.
"""
from typing import Any, Generic, List, Optional, Type, TypeVar

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

    def query_for_user(
        self,
        db: Session,
        user_id: int,
        order_by: str = "created_at",
        order_desc: bool = True,
        limit: Optional[int] = None,
        offset: int = 0,
        **filters
    ) -> List[ModelType]:
        """
        Query flexível com filtros, ordenação e paginação.

        Args:
            db: Sessão do banco
            user_id: ID do usuário
            order_by: Nome da coluna para ordenação (default: created_at)
            order_desc: Se True, ordena decrescente (default: True)
            limit: Limite de resultados (opcional)
            offset: Offset para paginação (default: 0)
            **filters: Filtros adicionais como column=value

        Returns:
            Lista de entidades

        Exemplo:
            # Buscar atestados do usuário com contratante específico
            repo.query_for_user(db, user_id, contratante="PREFEITURA")

            # Buscar com ordenação customizada
            repo.query_for_user(db, user_id, order_by="quantidade", order_desc=False)
        """
        query = db.query(self.model).filter(
            self.model.user_id == user_id  # type: ignore[attr-defined]
        )

        # Aplicar filtros adicionais
        for column_name, value in filters.items():
            if hasattr(self.model, column_name):
                column = getattr(self.model, column_name)
                query = query.filter(column == value)

        # Aplicar ordenação
        if hasattr(self.model, order_by):
            order_column = getattr(self.model, order_by)
            query = query.order_by(
                order_column.desc() if order_desc else order_column
            )

        # Aplicar paginação
        if offset:
            query = query.offset(offset)
        if limit:
            query = query.limit(limit)

        return query.all()

    def exists_for_user(self, db: Session, id: int, user_id: int) -> bool:
        """
        Verifica se entidade existe para o usuário.

        Args:
            db: Sessão do banco
            id: ID da entidade
            user_id: ID do usuário

        Returns:
            True se existe, False caso contrário
        """
        return db.query(self.model).filter(
            self.model.id == id,  # type: ignore[attr-defined]
            self.model.user_id == user_id  # type: ignore[attr-defined]
        ).first() is not None

    def bulk_create(self, db: Session, entities: List[ModelType]) -> List[ModelType]:
        """
        Cria múltiplas entidades em uma transação.

        Args:
            db: Sessão do banco
            entities: Lista de entidades a criar

        Returns:
            Lista de entidades criadas
        """
        for entity in entities:
            db.add(entity)
        db.commit()
        for entity in entities:
            db.refresh(entity)
        return entities

    def bulk_delete_for_user(
        self, db: Session, ids: List[int], user_id: int
    ) -> int:
        """
        Remove múltiplas entidades por IDs, filtradas por usuário.

        Args:
            db: Sessão do banco
            ids: Lista de IDs das entidades
            user_id: ID do usuário dono

        Returns:
            Quantidade de entidades removidas
        """
        result = db.query(self.model).filter(
            self.model.id.in_(ids),  # type: ignore[attr-defined]
            self.model.user_id == user_id  # type: ignore[attr-defined]
        ).delete(synchronize_session=False)
        db.commit()
        return result
