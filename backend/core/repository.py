"""
Repository pattern implementation for LicitaFacil.

Provides a base class for data access with common CRUD operations.
"""
from typing import Generic, TypeVar, Optional, List, Any
from sqlalchemy.orm import Session

ModelType = TypeVar("ModelType")


class BaseRepository(Generic[ModelType]):
    """
    Base repository class with common CRUD operations.

    Subclasses should set the `model` class attribute to the SQLAlchemy model.
    """

    model: Any  # SQLAlchemy model class

    def __init__(self, db: Session):
        """
        Initialize the repository.

        Args:
            db: SQLAlchemy database session
        """
        self.db = db

    def get(self, id: int) -> Optional[ModelType]:
        """
        Get a single record by ID.

        Args:
            id: Record ID

        Returns:
            The record or None if not found
        """
        return self.db.query(self.model).filter(self.model.id == id).first()

    def get_by_user(self, id: int, user_id: int) -> Optional[ModelType]:
        """
        Get a single record by ID, filtered by user.

        Args:
            id: Record ID
            user_id: User ID

        Returns:
            The record or None if not found/not owned by user
        """
        return self.db.query(self.model).filter(
            self.model.id == id,
            self.model.user_id == user_id
        ).first()

    def list_by_user(
        self,
        user_id: int,
        offset: int = 0,
        limit: int = 20,
        order_by: Optional[str] = None,
        desc: bool = True
    ) -> List[ModelType]:
        """
        List records for a user with pagination.

        Args:
            user_id: User ID
            offset: Number of records to skip
            limit: Maximum number of records to return
            order_by: Column name to order by (default: 'created_at')
            desc: Whether to order descending

        Returns:
            List of records
        """
        query = self.db.query(self.model).filter(self.model.user_id == user_id)

        if order_by:
            col = getattr(self.model, order_by, None)
            if col is not None:
                query = query.order_by(col.desc() if desc else col.asc())
        else:
            # Default to created_at if available
            if hasattr(self.model, 'created_at'):
                query = query.order_by(
                    self.model.created_at.desc() if desc else self.model.created_at.asc()
                )

        return query.offset(offset).limit(limit).all()

    def count_by_user(self, user_id: int) -> int:
        """
        Count records for a user.

        Args:
            user_id: User ID

        Returns:
            Number of records
        """
        return self.db.query(self.model).filter(self.model.user_id == user_id).count()

    def create(self, **kwargs) -> ModelType:
        """
        Create a new record.

        Args:
            **kwargs: Field values for the new record

        Returns:
            The created record
        """
        instance = self.model(**kwargs)
        self.db.add(instance)
        self.db.commit()
        self.db.refresh(instance)
        return instance

    def update(self, instance: ModelType, **kwargs) -> ModelType:
        """
        Update a record.

        Args:
            instance: The record to update
            **kwargs: Field values to update

        Returns:
            The updated record
        """
        for key, value in kwargs.items():
            if hasattr(instance, key):
                setattr(instance, key, value)
        self.db.commit()
        self.db.refresh(instance)
        return instance

    def delete(self, instance: ModelType) -> None:
        """
        Delete a record.

        Args:
            instance: The record to delete
        """
        self.db.delete(instance)
        self.db.commit()
