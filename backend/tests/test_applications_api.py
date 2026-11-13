"""Exercise application HTTP routes against the isolated real Mongo database."""

from typing import Any

import pytest
from bson import ObjectId
from httpx import AsyncClient
from pymongo import AsyncMongoClient


APPLICATION_REQUIRED_FIELDS = (
    "name",
    "description",
    "portfolioId",
    "productArea",
    "businessOwner",
    "technologyOwner",
    "etsOwner",
    "criticality",
    "tier",
    "lifecycleStatus",
    "technologyStack",
    "applicationHealthScore",
    "qualityScore",
    "automationCoverage",
    "unitTestCoverage",
    "openDefects",
    "openCriticalDefects",
    "riskLevel",
)


def app_payload(portfolio_id: str, name: str = "API-created application") -> dict[str, Any]:
    """Return a complete application payload suitable for the public API."""
    return {
        "name": name,
        "description": "Application record created through HTTP",
        "portfolioId": portfolio_id,
        "productArea": "Payments",
        "businessOwner": "Payments team",
        "technologyOwner": "Platform team",
        "etsOwner": "Quality office",
        "criticality": "High",
        "tier": 2,
        "lifecycleStatus": "Active",
        "technologyStack": "Python; MongoDB",
        "repositoryLink": "https://example.com/repository",
        "pipelineLink": None,
        "applicationHealthScore": 80,
        "qualityScore": 77,
        "automationCoverage": 66.5,
        "unitTestCoverage": 71,
        "openDefects": 3,
        "openCriticalDefects": 1,
        "riskLevel": "Medium",
    }


async def token(client: AsyncClient, email: str, password: str = "KetsipDemo2025!") -> dict[str, str]:
    """Sign in a seeded account and return authorization headers."""
    response = await client.post("/api/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['token']}"}


@pytest.mark.asyncio
async def test_application_list_filters_pagination_and_authentication(api_client: AsyncClient) -> None:
    """Require authentication and combine filters under the role's Mongo scope."""
    leader = await token(api_client, "portfolio.leader@ketsip.local")
    listed = await api_client.get("/api/applications?page=1&pageSize=2", headers=leader)
    assert listed.status_code == 200
    data = listed.json()
    assert set(data) == {"items", "page", "pageSize", "total"}
    assert data["total"] == 3 and len(data["items"]) == 2
    assert data["items"][0]["portfolioName"] == "Payments"

    exact = await api_client.get("/api/applications?search=Payment&criticality=Critical&lifecycleStatus=Active", headers=leader)
    assert exact.status_code == 200 and exact.json()["total"] == 1
    zero = await api_client.get("/api/applications?criticality=Low&riskLevel=High", headers=leader)
    assert zero.status_code == 200 and zero.json()["total"] == 0
    assert (await api_client.get("/api/applications?pageSize=101", headers=leader)).status_code == 422
    assert (await api_client.get("/api/applications?riskLevel=Extreme", headers=leader)).status_code == 422
    assert (await api_client.get("/api/applications")).status_code == 401


@pytest.mark.asyncio
async def test_detail_create_update_and_duplicate_conflict_with_audit(
    api_client: AsyncClient, started_app: AsyncMongoClient[dict[str, Any]]
) -> None:
    """Create, inspect, update, and reject duplicates with exact success audits."""
    headers = await token(api_client, "admin@ketsip.local", "TestAdminPassword123!")
    database = started_app.get_database("ketsip_test")
    portfolio = await database["portfolios"].find_one({"name": "Payments"})
    assert portfolio
    audit_before = await database["audit_logs"].count_documents({"entityType": "application"})

    created = await api_client.post("/api/applications", headers=headers, json=app_payload(str(portfolio["_id"])))
    assert created.status_code == 201
    application = created.json()
    assert application["portfolio"] == {"id": str(portfolio["_id"]), "name": "Payments"}
    assert "_id" not in application and isinstance(application["createdAt"], str)
    detail = await api_client.get(f"/api/applications/{application['id']}", headers=headers)
    assert detail.status_code == 200 and detail.json()["technologyStack"] == "Python; MongoDB"

    updated = await api_client.put(
        f"/api/applications/{application['id']}", headers=headers,
        json=app_payload(str(portfolio["_id"]), "Updated API application"),
    )
    assert updated.status_code == 200 and updated.json()["name"] == "Updated API application"
    stored_after_update = await database["applications"].find_one({"_id": ObjectId(application["id"])})
    assert stored_after_update is not None
    assert stored_after_update["name"] == "Updated API application"
    assert stored_after_update["technologyStack"] == "Python; MongoDB"
    duplicate = await api_client.post(
        "/api/applications", headers=headers,
        json=app_payload(str(portfolio["_id"]), "Payment Gateway"),
    )
    assert duplicate.status_code == 409
    assert await database["audit_logs"].count_documents({"entityType": "application"}) == audit_before + 2


