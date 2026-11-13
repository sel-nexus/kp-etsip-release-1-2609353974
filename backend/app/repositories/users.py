"""Persist auth lookups, account changes, roles, and audit events in MongoDB."""

from datetime import UTC, datetime
from typing import Any

from bson import ObjectId
from pymongo import ReturnDocument
from pymongo.asynchronous.database import AsyncDatabase


class UsersRepository:
    """Run auth-specific queries against the shared asynchronous Mongo database."""

    def __init__(self, database: AsyncDatabase[dict[str, Any]]) -> None:
        """Bind auth operations to existing MongoDB collections."""
        self.users = database["users"]
        self.roles = database["roles"]
        self.audit_logs = database["audit_logs"]

    async def find_by_email(self, email: str) -> dict[str, Any] | None:
        """Find a local account by its normalized email address."""
        return await self.users.find_one({"email": email.strip().lower()})

    async def find_by_id(self, user_id: str) -> dict[str, Any] | None:
        """Find a user by a validated Mongo ObjectId string."""
        if not ObjectId.is_valid(user_id):
            return None
        return await self.users.find_one({"_id": ObjectId(user_id)})

    async def get_permissions(self, role_name: str) -> list[str]:
        """Reload permissions from the current persisted role definition."""
        role = await self.roles.find_one({"name": role_name}, {"permissions": 1})
        permissions = role.get("permissions", []) if role else []
        return [permission for permission in permissions if isinstance(permission, str)]

    async def update_last_login(self, user_id: ObjectId, at: datetime) -> dict[str, Any] | None:
        """Persist the successful sign-in timestamp and return the stored record."""
        return await self.users.find_one_and_update(
            {"_id": user_id, "status": "Active"},
            {"$set": {"lastLogin": at, "updatedAt": at}},
            return_document=ReturnDocument.AFTER,
        )

    async def update_password(
        self,
        user_id: ObjectId,
        current_hash: str,
        new_hash: str,
        at: datetime,
    ) -> dict[str, Any] | None:
        """Change a password only if the stored credential has not changed."""
        return await self.users.find_one_and_update(
            {"_id": user_id, "passwordHash": current_hash, "status": "Active"},
            {"$set": {"passwordHash": new_hash, "mustChangePassword": False, "updatedAt": at}},
            return_document=ReturnDocument.AFTER,
        )

    async def update_landing_page(
        self,
        user_id: ObjectId,
        landing_page: str | None,
        at: datetime,
    ) -> dict[str, Any] | None:
        """Persist the account's allowed landing-page choice."""
        return await self.users.find_one_and_update(
            {"_id": user_id, "status": "Active"},
            {"$set": {"defaultLandingPage": landing_page, "updatedAt": at}},
            return_document=ReturnDocument.AFTER,
        )

    async def write_login_audit(self, user: dict[str, Any] | None, succeeded: bool, at: datetime) -> None:
        """Record every login outcome without storing submitted credentials."""
        # The audit schema requires an actor; all-zero ObjectId is reserved for unknown attempts.
        actor_id = user["_id"] if user else ObjectId("000000000000000000000000")
        actor_name = str(user.get("name", "Unknown login actor")) if user else "Unknown login actor"
        action = "login"
        details = "Local account authentication succeeded" if succeeded else "Local account authentication failed"
        await self.audit_logs.insert_one(
            {
                "timestamp": at,
                "userId": actor_id,
                "userName": actor_name,
                "action": action,
                "entityType": "auth",
                "entityId": None,
                "details": details,
            }
        )

    async def write_user_audit(self, user: dict[str, Any], action: str, details: str, at: datetime) -> None:
        """Persist a safe profile-action audit event for an authenticated user."""
        await self.audit_logs.insert_one(
            {
                "timestamp": at,
                "userId": user["_id"],
                "userName": str(user.get("name", "")),
                "action": action,
                "entityType": "User",
                "entityId": user["_id"],
                "details": details,
            }
        )

    @staticmethod
    def utc_now() -> datetime:
        """Return an aware UTC timestamp for persisted auth events."""
        return datetime.now(UTC)
