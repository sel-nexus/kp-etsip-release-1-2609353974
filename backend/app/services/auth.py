"""Enforce local authentication and self-service profile rules."""

from datetime import UTC, datetime, timedelta
from typing import Any

from bson import ObjectId
from fastapi import HTTPException, status
from jose import JWTError, jwt
from passlib.context import CryptContext
from passlib.exc import UnknownHashError
from starlette.concurrency import run_in_threadpool

from app.core.config import Settings, settings
from app.repositories.users import UsersRepository
from app.schemas.auth import ProfileUser

PASSWORD_CONTEXT = CryptContext(schemes=["bcrypt"], deprecated="auto")
JWT_ALGORITHM = "HS256"
TOKEN_LIFETIME = timedelta(hours=8)
AUTH_FAILURE = "Invalid email or password."
DASHBOARD_ROLES = {"Administrator", "Executive"}


class AuthService:
    """Apply authentication rules using durable user and audit repositories."""

    def __init__(self, repository: UsersRepository, configuration: Settings = settings) -> None:
        """Bind auth operations to a Mongo repository and validated settings."""
        self.repository = repository
        self.configuration = configuration

    def create_token(self, user_id: str, now: datetime | None = None) -> str:
        """Sign an eight-hour bearer token for one Mongo account."""
        secret = self.configuration.require_jwt_secret()
        issued_at = now or datetime.now(UTC)
        claims = {"sub": user_id, "iat": issued_at, "exp": issued_at + TOKEN_LIFETIME}
        return jwt.encode(claims, secret, algorithm=JWT_ALGORITHM)

    async def login(self, email: str, password: str) -> tuple[str, ProfileUser]:
        """Authenticate a local account, audit its outcome, and issue a token."""
        user = await self.repository.find_by_email(email)
        password_matches = False
        if user and user.get("authSource", "local") == "local" and isinstance(user.get("passwordHash"), str):
            try:
                password_matches = await run_in_threadpool(PASSWORD_CONTEXT.verify, password, user["passwordHash"])
            except (UnknownHashError, ValueError, TypeError):
                password_matches = False
        if not user or not password_matches or user.get("status") != "Active":
            await self.repository.write_login_audit(user, False, self.repository.utc_now())
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=AUTH_FAILURE, headers={"WWW-Authenticate": "Bearer"})

        logged_in = await self.repository.update_last_login(user["_id"], self.repository.utc_now())
        if not logged_in:
            await self.repository.write_login_audit(user, False, self.repository.utc_now())
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=AUTH_FAILURE, headers={"WWW-Authenticate": "Bearer"})
        await self.repository.write_login_audit(logged_in, True, self.repository.utc_now())
        refreshed = await self.get_current_user(str(logged_in["_id"]))
        return self.create_token(str(logged_in["_id"])), self.to_profile(refreshed)

    async def get_current_user(self, user_id: str) -> dict[str, Any]:
        """Reload the active account and its current role permissions from Mongo."""
        user = await self.repository.find_by_id(user_id)
        if not user or user.get("status") != "Active":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.", headers={"WWW-Authenticate": "Bearer"})
        user["permissions"] = await self.repository.get_permissions(str(user.get("role", "")))
        return user

    async def authenticate_token(self, token: str) -> dict[str, Any]:
        """Validate token signature and expiry, then reload its current actor."""
        try:
            payload = jwt.decode(
                token,
                self.configuration.require_jwt_secret(),
                algorithms=[JWT_ALGORITHM],
                options={"require_exp": True, "require_sub": True},
            )
            subject = payload.get("sub")
            if not isinstance(subject, str) or not ObjectId.is_valid(subject):
                raise JWTError("Invalid subject")
        except (JWTError, RuntimeError) as exc:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.", headers={"WWW-Authenticate": "Bearer"}) from exc
        return await self.get_current_user(subject)

    async def change_password(self, user: dict[str, Any], current_password: str, new_password: str) -> ProfileUser:
        """Verify the current secret, clear first-login state, and re-read Mongo."""
        latest = await self.repository.find_by_id(str(user["_id"]))
        if not latest or latest.get("status") != "Active":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")
        current_hash = latest.get("passwordHash")
        if latest.get("authSource", "local") != "local" or not isinstance(current_hash, str):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect.")
        try:
            current_matches = await run_in_threadpool(PASSWORD_CONTEXT.verify, current_password, current_hash)
        except (UnknownHashError, ValueError, TypeError):
            current_matches = False
        if not current_matches:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect.")
        if await run_in_threadpool(PASSWORD_CONTEXT.verify, new_password, current_hash):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Choose a new password different from the current password.")
        at = self.repository.utc_now()
        new_hash = await run_in_threadpool(PASSWORD_CONTEXT.hash, new_password)
        changed = await self.repository.update_password(latest["_id"], current_hash, new_hash, at)
        if not changed:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="The account changed. Please retry.")
        await self.repository.write_user_audit(changed, "edit", "Self-service password changed", at)
        refreshed = await self.get_current_user(str(changed["_id"]))
        return self.to_profile(refreshed)

    async def set_landing_page(self, user: dict[str, Any], landing_page: str | None) -> ProfileUser:
        """Save only an allowlisted landing destination accessible to this role."""
        latest = await self.get_current_user(str(user["_id"]))
        if latest.get("mustChangePassword"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Change your password before updating preferences.")
        allowed = self.allowed_landing_pages(latest)
        if landing_page is not None and landing_page not in allowed:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="That landing page is not available for this account.")
        at = self.repository.utc_now()
        updated = await self.repository.update_landing_page(latest["_id"], landing_page, at)
        if not updated:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")
        await self.repository.write_user_audit(updated, "edit", "Default landing page changed", at)
        refreshed = await self.get_current_user(str(updated["_id"]))
        return self.to_profile(refreshed)

    @staticmethod
    def allowed_landing_pages(user: dict[str, Any]) -> list[str]:
        """Return destinations available under the account's effective role."""
        pages: list[str] = []
        permissions = set(user.get("permissions", []))
        if "view" in permissions:
            pages.append("/applications")
            if user.get("role") in DASHBOARD_ROLES:
                pages.insert(0, "/dashboard")
        return pages

    def default_landing_page(self, user: dict[str, Any]) -> str:
        """Resolve the persisted preference or the account role's safe default."""
        allowed = self.allowed_landing_pages(user)
        preference = user.get("defaultLandingPage")
        if preference in allowed:
            return str(preference)
        if user.get("role") in DASHBOARD_ROLES and "/dashboard" in allowed:
            return "/dashboard"
        if "/applications" in allowed:
            return "/applications"
        return "/profile"

    def to_profile(self, user: dict[str, Any]) -> ProfileUser:
        """Map a Mongo document to a safe public self-profile DTO."""
        return ProfileUser(
            id=str(user["_id"]),
            name=str(user.get("name", "")),
            email=str(user.get("email", "")),
            role=str(user.get("role", "")),
            status=str(user.get("status", "")),
            permissions=list(user.get("permissions", [])),
            portfolioAccess=[str(value) for value in user.get("portfolioAccess", [])],
            mustChangePassword=bool(user.get("mustChangePassword", False)),
            lastLogin=user.get("lastLogin"),
            defaultLandingPage=user.get("defaultLandingPage"),
            landingPage=self.default_landing_page(user),
            allowedLandingPages=self.allowed_landing_pages(user),
        )

    @staticmethod
    def require_password_changed(user: dict[str, Any]) -> None:
        """Reject normal protected operations until the first password change."""
        if user.get("mustChangePassword"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Change your password before continuing.")
