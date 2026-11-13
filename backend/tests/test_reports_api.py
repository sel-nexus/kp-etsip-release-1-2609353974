"""Exercise report tables and CSV downloads through real Mongo-backed HTTP routes."""

import csv
import io
from typing import Any

import pytest
from httpx import AsyncClient
from pymongo import AsyncMongoClient


async def _auth(client: AsyncClient, email: str, password: str = "KetsipDemo2025!") -> dict[str, str]:
    """Sign in a seeded role and return its bearer token header."""
    result = await client.post("/api/auth/login", json={"email": email, "password": password})
    assert result.status_code == 200
    return {"Authorization": f"Bearer {result.json()['token']}"}


@pytest.mark.asyncio
async def test_application_report_is_bounded_and_uses_inventory_filters(api_client: AsyncClient) -> None:
    """Return the expected typed page using search, criticality, and lifecycle filters."""
    admin = await _auth(api_client, "admin@ketsip.local", "TestAdminPassword123!")
    response = await api_client.get(
        "/api/reports/applications?search=Payment&criticality=Critical&lifecycleStatus=Active&page=1&pageSize=2",
        headers=admin,
    )
    assert response.status_code == 200
    page = response.json()
    assert set(page) == {"items", "page", "pageSize", "total"}
    assert page["page"] == 1 and page["pageSize"] == 2 and page["total"] == 1
    assert page["items"][0]["name"] == "Payment Gateway"
    assert page["items"][0]["portfolioName"] == "Payments"


@pytest.mark.asyncio
async def test_portfolio_report_is_bounded_and_filters_inventory(api_client: AsyncClient) -> None:
    """Return matching portfolio source rows and derived values in a bounded page."""
    admin = await _auth(api_client, "admin@ketsip.local", "TestAdminPassword123!")
    response = await api_client.get(
        "/api/reports/portfolios?search=Payments&status=Active&productArea=Payments&pageSize=1",
        headers=admin,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1 and len(data["items"]) == 1
    assert data["items"][0]["name"] == "Payments"
    assert data["items"][0]["applicationCount"] == 3


@pytest.mark.asyncio
async def test_report_tables_require_login_view_permission_and_bounded_page_size(api_client: AsyncClient) -> None:
    """Reject anonymous requests and invalid bounds while permitting view-only tables."""
    assert (await api_client.get("/api/reports/applications")).status_code == 401
    readonly = await _auth(api_client, "readonly@ketsip.local")
    assert (await api_client.get("/api/reports/applications", headers=readonly)).status_code == 200
    assert (await api_client.get("/api/reports/portfolios?pageSize=101", headers=readonly)).status_code == 422
    assert (await api_client.get("/api/reports/applications?riskLevel=Extreme", headers=readonly)).status_code == 422
    assert (await api_client.get("/api/reports/applications?format=pdf", headers=readonly)).status_code == 422


@pytest.mark.asyncio
async def test_report_csv_exports_require_export_permission_and_write_no_denied_event(
    api_client: AsyncClient, started_app: AsyncMongoClient[dict[str, Any]],
) -> None:
    """Deny Read Only CSV requests without creating export audit records."""
    readonly = await _auth(api_client, "readonly@ketsip.local")
    database = started_app.get_database("ketsip_test")
    before = await database["audit_logs"].count_documents({"action": "export", "entityType": "report"})
    app_denied = await api_client.get("/api/reports/applications?format=csv", headers=readonly)
    portfolio_denied = await api_client.get("/api/reports/portfolios?format=csv", headers=readonly)
    assert app_denied.status_code == portfolio_denied.status_code == 403
    assert await database["audit_logs"].count_documents({"action": "export", "entityType": "report"}) == before


@pytest.mark.asyncio
async def test_application_csv_download_has_attachment_csv_and_single_audit_record(
    api_client: AsyncClient, started_app: AsyncMongoClient[dict[str, Any]],
) -> None:
    """Download filtered complete application rows and persist exactly one success event."""
    admin = await _auth(api_client, "admin@ketsip.local", "TestAdminPassword123!")
    database = started_app.get_database("ketsip_test")
    before = await database["audit_logs"].count_documents({"action": "export", "entityType": "report"})

    response = await api_client.get("/api/reports/applications?format=csv&search=Payment%20Gateway", headers=admin)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert 'attachment; filename="applications.csv"' in response.headers["content-disposition"]
    rows = list(csv.DictReader(io.StringIO(response.text)))
    assert len(rows) == 1 and rows[0]["name"] == "Payment Gateway"
    event = await database["audit_logs"].find_one({"action": "export", "entityType": "report"})
    assert event and event["details"] == "CSV export: applications"
    assert await database["audit_logs"].count_documents({"action": "export", "entityType": "report"}) == before + 1


@pytest.mark.asyncio
async def test_portfolio_leader_csv_scope_applies_to_rows_and_total(
    api_client: AsyncClient, started_app: AsyncMongoClient[dict[str, Any]],
) -> None:
    """Keep both report table and complete CSV restricted to assigned portfolio."""
    leader = await _auth(api_client, "portfolio.leader@ketsip.local")
    page = await api_client.get("/api/reports/portfolios", headers=leader)
    export = await api_client.get("/api/reports/portfolios?format=csv", headers=leader)
    assert page.status_code == export.status_code == 200
    assert page.json()["total"] == 1 and page.json()["items"][0]["name"] == "Payments"
    rows = list(csv.DictReader(io.StringIO(export.text)))
    assert [row["name"] for row in rows] == ["Payments"]
    assert "Customer Platform" not in export.text
    database = started_app.get_database("ketsip_test")
    assert await database["audit_logs"].count_documents({"action": "export", "entityType": "report"}) == 1


@pytest.mark.asyncio
async def test_export_audit_database_failure_returns_service_unavailable_without_success(
    api_client: AsyncClient, started_app: AsyncMongoClient[dict[str, Any]],
) -> None:
    """Fail the actual Mongo insert via a collection validator and return no CSV."""
    admin = await _auth(api_client, "admin@ketsip.local", "TestAdminPassword123!")
    database = started_app.get_database("ketsip_test")
    await database.command({
        "collMod": "audit_logs",
        "validator": {"action": {"$ne": "export"}},
        "validationLevel": "strict",
        "validationAction": "error",
    })

    response = await api_client.get("/api/reports/portfolios?format=csv", headers=admin)

    assert response.status_code == 503
    assert "text/csv" not in response.headers.get("content-type", "")
