"""Verify portfolio queries and mutations against the real Mongo test database."""

from typing import Any

import pytest
from bson import ObjectId
from fastapi import HTTPException
from pymongo import AsyncMongoClient

from app.repositories.audit import AuditRepository
from app.repositories.portfolios import PortfoliosRepository
from app.schemas.portfolio import PortfolioCreate, PortfolioUpdate
from app.services.portfolios import PortfoliosService


@pytest.mark.asyncio
async def test_listing_applies_assigned_scope_and_filters_before_count(
    started_app: AsyncMongoClient[dict[str, Any]],
) -> None:
    """Count only portfolio documents inside an assigned user scope."""
    database = started_app.get_database("ketsip_test")
    portfolio = await database["portfolios"].find_one({"name": "Payments"})
    assert portfolio is not None
    actor = {"role": "Portfolio Leader", "permissions": ["view"], "portfolioAccess": [portfolio["_id"]]}
    service = PortfoliosService(PortfoliosRepository(database), AuditRepository(database))

    page = await service.list_portfolios(actor, None, "Active", None, 1, 100)

    assert page.total == 1
    assert [item.name for item in page.items] == ["Payments"]


@pytest.mark.asyncio
async def test_portfolio_details_derive_count_and_quality_mean_from_applications(
    started_app: AsyncMongoClient[dict[str, Any]],
) -> None:
    """Compute detail rollups from linked applications and represent empty means as null."""
    database = started_app.get_database("ketsip_test")
    portfolio = await database["portfolios"].find_one({"name": "Payments"})
    assert portfolio is not None
    actor = {"role": "Administrator", "permissions": ["view", "administer"], "portfolioAccess": []}
    service = PortfoliosService(PortfoliosRepository(database), AuditRepository(database))

    details = await service.get_portfolio(str(portfolio["_id"]), actor)
    assert details.applicationCount == 3
    assert details.qualityScore == pytest.approx((78 + 86 + 73) / 3)

    empty_id = ObjectId()
    await database["portfolios"].insert_one({
        "_id": empty_id, "name": "Empty Rollup", "owner": "Platform", "description": "No linked apps",
        "productArea": "Internal", "status": "Active",
    })
    empty = await service.get_portfolio(str(empty_id), actor)
    assert empty.applicationCount == 0
    assert empty.qualityScore is None


@pytest.mark.asyncio
async def test_service_audits_successful_changes_and_rejects_duplicate_names(
    started_app: AsyncMongoClient[dict[str, Any]],
) -> None:
    """Audit successful administrator changes once and reject duplicate names without audit."""
    database = started_app.get_database("ketsip_test")
    actor_row = await database["users"].find_one({"email": "admin@ketsip.local"})
    assert actor_row is not None
    actor = {"_id": actor_row["_id"], "name": actor_row["name"], "role": "Administrator", "permissions": ["administer"]}
    service = PortfoliosService(PortfoliosRepository(database), AuditRepository(database))
    baseline = await database["audit_logs"].count_documents({"entityType": "portfolio"})

    created = await service.create_portfolio(PortfolioCreate(
        name="Service Created", owner="Platform", description="Created via service", productArea="Platform", status="Active",
    ), actor)
    assert created.name == "Service Created"
    updated = await service.update_portfolio(created.id, PortfolioUpdate(owner="Updated owner"), actor)
    assert updated.owner == "Updated owner"
    stored_after_update = await database["portfolios"].find_one({"_id": ObjectId(created.id)})
    assert stored_after_update is not None
    assert stored_after_update["owner"] == "Updated owner"
    with pytest.raises(HTTPException) as duplicate:
        await service.create_portfolio(PortfolioCreate(
            name="Payments", owner="Platform", description="Duplicate", productArea="Payments", status="Active",
        ), actor)
    assert duplicate.value.status_code == 409
    assert await database["audit_logs"].count_documents({"entityType": "portfolio"}) == baseline + 2


@pytest.mark.asyncio
async def test_rejected_portfolio_update_preserves_stored_values_and_audit(
    started_app: AsyncMongoClient[dict[str, Any]],
) -> None:
    """Reject duplicate-name edits without changing stored portfolio or audit state."""
    database = started_app.get_database("ketsip_test")
    existing = await database["portfolios"].find_one({"name": "Payments"})
    admin = await database["users"].find_one({"email": "admin@ketsip.local"})
    assert existing and admin
    actor = {
        "_id": admin["_id"], "name": admin["name"], "role": "Administrator",
        "permissions": ["view", "administer"],
    }
    service = PortfoliosService(PortfoliosRepository(database), AuditRepository(database))
    baseline = await database["portfolios"].find_one({"_id": existing["_id"]})
    audit_count = await database["audit_logs"].count_documents({"entityType": "portfolio"})

    with pytest.raises(HTTPException) as duplicate:
        await service.update_portfolio(str(existing["_id"]), PortfolioUpdate(name="Customer Platform"), actor)

    assert duplicate.value.status_code == 409
    assert await database["portfolios"].find_one({"_id": existing["_id"]}) == baseline
    assert await database["audit_logs"].count_documents({"entityType": "portfolio"}) == audit_count


