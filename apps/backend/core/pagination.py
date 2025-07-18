"""
Pagination utilities for BrainOps backend.
"""

from typing import TypeVar, Generic, List, Optional
from pydantic import BaseModel
from fastapi import Query
from sqlalchemy.orm import Query as SQLQuery


T = TypeVar("T")


class PaginationParams:
    """Dependency for pagination parameters."""
    
    def __init__(
        self,
        limit: int = Query(20, ge=1, le=100, description="Items per page"),
        offset: int = Query(0, ge=0, description="Number of items to skip")
    ):
        self.limit = limit
        self.offset = offset


class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated response model."""
    items: List[T]
    total: int
    limit: int
    offset: int
    has_more: bool


def paginate(query: SQLQuery, pagination: PaginationParams) -> List:
    """
    Apply pagination to a SQLAlchemy query.
    
    Args:
        query: SQLAlchemy query object
        pagination: Pagination parameters
    
    Returns:
        List of items for the current page
    """
    return query.offset(pagination.offset).limit(pagination.limit).all()


def paginate_with_total(query: SQLQuery, pagination: PaginationParams) -> tuple[List, int]:
    """
    Apply pagination and return total count.
    
    Args:
        query: SQLAlchemy query object
        pagination: Pagination parameters
    
    Returns:
        Tuple of (items, total_count)
    """
    total = query.count()
    items = query.offset(pagination.offset).limit(pagination.limit).all()
    
    return items, total


def create_paginated_response(
    items: List[T],
    total: int,
    pagination: PaginationParams
) -> PaginatedResponse[T]:
    """
    Create a paginated response object.
    
    Args:
        items: List of items for current page
        total: Total number of items
        pagination: Pagination parameters used
    
    Returns:
        PaginatedResponse object
    """
    has_more = (pagination.offset + len(items)) < total
    
    return PaginatedResponse(
        items=items,
        total=total,
        limit=pagination.limit,
        offset=pagination.offset,
        has_more=has_more
    )


class CursorPagination:
    """Cursor-based pagination for better performance with large datasets."""
    
    def __init__(
        self,
        cursor: Optional[str] = Query(None, description="Cursor for next page"),
        limit: int = Query(20, ge=1, le=100, description="Items per page")
    ):
        self.cursor = cursor
        self.limit = limit
    
    def decode_cursor(self) -> Optional[dict]:
        """Decode cursor string to pagination info."""
        if not self.cursor:
            return None
        
        # In production, use proper encoding/encryption
        import base64
        import json
        
        try:
            decoded = base64.b64decode(self.cursor).decode('utf-8')
            return json.loads(decoded)
        except:
            return None
    
    @staticmethod
    def encode_cursor(data: dict) -> str:
        """Encode pagination info to cursor string."""
        import base64
        import json
        
        encoded = base64.b64encode(
            json.dumps(data).encode('utf-8')
        ).decode('utf-8')
        
        return encoded


def apply_cursor_pagination(
    query: SQLQuery,
    cursor_pagination: CursorPagination,
    order_field: str = "id"
) -> tuple[List, Optional[str]]:
    """
    Apply cursor-based pagination to query.
    
    Args:
        query: SQLAlchemy query
        cursor_pagination: Cursor pagination params
        order_field: Field to order by (must be unique)
    
    Returns:
        Tuple of (items, next_cursor)
    """
    cursor_data = cursor_pagination.decode_cursor()
    
    if cursor_data and "last_id" in cursor_data:
        # Continue from last ID
        query = query.filter(
            getattr(query.column_descriptions[0]['type'], order_field) > cursor_data["last_id"]
        )
    
    # Get one extra item to check if there's a next page
    items = query.order_by(
        getattr(query.column_descriptions[0]['type'], order_field)
    ).limit(cursor_pagination.limit + 1).all()
    
    has_next = len(items) > cursor_pagination.limit
    
    if has_next:
        # Remove the extra item
        items = items[:-1]
        
        # Create cursor for next page
        last_item = items[-1]
        next_cursor = CursorPagination.encode_cursor({
            "last_id": getattr(last_item, order_field)
        })
    else:
        next_cursor = None
    
    return items, next_cursor