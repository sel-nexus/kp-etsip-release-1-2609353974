"""Enforce account and role administration rules over Mongo repositories."""

from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, status
from passlib.context import CryptContext
from pymongo.errors import DuplicateKeyError
from starlette.concurrency import run_in_threadpool

from app.repositories.administration import AdministrationRepository
from app.repositories.audit import AuditRepository
from app.schemas.admin import AdminUserRequest, AdminUserResponse, AdminUserUpdate, RoleProvisionRequest, RoleResponse, RoleUpdateRequest

ROLE_NAMES = ["Administrator", "Executive", "Portfolio Leader", "Engineer", "Auditor", "Read Only"]
DEFAULT_ROLE_PERMISSIONS: dict[str, list[str]] = {
    "Administrator": ["view", "create", "edit", "delete", "export", "administer"],
    "Executive": ["view", "create", "edit", "delete", "export"],
    "Portfolio Leader": ["view", "create", "edit", "delete", "export"],
    "Engineer": ["view", "create", "edit", "export"],
    "Auditor": ["view", "export"],
    "Read Only": ["view"],
}
PASSWORD_CONTEXT = CryptContext(schemes=["bcrypt"], deprecated="auto")


class AdministrationService:
    """Manage supported roles and accounts with durable audit events."""

    def __init__(self, repository: AdministrationRepository, audit: AuditRepository) -> None:
        """Bind account and audit operations to the same Mongo database."""
        self.repository = repository
        self.audit = audit

    async def list_users(self, page: int, page_size: int) -> dict[str, Any]:
        """Return safe user records in a bounded page."""
        rows, total = await self.repository.list_users(page, page_size)
        return {"items": [self._safe_user(row) for row in rows], "page": page, "pageSize": page_size, "total": total}

    async def get_user(self, user_id: str) -> AdminUserResponse:
        """Return one managed account or a not-found response."""
        row = await self.repository.get_user(user_id)
        if not row:
            raise HTTPException(status_code=404, detail="User not found.")
        return self._safe_user(row)

    async def create_user(self, payload: AdminUserRequest, actor: dict[str, Any]) -> AdminUserResponse:
        """Validate all references, insert an account, and record creation."""
        if not payload.name.strip() or not payload.email.strip():
            raise HTTPException(status_code=422, detail="Name and email must not be blank.")
        if not await self.repository.portfolios_exist(payload.portfolioAccess):
            raise HTTPException(status_code=422, detail="Every portfolioAccess reference must identify an existing portfolio.")
        now = datetime.now(UTC)
        document = {
            "name": payload.name.strip(), "email": payload.email.strip().lower(), "passwordHash": await run_in_threadpool(PASSWORD_CONTEXT.hash, payload.password),
            "role": payload.role, "portfolioAccess": payload.portfolioAccess, "status": payload.status,
            "authSource": "local", "mustChangePassword": True, "lastLogin": None, "createdAt": now, "updatedAt": now,
        }
        try:
            row = await self.repository.create_user(document)
        except DuplicateKeyError as exc:
            raise HTTPException(status_code=409, detail="An account already uses this email address.") from exc
        await self.audit.record(actor, "create", "user", str(row["_id"]), "Managed account created", now)
        return self._safe_user(row)

    async def update_user(self, user_id: str, payload: AdminUserUpdate, actor: dict[str, Any]) -> AdminUserResponse:
        """Update allowed account fields and audit the successful change."""
        existing = await self.repository.get_user(user_id)
        if not existing:
            raise HTTPException(status_code=404, detail="User not found.")
        changes = payload.model_dump(exclude_unset=True)
        if not changes:
            raise HTTPException(status_code=422, detail="At least one account field is required.")
        if ("name" in changes and not changes["name"].strip()) or ("email" in changes and not changes["email"].strip()):
            raise HTTPException(status_code=422, detail="Name and email must not be blank.")
        if "portfolioAccess" in changes and not await self.repository.portfolios_exist(changes["portfolioAccess"] or []):
            raise HTTPException(status_code=422, detail="Every portfolioAccess reference must identify an existing portfolio.")
        new_password = changes.pop("password", None)
        if new_password:
            changes["passwordHash"] = await run_in_threadpool(PASSWORD_CONTEXT.hash, new_password)
            changes["mustChangePassword"] = True
        role_changed = "role" in changes and changes["role"] != existing["role"]
        if "email" in changes:
            changes["email"] = changes["email"].strip().lower()
        if "name" in changes:
            changes["name"] = changes["name"].strip()
        try:
            row = await self.repository.update_user(user_id, changes)
        except DuplicateKeyError as exc:
            raise HTTPException(status_code=409, detail="An account already uses this email address.") from exc
        if not row:
            raise HTTPException(status_code=404, detail="User not found.")
        action = "roleChange" if role_changed else "edit"
        details = "Account role changed" if role_changed else "Managed account updated"
        await self.audit.record(actor, action, "user", user_id, details, datetime.now(UTC))
        return self._safe_user(row)

    async def deactivate_user(self, user_id: str, actor: dict[str, Any]) -> AdminUserResponse:
        """Soft deactivate an account and preserve its persisted identity."""
        row = await self.repository.deactivate_user(user_id)
        if not row:
            raise HTTPException(status_code=404, detail="User not found.")
        await self.audit.record(actor, "delete", "user", user_id, "Managed account deactivated", datetime.now(UTC))
        return self._safe_user(row)

    async def list_roles(self) -> list[RoleResponse]:
        """Return the existing six supported roles and no additional records."""
        return [RoleResponse(id=str(row["_id"]), name=row["name"], description=row["description"], permissions=row["permissions"])
                for row in await self.repository.list_roles(ROLE_NAMES)]

    async def provision_role(self, payload: RoleProvisionRequest, actor: dict[str, Any]) -> tuple[RoleResponse, bool]:
        """Provision an absent supported role without changing an existing one."""
        if payload.name not in ROLE_NAMES:
            raise HTTPException(status_code=422, detail="Only the six supported roles can be provisioned.")
        default_permissions = DEFAULT_ROLE_PERMISSIONS[payload.name]
        permissions = default_permissions if payload.permissions is None else payload.permissions
        if len(set(permissions)) != len(permissions):
            raise HTTPException(status_code=422, detail="Permissions must not contain duplicates.")
        if not set(permissions).issubset(default_permissions):
            raise HTTPException(status_code=422, detail="Permissions must be a subset of the role's default permissions.")

        now = datetime.now(UTC)
        row, created = await self.repository.provision_role({
            "name": payload.name,
            "description": payload.description,
            "permissions": permissions,
            "createdAt": now,
            "updatedAt": now,
        })
        if created:
            await self.audit.record(actor, "create", "role", str(row["_id"]), f"Supported role provisioned: {payload.name}", now)
        response = RoleResponse(id=str(row["_id"]), name=row["name"], description=row["description"], permissions=row["permissions"])
        return response, created

    async def update_role(self, name: str, payload: RoleUpdateRequest, actor: dict[str, Any]) -> RoleResponse:
        """Edit one existing role and audit a successful permission change."""
        if name not in ROLE_NAMES:
            raise HTTPException(status_code=404, detail="Role not found.")
        existing = await self.repository.get_role(name)
        if not existing:
            raise HTTPException(status_code=404, detail="Role not found.")
        if len(set(payload.permissions)) != len(payload.permissions):
            raise HTTPException(status_code=422, detail="Permissions must not contain duplicates.")
        changed = payload.permissions != existing.get("permissions", [])
        description_changed = payload.description != existing.get("description")
        row = await self.repository.update_role(name, payload.model_dump())
        if not row:
            raise HTTPException(status_code=404, detail="Role not found.")
        if changed:
            await self.audit.record(actor, "permissionChange", "role", str(row["_id"]), f"Permissions changed for {name}", datetime.now(UTC))
        elif description_changed:
            await self.audit.record(actor, "edit", "role", str(row["_id"]), f"Role description changed for {name}", datetime.now(UTC))
        return RoleResponse(id=str(row["_id"]), name=row["name"], description=row["description"], permissions=row["permissions"])

    @staticmethod
    def _safe_user(row: dict[str, Any]) -> AdminUserResponse:
        """Map a persisted account to its credential-free API representation."""
        return AdminUserResponse(
            id=str(row["_id"]), name=row["name"], email=row["email"], role=row["role"],
            portfolioAccess=[str(value) for value in row.get("portfolioAccess", [])], status=row["status"],
            lastLogin=row["lastLogin"].isoformat() if row.get("lastLogin") else None,
            createdAt=row["createdAt"].isoformat() if row.get("createdAt") else None,
            updatedAt=row["updatedAt"].isoformat() if row.get("updatedAt") else None,
        )
