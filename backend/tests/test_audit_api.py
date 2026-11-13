"""Exercise authorized audit queries against real Mongo audit documents."""

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from bson import ObjectId
from httpx import AsyncClient
from pymongo import AsyncMongoClient


async def _headers(client: AsyncClient, email: str, password: str = "KetsipDemo2025!") -> dict[str, str]:
    """Sign in a seeded actor and return bearer authorization headers."""
    response = await client.post("/api/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['token']}"}


@pytest.mark.asyncio
async def test_admin_and_auditor_can_read_sorted_login_audit(api_client: AsyncClient, started_app: AsyncMongoClient[dict[str, Any]]) -> None:
    """Serve login events to administrators and auditors in UTC descending order."""
    admin = await _headers(api_client, "admin@ketsip.local", "TestAdminPassword123!")
    actor = await api_client.post("/api/auth/login", json={"email": "executive@ketsip.local", "password": "KetsipDemo2025!"})
    database = started_app.get_database("ketsip_test")
    listing = await api_client.get("/api/audit-logs?action=login&page=1&pageSize=20", headers=admin)
    assert listing.status_code == 200
    payload = listing.json()
    assert set(payload) == {"items", "page", "pageSize", "total"}
    assert payload["items"]
    assert all(item["action"] == "login" and item["entityType"] == "auth" for item in payload["items"])
    timestamps = [datetime.fromisoformat(item["timestamp"].replace("Z", "+00:00")) for item in payload["items"]]
    assert timestamps == sorted(timestamps, reverse=True)
    user_id = actor.json()["user"]["id"]
    filtered = await api_client.get(f"/api/audit-logs?userId={user_id}&action=login", headers=admin)
    assert filtered.status_code == 200 and all(item["userId"] == user_id for item in filtered.json()["items"])
    auditor = await _headers(api_client, "auditor@ketsip.local")
    assert (await api_client.get("/api/audit-logs", headers=auditor)).status_code == 200
    assert await database["audit_logs"].count_documents({"action": "login"}) >= 2


@pytest.mark.asyncio
async def test_audit_denies_non_auditors_and_unauthenticated_users(api_client: AsyncClient) -> None:
    """Keep audit history unavailable to roles other than administrators and auditors."""
    assert (await api_client.get("/api/audit-logs")).status_code == 401
    for email in ("executive@ketsip.local", "engineer@ketsip.local", "readonly@ketsip.local"):
        headers = await _headers(api_client, email)
        assert (await api_client.get("/api/audit-logs", headers=headers)).status_code == 403


@pytest.mark.asyncio
async def test_audit_filters_date_bounds_pagination_and_invalid_values(api_client: AsyncClient, started_app: AsyncMongoClient[dict[str, Any]]) -> None:
    """Search by actor and UTC interval with bounded pagination and safe validation."""
    headers = await _headers(api_client, "admin@ketsip.local", "TestAdminPassword123!")
    database = started_app.get_database("ketsip_test")
    now = datetime.now(UTC)
    user = await database["users"].find_one({"email": "engineer@ketsip.local"})
    assert user is not None
    for delta in range(3):
        await database["audit_logs"].insert_one({
            "timestamp": now + timedelta(seconds=delta), "userId": user["_id"], "userName": user["name"],
            "action": "edit", "entityType": "user", "entityId": user["_id"], "details": f"Seeded audit {delta}",
        })
    page = await api_client.get(f"/api/audit-logs?userId={user['_id']}&action=edit&page=1&pageSize=2", headers=headers)
    assert page.status_code == 200 and len(page.json()["items"]) == 2 and page.json()["total"] == 3
    assert page.json()["items"][0]["details"] == "Seeded audit 2"
    interval = await api_client.get("/api/audit-logs", params={
        "userId": str(user["_id"]), "from": now.isoformat(), "to": (now + timedelta(seconds=1)).isoformat(),
    }, headers=headers)
    assert interval.status_code == 200 and interval.json()["total"] == 2
    assert (await api_client.get("/api/audit-logs?pageSize=101", headers=headers)).status_code == 422
    assert (await api_client.get("/api/audit-logs?userId=invalid", headers=headers)).status_code == 422
    assert (await api_client.get("/api/audit-logs?from=not-a-date", headers=headers)).status_code == 422
    assert (await api_client.get("/api/audit-logs", params={
        "from": (now + timedelta(days=1)).isoformat(), "to": now.isoformat(),
    }, headers=headers)).status_code == 422
