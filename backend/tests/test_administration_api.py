"""Exercise user and role administration through real Mongo-backed HTTP routes."""

from typing import Any

import pytest
from bson import ObjectId
from httpx import AsyncClient
from pymongo import AsyncMongoClient


async def _admin_headers(client: AsyncClient) -> dict[str, str]:
    """Sign in using the isolated fixture's seeded platform administrator."""
    response = await client.post("/api/auth/login", json={"email": "admin@ketsip.local", "password": "TestAdminPassword123!"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['token']}"}


async def _login_headers(client: AsyncClient, email: str) -> dict[str, str]:
    """Sign in a seeded non-administrator for direct-route authorization checks."""
    response = await client.post("/api/auth/login", json={"email": email, "password": "KetsipDemo2025!"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['token']}"}


@pytest.mark.asyncio
async def test_user_crud_reactivation_and_safe_responses(api_client: AsyncClient, started_app: AsyncMongoClient[dict[str, Any]]) -> None:
    """Create, read, edit, deactivate, and reactivate while preserving history."""
    headers = await _admin_headers(api_client)
    created = await api_client.post("/api/users", headers=headers, json={
        "name": "Managed Person", "email": "managed@example.com", "role": "Engineer", "password": "ManagedPassword123!",
    })
    assert created.status_code == 201
    account = created.json()
    assert account["status"] == "Active"
    assert "passwordHash" not in account and "password" not in account
    user_id = account["id"]
    assert (await api_client.get(f"/api/users/{user_id}", headers=headers)).json()["email"] == "managed@example.com"
    changed = await api_client.put(f"/api/users/{user_id}", headers=headers, json={"name": "Managed Updated", "role": "Portfolio Leader"})
    assert changed.status_code == 200 and changed.json()["role"] == "Portfolio Leader"
    deactivated = await api_client.delete(f"/api/users/{user_id}", headers=headers)
    assert deactivated.status_code == 200 and deactivated.json()["status"] == "Inactive"
    reactivated = await api_client.put(f"/api/users/{user_id}", headers=headers, json={"status": "Active"})
    assert reactivated.status_code == 200 and reactivated.json()["status"] == "Active"
    database = started_app.get_database("ketsip_test")
    stored = await database["users"].find_one({"_id": ObjectId(user_id)})
    assert stored is not None and stored["passwordHash"] != "ManagedPassword123!"
    assert await database["audit_logs"].count_documents({"entityType": "user", "entityId": ObjectId(user_id)}) == 4


@pytest.mark.asyncio
async def test_user_list_is_bounded_and_never_exposes_hash(api_client: AsyncClient) -> None:
    """Return stable page fields and safe user entries."""
    response = await api_client.get("/api/users?page=1&pageSize=2", headers=await _admin_headers(api_client))
    assert response.status_code == 200
    payload = response.json()
    assert set(payload) == {"items", "page", "pageSize", "total"}
    assert payload["pageSize"] == 2 and len(payload["items"]) == 2
    assert all("passwordHash" not in item for item in payload["items"])


@pytest.mark.asyncio
async def test_user_creation_rejects_bad_role_and_invalid_portfolio_reference(api_client: AsyncClient) -> None:
    """Reject unsupported role names and nonexistent portfolio references before persistence."""
    headers = await _admin_headers(api_client)
    base = {"name": "Invalid User", "email": "invalid@example.com", "password": "ManagedPassword123!"}
    bad_role = await api_client.post("/api/users", headers=headers, json={**base, "role": "Superuser"})
    assert bad_role.status_code == 422
    bad_portfolio = await api_client.post("/api/users", headers=headers, json={**base, "role": "Engineer", "portfolioAccess": [str(ObjectId())]})
    assert bad_portfolio.status_code == 422


@pytest.mark.asyncio
async def test_user_missing_ids_duplicate_email_and_invalid_page_are_rejected(api_client: AsyncClient) -> None:
    """Return appropriate not-found, conflict, and bounded-pagination errors."""
    headers = await _admin_headers(api_client)
    assert (await api_client.get("/api/users/not-an-id", headers=headers)).status_code == 404
    assert (await api_client.put("/api/users/not-an-id", headers=headers, json={"status": "Active"})).status_code == 404
    assert (await api_client.delete("/api/users/not-an-id", headers=headers)).status_code == 404
    duplicate = await api_client.post("/api/users", headers=headers, json={
        "name": "Duplicate", "email": "executive@ketsip.local", "role": "Engineer", "password": "ManagedPassword123!",
    })
    assert duplicate.status_code == 409
    assert (await api_client.get("/api/users?pageSize=101", headers=headers)).status_code == 422


@pytest.mark.asyncio
async def test_only_administer_role_can_access_user_and_role_management(api_client: AsyncClient) -> None:
    """Reject direct user and role management calls for every non-admin role sample."""
    for email in ("executive@ketsip.local", "engineer@ketsip.local", "auditor@ketsip.local", "readonly@ketsip.local"):
        headers = await _login_headers(api_client, email)
        assert (await api_client.get("/api/users", headers=headers)).status_code == 403
        assert (await api_client.get("/api/roles", headers=headers)).status_code == 403
        assert (await api_client.post("/api/users", headers=headers, json={})).status_code == 403


@pytest.mark.asyncio
async def test_user_and_role_management_require_authentication(api_client: AsyncClient) -> None:
    """Reject requests without bearer credentials before management work."""
    assert (await api_client.get("/api/users")).status_code == 401
    assert (await api_client.get("/api/roles")).status_code == 401


@pytest.mark.asyncio
async def test_role_edit_changes_persist_and_emit_one_permission_audit(api_client: AsyncClient, started_app: AsyncMongoClient[dict[str, Any]]) -> None:
    """List only six roles and audit exactly one changed permission set."""
    headers = await _admin_headers(api_client)
    listing = await api_client.get("/api/roles", headers=headers)
    assert listing.status_code == 200 and len(listing.json()) == 6
    engineer = next(role for role in listing.json() if role["name"] == "Engineer")
    permissions = list(engineer["permissions"])
    updated = await api_client.put("/api/roles/Engineer", headers=headers, json={"description": engineer["description"], "permissions": ["view", "edit"]})
    assert updated.status_code == 200 and updated.json()["permissions"] == ["view", "edit"]
    database = started_app.get_database("ketsip_test")
    assert await database["roles"].count_documents({}) == 6
    assert await database["audit_logs"].count_documents({"action": "permissionChange", "entityType": "role"}) == 1
    await api_client.put("/api/roles/Engineer", headers=headers, json={"description": engineer["description"], "permissions": permissions})


@pytest.mark.asyncio
async def test_roles_reject_unsupported_role_permissions_duplicates_and_missing_role(api_client: AsyncClient) -> None:
    """Reject new role names, unsupported capabilities, duplicates, and missing role records."""
    headers = await _admin_headers(api_client)
    payload = {"description": "Known role", "permissions": ["view"]}
    assert (await api_client.put("/api/roles/Unrecognized", headers=headers, json=payload)).status_code == 404
    assert (await api_client.put("/api/roles/Engineer", headers=headers, json={"description": "x", "permissions": ["admin"]})).status_code == 422
    assert (await api_client.put("/api/roles/Engineer", headers=headers, json={"description": "x", "permissions": ["view", "view"]})).status_code == 422
    assert (await api_client.put("/api/roles/Engineer", headers=headers, json={"description": "x", "permissions": ["view"], "extra": True})).status_code == 422
