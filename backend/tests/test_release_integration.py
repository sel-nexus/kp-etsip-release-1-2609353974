"""Verify cross-feature release flows against the isolated real Mongo database."""

import csv
import io
from typing import Any

import pytest
from bson import ObjectId
from httpx import AsyncClient
from pymongo import AsyncMongoClient


ADMIN_EMAIL = "admin@ketsip.local"
ADMIN_PASSWORD = "TestAdminPassword123!"


def application_payload(portfolio_id: str, name: str) -> dict[str, Any]:
    """Return a complete application request linked to the supplied portfolio."""
    return {
        "name": name,
        "description": "Cross-feature release integration record",
        "portfolioId": portfolio_id,
        "productArea": "Release Integration",
        "businessOwner": "Release Integration Team",
        "technologyOwner": "Platform Engineering",
        "etsOwner": "Quality Office",
        "criticality": "High",
        "tier": 2,
        "lifecycleStatus": "Active",
        "technologyStack": "Python; MongoDB",
        "repositoryLink": "https://example.com/release-integration",
        "pipelineLink": None,
        "applicationHealthScore": 90,
        "qualityScore": 88,
        "automationCoverage": 75,
        "unitTestCoverage": 80,
        "openDefects": 2,
        "openCriticalDefects": 2,
        "riskLevel": "High",
    }


async def sign_in_admin(client: AsyncClient) -> tuple[dict[str, str], str]:
    """Sign in the seeded administrator and return bearer headers and identity."""
    response = await client.post(
        "/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
    )
    assert response.status_code == 200
    profile = response.json()["user"]
    assert profile["role"] == "Administrator"
    return {"Authorization": f"Bearer {response.json()['token']}"}, profile["id"]


@pytest.mark.asyncio
async def test_admin_release_flow_persists_cross_feature_state_and_audit_events(
    api_client: AsyncClient,
    started_app: AsyncMongoClient[dict[str, Any]],
) -> None:
    """Carry new inventory through auth, portfolios, applications, dashboard, and reports."""
    headers, admin_id = await sign_in_admin(api_client)
    database = started_app.get_database("ketsip_test")
    admin_object_id = ObjectId(admin_id)

    portfolio_response = await api_client.post(
        "/api/portfolios",
        headers=headers,
        json={
            "name": "Release Integration Portfolio",
            "owner": "Release Integration Team",
            "description": "Portfolio created for the release integration flow.",
            "productArea": "Release Integration",
            "status": "Active",
        },
    )
    assert portfolio_response.status_code == 201
    portfolio_id = portfolio_response.json()["id"]
    portfolio_object_id = ObjectId(portfolio_id)
    persisted_portfolio = await database["portfolios"].find_one({"_id": portfolio_object_id})
    assert persisted_portfolio is not None
    assert persisted_portfolio["name"] == "Release Integration Portfolio"

    application_name = "Release Integration Application"
    application_response = await api_client.post(
        "/api/applications",
        headers=headers,
        json=application_payload(portfolio_id, application_name),
    )
    assert application_response.status_code == 201
    application_id = application_response.json()["id"]
    application_object_id = ObjectId(application_id)
    assert application_response.json()["portfolio"] == {
        "id": portfolio_id,
        "name": "Release Integration Portfolio",
    }
    persisted_application = await database["applications"].find_one({"_id": application_object_id})
    assert persisted_application is not None
    assert persisted_application["portfolioId"] == portfolio_object_id
    assert persisted_application["qualityScore"] == 88

    dashboard_response = await api_client.get(
        "/api/dashboard/executive",
        params={"portfolioId": portfolio_id},
        headers=headers,
    )
    assert dashboard_response.status_code == 200
    assert dashboard_response.json() == {
        "enterpriseQualityScore": 88,
        "averageApplicationHealthScore": 90,
        "automationMaturityScore": 75,
        "openCriticalDefects": 2,
        "applicationsAtRisk": 1,
        "totalApplications": 1,
        "totalPortfolios": 1,
        "portfolioQualityScores": [
            {
                "portfolioId": portfolio_id,
                "portfolioName": "Release Integration Portfolio",
                "qualityScore": 88,
                "highRiskApplicationCount": 1,
            }
        ],
    }

    report_response = await api_client.get(
        "/api/reports/applications",
        params={"search": application_name, "portfolioId": portfolio_id, "page": 1, "pageSize": 10},
        headers=headers,
    )
    assert report_response.status_code == 200
    report_page = report_response.json()
    assert report_page["total"] == 1
    assert len(report_page["items"]) == 1
    assert report_page["items"][0]["id"] == application_id
    assert report_page["items"][0]["portfolioName"] == "Release Integration Portfolio"

    csv_response = await api_client.get(
        "/api/reports/applications",
        params={"format": "csv", "search": application_name, "portfolioId": portfolio_id},
        headers=headers,
    )
    assert csv_response.status_code == 200
    assert csv_response.headers["content-type"].startswith("text/csv")
    csv_rows = list(csv.DictReader(io.StringIO(csv_response.text)))
    assert len(csv_rows) == 1
    assert csv_rows[0]["id"] == application_id
    assert csv_rows[0]["name"] == application_name
    assert csv_rows[0]["portfolioId"] == portfolio_id
    assert csv_rows[0]["portfolioName"] == "Release Integration Portfolio"

    events = await database["audit_logs"].find({"userId": admin_object_id}).to_list(length=None)
    actual_events = {
        (event["action"], event["entityType"], str(event["entityId"]) if event["entityId"] else None, event["details"])
        for event in events
    }
    assert len(events) == 4
    assert actual_events == {
        ("login", "auth", None, "Local account authentication succeeded"),
        ("create", "portfolio", portfolio_id, "Portfolio created"),
        ("create", "application", application_id, "Application created"),
        ("export", "report", None, "CSV export: applications"),
    }


