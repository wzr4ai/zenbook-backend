"""Common Pydantic schemas."""

from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ResponseEnvelope(BaseModel, Generic[T]):
    """Standard API envelope."""

    success: bool = True
    data: T | None = None
    message: str | None = None


class PaginationMeta(BaseModel):
    total: int
    limit: int
    offset: int
