"""Provide persisted-permission authorization and role scope policy."""

from typing import Annotated, Any

from fastapi import Depends, HTTPException, Request, status

from app.routers.auth import get_authenticated_user

ROLE_PERMISSIONS: dict[str, frozenset[str]] = {
    "Administrator": frozenset({"view", "create", "edit", "delete", "export", "administer"}),
    "Executive": frozenset({"view", "export"}),
    "Portfolio Leader": frozenset({"view", "create", "edit", "export"}),
    "Engineer": frozenset({"view", "create", "edit", "export"}),
    "Auditor": frozenset({"view", "export"}),
    "Read Only": frozenset({"view"}),
}
ALLOWED_PERMISSIONS = frozenset({"view", "create", "edit", "delete", "export", "administer"})
GLOBAL_EMPTY_PORTFOLIO_ROLES = frozenset({"Administrator", "Executive", "Auditor"})


def has_permission(user: dict[str, Any], permission: str) -> bool:
    """Check an effective permission freshly loaded from the persisted role."""
    return permission in user.get("permissions", [])


def can_access_portfolio(user: dict[str, Any], portfolio_id: str, *, write: bool = False) -> bool:
    """Apply explicit portfolio assignments and role-specific empty-scope rules."""
    if not has_permission(user, "view"):
        return False
    if write and not any(has_permission(user, permission) for permission in ("create", "edit", "administer")):
        return False
    assigned = {str(value) for value in user.get("portfolioAccess", [])}
    if not assigned:
        if write:
            return str(user.get("role")) == "Administrator" and has_permission(user, "administer")
        return str(user.get("role")) in GLOBAL_EMPTY_PORTFOLIO_ROLES
    return portfolio_id in assigned


def require_permission(permission: str):
    """Build a dependency that enforces one fresh persisted permission."""
    async def dependency(user: Annotated[dict[str, Any], Depends(get_authenticated_user)]) -> dict[str, Any]:
        """Reject users without the requested effective capability."""
        if not has_permission(user, permission):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This account is not authorized for this action.")
        return user
    return dependency


def get_policy_user(request: Request, user: Annotated[dict[str, Any], Depends(get_authenticated_user)]) -> dict[str, Any]:
    """Expose the authenticated account while requiring a request database context."""
    if not getattr(request.app.state, "mongo_database", None):
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database is unavailable.")
    return user


AdminUser = Annotated[dict[str, Any], Depends(require_permission("administer"))]
AuditUser = Annotated[dict[str, Any], Depends(require_permission("administer"))]


def require_audit_access():
    """Build the administrator-or-auditor audit-read dependency."""
    async def dependency(user: Annotated[dict[str, Any], Depends(get_authenticated_user)]) -> dict[str, Any]:
        """Allow only the administering role or the read-only Auditor role."""
        if not has_permission(user, "administer") and user.get("role") != "Auditor":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Audit history is not available to this account.")
        return user
    return dependency
