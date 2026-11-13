"""Verify application service policy, persistence, and audits against real MongoDB."""

from typing import Any

import pytest
from bson import ObjectId
from fastapi import HTTPException
from pymongo import AsyncMongoClient

from app.repositories.applications import ApplicationsRepository
from app.repositories.audit import AuditRepository
from app.schemas.application import ApplicationCreate, ApplicationUpdate
from app.services.applications import ApplicationsService


def application_values(portfolio_id: str, name: str = "Service application") -> dict[str, Any]:
    """Build a complete valid source record for an assigned portfolio."""
    return {
        "name": name,
        "description": "Application created by service test",
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


@pytest.mark.asyncio
async def test_list_scopes_before_filters_and_count_and_returns_portfolio_name(
    started_app: AsyncMongoClient[dict[str, Any]],
) -> None:
    """Count only scoped filtered rows and map portfolio display names safely."""
    database = started_app.get_database("ketsip_test")
    portfolio = await database["portfolios"].find_one({"name": "Payments"})
    other = await database["portfolios"].find_one({"name": "Customer Platform"})
    assert portfolio and other
    actor = {"role": "Portfolio Leader", "permissions": ["view"], "portfolioAccess": [portfolio["_id"]]}
    service = ApplicationsService(ApplicationsRepository(database), AuditRepository(database))

    page = await service.list_applications(actor, "Payment", None, None, None, None, 1, 1)
    filtered = await service.list_applications(actor, None, None, "Critical", "Low", "Active", 1, 25)
    hidden = await service.list_applications(actor, None, str(other["_id"]), None, None, None, 1, 25)

    assert page.total == 3 and len(page.items) == 1 and page.items[0].portfolioName == "Payments"
    assert filtered.total == 0
    assert hidden.total == 0 and hidden.items == []


@pytest.mark.asyncio
async def test_create_update_and_delete_audit_only_successful_changes(
    started_app: AsyncMongoClient[dict[str, Any]],
) -> None:
    """Persist complete records and write exactly one shared audit event per operation."""
    database = started_app.get_database("ketsip_test")
    portfolio = await database["portfolios"].find_one({"name": "Payments"})
    admin = await database["users"].find_one({"email": "admin@ketsip.local"})
    assert portfolio and admin
    actor = {"_id": admin["_id"], "name": admin["name"], "role": "Administrator", "permissions": ["view", "create", "edit", "delete", "administer"], "portfolioAccess": []}
    service = ApplicationsService(ApplicationsRepository(database), AuditRepository(database))
    source = application_values(str(portfolio["_id"]))
    before = await database["audit_logs"].count_documents({"entityType": "application"})

    created = await service.create_application(ApplicationCreate(**source), actor)
    assert created.name == source["name"] and created.portfolio.name == "Payments"
    assert str(created.repositoryLink) == source["repositoryLink"]
    updated_values = application_values(str(portfolio["_id"]), "Updated service application")
    updated = await service.update_application(created.id, ApplicationUpdate(**updated_values), actor)
    assert updated.name == "Updated service application"
    stored_after_update = await database["applications"].find_one({"_id": ObjectId(created.id)})
    assert stored_after_update is not None
    assert stored_after_update["name"] == "Updated service application"
    assert stored_after_update["technologyStack"] == updated_values["technologyStack"]
    await service.delete_application(created.id, actor)

    assert await database["applications"].find_one({"_id": ObjectId(created.id)}) is None
    events = await database["audit_logs"].find({"entityType": "application"}).to_list(length=20)
    assert len(events) == before + 3
    assert [event["action"] for event in events[:3]] == ["create", "edit", "delete"]


@pytest.mark.asyncio
async def test_reject_duplicate_missing_and_unassigned_portfolios_without_mutation_or_audit(
    started_app: AsyncMongoClient[dict[str, Any]],
) -> None:
    """Reject duplicate names and out-of-scope writes without changing Mongo state."""
    database = started_app.get_database("ketsip_test")
    payments = await database["portfolios"].find_one({"name": "Payments"})
    customer = await database["portfolios"].find_one({"name": "Customer Platform"})
    assert payments and customer
    leader = {"role": "Portfolio Leader", "permissions": ["view", "create", "edit"], "portfolioAccess": [payments["_id"]]}
    service = ApplicationsService(ApplicationsRepository(database), AuditRepository(database))
    baseline_apps = await database["applications"].count_documents({})
    baseline_audits = await database["audit_logs"].count_documents({"entityType": "application"})

    for portfolio_id, name in ((str(customer["_id"]), "Outside grant"), (str(ObjectId()), "Missing portfolio")):
        with pytest.raises(HTTPException) as rejected:
            await service.create_application(ApplicationCreate(**application_values(portfolio_id, name)), leader)
        assert rejected.value.status_code in {404, 409}
    with pytest.raises(HTTPException) as duplicate:
        await service.create_application(ApplicationCreate(**application_values(str(payments["_id"]), "Payment Gateway")), leader)
    assert duplicate.value.status_code == 409
    assert await database["applications"].count_documents({}) == baseline_apps
    assert await database["audit_logs"].count_documents({"entityType": "application"}) == baseline_audits


@pytest.mark.asyncio
async def test_hidden_details_and_non_admin_delete_are_denied(
    started_app: AsyncMongoClient[dict[str, Any]],
) -> None:
    """Return not-found for hidden records and deny deletion to non-administrators."""
    database = started_app.get_database("ketsip_test")
    portfolio = await database["portfolios"].find_one({"name": "Payments"})
    assert portfolio
    application = await database["applications"].find_one({"name": "Payment Gateway"})
    assert application
    service = ApplicationsService(ApplicationsRepository(database), AuditRepository(database))
    outsider = {"role": "Portfolio Leader", "permissions": ["view", "edit"], "portfolioAccess": []}
    engineer = {"role": "Engineer", "permissions": ["view", "delete"], "portfolioAccess": [portfolio["_id"]]}

    with pytest.raises(HTTPException) as hidden:
        await service.get_application(str(application["_id"]), outsider)
    assert hidden.value.status_code == 404
    with pytest.raises(HTTPException) as denied:
        await service.delete_application(str(application["_id"]), engineer)
    assert denied.value.status_code == 403
    assert await database["applications"].find_one({"_id": application["_id"]}) is not None


@pytest.mark.asyncio
async def test_schema_rejects_invalid_bounds_enums_and_urls() -> None:
    """Reject malformed application source values before reaching Mongo writes."""
    source = application_values(str(ObjectId()))
    for override in (
        {"openCriticalDefects": -1},
        {"tier": 5},
        {"qualityScore": 101},
        {"automationCoverage": -0.1},
        {"criticality": "Urgent"},
        {"repositoryLink": "javascript:alert(1)"},
    ):
        with pytest.raises(ValueError):
            ApplicationCreate(**(source | override))


@pytest.mark.asyncio
async def test_rejected_application_update_preserves_stored_values_and_audit(
    started_app: AsyncMongoClient[dict[str, Any]],
) -> None:
    """Reject duplicate-name updates without changing Mongo values or audit history."""
    database = started_app.get_database("ketsip_test")
    portfolio = await database["portfolios"].find_one({"name": "Payments"})
    existing = await database["applications"].find_one({"name": "Payment Gateway"})
    admin = await database["users"].find_one({"email": "admin@ketsip.local"})
    assert portfolio and existing and admin
    actor = {
        "_id": admin["_id"], "name": admin["name"], "role": "Administrator",
        "permissions": ["view", "create", "edit", "delete", "administer"], "portfolioAccess": [],
    }
    service = ApplicationsService(ApplicationsRepository(database), AuditRepository(database))
    baseline = await database["applications"].find_one({"_id": existing["_id"]})
    audit_count = await database["audit_logs"].count_documents({"entityType": "application"})

    with pytest.raises(HTTPException) as duplicate:
        await service.update_application(
            str(existing["_id"]),
            ApplicationUpdate(**application_values(str(portfolio["_id"]), "Settlement Orchestrator")),
            actor,
        )

    assert duplicate.value.status_code == 409
    assert await database["applications"].find_one({"_id": existing["_id"]}) == baseline
    assert await database["audit_logs"].count_documents({"entityType": "application"}) == audit_count


@pytest.mark.asyncio
async def test_application_update_lost_row_and_audit_failure_have_explicit_persisted_outcomes(
    started_app: AsyncMongoClient[dict[str, Any]],
) -> None:
    """Reject a lost update row without audit and expose the committed create if audit fails."""
    database = started_app.get_database("ketsip_test")
    portfolio = await database["portfolios"].find_one({"name": "Payments"})
    existing = await database["applications"].find_one({"name": "Payment Gateway"})
    admin = await database["users"].find_one({"email": "admin@ketsip.local"})
    assert portfolio is not None and existing is not None and admin is not None
    actor = {
        "_id": admin["_id"], "name": admin["name"], "role": "Administrator",
        "permissions": ["view", "create", "edit", "delete", "administer"], "portfolioAccess": [],
    }
    audit_count = await database["audit_logs"].count_documents({"entityType": "application"})

    class DeletingApplicationRepository(ApplicationsRepository):
        """Remove the application after service lookup but before its conditional update."""

        async def update_application(self, application_id: str, values: dict[str, Any]) -> dict[str, Any] | None:
            await self.applications.delete_one({"_id": ObjectId(application_id)})
            return await super().update_application(application_id, values)

    raced = ApplicationsService(DeletingApplicationRepository(database), AuditRepository(database))
    with pytest.raises(HTTPException) as missing:
        await raced.update_application(
            str(existing["_id"]),
            ApplicationUpdate(**application_values(str(portfolio["_id"]), "Lost update")),
            actor,
        )
    assert missing.value.status_code == 404
    assert await database["applications"].find_one({"_id": existing["_id"]}) is None
    assert await database["audit_logs"].count_documents({"entityType": "application"}) == audit_count

    class FailingAuditRepository(AuditRepository):
        """Fail when the service records an already-persisted application create."""

        async def record(self, actor: dict[str, Any], action: str, entity_type: str, entity_id: str | None, details: str, at: Any) -> None:
            raise RuntimeError("simulated audit persistence failure")

    failure_service = ApplicationsService(ApplicationsRepository(database), FailingAuditRepository(database))
    with pytest.raises(RuntimeError, match="audit persistence failure"):
        await failure_service.create_application(
            ApplicationCreate(**application_values(str(portfolio["_id"]), "Audit boundary application")), actor
        )
    persisted = await database["applications"].find_one({"name": "Audit boundary application"})
    assert persisted is not None and persisted["portfolioId"] == portfolio["_id"]
    assert await database["audit_logs"].count_documents({"entityType": "application"}) == audit_count


def test_application_create_schema_rejects_missing_fields_and_invalid_json_types() -> None:
    """Reject omitted required source fields and non-scalar typed values."""
    source = application_values(str(ObjectId()))
    missing = dict(source)
    missing.pop("name")
    for invalid in (missing, source | {"name": None}, source | {"tier": {"$gt": 1}}, source | {"description": []}):
        with pytest.raises(ValueError):
            ApplicationCreate(**invalid)
