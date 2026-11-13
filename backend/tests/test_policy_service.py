"""Exercise permission matrices and portfolio policy branches."""

import pytest

from app.services.policy import GLOBAL_EMPTY_PORTFOLIO_ROLES, ROLE_PERMISSIONS, can_access_portfolio, has_permission


def test_six_roles_have_exact_permission_matrix() -> None:
    """Keep supported role capabilities explicit and stable."""
    assert ROLE_PERMISSIONS == {
        "Administrator": frozenset({"view", "create", "edit", "delete", "export", "administer"}),
        "Executive": frozenset({"view", "export"}),
        "Portfolio Leader": frozenset({"view", "create", "edit", "export"}),
        "Engineer": frozenset({"view", "create", "edit", "export"}),
        "Auditor": frozenset({"view", "export"}),
        "Read Only": frozenset({"view"}),
    }
    assert len(ROLE_PERMISSIONS) == 6


@pytest.mark.parametrize("role", sorted(GLOBAL_EMPTY_PORTFOLIO_ROLES))
def test_empty_portfolio_scope_allows_global_read(role: str) -> None:
    """Allow global viewing for only the three designated empty-scope roles."""
    user = {"role": role, "permissions": ["view"], "portfolioAccess": []}
    assert can_access_portfolio(user, "portfolio-1")
    assert not can_access_portfolio(user, "portfolio-1", write=True)


@pytest.mark.parametrize("role", ["Portfolio Leader", "Engineer", "Read Only"])
def test_empty_portfolio_scope_denies_non_global_roles(role: str) -> None:
    """Deny portfolio access to other roles when the assignment list is empty."""
    user = {"role": role, "permissions": ["view", "create", "edit"], "portfolioAccess": []}
    assert not can_access_portfolio(user, "portfolio-1")
    assert not can_access_portfolio(user, "portfolio-1", write=True)


def test_assigned_portfolio_scope_and_fresh_permissions_are_enforced() -> None:
    """Restrict scoped writes and require a current permission in the user record."""
    user = {"role": "Portfolio Leader", "permissions": ["view", "edit"], "portfolioAccess": ["p-1"]}
    assert can_access_portfolio(user, "p-1", write=True)
    assert not can_access_portfolio(user, "p-2", write=True)
    assert has_permission(user, "edit")
    user["permissions"] = ["view"]
    assert not has_permission(user, "edit")
    assert not can_access_portfolio(user, "p-1", write=True)


def test_missing_view_permission_denies_portfolio_read() -> None:
    """Require view access even for a portfolio assignment."""
    user = {"role": "Engineer", "permissions": ["edit"], "portfolioAccess": ["p-1"]}
    assert not can_access_portfolio(user, "p-1")
