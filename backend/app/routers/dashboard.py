"""Expose authenticated executive dashboard measures and comparisons."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request
from pymongo.asynchronous.database import AsyncDatabase

from app.routers.auth import get_authenticated_user
from app.schemas.dashboard import ExecutiveDashboardResponse
from app.services.dashboard import DashboardService

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


def get_dashboard_service(request: Request) -> DashboardService:
    """Build dashboard aggregation from the lifespan-owned Mongo database."""
    database: AsyncDatabase[dict[str, Any]] = request.app.state.mongo_database
    return DashboardService(database)


@router.get("/executive", response_model=ExecutiveDashboardResponse, summary="Read executive dashboard metrics")
async def executive_dashboard(
    user: Annotated[dict[str, Any], Depends(get_authenticated_user)],
    service: Annotated[DashboardService, Depends(get_dashboard_service)],
    portfolio_id: Annotated[str | None, Query(alias="portfolioId", pattern="^[0-9a-fA-F]{24}$")] = None,
    product_area: Annotated[str | None, Query(alias="productArea", max_length=120)] = None,
    risk_level: Annotated[str | None, Query(alias="riskLevel", pattern="^(Low|Medium|High)$")] = None,
) -> ExecutiveDashboardResponse:
    """Return formula-based metrics scoped to visible portfolios and filters."""
    return await service.executive(user, portfolio_id, product_area, risk_level)


__all__ = ["get_dashboard_service", "router"]
