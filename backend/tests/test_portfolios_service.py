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
    with pytest.raises(HTTPException) as duplicate:
        await service.create_portfolio(PortfolioCreate(
            name="Payments", owner="Platform", description="Duplicate", productArea="Payments", status="Active",
        ), actor)
    assert duplicate.value.status_code == 409
    assert await database["audit_logs"].count_documents({"entityType": "portfolio"}) == baseline + 2


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
