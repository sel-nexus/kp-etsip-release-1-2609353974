"""Define typed authentication requests and safe profile responses."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class LoginRequest(BaseModel):
    """Validate a local account sign-in request."""

    model_config = ConfigDict(extra="forbid")

    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    password: str = Field(min_length=1, max_length=128)


class ProfileUser(BaseModel):
    """Expose only the signed-in user's safe profile and effective access."""

    id: str
    name: str
    email: str
    role: str
    status: str
    permissions: list[str]
    portfolioAccess: list[str]
    mustChangePassword: bool
    lastLogin: datetime | None
    defaultLandingPage: str | None
    landingPage: str
    allowedLandingPages: list[str]


class LoginResponse(BaseModel):
    """Return the backend-issued token and safe user profile."""

    token: str
    user: ProfileUser


class PasswordChangeRequest(BaseModel):
    """Validate a self-service password change."""

    model_config = ConfigDict(extra="forbid")

    currentPassword: str = Field(min_length=1, max_length=128)
    newPassword: str = Field(min_length=12, max_length=128)


class LandingPreferenceRequest(BaseModel):
    """Validate an allowlisted landing-page preference."""

    model_config = ConfigDict(extra="forbid")

    defaultLandingPage: Literal["/dashboard", "/applications"] | None


class LogoutResponse(BaseModel):
    """Acknowledge client-side logout of a bearer-token session."""

    success: bool


class PreferencesResponse(BaseModel):
    """Return the updated safe profile after a preference change."""

    user: ProfileUser