@pytest.mark.asyncio
async def test_referenced_portfolio_delete_error_preserves_records_without_delete_audit(
    api_client: AsyncClient,
    started_app: AsyncMongoClient[dict[str, Any]],
) -> None:
    """Keep a linked portfolio and application intact when its delete conflicts."""
    headers, admin_id = await sign_in_admin(api_client)
    database = started_app.get_database("ketsip_test")

    created_portfolio = await api_client.post(
        "/api/portfolios",
        headers=headers,
        json={
            "name": "Referenced Release Portfolio",
            "owner": "Release Integration Team",
            "description": "Portfolio retained because it has a linked application.",
            "productArea": "Release Integration",
            "status": "Active",
        },
    )
    assert created_portfolio.status_code == 201
    portfolio_id = created_portfolio.json()["id"]
    portfolio_object_id = ObjectId(portfolio_id)

    created_application = await api_client.post(
        "/api/applications",
        headers=headers,
        json=application_payload(portfolio_id, "Referenced Release Application"),
    )
    assert created_application.status_code == 201
    application_id = created_application.json()["id"]
    application_object_id = ObjectId(application_id)
    portfolio_before = await database["portfolios"].find_one({"_id": portfolio_object_id})
    application_before = await database["applications"].find_one({"_id": application_object_id})
    assert portfolio_before is not None and application_before is not None

    conflict = await api_client.delete(f"/api/portfolios/{portfolio_id}", headers=headers)

    assert conflict.status_code == 409
    assert await database["portfolios"].find_one({"_id": portfolio_object_id}) == portfolio_before
    assert await database["applications"].find_one({"_id": application_object_id}) == application_before
    assert await database["applications"].count_documents({"portfolioId": portfolio_object_id}) == 1
    admin_object_id = ObjectId(admin_id)
    events = await database["audit_logs"].find({"userId": admin_object_id}).to_list(length=None)
    actual_events = {
        (event["action"], event["entityType"], str(event["entityId"]) if event["entityId"] else None, event["details"])
        for event in events
    }
    assert len(events) == 3
    assert actual_events == {
        ("login", "auth", None, "Local account authentication succeeded"),
        ("create", "portfolio", portfolio_id, "Portfolio created"),
        ("create", "application", application_id, "Application created"),
    }
    assert await database["audit_logs"].count_documents(
        {"userId": admin_object_id, "action": "delete", "entityType": "portfolio", "entityId": portfolio_object_id}
    ) == 0
    assert await database["audit_logs"].count_documents(
        {"userId": admin_object_id, "action": "delete", "entityType": "application", "entityId": application_object_id}
    ) == 0


