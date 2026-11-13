"""Expose authenticated application inventory and administrator deletion routes."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request, Response, status
from pymongo.asynchronous.database import AsyncDatabase

from app.repositories.applications import ApplicationsRepository
from app.repositories.audit import AuditRepository
from app.routers.auth import get_authenticated_user
from app.schemas.application import (
    ApplicationCreate,
    ApplicationDetail,
    ApplicationPage,
    ApplicationUpdate,
)
from app.services.applications import ApplicationsService

router = APIRouter(prefix="/api/applications", tags=["applications"])


def get_applications_service(request: Request) -> ApplicationsService:
    """Build application services from the lifespan-owned Mongo database."""
    database: AsyncDatabase[dict[str, Any]] = request.app.state.mongo_database
    return ApplicationsService(ApplicationsRepository(database), AuditRepository(database))


@router.get("", response_model=ApplicationPage, summary="List visible applications")
async def list_applications(
    user: Annotated[dict[str, Any], Depends(get_authenticated_user)],
    service: Annotated[ApplicationsService, Depends(get_applications_service)],
    search: Annotated[str | None, Query(max_length=160)] = None,
    portfolio_id: Annotated[str | None, Query(alias="portfolioId", max_length=64)] = None,
    criticality: Annotated[str | None, Query(pattern="^(Low|Medium|High|Critical)$")] = None,
    risk_level: Annotated[str | None, Query(alias="riskLevel", pattern="^(Low|Medium|High)$")] = None,
    lifecycle_status: Annotated[str | None, Query(alias="lifecycleStatus", pattern="^(Active|Deprecated|Retired)$")] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(alias="pageSize", ge=1, le=100)] = 25,
) -> ApplicationPage:
    """Return a bounded, filtered page of applications visible to the user."""
    return await service.list_applications(
        user, search, portfolio_id, criticality, risk_level, lifecycle_status, page, page_size
    )


@router.get("/{application_id}", response_model=ApplicationDetail, summary="Read application details")
async def get_application(
    application_id: str,
    user: Annotated[dict[str, Any], Depends(get_authenticated_user)],
    service: Annotated[ApplicationsService, Depends(get_applications_service)],
) -> ApplicationDetail:
    """Return safe complete details for an accessible application."""
    return await service.get_application(application_id, user)


@router.post("", response_model=ApplicationDetail, status_code=status.HTTP_201_CREATED, summary="Create an application")
async def create_application(
    payload: ApplicationCreate,
    user: Annotated[dict[str, Any], Depends(get_authenticated_user)],
    service: Annotated[ApplicationsService, Depends(get_applications_service)],
) -> ApplicationDetail:
    """Create an application after enforcing role and portfolio write access."""
    return await service.create_application(payload, user)


@router.put("/{application_id}", response_model=ApplicationDetail, summary="Replace application source fields")
async def update_application(
    application_id: str,
    payload: ApplicationUpdate,
    user: Annotated[dict[str, Any], Depends(get_authenticated_user)],
    service: Annotated[ApplicationsService, Depends(get_applications_service)],
) -> ApplicationDetail:
    """Replace an accessible application and audit the successful change."""
    return await service.update_application(application_id, payload, user)


@router.delete("/{application_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete an application")
async def delete_application(
    application_id: str,
    user: Annotated[dict[str, Any], Depends(get_authenticated_user)],
    service: Annotated[ApplicationsService, Depends(get_applications_service)],
) -> Response:
    """Delete one application only for an administrator."""
    await service.delete_application(application_id, user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


__all__ = ["get_applications_service", "router"]