@pytest.mark.asyncio
async def test_application_create_and_update_reject_missing_types_and_bounds_without_state_changes(
    api_client: AsyncClient, started_app: AsyncMongoClient[dict[str, Any]]
) -> None:
    """Return 422 for malformed source requests without mutating Mongo or audit history."""
    headers = await token(api_client, "admin@ketsip.local", "TestAdminPassword123!")
    database = started_app.get_database("ketsip_test")
    portfolio = await database["portfolios"].find_one({"name": "Payments"})
    existing = await database["applications"].find_one({"name": "Payment Gateway"})
    assert portfolio and existing
    baseline = await database["applications"].find_one({"_id": existing["_id"]})
    application_count = await database["applications"].count_documents({})
    audit_count = await database["audit_logs"].count_documents({"entityType": "application"})
    valid = app_payload(str(portfolio["_id"]))

    missing_create_field = dict(valid)
    missing_create_field.pop("name")
    rejected_creates = (
        missing_create_field,
        valid | {"name": None},
        valid | {"description": ["not", "a", "string"]},
        valid | {"openDefects": {"$gt": 0}},
        valid | {"qualityScore": 101},
    )
    for payload in rejected_creates:
        response = await api_client.post("/api/applications", headers=headers, json=payload)
        assert response.status_code == 422
        assert await database["applications"].count_documents({}) == application_count
        assert await database["audit_logs"].count_documents({"entityType": "application"}) == audit_count

    missing_update_field = dict(valid)
    missing_update_field.pop("qualityScore")
    rejected_updates = (
        missing_update_field,
        valid | {"tier": {"$ne": 2}},
        valid | {"automationCoverage": 100.1},
        valid | {"$set": {"name": "Injected"}},
    )
    for payload in rejected_updates:
        response = await api_client.put(
            f"/api/applications/{existing['_id']}", headers=headers, json=payload
        )
        assert response.status_code == 422
        assert await database["applications"].find_one({"_id": existing["_id"]}) == baseline
        assert await database["applications"].count_documents({}) == application_count
        assert await database["audit_logs"].count_documents({"entityType": "application"}) == audit_count


@pytest.mark.parametrize(
    ("method", "missing_field"),
    [
        (method, field)
        for method in ("POST", "PUT")
        for field in APPLICATION_REQUIRED_FIELDS
    ],
)
@pytest.mark.asyncio
async def test_application_create_and_full_replacement_reject_each_missing_required_field_without_writes(
    api_client: AsyncClient,
    started_app: AsyncMongoClient[dict[str, Any]],
    method: str,
    missing_field: str,
) -> None:
    """Reject individually omitted required fields without Mongo or audit effects."""
    headers = await token(api_client, "admin@ketsip.local", "TestAdminPassword123!")
    database = started_app.get_database("ketsip_test")
    portfolio = await database["portfolios"].find_one({"name": "Payments"})
    existing = await database["applications"].find_one({"name": "Payment Gateway"})
    assert portfolio is not None and existing is not None
    baseline = await database["applications"].find_one({"_id": existing["_id"]})
    application_count = await database["applications"].count_documents({})
    audit_count = await database["audit_logs"].count_documents({"entityType": "application"})
    payload = app_payload(str(portfolio["_id"]))
    payload.pop(missing_field)

    if method == "POST":
        response = await api_client.post("/api/applications", headers=headers, json=payload)
    else:
        response = await api_client.put(
            f"/api/applications/{existing['_id']}", headers=headers, json=payload
        )

    assert response.status_code == 422
    assert await database["applications"].count_documents({}) == application_count
    assert await database["audit_logs"].count_documents({"entityType": "application"}) == audit_count
    assert await database["applications"].find_one({"_id": existing["_id"]}) == baseline


