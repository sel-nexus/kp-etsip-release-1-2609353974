"""Exercise application HTTP routes against the isolated real Mongo database."""

from typing import Any

import pytest
from bson import ObjectId
from httpx import AsyncClient
from pymongo import AsyncMongoClient


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
    duplicate = await api_client.post(
        "/api/applications", headers=headers,
        json=app_payload(str(portfolio["_id"]), "Payment Gateway"),
    )
    assert duplicate.status_code == 409
    assert await database["audit_logs"].count_documents({"entityType": "application"}) == audit_before + 2


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
