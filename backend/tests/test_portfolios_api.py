"""Exercise portfolio APIs through the live app and real MongoDB fixtures."""

from typing import Any

import pytest
from bson import ObjectId
from httpx import AsyncClient
from pymongo import AsyncMongoClient

from app.main import app


PORTFOLIO_FIELDS = ("name", "owner", "description", "productArea", "status")


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
    database = started_app.get_database("ketsip_test")
    stored_after_update = await database["portfolios"].find_one({"_id": ObjectId(portfolio_id)})
    assert stored_after_update is not None and stored_after_update["owner"] == "Updated Architecture"
    invalid = await api_client.put(f"/api/portfolios/{portfolio_id}", headers=headers, json={"status": "Draft"})
    assert invalid.status_code == 422
    assert await database["portfolios"].find_one({"_id": ObjectId(portfolio_id)}) == stored_after_update
    deleted = await api_client.delete(f"/api/portfolios/{portfolio_id}", headers=headers)
    assert deleted.status_code == 204
    assert await database["portfolios"].find_one({"_id": ObjectId(portfolio_id)}) is None
    audits = await database["audit_logs"].count_documents({"entityType": "portfolio", "entityId": ObjectId(portfolio_id)})
    assert audits == 3


@pytest.mark.asyncio
async def test_portfolio_create_and_update_reject_missing_types_and_bounds_without_state_changes(
    api_client: AsyncClient, started_app: AsyncMongoClient[dict[str, Any]]
) -> None:
    """Return 422 for invalid portfolio request shapes and preserve Mongo/audit state."""
    headers = await _token(api_client, "admin@ketsip.local", "TestAdminPassword123!")
    database = started_app.get_database("ketsip_test")
    existing = await database["portfolios"].find_one({"name": "Payments"})
    assert existing
    baseline = await database["portfolios"].find_one({"_id": existing["_id"]})
    portfolio_count = await database["portfolios"].count_documents({})
    audit_count = await database["audit_logs"].count_documents({"entityType": "portfolio"})
    valid = {
        "name": "Validation Portfolio",
        "owner": "Architecture",
        "description": "Complete portfolio payload",
        "productArea": "Core Platform",
        "status": "Active",
    }

    missing_create_field = dict(valid)
    missing_create_field.pop("owner")
    rejected_creates = (
        missing_create_field,
        valid | {"name": ["not", "a", "string"]},
        valid | {"owner": {"$ne": ""}},
        valid | {"description": "d" * 1001},
    )
    for payload in rejected_creates:
        response = await api_client.post("/api/portfolios", headers=headers, json=payload)
        assert response.status_code == 422
        assert await database["portfolios"].count_documents({}) == portfolio_count
        assert await database["audit_logs"].count_documents({"entityType": "portfolio"}) == audit_count

    rejected_updates = (
        {},
        {"owner": ["not", "a", "string"]},
        {"status": {"$ne": "Archived"}},
        {"name": ""},
        {"description": "d" * 1001},
        {"$set": {"owner": "Injected owner"}},
    )
    for payload in rejected_updates:
        response = await api_client.put(f"/api/portfolios/{existing['_id']}", headers=headers, json=payload)
        assert response.status_code == 422
        assert await database["portfolios"].find_one({"_id": existing["_id"]}) == baseline
        assert await database["portfolios"].count_documents({}) == portfolio_count
        assert await database["audit_logs"].count_documents({"entityType": "portfolio"}) == audit_count


@pytest.mark.parametrize("missing_field", PORTFOLIO_FIELDS)
@pytest.mark.asyncio
async def test_portfolio_create_rejects_each_missing_required_field_without_writes(
    api_client: AsyncClient,
    started_app: AsyncMongoClient[dict[str, Any]],
    missing_field: str,
) -> None:
    """Require each PortfolioCreate field and preserve Mongo/audit state on rejection."""
    headers = await _token(api_client, "admin@ketsip.local", "TestAdminPassword123!")
    database = started_app.get_database("ketsip_test")
    portfolio_count = await database["portfolios"].count_documents({})
    audit_count = await database["audit_logs"].count_documents({"entityType": "portfolio"})
    payload = {
        "name": "Each Field Validation Portfolio",
        "owner": "Architecture",
        "description": "Complete portfolio payload",
        "productArea": "Core Platform",
        "status": "Active",
    }
    payload.pop(missing_field)

    response = await api_client.post("/api/portfolios", headers=headers, json=payload)

    assert response.status_code == 422
    assert await database["portfolios"].count_documents({}) == portfolio_count
    assert await database["audit_logs"].count_documents({"entityType": "portfolio"}) == audit_count
    assert await database["portfolios"].find_one({"name": "Each Field Validation Portfolio"}) is None


