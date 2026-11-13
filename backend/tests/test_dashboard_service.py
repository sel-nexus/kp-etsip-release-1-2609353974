"""Verify dashboard formulas and comparisons using real Mongo aggregations."""

from typing import Any

import pytest
from bson import ObjectId
from pymongo import AsyncMongoClient

from app.schemas.dashboard import ExecutiveDashboardResponse
from app.services.dashboard import DashboardService


@pytest.mark.asyncio
async def test_executive_aggregates_seed_metrics_and_half_up_rounding(
    started_app: AsyncMongoClient[dict[str, Any]],
) -> None:
    """Match exact seeded data formulas and include visible zero-app portfolios."""
    database = started_app.get_database("ketsip_test")
    service = DashboardService(database)
    executive = {"role": "Executive", "permissions": ["view"], "portfolioAccess": []}

    response = await service.executive(executive)

    assert isinstance(response, ExecutiveDashboardResponse)
    assert response.model_dump() == {
        "enterpriseQualityScore": 81,
        "averageApplicationHealthScore": 84,
        "automationMaturityScore": 75,
        "openCriticalDefects": 11,
        "applicationsAtRisk": 3,
        "totalApplications": 10,
        "totalPortfolios": 3,
        "portfolioQualityScores": [
            {"portfolioId": str(row["_id"]), "portfolioName": row["name"], "qualityScore": score, "highRiskApplicationCount": risk}
            for row, score, risk in [
                (await database["portfolios"].find_one({"name": "Customer Platform"}), 82, 1),
                (await database["portfolios"].find_one({"name": "Data & Analytics"}), 83, 1),
                (await database["portfolios"].find_one({"name": "Payments"}), 79, 1),
            ]
        ],
    }


@pytest.mark.asyncio
async def test_filters_scope_before_aggregation_and_keep_visible_empty_portfolios(
    started_app: AsyncMongoClient[dict[str, Any]],
) -> None:
    """Apply all filters in Mongo and return null means and zero sums when empty."""
    database = started_app.get_database("ketsip_test")
    payment_portfolio = await database["portfolios"].find_one({"name": "Payments"})
    customer_portfolio = await database["portfolios"].find_one({"name": "Customer Platform"})
    assert payment_portfolio and customer_portfolio
    service = DashboardService(database)
    leader = {"role": "Portfolio Leader", "permissions": ["view"], "portfolioAccess": [payment_portfolio["_id"]]}

    filtered = await service.executive(leader, product_area="Payments", risk_level="High")
    empty = await service.executive(leader, product_area="Does not exist")

    assert filtered.totalApplications == 1
    assert filtered.enterpriseQualityScore == 73
    assert filtered.applicationsAtRisk == 1
    assert filtered.openCriticalDefects == 2
    assert filtered.totalPortfolios == 1
    assert [row.portfolioName for row in filtered.portfolioQualityScores] == ["Payments"]
    assert empty.totalApplications == 0
    assert empty.enterpriseQualityScore is None and empty.averageApplicationHealthScore is None and empty.automationMaturityScore is None
    assert empty.openCriticalDefects == empty.applicationsAtRisk == 0
    assert empty.totalPortfolios == 1
    assert empty.portfolioQualityScores[0].qualityScore is None and empty.portfolioQualityScores[0].highRiskApplicationCount == 0
    assert str(customer_portfolio["_id"]) not in {row.portfolioId for row in filtered.portfolioQualityScores}


@pytest.mark.asyncio
async def test_temporary_real_mongo_records_prove_exact_half_up_and_grouping(
    started_app: AsyncMongoClient[dict[str, Any]],
) -> None:
    """Insert and read temporary source records through Mongo's aggregation engine."""
    database = started_app.get_database("ketsip_test")
    portfolio_id = ObjectId()
    await database["portfolios"].insert_one({"_id": portfolio_id, "name": "Dashboard test", "productArea": "Test area"})
    base = {
        "portfolioId": portfolio_id,
        "productArea": "Test area",
        "qualityScore": 84,
        "applicationHealthScore": 80,
        "automationCoverage": 50,
        "openCriticalDefects": 0,
        "riskLevel": "Low",
    }
    await database["applications"].insert_many([
        dict(base, name="Half lower"),
        dict(base, name="Half upper", qualityScore=85, applicationHealthScore=81, automationCoverage=51),
    ])
    try:
        result = await DashboardService(database).executive(
            {"role": "Administrator", "permissions": ["view", "administer"], "portfolioAccess": []},
            portfolio_id=str(portfolio_id),
        )
        assert result.enterpriseQualityScore == 85
        assert result.averageApplicationHealthScore == 81
        assert result.automationMaturityScore == 51
        assert result.portfolioQualityScores[0].qualityScore == 85
        assert result.totalApplications == 2
    finally:
        await database["applications"].delete_many({"portfolioId": portfolio_id, "name": {"$in": ["Half lower", "Half upper"]}})
        await database["portfolios"].delete_one({"_id": portfolio_id})


@pytest.mark.asyncio
async def test_invalid_and_invisible_portfolios_are_hidden(
    started_app: AsyncMongoClient[dict[str, Any]],
) -> None:
    """Use a uniform not-found response for malformed and unauthorized IDs."""
    from fastapi import HTTPException

    database = started_app.get_database("ketsip_test")
    customer = await database["portfolios"].find_one({"name": "Customer Platform"})
    payments = await database["portfolios"].find_one({"name": "Payments"})
    assert customer and payments
    service = DashboardService(database)
    actor = {"role": "Portfolio Leader", "permissions": ["view"], "portfolioAccess": [customer["_id"]]}

    for portfolio_id in ("not-an-object-id", str(payments["_id"])):
        with pytest.raises(HTTPException) as hidden:
            await service.executive(actor, portfolio_id=portfolio_id)
        assert hidden.value.status_code == 404

    with pytest.raises(HTTPException) as denied:
        await service.executive({"role": "Engineer", "permissions": [], "portfolioAccess": []})
    assert denied.value.status_code == 403