@pytest.mark.asyncio
async def test_portfolio_leader_release_flow_is_limited_to_assigned_portfolio(
    api_client: AsyncClient,
    started_app: AsyncMongoClient[dict[str, Any]],
) -> None:
    """Carry a leader's assigned inventory through real writes, dashboard, reports, and export audits."""
    login = await api_client.post(
        "/api/auth/login",
        json={"email": "portfolio.leader@ketsip.local", "password": "KetsipDemo2025!"},
    )
    assert login.status_code == 200
    profile = login.json()["user"]
    assert profile["role"] == "Portfolio Leader"
    headers = {"Authorization": f"Bearer {login.json()['token']}"}
    leader_object_id = ObjectId(profile["id"])

    database = started_app.get_database("ketsip_test")
    payments = await database["portfolios"].find_one({"name": "Payments"})
    customer_platform = await database["portfolios"].find_one({"name": "Customer Platform"})
    assert payments is not None and customer_platform is not None
    customer_application = await database["applications"].find_one({"portfolioId": customer_platform["_id"]})
    persisted_leader = await database["users"].find_one({"_id": leader_object_id})
    assert customer_application is not None and persisted_leader is not None
    assert persisted_leader["portfolioAccess"] == [payments["_id"]]
    assert profile["portfolioAccess"] == [str(payments["_id"])]

    portfolio_inventory = await api_client.get("/api/portfolios?page=1&pageSize=10", headers=headers)
    assert portfolio_inventory.status_code == 200
    assert portfolio_inventory.json()["total"] == 1
    assert [row["name"] for row in portfolio_inventory.json()["items"]] == ["Payments"]
    assert portfolio_inventory.json()["items"][0]["id"] == str(payments["_id"])

    assigned_applications = await api_client.get(
        f"/api/portfolios/{payments['_id']}/applications?page=1&pageSize=10", headers=headers
    )
    assert assigned_applications.status_code == 200
    assert assigned_applications.json()["total"] == 3
    assert all(row["portfolioId"] == str(payments["_id"]) for row in assigned_applications.json()["items"])
    for endpoint in (
        f"/api/portfolios/{customer_platform['_id']}",
        f"/api/portfolios/{customer_platform['_id']}/applications",
        f"/api/applications/{customer_application['_id']}",
    ):
        assert (await api_client.get(endpoint, headers=headers)).status_code == 404

    application_name = "Portfolio Leader Assigned Release Application"
    created = await api_client.post(
        "/api/applications",
        headers=headers,
        json=application_payload(str(payments["_id"]), application_name),
    )
    assert created.status_code == 201
    application_id = created.json()["id"]
    application_object_id = ObjectId(application_id)
    assert created.json()["portfolio"] == {"id": str(payments["_id"]), "name": "Payments"}
    persisted_application = await database["applications"].find_one({"_id": application_object_id})
    assert persisted_application is not None
    assert persisted_application["portfolioId"] == payments["_id"]
    assert persisted_application["name"] == application_name

    audit_count_before_denied_write = await database["audit_logs"].count_documents({"userId": leader_object_id})
    denied_write = await api_client.post(
        "/api/applications",
        headers=headers,
        json=application_payload(str(customer_platform["_id"]), "Portfolio Leader Out-of-Scope Application"),
    )
    assert denied_write.status_code == 404
    assert await database["applications"].find_one({"name": "Portfolio Leader Out-of-Scope Application"}) is None
    assert await database["audit_logs"].count_documents({"userId": leader_object_id}) == audit_count_before_denied_write

    hidden_dashboard = await api_client.get(
        "/api/dashboard/executive", params={"portfolioId": str(customer_platform["_id"])}, headers=headers
    )
    assert hidden_dashboard.status_code == 404
    dashboard = await api_client.get("/api/dashboard/executive", headers=headers)
    assert dashboard.status_code == 200
    assert dashboard.json() == {
        "enterpriseQualityScore": 81,
        "averageApplicationHealthScore": 85,
        "automationMaturityScore": 73,
        "openCriticalDefects": 5,
        "applicationsAtRisk": 2,
        "totalApplications": 4,
        "totalPortfolios": 1,
        "portfolioQualityScores": [
            {
                "portfolioId": str(payments["_id"]),
                "portfolioName": "Payments",
                "qualityScore": 81,
                "highRiskApplicationCount": 2,
            }
        ],
    }

    application_list = await api_client.get("/api/applications?page=1&pageSize=10", headers=headers)
    assert application_list.status_code == 200
    assert application_list.json()["total"] == 4
    assert {row["name"] for row in application_list.json()["items"]} == {
        "Payment Gateway", "Settlement Orchestrator", "Merchant Portal", application_name,
    }
    assert all(row["portfolioId"] == str(payments["_id"]) for row in application_list.json()["items"])

    application_report = await api_client.get("/api/reports/applications", headers=headers)
    assert application_report.status_code == 200
    assert application_report.json()["total"] == 4
    assert {row["name"] for row in application_report.json()["items"]} == {
        "Payment Gateway", "Settlement Orchestrator", "Merchant Portal", application_name,
    }
    assert all(row["portfolioName"] == "Payments" for row in application_report.json()["items"])
    out_of_scope_report = await api_client.get(
        "/api/reports/applications", params={"portfolioId": str(customer_platform["_id"])}, headers=headers
    )
    assert out_of_scope_report.status_code == 200
    assert out_of_scope_report.json()["total"] == 0
    assert out_of_scope_report.json()["items"] == []

    portfolio_report = await api_client.get("/api/reports/portfolios", headers=headers)
    assert portfolio_report.status_code == 200
    assert portfolio_report.json()["total"] == 1
    assert [row["name"] for row in portfolio_report.json()["items"]] == ["Payments"]
    assert portfolio_report.json()["items"][0]["applicationCount"] == 4

    application_csv = await api_client.get("/api/reports/applications?format=csv", headers=headers)
    assert application_csv.status_code == 200
    assert application_csv.headers["content-type"].startswith("text/csv")
    application_rows = list(csv.DictReader(io.StringIO(application_csv.text)))
    assert len(application_rows) == 4
    assert {row["name"] for row in application_rows} == {
        "Payment Gateway", "Settlement Orchestrator", "Merchant Portal", application_name,
    }
    assert all(row["portfolioId"] == str(payments["_id"]) for row in application_rows)
    assert "Customer Identity Service" not in application_csv.text
    assert "Enterprise Data Lake" not in application_csv.text

    portfolio_csv = await api_client.get("/api/reports/portfolios?format=csv", headers=headers)
    assert portfolio_csv.status_code == 200
    portfolio_rows = list(csv.DictReader(io.StringIO(portfolio_csv.text)))
    assert len(portfolio_rows) == 1
    assert portfolio_rows[0]["id"] == str(payments["_id"])
    assert portfolio_rows[0]["name"] == "Payments"
    assert "Customer Platform" not in portfolio_csv.text
    assert "Data & Analytics" not in portfolio_csv.text

    events = await database["audit_logs"].find({"userId": leader_object_id}).to_list(length=None)
    actual_events = {
        (event["action"], event["entityType"], str(event["entityId"]) if event["entityId"] else None, event["details"])
        for event in events
    }
    assert len(events) == 4
    assert actual_events == {
        ("login", "auth", None, "Local account authentication succeeded"),
        ("create", "application", application_id, "Application created"),
        ("export", "report", None, "CSV export: applications"),
        ("export", "report", None, "CSV export: portfolios"),
    }
