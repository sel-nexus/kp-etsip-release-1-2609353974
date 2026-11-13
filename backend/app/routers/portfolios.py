"""Expose authenticated, permission-scoped portfolio inventory routes."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request, Response, status
from pymongo.asynchronous.database import AsyncDatabase

from app.repositories.audit import AuditRepository
from app.repositories.portfolios import PortfoliosRepository
from app.routers.auth import get_authenticated_user
from app.schemas.portfolio import (
    ApplicationPage,
    PortfolioCreate,
    PortfolioDetail,
    PortfolioPage,
    PortfolioUpdate,
)
from app.services.portfolios import PortfoliosService
from app.services.policy import require_permission

router = APIRouter(prefix="/api/portfolios", tags=["portfolios"])
Administrator = Annotated[dict[str, Any], Depends(require_permission("administer"))]


def get_portfolios_service(request: Request) -> PortfoliosService:
    """Build portfolio operations from the lifespan-owned Mongo database."""
    database: AsyncDatabase[dict[str, Any]] = request.app.state.mongo_database
    return PortfoliosService(PortfoliosRepository(database), AuditRepository(database))


@router.get("", response_model=PortfolioPage, summary="List visible portfolios")
async def list_portfolios(
    user: Annotated[dict[str, Any], Depends(get_authenticated_user)],
    service: Annotated[PortfoliosService, Depends(get_portfolios_service)],
    search: Annotated[str | None, Query(max_length=120)] = None,
    portfolio_status: Annotated[str | None, Query(alias="status", pattern="^(Active|Archived)$")] = None,
    product_area: Annotated[str | None, Query(alias="productArea", max_length=120)] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(alias="pageSize", ge=1, le=100)] = 25,
) -> PortfolioPage:
    """Return filtered, visible portfolio records in a bounded page."""
    return await service.list_portfolios(user, search, portfolio_status, product_area, page, page_size)


@router.get("/{portfolio_id}/applications", response_model=ApplicationPage, summary="List linked applications")
async def list_portfolio_applications(
    portfolio_id: str,
    user: Annotated[dict[str, Any], Depends(get_authenticated_user)],
    service: Annotated[PortfoliosService, Depends(get_portfolios_service)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(alias="pageSize", ge=1, le=100)] = 25,
) -> ApplicationPage:
    """Return applications for a portfolio only when it is accessible."""
    return await service.list_applications(portfolio_id, user, page, page_size)


@router.get("/{portfolio_id}", response_model=PortfolioDetail, summary="Read portfolio details")
async def get_portfolio(
    portfolio_id: str,
    user: Annotated[dict[str, Any], Depends(get_authenticated_user)],
    service: Annotated[PortfoliosService, Depends(get_portfolios_service)],
) -> PortfolioDetail:
    """Return a visible portfolio and its source-derived rollups."""
    return await service.get_portfolio(portfolio_id, user)


@router.post("", response_model=PortfolioDetail, status_code=status.HTTP_201_CREATED, summary="Create a portfolio")
async def create_portfolio(
    payload: PortfolioCreate,
    user: Administrator,
    service: Annotated[PortfoliosService, Depends(get_portfolios_service)],
) -> PortfolioDetail:
    """Create a portfolio through the administrator-only service rule."""
    return await service.create_portfolio(payload, user)


@router.put("/{portfolio_id}", response_model=PortfolioDetail, summary="Update a portfolio")
async def update_portfolio(
    portfolio_id: str,
    payload: PortfolioUpdate,
    user: Administrator,
    service: Annotated[PortfoliosService, Depends(get_portfolios_service)],
) -> PortfolioDetail:
    """Update portfolio fields and audit only a successful write."""
    return await service.update_portfolio(portfolio_id, payload, user)


@router.delete("/{portfolio_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete an unlinked portfolio")
async def delete_portfolio(
    portfolio_id: str,
    user: Administrator,
    service: Annotated[PortfoliosService, Depends(get_portfolios_service)],
) -> Response:
    """Delete an unlinked portfolio and return an empty successful response."""
    await service.delete_portfolio(portfolio_id, user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
