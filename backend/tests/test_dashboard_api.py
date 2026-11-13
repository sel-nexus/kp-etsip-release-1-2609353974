"""Exercise the executive dashboard HTTP contract against real MongoDB."""

from typing import Any

import pytest
from httpx import AsyncClient
from pymongo import AsyncMongoClient


async def auth_headers(client: AsyncClient, email: str, password: str = "KetsipDemo2025!") -> dict[str, str]:
    """Sign in a persisted demo user and return its bearer authorization."""
    response = await client.post("/api/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['token']}"}


@pytest.mark.asyncio
async def test_dashboard_returns_exact_seed_metrics_and_role_scoped_comparisons(
    api_client: AsyncClient, started_app: AsyncMongoClient[dict[str, Any]]
) -> None:
    """Return exact seeded formulas to an executive and limit a leader to grants."""
    executive = await auth_headers(api_client, "executive@ketsip.local")
    response = await api_client.get("/api/dashboard/executive", headers=executive)
    assert response.status_code == 200
    assert response.json() == {
        "enterpriseQuality": 81,
        "averageHealth": 84,
        "automationMaturity": 75,
        "openCriticalDefects": 11,
        "applicationsAtRisk": 3,
        "totalApplications": 10,
        "totalPortfolios": 3,
        "portfolios": [
            {"id": str(row["_id"]), "name": row["name"], "productArea": row["productArea"], "qualityScore": score, "highRiskApplications": risk}
            for row, score, risk in [
                (await started_app.get_database("ketsip_test")["portfolios"].find_one({"name": "Customer Platform"}), 82, 1),
                (await started_app.get_database("ketsip_test")["portfolios"].find_one({"name": "Data & Analytics"}), 83, 1),
                (await started_app.get_database("ketsip_test")["portfolios"].find_one({"name": "Payments"}), 79, 1),
            ]
        ],
    }

    leader = await auth_headers(api_client, "portfolio.leader@ketsip.local")
    scoped = await api_client.get("/api/dashboard/executive?riskLevel=High", headers=leader)
    assert scoped.status_code == 200
    assert scoped.json()["totalApplications"] == 1
    assert scoped.json()["totalPortfolios"] == 1
    assert [row["name"] for row in scoped.json()["portfolios"]] == ["Payments"]
    assert scoped.json()["enterpriseQuality"] == 73


@pytest.mark.asyncio
async def test_dashboard_validation_auth_empty_and_inaccessible_id(
    api_client: AsyncClient, started_app: AsyncMongoClient[dict[str, Any]]
) -> None:
    """Reject invalid inputs and hide portfolio access while preserving empty metrics."""
    assert (await api_client.get("/api/dashboard/executive")).status_code == 401
    executive = await auth_headers(api_client, "executive@ketsip.local")
    assert (await api_client.get("/api/dashboard/executive?riskLevel=Extreme", headers=executive)).status_code == 422
    assert (await api_client.get("/api/dashboard/executive?productArea=" + "x" * 121, headers=executive)).status_code == 422
    assert (await api_client.get("/api/dashboard/executive?portfolioId=invalid", headers=executive)).status_code == 422

    database = started_app.get_database("ketsip_test")
    payments = await database["portfolios"].find_one({"name": "Payments"})
    assert payments
    leader = await auth_headers(api_client, "portfolio.leader@ketsip.local")
    hidden = await api_client.get(f"/api/dashboard/executive?portfolioId={payments['_id']}", headers=leader)
    assert hidden.status_code == 200
    no_match = await api_client.get("/api/dashboard/executive?productArea=No%20such%20area", headers=leader)
    assert no_match.status_code == 200
    assert no_match.json() == {
        "enterpriseQuality": None,
        "averageHealth": None,
        "automationMaturity": None,
        "openCriticalDefects": 0,
        "applicationsAtRisk": 0,
        "totalApplications": 0,
        "totalPortfolios": 1,
        "portfolios": [{"id": str(payments["_id"]), "name": "Payments", "productArea": "Payments", "qualityScore": None, "highRiskApplications": 0}],
    }

    readonly = await auth_headers(api_client, "readonly@ketsip.local")
    executive_scope = await database["portfolios"].find_one({"name": "Data & Analytics"})
    assert executive_scope
    inaccessible = await api_client.get(f"/api/dashboard/executive?portfolioId={payments['_id']}", headers=readonly)
    assert inaccessible.status_code == 404
    assert (await api_client.get(f"/api/dashboard/executive?portfolioId={executive_scope['_id']}", headers=readonly)).status_code == 200


@pytest.mark.asyncio
async def test_dashboard_denies_user_without_persisted_view_permission(
    api_client: AsyncClient, started_app: AsyncMongoClient[dict[str, Any]]
) -> None:
    """Deny dashboard reads after the engineer role loses persisted view permission."""
    database = started_app.get_database("ketsip_test")
    role = await database["roles"].find_one({"name": "Engineer"})
    assert role
    original_permissions = role["permissions"]
    await database["roles"].update_one({"_id": role["_id"]}, {"$set": {"permissions": ["create", "edit"]}})
    try:
        headers = await auth_headers(api_client, "engineer@ketsip.local")
        assert (await api_client.get("/api/dashboard/executive", headers=headers)).status_code == 403
    finally:
        await database["roles"].update_one({"_id": role["_id"]}, {"$set": {"permissions": original_permissions}})
