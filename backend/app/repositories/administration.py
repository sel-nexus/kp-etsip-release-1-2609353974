"""Persist account and role administration using the active Mongo database."""

from datetime import UTC, datetime
from typing import Any

from bson import ObjectId
from pymongo import ReturnDocument
from pymongo.asynchronous.database import AsyncDatabase


class AdministrationRepository:
    """Run account and role queries against real Mongo collections."""

    def __init__(self, database: AsyncDatabase[dict[str, Any]]) -> None:
        """Bind account and role operations to the app-owned database."""
        self.users = database["users"]
        self.roles = database["roles"]
        self.portfolios = database["portfolios"]

    async def list_users(self, page: int, page_size: int) -> tuple[list[dict[str, Any]], int]:
        """Return a bounded user page and total account count."""
        total = await self.users.count_documents({})
        cursor = self.users.find({}, {"passwordHash": 0}).sort("name", 1).skip((page - 1) * page_size).limit(page_size)
        return await cursor.to_list(length=page_size), total

    async def get_user(self, user_id: str) -> dict[str, Any] | None:
        """Find a managed account without its password hash."""
        if not ObjectId.is_valid(user_id):
            return None
        return await self.users.find_one({"_id": ObjectId(user_id)}, {"passwordHash": 0})

    async def create_user(self, document: dict[str, Any]) -> dict[str, Any]:
        """Insert a new managed account and return its safe document."""
        result = await self.users.insert_one(document)
        return await self.get_user(str(result.inserted_id)) or {}

    async def update_user(self, user_id: str, changes: dict[str, Any]) -> dict[str, Any] | None:
        """Update a managed account and return the resulting safe document."""
        if not ObjectId.is_valid(user_id):
            return None
        changes["updatedAt"] = datetime.now(UTC)
        return await self.users.find_one_and_update(
            {"_id": ObjectId(user_id)}, {"$set": changes}, return_document=ReturnDocument.AFTER,
            projection={"passwordHash": 0},
        )

    async def deactivate_user(self, user_id: str) -> dict[str, Any] | None:
        """Set an account inactive without deleting its history."""
        return await self.update_user(user_id, {"status": "Inactive"})

    async def portfolios_exist(self, portfolio_ids: list[str]) -> bool:
        """Confirm every supplied portfolio reference identifies a record."""
        if not portfolio_ids:
            return True
        if any(not ObjectId.is_valid(value) for value in portfolio_ids):
            return False
        count = await self.portfolios.count_documents({"_id": {"$in": [ObjectId(value) for value in portfolio_ids]}})
        return count == len(set(portfolio_ids))

    async def list_roles(self, names: list[str]) -> list[dict[str, Any]]:
        """Return only supported persisted role definitions in configured order."""
        docs = await self.roles.find({"name": {"$in": names}}).to_list(length=len(names))
        by_name = {doc["name"]: doc for doc in docs}
        return [by_name[name] for name in names if name in by_name]

    async def get_role(self, name: str) -> dict[str, Any] | None:
        """Find one persisted role definition by its exact supported name."""
        return await self.roles.find_one({"name": name})

    async def update_role(self, name: str, changes: dict[str, Any]) -> dict[str, Any] | None:
        """Update an existing role without creating any new role record."""
        changes["updatedAt"] = datetime.now(UTC)
        return await self.roles.find_one_and_update(
            {"name": name}, {"$set": changes}, return_document=ReturnDocument.AFTER
        )