@pytest.mark.asyncio
async def test_service_hides_inaccessible_portfolios_and_denies_non_admin_writes(
    started_app: AsyncMongoClient[dict[str, Any]],
) -> None:
    """Use consistent not-found responses for inaccessible details and applications."""
    database = started_app.get_database("ketsip_test")
    portfolio = await database["portfolios"].find_one({"name": "Payments"})
    assert portfolio is not None
    actor = {"role": "Portfolio Leader", "permissions": ["view", "create", "edit"], "portfolioAccess": []}
    service = PortfoliosService(PortfoliosRepository(database), AuditRepository(database))

    for operation in (
        service.get_portfolio(str(portfolio["_id"]), actor),
        service.list_applications(str(portfolio["_id"]), actor, 1, 20),
    ):
        with pytest.raises(HTTPException) as inaccessible:
            await operation
        assert inaccessible.value.status_code == 404
    with pytest.raises(HTTPException) as denied:
        await service.create_portfolio(PortfolioCreate(
            name="Unauthorized", owner="Team", description="No", productArea="Platform", status="Active",
        ), actor)
    assert denied.value.status_code == 403


@pytest.mark.asyncio
async def test_referenced_delete_conflict_preserves_portfolio_applications_and_audit(
    started_app: AsyncMongoClient[dict[str, Any]],
) -> None:
    """Preserve both sides of a linked reference and record no delete audit on conflict."""
    database = started_app.get_database("ketsip_test")
    portfolio = await database["portfolios"].find_one({"name": "Payments"})
    assert portfolio is not None
    actor_row = await database["users"].find_one({"email": "admin@ketsip.local"})
    assert actor_row is not None
    actor = {"_id": actor_row["_id"], "name": actor_row["name"], "role": "Administrator", "permissions": ["administer"]}
    service = PortfoliosService(PortfoliosRepository(database), AuditRepository(database))
    before_apps = await database["applications"].count_documents({"portfolioId": portfolio["_id"]})
    before_audits = await database["audit_logs"].count_documents({"entityType": "portfolio", "action": "delete"})

    with pytest.raises(HTTPException) as conflict:
        await service.delete_portfolio(str(portfolio["_id"]), actor)

    assert conflict.value.status_code == 409
    assert await database["portfolios"].find_one({"_id": portfolio["_id"]}) is not None
    assert await database["applications"].count_documents({"portfolioId": portfolio["_id"]}) == before_apps
    assert await database["audit_logs"].count_documents({"entityType": "portfolio", "action": "delete"}) == before_audits


@pytest.mark.asyncio
async def test_portfolio_update_lost_row_and_audit_failure_preserve_expected_mongo_state(
    started_app: AsyncMongoClient[dict[str, Any]],
) -> None:
    """Return not-found after a lost update race and show a committed write if audit fails."""
    database = started_app.get_database("ketsip_test")
    portfolio = await database["portfolios"].find_one({"name": "Payments"})
    admin = await database["users"].find_one({"email": "admin@ketsip.local"})
    assert portfolio is not None and admin is not None
    actor = {"_id": admin["_id"], "name": admin["name"], "role": "Administrator", "permissions": ["view", "administer"]}
    audit_count = await database["audit_logs"].count_documents({"entityType": "portfolio"})

    class DeletingPortfolioRepository(PortfoliosRepository):
        """Remove the portfolio after service lookup but before its conditional write."""

        async def update_portfolio(self, portfolio_id: str, changes: dict[str, Any]) -> dict[str, Any] | None:
            await self.portfolios.delete_one({"_id": ObjectId(portfolio_id)})
            return await super().update_portfolio(portfolio_id, changes)

    raced = PortfoliosService(DeletingPortfolioRepository(database), AuditRepository(database))
    with pytest.raises(HTTPException) as missing:
        await raced.update_portfolio(str(portfolio["_id"]), PortfolioUpdate(owner="Raced write"), actor)
    assert missing.value.status_code == 404
    assert await database["portfolios"].find_one({"_id": portfolio["_id"]}) is None
    assert await database["audit_logs"].count_documents({"entityType": "portfolio"}) == audit_count

    class FailingAuditRepository(AuditRepository):
        """Fail after portfolio persistence to expose the non-transactional boundary."""

        async def record(self, actor: dict[str, Any], action: str, entity_type: str, entity_id: str | None, details: str, at: Any) -> None:
            raise RuntimeError("simulated audit persistence failure")

    failure_service = PortfoliosService(PortfoliosRepository(database), FailingAuditRepository(database))
    with pytest.raises(RuntimeError, match="audit persistence failure"):
        await failure_service.create_portfolio(
            PortfolioCreate(name="Audit boundary portfolio", owner="Platform", description="Stored before audit", productArea="Platform", status="Active"),
            actor,
        )
    persisted = await database["portfolios"].find_one({"name": "Audit boundary portfolio"})
    assert persisted is not None and persisted["description"] == "Stored before audit"
    assert await database["audit_logs"].count_documents({"entityType": "portfolio"}) == audit_count


def test_portfolio_create_schema_rejects_missing_fields_and_invalid_json_types() -> None:
    """Reject omitted required fields and non-scalar values in portfolio schemas."""
    values = {
        "name": "Schema portfolio",
        "owner": "Platform",
        "description": "Schema validation",
        "productArea": "Internal",
        "status": "Active",
    }
    missing = dict(values)
    missing.pop("name")
    for invalid in (missing, values | {"owner": None}, values | {"status": {"$ne": "Archived"}}):
        with pytest.raises(ValueError):
            PortfolioCreate(**invalid)
    for invalid in ({"owner": ["not", "a", "string"]}, {"$set": {"owner": "injected"}}):
        with pytest.raises(ValueError):
            PortfolioUpdate(**invalid)
