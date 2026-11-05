"""Common Pydantic schemas for REST API."""

from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class ErrorDetail(BaseModel):
    code: str = Field(..., description="Error code identifier")
    message: str = Field(..., description="Human-readable error description")


class ErrorResponse(BaseModel):
    error: ErrorDetail


class PaginationMeta(BaseModel):
    page: int = Field(1, ge=1, description="Current page number")
    page_size: int = Field(50, ge=1, le=1000, description="Items per page")
    total_items: int = Field(0, ge=0, description="Total matching items")
    total_pages: int = Field(0, ge=0, description="Total pages available")


class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    pagination: PaginationMeta