@pytest.mark.parametrize("missing_field", PORTFOLIO_FIELDS)
@pytest.mark.asyncio
async def test_portfolio_update_allows_each_omitted_optional_field_and_preserves_it(
    api_client: AsyncClient,
    started_app: AsyncMongoClient[dict[str, Any]],
    missing_field: str,
) -> None:
    """PortfolioUpdate permits omitted fields and leaves their stored values unchanged."""
    headers = await _token(api_client, "admin@ketsip.local", "TestAdminPassword123!")
    database = started_app.get_database("ketsip_test")
    existing = await database["portfolios"].find_one({"name": "Payments"})
    assert existing is not None
    baseline = await database["portfolios"].find_one({"_id": existing["_id"]})
    portfolio_count = await database["portfolios"].count_documents({})
    audit_count = await database["audit_logs"].count_documents({"entityType": "portfolio"})
    payload = {
        "name": f"Updated {baseline['name']}",
        "owner": f"Updated {baseline['owner']}",
        "description": f"Updated {baseline['description']}",
        "productArea": f"Updated {baseline['productArea']}",
        "status": "Archived" if baseline["status"] == "Active" else "Active",
    }
    payload.pop(missing_field)

    response = await api_client.put(
        f"/api/portfolios/{existing['_id']}", headers=headers, json=payload
    )

    assert response.status_code == 200
    stored = await database["portfolios"].find_one({"_id": existing["_id"]})
    assert stored is not None and stored[missing_field] == baseline[missing_field]
    assert await database["portfolios"].count_documents({}) == portfolio_count
    assert await database["audit_logs"].count_documents({"entityType": "portfolio"}) == audit_count + 1


@pytest.mark.asyncio
async def test_absent_portfolio_object_id_get_put_delete_return_404_without_changes(
    api_client: AsyncClient, started_app: AsyncMongoClient[dict[str, Any]]
) -> None:
    """Return 404 for each operation on a valid ObjectId that is not in Mongo."""
    headers = await _token(api_client, "admin@ketsip.local", "TestAdminPassword123!")
    database = started_app.get_database("ketsip_test")
    absent_id = ObjectId()
    portfolio_count = await database["portfolios"].count_documents({})
    audit_count = await database["audit_logs"].count_documents({"entityType": "portfolio"})

    get_response = await api_client.get(f"/api/portfolios/{absent_id}", headers=headers)
    put_response = await api_client.put(
        f"/api/portfolios/{absent_id}", headers=headers, json={"owner": "Must not exist"}
    )
    delete_response = await api_client.delete(f"/api/portfolios/{absent_id}", headers=headers)

    assert get_response.status_code == put_response.status_code == delete_response.status_code == 404
    assert await database["portfolios"].find_one({"_id": absent_id}) is None
    assert await database["portfolios"].count_documents({}) == portfolio_count
    assert await database["audit_logs"].count_documents({"entityType": "portfolio"}) == audit_count


@pytest.mark.asyncio
async def test_portfolio_search_is_literal_scoped_and_html_path_text_is_inert(
    api_client: AsyncClient, started_app: AsyncMongoClient[dict[str, Any]]
) -> None:
    """Prevent regex-shaped queries from widening scope and keep submitted text inert."""
    database = started_app.get_database("ketsip_test")
    leader = await _token(api_client, "portfolio.leader@ketsip.local")
    for search in (".*", "{\"$ne\":null}", "(?s).*Customer"):
        response = await api_client.get("/api/portfolios", headers=leader, params={"search": search})
        assert response.status_code == 200
        assert response.json()["total"] == 0
        assert all(item["name"] == "Payments" for item in response.json()["items"])

    admin = await _token(api_client, "admin@ketsip.local", "TestAdminPassword123!")
    html_text = "<script>window.__portfolio_test__ = true</script>"
    path_text = "../../etc/passwd"
    portfolio_count_before = await database["portfolios"].count_documents({})
    audit_count_before = await database["audit_logs"].count_documents({"entityType": "portfolio"})
    payload = {
        "name": "Literal security text portfolio",
        "owner": path_text,
        "description": html_text,
        "productArea": "Core Platform",
        "status": "Active",
    }
    created = await api_client.post("/api/portfolios", headers=admin, json=payload)
    assert created.status_code == 201
    stored = await database["portfolios"].find_one({"_id": ObjectId(created.json()["id"])})
    assert stored is not None
    assert stored["description"] == html_text
    assert stored["owner"] == path_text
    detail = await api_client.get(f"/api/portfolios/{created.json()['id']}", headers=admin)
    assert detail.status_code == 200
    assert "application/json" in detail.headers["content-type"]
    assert detail.json()["description"] == html_text

    operator = await api_client.post(
        "/api/portfolios", headers=admin, json=payload | {"name": {"$ne": ""}}
    )
    assert operator.status_code == 422
    assert await database["portfolios"].count_documents({}) == portfolio_count_before + 1
    assert await database["audit_logs"].count_documents({"entityType": "portfolio"}) == audit_count_before + 1


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
