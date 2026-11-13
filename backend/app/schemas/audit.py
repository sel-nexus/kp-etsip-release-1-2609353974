"""Define safe, bounded audit history response contracts."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

AuditAction = Literal["login", "create", "edit", "delete", "roleChange", "permissionChange", "export"]


class AuditEntry(BaseModel):
    """Expose one safe persisted audit event."""

    id: str
    timestamp: datetime
    userId: str
    userName: str
    action: AuditAction
    entityType: str
    entityId: str | None = None
    details: str


class AuditPage(BaseModel):
    """Return a stable bounded audit page and matching count."""

    items: list[AuditEntry]
    page: int
    pageSize: int
    total: int


class AuditFilters(BaseModel):
    """Validate searchable audit filters and pagination bounds."""

    model_config = ConfigDict(extra="forbid")

    userId: str | None = None
    action: AuditAction | None = None
    from_: datetime | None = Field(default=None, alias="from")
    to: datetime | None = None
    page: int = Field(default=1, ge=1)
    pageSize: int = Field(default=25, ge=1, le=100)
