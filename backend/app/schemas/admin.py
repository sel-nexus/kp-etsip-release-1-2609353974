"""Define typed administration requests and safe account and role responses."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

RoleName = Literal["Administrator", "Executive", "Portfolio Leader", "Engineer", "Auditor", "Read Only"]
Permission = Literal["view", "create", "edit", "delete", "export", "administer"]
AccountStatus = Literal["Active", "Inactive"]


class AdminUserRequest(BaseModel):
    """Validate fields allowed when creating a managed account."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    email: str = Field(min_length=3, max_length=254, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    role: RoleName
    portfolioAccess: list[str] = Field(default_factory=list, max_length=100)
    password: str = Field(min_length=12, max_length=128)
    status: AccountStatus = "Active"


class AdminUserUpdate(BaseModel):
    """Validate partial account edits without accepting persisted secrets."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=120)
    email: str | None = Field(default=None, min_length=3, max_length=254, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    role: RoleName | None = None
    portfolioAccess: list[str] | None = Field(default=None, max_length=100)
    password: str | None = Field(default=None, min_length=12, max_length=128)
    status: AccountStatus | None = None


class AdminUserResponse(BaseModel):
    """Expose a managed account without password or authentication secrets."""

    id: str
    name: str
    email: str
    role: RoleName
    portfolioAccess: list[str]
    status: AccountStatus
    lastLogin: str | None = None
    createdAt: str | None = None
    updatedAt: str | None = None


class RoleUpdateRequest(BaseModel):
    """Validate permission edits for one of the six persisted roles."""

    model_config = ConfigDict(extra="forbid")

    description: str = Field(min_length=1, max_length=240)
    permissions: list[Permission] = Field(max_length=6)


class RoleProvisionRequest(BaseModel):
    """Validate provisioning of one of the six supported role definitions."""

    model_config = ConfigDict(extra="forbid")

    name: RoleName
    description: str = Field(min_length=1, max_length=240)
    permissions: list[Permission] | None = Field(default=None, max_length=6)


class RoleResponse(BaseModel):
    """Expose a supported role and its editable permission set."""

    id: str
    name: RoleName
    description: str
    permissions: list[Permission]
