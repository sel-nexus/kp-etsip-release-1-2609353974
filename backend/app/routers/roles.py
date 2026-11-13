"""Expose administrator-only role listing and permission editing."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from pymongo.asynchronous.database import AsyncDatabase

from app.repositories.administration import AdministrationRepository
from app.repositories.audit import AuditRepository
from app.routers.users import get_administration_service
from app.schemas.admin import RoleResponse, RoleUpdateRequest
from app.services.administration import AdministrationService
from app.services.policy import require_permission

router = APIRouter(prefix="/api/roles", tags=["administration"])
AdminUser = Annotated[dict[str, Any], Depends(require_permission("administer"))]


@router.get("", response_model=list[RoleResponse], summary="List the supported roles")
async def list_roles(actor: AdminUser, service: Annotated[AdministrationService, Depends(get_administration_service)]) -> list[RoleResponse]:
    """Return only the six supported persisted roles."""
    return await service.list_roles()


@router.put("/{role_name}", response_model=RoleResponse, summary="Edit role permissions")
async def update_role(role_name: str, payload: RoleUpdateRequest, actor: AdminUser, service: Annotated[AdministrationService, Depends(get_administration_service)]) -> RoleResponse:
    """Update one existing supported role and audit its permission changes."""
    return await service.update_role(role_name, payload, actor)