@pytest.mark.asyncio
async def test_application_oversized_bounded_text_fields_and_request_payload_are_rejected_without_writes(
    api_client: AsyncClient, started_app: AsyncMongoClient[dict[str, Any]]
) -> None:
    """Reject over-limit source strings on create and update without Mongo or audit changes."""
    headers = await token(api_client, "admin@ketsip.local", "TestAdminPassword123!")
    database = started_app.get_database("ketsip_test")
    portfolio = await database["portfolios"].find_one({"name": "Payments"})
    existing = await database["applications"].find_one({"name": "Payment Gateway"})
    assert portfolio is not None and existing is not None
    baseline = await database["applications"].find_one({"_id": existing["_id"]})
    application_count = await database["applications"].count_documents({})
    audit_count = await database["audit_logs"].count_documents({"entityType": "application"})
    valid = app_payload(str(portfolio["_id"]))

    oversized_payloads = (
        valid | {"name": "n" * 161},
        valid | {"description": "d" * 2001},
        valid | {"businessOwner": "o" * 121},
        valid | {"technologyStack": "t" * 1001},
    )
    for payload in oversized_payloads:
        response = await api_client.post("/api/applications", headers=headers, json=payload)
        assert response.status_code == 422
        assert await database["applications"].count_documents({}) == application_count
        assert await database["audit_logs"].count_documents({"entityType": "application"}) == audit_count

    oversized_request = valid | {"description": "r" * 2001, "technologyStack": "s" * 1001}
    rejected = await api_client.put(
        f"/api/applications/{existing['_id']}", headers=headers, json=oversized_request
    )
    assert rejected.status_code == 422
    assert await database["applications"].find_one({"_id": existing["_id"]}) == baseline
    assert await database["applications"].count_documents({}) == application_count
    assert await database["audit_logs"].count_documents({"entityType": "application"}) == audit_count


@pytest.mark.asyncio
async def test_absent_application_object_id_get_put_delete_return_404_without_changes(
    api_client: AsyncClient, started_app: AsyncMongoClient[dict[str, Any]]
) -> None:
    """Return 404 for each operation on a syntactically valid absent application id."""
    headers = await token(api_client, "admin@ketsip.local", "TestAdminPassword123!")
    database = started_app.get_database("ketsip_test")
    portfolio = await database["portfolios"].find_one({"name": "Payments"})
    assert portfolio
    absent_id = ObjectId()
    application_count = await database["applications"].count_documents({})
    audit_count = await database["audit_logs"].count_documents({"entityType": "application"})

    get_response = await api_client.get(f"/api/applications/{absent_id}", headers=headers)
    put_response = await api_client.put(
        f"/api/applications/{absent_id}", headers=headers,
        json=app_payload(str(portfolio["_id"]), "Must not be created"),
    )
    delete_response = await api_client.delete(f"/api/applications/{absent_id}", headers=headers)

    assert get_response.status_code == put_response.status_code == delete_response.status_code == 404
    assert await database["applications"].find_one({"_id": absent_id}) is None
    assert await database["applications"].count_documents({}) == application_count
    assert await database["audit_logs"].count_documents({"entityType": "application"}) == audit_count


