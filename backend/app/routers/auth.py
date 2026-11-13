"""Expose bearer-token sign-in and self-service profile endpoints."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from pymongo.asynchronous.database import AsyncDatabase

from app.repositories.users import UsersRepository
from app.schemas.auth import (
    LandingPreferenceRequest,
    LoginRequest,
    LoginResponse,
    LogoutResponse,
    PasswordChangeRequest,
    PreferencesResponse,
    ProfileUser,
)
from app.services.auth import AuthService

router = APIRouter(prefix="/api/auth", tags=["auth"])
bearer_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def get_auth_service(request: Request) -> AuthService:
    """Build a service using the Mongo database owned by app lifespan."""
    database: AsyncDatabase[dict[str, Any]] = request.app.state.mongo_database
    return AuthService(UsersRepository(database))


async def get_authenticated_user(
    token: Annotated[str, Depends(bearer_scheme)],
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> dict[str, Any]:
    """Validate the signed token and reload active user and role from Mongo."""
    return await service.authenticate_token(token)


@router.post("/login", response_model=LoginResponse, summary="Sign in with a local account")
async def login(
    payload: LoginRequest,
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> LoginResponse:
    """Return a signed bearer token and safe account profile."""
    token, user = await service.login(str(payload.email), payload.password)
    return LoginResponse(token=token, user=user)


@router.post("/logout", response_model=LogoutResponse, summary="Acknowledge bearer-token logout")
async def logout(user: Annotated[dict[str, Any], Depends(get_authenticated_user)]) -> LogoutResponse:
    """Acknowledge logout; bearer tokens are revoked by clearing client state."""
    return LogoutResponse(success=True)


@router.get("/me", response_model=ProfileUser, summary="Read the current safe profile")
async def current_profile(
    user: Annotated[dict[str, Any], Depends(get_authenticated_user)],
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> ProfileUser:
    """Return the current user's safe profile and effective access."""
    return service.to_profile(user)


@router.put("/me/password", response_model=ProfileUser, summary="Change the current user's password")
async def change_password(
    payload: PasswordChangeRequest,
    user: Annotated[dict[str, Any], Depends(get_authenticated_user)],
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> ProfileUser:
    """Verify and update only the authenticated user's password."""
    return await service.change_password(user, payload.currentPassword, payload.newPassword)


@router.put("/me/preferences", response_model=PreferencesResponse, summary="Save the current user's landing preference")
async def update_preferences(
    payload: LandingPreferenceRequest,
    user: Annotated[dict[str, Any], Depends(get_authenticated_user)],
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> PreferencesResponse:
    """Persist a landing page only when the user's role can access it."""
    service.require_password_changed(user)
    updated = await service.set_landing_page(user, payload.defaultLandingPage)
    return PreferencesResponse(user=updated)


__all__ = ["get_auth_service", "get_authenticated_user", "router"]
