"""
Base Schemas

Shared response wrappers, pagination, and error formats
used across all endpoints.
"""

from datetime import datetime
from typing import Any, Generic, List, Optional, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class PaginationMeta(BaseModel):
    """Pagination metadata included in list responses."""

    page: int = Field(ge=1, description="Current page number (1-indexed)")
    page_size: int = Field(ge=1, le=100, description="Items per page")
    total_items: int = Field(ge=0, description="Total matching items")
    total_pages: int = Field(ge=0, description="Total pages available")


class PaginatedResponse(BaseModel):
    """Paginated list response wrapper."""

    status: str = "success"
    data: List[Any] = Field(default_factory=list)
    meta: PaginationMeta


class ErrorDetail(BaseModel):
    """Detailed error information."""

    code: str = Field(description="Machine-readable error code")
    message: str = Field(description="Human-readable error message")
    field: Optional[str] = Field(default=None, description="Field name if validation error")
    details: Optional[Any] = Field(default=None, description="Additional error context")


class ErrorResponse(BaseModel):
    """Standard error response format."""

    status: str = "error"
    error: ErrorDetail


class SuccessResponse(BaseModel):
    """Generic success response."""

    status: str = "success"
    message: str = ""
    data: Optional[Any] = None


class PaginationParams(BaseModel):
    """Query parameters for pagination."""

    page: int = Field(default=1, ge=1, description="Page number")
    page_size: int = Field(default=20, ge=1, le=100, description="Items per page")

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size

    @property
    def limit(self) -> int:
        return self.page_size
