"""Exercise portfolio APIs through the live app and real MongoDB fixtures."""

from typing import Any

import pytest
from bson import ObjectId
from httpx import AsyncClient
from pymongo import AsyncMongoClient

from app.main import app


async def _token(client: AsyncClient, email: str, password: str = "KetsipDemo2025!") -> dict[str, str]:
    """Authenticate a seeded role account and return bearer headers."""
    response = await client.post("/api/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['token']}"}


@pytest.mark.asyncio
async def test_visible_scope_and_filters_are_applied_before_list_count(api_client: AsyncClient) -> None:
    """Return only assigned portfolios and count the filtered visible set."""
    leader_headers = await _token(api_client, "portfolio.leader@ketsip.local")
    response = await api_client.get("/api/portfolios?status=Active&page=1&pageSize=10", headers=leader_headers)
    assert response.status_code == 200
    payload = response.json()
    assert set(payload) == {"items", "page", "pageSize", "total"}
    assert payload["total"] == len(payload["items"]) == 1
    assert payload["items"][0]["name"] == "Payments"

    area_filtered = await api_client.get(
        "/api/portfolios?status=Active&productArea=Payments&page=1&pageSize=10", headers=leader_headers
    )
    assert area_filtered.status_code == 200 and area_filtered.json()["total"] == 1
    search_filtered = await api_client.get("/api/portfolios?search=Customer", headers=leader_headers)
    assert search_filtered.status_code == 200 and search_filtered.json()["total"] == 0
    assert (await api_client.get("/api/portfolios?pageSize=101", headers=leader_headers)).status_code == 422


@pytest.mark.asyncio
async def test_detail_and_linked_applications_include_derived_measures(api_client: AsyncClient) -> None:
    """Return linked applications and an arithmetic quality mean in detail."""
    headers = await _token(api_client, "admin@ketsip.local", "TestAdminPassword123!")
    listed = await api_client.get("/api/portfolios?search=Payments", headers=headers)
    assert listed.status_code == 200
    portfolio = listed.json()["items"][0]
    detail = await api_client.get(f"/api/portfolios/{portfolio['id']}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["applicationCount"] == 3
    assert detail.json()["qualityScore"] == pytest.approx((78 + 86 + 73) / 3)
    applications = await api_client.get(f"/api/portfolios/{portfolio['id']}/applications?page=1&pageSize=2", headers=headers)
    assert applications.status_code == 200
    assert applications.json()["total"] == 3
    assert len(applications.json()["items"]) == 2
    assert all(app["portfolioId"] == portfolio["id"] for app in applications.json()["items"])


@pytest.mark.asyncio
async def test_admin_crud_duplicate_conflict_and_unlinked_delete_audits(
    api_client: AsyncClient, started_app: AsyncMongoClient[dict[str, Any]]
) -> None:
    """Create, update, reject duplicate names, and delete an unlinked portfolio."""
    headers = await _token(api_client, "admin@ketsip.local", "TestAdminPassword123!")
    response = await api_client.post("/api/portfolios", headers=headers, json={
        "name": "New Portfolio", "owner": "Architecture", "description": "New inventory group",
        "productArea": "Core Platform", "status": "Active",
    })
    assert response.status_code == 201
    portfolio_id = response.json()["id"]
    assert response.json()["applicationCount"] == 0 and response.json()["qualityScore"] is None
    duplicate = await api_client.post("/api/portfolios", headers=headers, json={
        "name": "New Portfolio", "owner": "Another owner", "description": "Duplicate",
        "productArea": "Core Platform", "status": "Active",
    })
    assert duplicate.status_code == 409
    update = await api_client.put(f"/api/portfolios/{portfolio_id}", headers=headers, json={"owner": "Updated Architecture"})
    assert update.status_code == 200 and update.json()["owner"] == "Updated Architecture"
    invalid = await api_client.put(f"/api/portfolios/{portfolio_id}", headers=headers, json={"status": "Draft"})
    assert invalid.status_code == 422
    deleted = await api_client.delete(f"/api/portfolios/{portfolio_id}", headers=headers)
    assert deleted.status_code == 204
    database = started_app.get_database("ketsip_test")
    assert await database["portfolios"].find_one({"_id": ObjectId(portfolio_id)}) is None
    audits = await database["audit_logs"].count_documents({"entityType": "portfolio", "entityId": ObjectId(portfolio_id)})
    assert audits == 3


@pytest.mark.asyncio
async def test_referenced_delete_and_out_of_scope_reads_are_denied_consistently(
    api_client: AsyncClient, started_app: AsyncMongoClient[dict[str, Any]]
) -> None:
    """Preserve referenced data on delete conflict and hide inaccessible details."""
    admin = await _token(api_client, "admin@ketsip.local", "TestAdminPassword123!")
    visible = await api_client.get("/api/portfolios?search=Payments", headers=admin)
    portfolio_id = visible.json()["items"][0]["id"]
    database = started_app.get_database("ketsip_test")
    portfolio_object_id = ObjectId(portfolio_id)
    application_count = await database["applications"].count_documents({"portfolioId": portfolio_object_id})
    audits_before = await database["audit_logs"].count_documents({"entityType": "portfolio", "action": "delete"})

    conflict = await api_client.delete(f"/api/portfolios/{portfolio_id}", headers=admin)

    assert conflict.status_code == 409
    assert await database["portfolios"].find_one({"_id": portfolio_object_id}) is not None
    assert await database["applications"].count_documents({"portfolioId": portfolio_object_id}) == application_count
    assert await database["audit_logs"].count_documents({"entityType": "portfolio", "action": "delete"}) == audits_before

    leader = await _token(api_client, "portfolio.leader@ketsip.local")
    other_portfolio = await database["portfolios"].find_one({"name": "Customer Platform"})
    assert other_portfolio is not None
    for endpoint in (
        f"/api/portfolios/{other_portfolio['_id']}",
        f"/api/portfolios/{other_portfolio['_id']}/applications",
    ):
        denied = await api_client.get(endpoint, headers=leader)
        assert denied.status_code == 404

    engineer = await _token(api_client, "engineer@ketsip.local")
    denied_mutation = await api_client.post("/api/portfolios", headers=engineer, json={
        "name": "Unauthorized Portfolio", "owner": "Engineering", "description": "Should not persist",
        "productArea": "Core Platform", "status": "Active",
    })
    assert denied_mutation.status_code == 403
    assert (await api_client.get("/api/portfolios")).status_code == 401
