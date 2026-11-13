"""Apply safe audit filters and map durable records to API responses."""

from datetime import UTC, datetime
from typing import Any

from bson import ObjectId
from fastapi import HTTPException

from app.repositories.audit import AuditRepository
from app.schemas.audit import AuditEntry, AuditFilters, AuditPage


class AuditService:
    """Serve bounded and searchable Mongo audit history."""

    def __init__(self, repository: AuditRepository) -> None:
        """Bind audit queries to the persisted collection repository."""
        self.repository = repository

    async def search(self, filters: AuditFilters) -> AuditPage:
        """Apply validated user, action, and UTC time filters."""
        query: dict[str, Any] = {}
        if filters.userId:
            if not ObjectId.is_valid(filters.userId):
                raise HTTPException(status_code=422, detail="userId must be a valid account identifier.")
            query["userId"] = ObjectId(filters.userId)
        if filters.action:
            query["action"] = filters.action
        bounds: dict[str, datetime] = {}
        if filters.from_:
            bounds["$gte"] = _utc(filters.from_)
        if filters.to:
            bounds["$lte"] = _utc(filters.to)
        if bounds:
            query["timestamp"] = bounds
        if filters.from_ and filters.to and _utc(filters.from_) > _utc(filters.to):
            raise HTTPException(status_code=422, detail="from must not be later than to.")
        documents, total = await self.repository.list_page(query, filters.page, filters.pageSize)
        items = [AuditEntry(
            id=str(row["_id"]), timestamp=_utc(row["timestamp"]), userId=str(row["userId"]),
            userName=str(row.get("userName", "")), action=row["action"], entityType=str(row.get("entityType", "auth")).lower(),
            entityId=str(row["entityId"]) if row.get("entityId") else None, details=str(row.get("details", "")),
        ) for row in documents]
        return AuditPage(items=items, page=filters.page, pageSize=filters.pageSize, total=total)


def _utc(value: datetime) -> datetime:
    """Normalize parsed timestamps to timezone-aware UTC values."""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
