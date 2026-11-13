"""Expose authorized table reports and explicitly requested CSV downloads."""

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from pymongo.asynchronous.database import AsyncDatabase

from app.routers.auth import get_authenticated_user
from app.schemas.report import ApplicationReportPage, PortfolioReportPage
from app.services.policy import has_permission
from app.services.reports import ReportsService, build_reports_service

router = APIRouter(prefix="/api/reports", tags=["reports"])


def get_reports_service(request: Request) -> ReportsService:
    """Bind report queries to the lifespan-owned Mongo database."""
    database: AsyncDatabase[dict[str, Any]] = request.app.state.mongo_database
    return build_reports_service(database)


def _require_view(user: dict[str, Any]) -> None:
    """Require current view permission for report table pages."""
    if not has_permission(user, "view"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This account may not view reports.")


def _require_export(user: dict[str, Any]) -> None:
    """Reject report requests unless the persisted user can export."""
    if not has_permission(user, "export"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This account may not export reports.")


@router.get("/applications", response_model=ApplicationReportPage, summary="List application report rows")
async def application_report(
    user: Annotated[dict[str, Any], Depends(get_authenticated_user)],
    service: Annotated[ReportsService, Depends(get_reports_service)],
    format: Annotated[Literal["csv"] | None, Query()] = None,
    search: Annotated[str | None, Query(max_length=160)] = None,
    portfolio_id: Annotated[str | None, Query(alias="portfolioId", max_length=64)] = None,
    criticality: Annotated[str | None, Query(pattern="^(Low|Medium|High|Critical)$")] = None,
    risk_level: Annotated[str | None, Query(alias="riskLevel", pattern="^(Low|Medium|High)$")] = None,
    lifecycle_status: Annotated[str | None, Query(alias="lifecycleStatus", pattern="^(Active|Deprecated|Retired)$")] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(alias="pageSize", ge=1, le=100)] = 25,
) -> ApplicationReportPage | Response:
    """Return filtered visible application report rows or a complete CSV."""
    _require_view(user)
    filters = {
        "search": search, "portfolioId": portfolio_id, "criticality": criticality,
        "riskLevel": risk_level, "lifecycleStatus": lifecycle_status,
    }
    if format == "csv":
        _require_export(user)
        content = await service.export_applications(user, filters)
        return Response(content, media_type="text/csv; charset=utf-8", headers={"Content-Disposition": 'attachment; filename="applications.csv"'})
    return await service.application_page(user, filters, page, page_size)


@router.get("/portfolios", response_model=PortfolioReportPage, summary="List portfolio report rows")
async def portfolio_report(
    user: Annotated[dict[str, Any], Depends(get_authenticated_user)],
    service: Annotated[ReportsService, Depends(get_reports_service)],
    format: Annotated[Literal["csv"] | None, Query()] = None,
    search: Annotated[str | None, Query(max_length=120)] = None,
    portfolio_status: Annotated[str | None, Query(alias="status", pattern="^(Active|Archived)$")] = None,
    product_area: Annotated[str | None, Query(alias="productArea", max_length=120)] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(alias="pageSize", ge=1, le=100)] = 25,
) -> PortfolioReportPage | Response:
    """Return filtered visible portfolio report rows or a complete CSV."""
    _require_view(user)
    filters = {"search": search, "status": portfolio_status, "productArea": product_area}
    if format == "csv":
        _require_export(user)
        content = await service.export_portfolios(user, filters)
        return Response(content, media_type="text/csv; charset=utf-8", headers={"Content-Disposition": 'attachment; filename="portfolios.csv"'})
    return await service.portfolio_page(user, filters, page, page_size)


__all__ = ["get_reports_service", "router"]
