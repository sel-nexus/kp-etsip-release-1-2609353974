"""Expose administrator-only managed account endpoints."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pymongo.asynchronous.database import AsyncDatabase

from app.repositories.administration import AdministrationRepository
from app.repositories.audit import AuditRepository
from app.schemas.admin import AdminUserRequest, AdminUserResponse, AdminUserUpdate
from app.schemas.common import PageResponse
from app.services.administration import AdministrationService
from app.services.policy import require_permission

router = APIRouter(prefix="/api/users", tags=["administration"])
AdminUser = Annotated[dict[str, Any], Depends(require_permission("administer"))]


def get_administration_service(request: Request) -> AdministrationService:
    """Construct services from the live lifespan-owned Mongo database."""
    database: AsyncDatabase[dict[str, Any]] = request.app.state.mongo_database
    return AdministrationService(AdministrationRepository(database), AuditRepository(database))


@router.get("", response_model=PageResponse[AdminUserResponse], summary="List managed accounts")
async def list_users(
    actor: AdminUser,
    service: Annotated[AdministrationService, Depends(get_administration_service)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, alias="pageSize", ge=1, le=100),
) -> dict[str, Any]:
    """Return a bounded safe account listing."""
    return await service.list_users(page, page_size)


@router.post("", response_model=AdminUserResponse, status_code=status.HTTP_201_CREATED, summary="Create a managed account")
async def create_user(payload: AdminUserRequest, actor: AdminUser, service: Annotated[AdministrationService, Depends(get_administration_service)]) -> AdminUserResponse:
    """Create an account after validating role and portfolio references."""
    return await service.create_user(payload, actor)


@router.get("/{user_id}", response_model=AdminUserResponse, summary="Read one managed account")
async def get_user(user_id: str, actor: AdminUser, service: Annotated[AdministrationService, Depends(get_administration_service)]) -> AdminUserResponse:
    """Return one credential-free account response."""
    return await service.get_user(user_id)


@router.put("/{user_id}", response_model=AdminUserResponse, summary="Update a managed account")
async def update_user(user_id: str, payload: AdminUserUpdate, actor: AdminUser, service: Annotated[AdministrationService, Depends(get_administration_service)]) -> AdminUserResponse:
    """Update allowed fields, including status reactivation, without exposing credentials."""
    return await service.update_user(user_id, payload, actor)


@router.delete("/{user_id}", response_model=AdminUserResponse, summary="Deactivate a managed account")
async def delete_user(user_id: str, actor: AdminUser, service: Annotated[AdministrationService, Depends(get_administration_service)]) -> AdminUserResponse:
    """Soft deactivate a user account without deleting audit history."""
    return await service.deactivate_user(user_id, actor)
