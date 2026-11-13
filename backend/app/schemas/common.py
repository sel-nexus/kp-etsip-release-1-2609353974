"""Define reusable API pagination and safe error response schemas."""

from typing import Annotated, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field


class HealthResponse(BaseModel):
    """Expose the minimal public liveness response."""

    status: str


class PageRequest(BaseModel):
    """Validate bounded one-based list pagination parameters."""

    model_config = ConfigDict(extra="forbid")
    page: int = Field(default=1, ge=1)
    pageSize: int = Field(default=25, ge=1, le=100)


T = TypeVar("T")


class PageResponse(BaseModel, Generic[T]):
    """Represent a page and its authoritative total count."""

    items: list[T]
    page: int
    pageSize: int
    total: int


class FieldError(BaseModel):
    """Describe a single safe request validation issue."""

    field: str
    message: str


class ErrorDetail(BaseModel):
    """Represent a public API error without internal details."""

    code: str
    message: str
    field_errors: list[FieldError] | None = None


class ErrorEnvelope(BaseModel):
    """Wrap API error details with a request correlation identifier."""

    error: ErrorDetail
    request_id: str


PyPageSize = Annotated[int, Field(ge=1, le=100)]
