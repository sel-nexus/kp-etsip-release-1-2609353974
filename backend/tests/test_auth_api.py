"""Exercise the complete auth HTTP surface with real MongoDB persistence."""

from typing import Any

import pytest
from bson import ObjectId
from httpx import AsyncClient
from pymongo import AsyncMongoClient

from app.core.config import settings

settings.JWT_SECRET = "auth-profile-api-test-signing-key-with-at-least-32-characters"


@pytest.mark.asyncio
async def test_login_me_and_logout_use_signed_bearer_contract(
    api_client: AsyncClient,
    started_app: AsyncMongoClient[dict[str, Any]],
) -> None:
    """Sign in, read the response-backed current profile, and acknowledge logout."""
    response = await api_client.post("/api/auth/login", json={"email": "executive@ketsip.local", "password": "KetsipDemo2025!"})
    assert response.status_code == 200
    payload = response.json()
    assert set(payload) == {"token", "user"}
    assert payload["user"]["role"] == "Executive"
    assert payload["user"]["landingPage"] == "/dashboard"
    assert "passwordHash" not in payload["user"]
    headers = {"Authorization": f"Bearer {payload['token']}"}
    profile = await api_client.get("/api/auth/me", headers=headers)
    assert profile.status_code == 200
    assert profile.json()["email"] == "executive@ketsip.local"
    logout = await api_client.post("/api/auth/logout", headers=headers)
    assert logout.status_code == 200 and logout.json() == {"success": True}
    database = started_app.get_database("ketsip_test")
    assert await database["audit_logs"].count_documents({"action": "login", "userId": ObjectId(payload["user"]["id"]), "details": "Local account authentication succeeded"}) == 1


@pytest.mark.asyncio
async def test_login_bad_password_and_inactive_account_are_generic_and_audited(
    api_client: AsyncClient,
    started_app: AsyncMongoClient[dict[str, Any]],
) -> None:
    """Return generic 401 responses and durably audit failed attempts."""
    bad = await api_client.post("/api/auth/login", json={"email": "executive@ketsip.local", "password": "wrong"})
    assert bad.status_code == 401 and bad.json()["detail"] == "Invalid email or password."
    database = started_app.get_database("ketsip_test")
    await database["users"].update_one({"email": "executive@ketsip.local"}, {"$set": {"status": "Inactive"}})
    inactive = await api_client.post("/api/auth/login", json={"email": "executive@ketsip.local", "password": "KetsipDemo2025!"})
    assert inactive.status_code == 401 and inactive.json()["detail"] == "Invalid email or password."
    assert await database["audit_logs"].count_documents({"action": "login", "details": "Local account authentication failed"}) == 2


@pytest.mark.asyncio
async def test_token_rejects_forged_and_inactive_user(api_client: AsyncClient, started_app: AsyncMongoClient[dict[str, Any]]) -> None:
    """Require a valid signature and a currently active Mongo actor on /me."""
    forged = await api_client.get("/api/auth/me", headers={"Authorization": "Bearer forged.token.value"})
    assert forged.status_code == 401
    login = await api_client.post("/api/auth/login", json={"email": "executive@ketsip.local", "password": "KetsipDemo2025!"})
    token = login.json()["token"]
    user_id = login.json()["user"]["id"]
    await started_app.get_database("ketsip_test")["users"].update_one({"_id": ObjectId(user_id)}, {"$set": {"status": "Inactive"}})
    response = await api_client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_password_change_first_login_gate_and_persisted_state(
    api_client: AsyncClient,
    started_app: AsyncMongoClient[dict[str, Any]],
) -> None:
    """Permit self password rotation for seeded admin and clear normal-route gate."""
    login = await api_client.post("/api/auth/login", json={"email": "admin@ketsip.local", "password": "TestAdminPassword123!"})
    assert login.status_code == 200 and login.json()["user"]["mustChangePassword"] is True
    headers = {"Authorization": f"Bearer {login.json()['token']}"}
    profile = await api_client.get("/api/auth/me", headers=headers)
    assert profile.status_code == 200 and profile.json()["mustChangePassword"] is True
    changed = await api_client.put("/api/auth/me/password", headers=headers, json={"currentPassword": "TestAdminPassword123!", "newPassword": "AdminChangedPassword456!"})
    assert changed.status_code == 200 and changed.json()["mustChangePassword"] is False
    persisted = await started_app.get_database("ketsip_test")["users"].find_one({"email": "admin@ketsip.local"})
    assert persisted is not None and persisted["passwordHash"] != "AdminChangedPassword456!"
    assert await started_app.get_database("ketsip_test")["audit_logs"].count_documents({"action": "edit", "entityType": "User", "userId": persisted["_id"], "details": "Self-service password changed"}) == 1


@pytest.mark.asyncio
async def test_preferences_require_accessible_destination_and_invalid_token(api_client: AsyncClient) -> None:
    """Save a role-allowed preference while refusing a dashboard for an engineer."""
    login = await api_client.post("/api/auth/login", json={"email": "engineer@ketsip.local", "password": "KetsipDemo2025!"})
    headers = {"Authorization": f"Bearer {login.json()['token']}"}
    denied = await api_client.put("/api/auth/me/preferences", headers=headers, json={"defaultLandingPage": "/dashboard"})
    assert denied.status_code == 403
    allowed = await api_client.put("/api/auth/me/preferences", headers=headers, json={"defaultLandingPage": "/applications"})
    assert allowed.status_code == 200 and allowed.json()["user"]["landingPage"] == "/applications"
    unauthorized = await api_client.put("/api/auth/me/preferences", json={"defaultLandingPage": "/applications"})
    assert unauthorized.status_code == 401


@pytest.mark.asyncio
async def test_login_schema_rejects_extra_fields_and_logout_needs_token(
    api_client: AsyncClient,
    started_app: AsyncMongoClient[dict[str, Any]],
) -> None:
    """Reject malformed typed requests and unauthenticated logout attempts."""
    malformed = await api_client.post("/api/auth/login", json={"email": "bad", "password": "x", "extra": True})
    assert malformed.status_code == 422
    logout = await api_client.post("/api/auth/logout")
    assert logout.status_code == 401
