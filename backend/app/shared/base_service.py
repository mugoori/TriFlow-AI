"""
Base service class for CRUD operations
"""
from typing import Generic, TypeVar, Type, List, Optional, Dict, Any
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import select, and_

from .pagination import paginate, create_paginated_response, PaginatedResponse

T = TypeVar('T')


class BaseService(Generic[T]):
    """
    Base service class providing common CRUD operations

    All module services can inherit from this class to get
    standard CRUD functionality with tenant isolation.

    Example:
        class ProductService(BaseService[Product]):
            def __init__(self, db: Session):
                super().__init__(db, Product)
    """

    def __init__(self, db: Session, model: Type[T]):
        """
        Initialize base service

        Args:
            db: SQLAlchemy database session
            model: SQLAlchemy model class
        """
        self.db = db
        self.model = model

    async def get_by_id(
        self,
        item_id: UUID,
        tenant_id: UUID
    ) -> Optional[T]:
        """
        Get item by ID with tenant isolation

        Args:
            item_id: Item UUID
            tenant_id: Tenant UUID for isolation

        Returns:
            Model instance or None if not found
        """
        stmt = select(self.model).where(
            and_(
                self.model.id == item_id,
                self.model.tenant_id == tenant_id
            )
        )
        result = self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_items(
        self,
        tenant_id: UUID,
        page: int = 1,
        page_size: int = 20,
        filters: Optional[Dict[str, Any]] = None,
        sort_by: Optional[str] = None,
        sort_order: str = 'asc'
    ) -> tuple[List[T], int]:
        """
        List items with pagination, filtering, and sorting

        Args:
            tenant_id: Tenant UUID for isolation
            page: Page number (1-indexed)
            page_size: Number of items per page
            filters: Dictionary of field: value filters
            sort_by: Field name to sort by
            sort_order: 'asc' or 'desc'

        Returns:
            Tuple of (items list, total count)
        """
        # Base query with tenant isolation
        stmt = select(self.model).where(self.model.tenant_id == tenant_id)

        # Apply filters
        if filters:
            for field, value in filters.items():
                if value is not None and hasattr(self.model, field):
                    stmt = stmt.where(getattr(self.model, field) == value)

        # Apply sorting
        if sort_by and hasattr(self.model, sort_by):
            order_field = getattr(self.model, sort_by)
            if sort_order == 'desc':
                stmt = stmt.order_by(order_field.desc())
            else:
                stmt = stmt.order_by(order_field.asc())

        # Execute query with pagination
        query = self.db.scalars(stmt)
        return paginate(query, page, page_size)

    async def list_items_paginated(
        self,
        tenant_id: UUID,
        page: int = 1,
        page_size: int = 20,
        filters: Optional[Dict[str, Any]] = None,
        sort_by: Optional[str] = None,
        sort_order: str = 'asc'
    ) -> PaginatedResponse[T]:
        """
        List items with paginated response object

        Same as list_items but returns a PaginatedResponse object
        """
        items, total = await self.list_items(
            tenant_id=tenant_id,
            page=page,
            page_size=page_size,
            filters=filters,
            sort_by=sort_by,
            sort_order=sort_order
        )

        return create_paginated_response(items, total, page, page_size)

    async def create(
        self,
        tenant_id: UUID,
        data: Dict[str, Any]
    ) -> T:
        """
        Create new item

        Args:
            tenant_id: Tenant UUID for isolation
            data: Dictionary of field values

        Returns:
            Created model instance
        """
        # Add tenant_id to data
        data['tenant_id'] = tenant_id

        # Create instance
        instance = self.model(**data)
        self.db.add(instance)
        self.db.commit()
        self.db.refresh(instance)

        return instance

    async def update(
        self,
        item_id: UUID,
        tenant_id: UUID,
        data: Dict[str, Any]
    ) -> Optional[T]:
        """
        Update existing item

        Args:
            item_id: Item UUID
            tenant_id: Tenant UUID for isolation
            data: Dictionary of fields to update

        Returns:
            Updated model instance or None if not found
        """
        # Get existing item
        item = await self.get_by_id(item_id, tenant_id)
        if not item:
            return None

        # Update fields
        for field, value in data.items():
            if hasattr(item, field) and field != 'tenant_id':
                setattr(item, field, value)

        self.db.commit()
        self.db.refresh(item)

        return item

    async def delete(
        self,
        item_id: UUID,
        tenant_id: UUID
    ) -> bool:
        """
        Delete item

        Args:
            item_id: Item UUID
            tenant_id: Tenant UUID for isolation

        Returns:
            True if deleted, False if not found
        """
        item = await self.get_by_id(item_id, tenant_id)
        if not item:
            return False

        self.db.delete(item)
        self.db.commit()

        return True
