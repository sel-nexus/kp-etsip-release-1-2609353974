"""Verify auth service behavior against the isolated real Mongo database."""

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from bson import ObjectId
from fastapi import HTTPException
from jose import jwt
from pymongo import AsyncMongoClient

from app.core.config import settings
from app.repositories.users import UsersRepository
from app.services.auth import AuthService, JWT_ALGORITHM, PASSWORD_CONTEXT

settings.JWT_SECRET = "auth-profile-test-signing-key-with-at-least-32-characters"


def make_service(database: Any) -> AuthService:
    """Bind the production service to a real test database."""
    return AuthService(UsersRepository(database))


@pytest.mark.asyncio
async def test_login_issues_eight_hour_token_and_audits_success(started_app: AsyncMongoClient[dict[str, Any]]) -> None:
    """Authenticate a seeded active user and persist its successful audit event."""
    database = started_app.get_database("ketsip_test")
    service = make_service(database)
    token, profile = await service.login("executive@ketsip.local", "KetsipDemo2025!")
    claims = jwt.decode(token, settings.JWT_SECRET, algorithms=[JWT_ALGORITHM])
    assert claims["sub"] == profile.id
    assert datetime.fromtimestamp(claims["exp"], UTC) - datetime.fromtimestamp(claims["iat"], UTC) == timedelta(hours=8)
    assert profile.role == "Executive"
    assert not hasattr(profile, "passwordHash")
    assert await database["audit_logs"].count_documents({"action": "login", "userId": ObjectId(profile.id)}) == 1


@pytest.mark.asyncio
async def test_invalid_login_is_generic_and_audits_unknown_actor(started_app: AsyncMongoClient[dict[str, Any]]) -> None:
    """Audit unknown email failures without recording the attempted email or secret."""
    database = started_app.get_database("ketsip_test")
    service = make_service(database)
    with pytest.raises(HTTPException) as raised:
        await service.login("missing@ketsip.local", "not-a-password")
    assert raised.value.status_code == 401
    assert raised.value.detail == "Invalid email or password."
    audit = await database["audit_logs"].find_one({"action": "login", "details": "Local account authentication failed"})
    assert audit is not None
    assert audit["userId"] == ObjectId("000000000000000000000000")
    assert audit["userName"] == "Unknown login actor"
    assert "missing@ketsip.local" not in audit["details"]
    assert "not-a-password" not in audit["details"]


@pytest.mark.asyncio
async def test_inactive_user_login_is_generic_and_audited(started_app: AsyncMongoClient[dict[str, Any]]) -> None:
    """Reject an inactive account with the same public message as bad credentials."""
    database = started_app.get_database("ketsip_test")
    await database["users"].update_one({"email": "executive@ketsip.local"}, {"$set": {"status": "Inactive"}})
    service = make_service(database)
    with pytest.raises(HTTPException) as raised:
        await service.login("executive@ketsip.local", "KetsipDemo2025!")
    assert raised.value.status_code == 401
    assert raised.value.detail == "Invalid email or password."
    assert await database["audit_logs"].count_documents({"action": "login", "details": "Local account authentication failed"}) == 1


@pytest.mark.asyncio
async def test_token_reload_rejects_inactive_current_user(started_app: AsyncMongoClient[dict[str, Any]]) -> None:
    """Reject a valid signed token once its persisted user becomes inactive."""
    database = started_app.get_database("ketsip_test")
    service = make_service(database)
    token, profile = await service.login("executive@ketsip.local", "KetsipDemo2025!")
    await database["users"].update_one({"_id": ObjectId(profile.id)}, {"$set": {"status": "Inactive"}})
    with pytest.raises(HTTPException) as raised:
        await service.authenticate_token(token)
    assert raised.value.status_code == 401


@pytest.mark.asyncio
async def test_change_password_reloads_persisted_state(started_app: AsyncMongoClient[dict[str, Any]]) -> None:
    """Verify password and first-login transition by reading the stored document."""
    database = started_app.get_database("ketsip_test")
    raw = await database["users"].find_one({"email": "admin@ketsip.local"})
    assert raw is not None
    service = make_service(database)
    user = await service.get_current_user(str(raw["_id"]))
    updated = await service.change_password(user, "TestAdminPassword123!", "NewAdminPassword123!")
    persisted = await database["users"].find_one({"_id": raw["_id"]})
    assert updated.mustChangePassword is False
    assert persisted is not None and persisted["mustChangePassword"] is False
    assert PASSWORD_CONTEXT.verify("NewAdminPassword123!", persisted["passwordHash"])
    assert persisted["passwordHash"] != "NewAdminPassword123!"


@pytest.mark.asyncio
async def test_landing_preferences_are_role_authorized(started_app: AsyncMongoClient[dict[str, Any]]) -> None:
    """Keep role-inaccessible dashboard preferences from being persisted."""
    database = started_app.get_database("ketsip_test")
    service = make_service(database)
    user = await service.get_current_user(str((await database["users"].find_one({"email": "engineer@ketsip.local"}))["_id"]))
    with pytest.raises(HTTPException) as raised:
        await service.set_landing_page(user, "/dashboard")
    assert raised.value.status_code == 403
    persisted = await database["users"].find_one({"_id": ObjectId(user["_id"])})
    assert persisted is not None and persisted.get("defaultLandingPage") is None