@pytest.mark.asyncio
async def test_search_and_text_payloads_are_literal_scoped_and_inert(
    api_client: AsyncClient, started_app: AsyncMongoClient[dict[str, Any]]
) -> None:
    """Keep regex/operator-like search text scoped and preserve HTML/path strings as inert data."""
    database = started_app.get_database("ketsip_test")
    leader = await token(api_client, "portfolio.leader@ketsip.local")
    for search in (".*", "{\"$ne\":null}", "(?s).*Customer"):
        response = await api_client.get("/api/applications", headers=leader, params={"search": search})
        assert response.status_code == 200
        assert response.json()["total"] == 0
        assert all(item["portfolioName"] == "Payments" for item in response.json()["items"])

    admin = await token(api_client, "admin@ketsip.local", "TestAdminPassword123!")
    portfolio = await database["portfolios"].find_one({"name": "Payments"})
    assert portfolio
    html_text = "<script>window.__inventory_test__ = true</script>"
    path_text = "../../etc/passwd"
    application_count_before = await database["applications"].count_documents({})
    audit_count_before = await database["audit_logs"].count_documents({"entityType": "application"})
    literal_payload = app_payload(str(portfolio["_id"]), "Literal security text") | {
        "description": html_text,
        "technologyStack": path_text,
    }
    created = await api_client.post("/api/applications", headers=admin, json=literal_payload)
    assert created.status_code == 201
    assert "application/json" in created.headers["content-type"]
    stored = await database["applications"].find_one({"_id": ObjectId(created.json()["id"])})
    assert stored is not None
    assert stored["description"] == html_text
    assert stored["technologyStack"] == path_text
    assert created.json()["description"] == html_text
    assert created.json()["technologyStack"] == path_text

    rejected_operator = await api_client.post(
        "/api/applications", headers=admin,
        json=app_payload(str(portfolio["_id"]), "Raw operator rejected") | {"$where": "return true"},
    )
    assert rejected_operator.status_code == 422
    assert await database["applications"].find_one({"name": "Raw operator rejected"}) is None
    assert await database["applications"].count_documents({}) == application_count_before + 1
    assert await database["audit_logs"].count_documents({"entityType": "application"}) == audit_count_before + 1


@pytest.mark.asyncio
async def test_invalid_fields_inaccessible_reads_scope_write_and_admin_delete(
    api_client: AsyncClient, started_app: AsyncMongoClient[dict[str, Any]]
) -> None:
    """Reject invalid values and hide or deny operations outside role scope."""
    database = started_app.get_database("ketsip_test")
    admin = await token(api_client, "admin@ketsip.local", "TestAdminPassword123!")
    payments = await database["portfolios"].find_one({"name": "Payments"})
    customer = await database["portfolios"].find_one({"name": "Customer Platform"})
    application = await database["applications"].find_one({"name": "Payment Gateway"})
    assert payments and customer and application
    baseline = await database["applications"].find_one({"_id": application["_id"]})
    audit_count = await database["audit_logs"].count_documents({"entityType": "application"})

    invalid = app_payload(str(payments["_id"])) | {"openCriticalDefects": -2}
    assert (await api_client.post("/api/applications", headers=admin, json=invalid)).status_code == 422
    invalid_url = app_payload(str(payments["_id"])) | {"pipelineLink": "javascript:bad"}
    assert (await api_client.post("/api/applications", headers=admin, json=invalid_url)).status_code == 422

    leader = await token(api_client, "portfolio.leader@ketsip.local")
    assert (await api_client.get(f"/api/applications/{ObjectId()}", headers=leader)).status_code == 404
    customer_app = await database["applications"].find_one({"portfolioId": customer["_id"]})
    assert customer_app
    assert (await api_client.get(f"/api/applications/{customer_app['_id']}", headers=leader)).status_code == 404
    outside = await api_client.post("/api/applications", headers=leader, json=app_payload(str(customer["_id"]), "Outside scope"))
    assert outside.status_code == 404
    denied_delete = await api_client.delete(f"/api/applications/{application['_id']}", headers=leader)
    assert denied_delete.status_code == 403
    assert await database["applications"].find_one({"_id": application["_id"]}) == baseline
    assert await database["audit_logs"].count_documents({"entityType": "application"}) == audit_count

    deleted = await api_client.delete(f"/api/applications/{application['_id']}", headers=admin)
    assert deleted.status_code == 204
    assert await database["applications"].find_one({"_id": application["_id"]}) is None
    assert await database["audit_logs"].count_documents({"entityType": "application"}) == audit_count + 1
