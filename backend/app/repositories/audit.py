"""Store searchable audit history in the real Mongo audit collection."""

from datetime import datetime
from typing import Any

from bson import ObjectId
from pymongo import DESCENDING
from pymongo.asynchronous.database import AsyncDatabase


class AuditRepository:
    """Query and append durable audit events."""

    def __init__(self, database: AsyncDatabase[dict[str, Any]]) -> None:
        """Bind queries to the persisted audit collection."""
        self.collection = database["audit_logs"]

    async def record(self, actor: dict[str, Any], action: str, entity_type: str, entity_id: str | None, details: str, at: datetime) -> None:
        """Insert a vocabulary-compliant event attributed to its actor."""
        await self.collection.insert_one({
            "timestamp": at,
            "userId": actor.get("_id", ObjectId("000000000000000000000000")),
            "userName": str(actor.get("name", "Unknown login actor")),
            "action": action,
            "entityType": entity_type,
            "entityId": ObjectId(entity_id) if entity_id and ObjectId.is_valid(entity_id) else None,
            "details": details[:500],
        })

    async def list_page(self, query: dict[str, Any], page: int, page_size: int) -> tuple[list[dict[str, Any]], int]:
        """Return a timestamp-descending stable page and filtered total."""
        total = await self.collection.count_documents(query)
        cursor = self.collection.find(query).sort([("timestamp", DESCENDING), ("_id", DESCENDING)]).skip((page - 1) * page_size).limit(page_size)
        return await cursor.to_list(length=page_size), total