@pytest.mark.asyncio
async def test_password_change_rejects_same_secret_without_changing_state(started_app: AsyncMongoClient[dict[str, Any]]) -> None:
    """Reject reusing the current secret without changing the stored hash or first-login flag."""
    database = started_app.get_database("ketsip_test")
    raw = await database["users"].find_one({"email": "admin@ketsip.local"})
    assert raw is not None
    service = make_service(database)

    with pytest.raises(HTTPException) as raised:
        await service.change_password(
            await service.get_current_user(str(raw["_id"])),
            "TestAdminPassword123!",
            "TestAdminPassword123!",
        )

    assert raised.value.status_code == 422
    assert raised.value.detail == "Choose a new password different from the current password."
    persisted = await database["users"].find_one({"_id": raw["_id"]})
    assert persisted is not None
    assert persisted["passwordHash"] == raw["passwordHash"]
    assert persisted["mustChangePassword"] is True
    assert await database["audit_logs"].count_documents({"action": "edit", "userId": raw["_id"]}) == 0


class ConcurrentPasswordUpdateRepository(UsersRepository):
    """Change a real Mongo credential immediately before its conditional update."""

    def __init__(self, database: Any, competing_hash: str) -> None:
        super().__init__(database)
        self.competing_hash = competing_hash

    async def update_password(
        self,
        user_id: ObjectId,
        current_hash: str,
        new_hash: str,
        at: datetime,
    ) -> dict[str, Any] | None:
        await self.users.update_one({"_id": user_id}, {"$set": {"passwordHash": self.competing_hash}})
        return await super().update_password(user_id, current_hash, new_hash, at)


@pytest.mark.asyncio
async def test_password_change_rejects_conditional_update_conflict_without_overwriting_concurrent_change(
    started_app: AsyncMongoClient[dict[str, Any]],
) -> None:
    """Preserve a concurrent real-Mongo credential change when the CAS update no longer matches."""
    database = started_app.get_database("ketsip_test")
    raw = await database["users"].find_one({"email": "admin@ketsip.local"})
    assert raw is not None
    competing_password = "ConcurrentAdminPassword456!"
    competing_hash = PASSWORD_CONTEXT.hash(competing_password)
    service = AuthService(ConcurrentPasswordUpdateRepository(database, competing_hash))

    with pytest.raises(HTTPException) as raised:
        await service.change_password(
            await service.get_current_user(str(raw["_id"])),
            "TestAdminPassword123!",
            "NewAdminPassword123!",
        )

    assert raised.value.status_code == 409
    assert raised.value.detail == "The account changed. Please retry."
    persisted = await database["users"].find_one({"_id": raw["_id"]})
    assert persisted is not None
    assert persisted["passwordHash"] == competing_hash
    assert PASSWORD_CONTEXT.verify(competing_password, persisted["passwordHash"])
    assert persisted["mustChangePassword"] is True
    assert await database["audit_logs"].count_documents({"action": "edit", "userId": raw["_id"]}) == 0


@pytest.mark.asyncio
async def test_password_change_rejects_wrong_current_secret(started_app: AsyncMongoClient[dict[str, Any]]) -> None:
    """Leave persisted credentials unchanged when the submitted current password is wrong."""
    database = started_app.get_database("ketsip_test")
    raw = await database["users"].find_one({"email": "executive@ketsip.local"})
    assert raw is not None
    service = make_service(database)
    with pytest.raises(HTTPException) as raised:
        await service.change_password(await service.get_current_user(str(raw["_id"])), "incorrect", "NewPassword12345!")
    assert raised.value.status_code == 400
    persisted = await database["users"].find_one({"_id": raw["_id"]})
    assert persisted is not None and PASSWORD_CONTEXT.verify("KetsipDemo2025!", persisted["passwordHash"])


@pytest.mark.asyncio
async def test_token_signature_and_expiry_are_checked(started_app: AsyncMongoClient[dict[str, Any]]) -> None:
    """Reject invalid signatures and expired tokens before loading an actor."""
    service = make_service(started_app.get_database("ketsip_test"))
    with pytest.raises(HTTPException):
        await service.authenticate_token("not-a-jwt")
    expired = jwt.encode(
        {"sub": str(ObjectId()), "iat": datetime.now(UTC) - timedelta(hours=10), "exp": datetime.now(UTC) - timedelta(hours=2)},
        settings.JWT_SECRET,
        algorithm=JWT_ALGORITHM,
    )
    with pytest.raises(HTTPException):
        await service.authenticate_token(expired)


def test_signing_secret_rejects_known_placeholders() -> None:
    """Fail closed when a JWT signing value is short or recognizable as a sample."""
    original_secret = settings.JWT_SECRET
    try:
        settings.JWT_SECRET = "dev-secret-not-for-production"
        with pytest.raises(RuntimeError, match="JWT_SECRET"):
            settings.require_jwt_secret()
    finally:
        settings.JWT_SECRET = original_secret
