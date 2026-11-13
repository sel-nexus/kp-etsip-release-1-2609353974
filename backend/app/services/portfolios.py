"""Enforce portfolio access, derive rollups, and audit successful changes."""

import re
from datetime import UTC, datetime
from typing import Any

from bson import ObjectId
from fastapi import HTTPException, status
from pymongo.errors import DuplicateKeyError

from app.repositories.audit import AuditRepository
from app.repositories.portfolios import PortfoliosRepository
from app.schemas.portfolio import (
    ApplicationListItem,
    ApplicationPage,
    PortfolioCreate,
    PortfolioDetail,
    PortfolioPage,
    PortfolioSummary,
    PortfolioUpdate,
)
from app.services.policy import can_access_portfolio, has_permission


class PortfoliosService:
    """Serve role-scoped portfolio inventory backed by MongoDB."""

    def __init__(self, repository: PortfoliosRepository, audit: AuditRepository) -> None:
        """Bind inventory decisions and audit records to Mongo repositories."""
        self.repository = repository
        self.audit = audit

    async def list_portfolios(
        self,
        user: dict[str, Any],
        search: str | None,
        portfolio_status: str | None,
        product_area: str | None,
        page: int,
        page_size: int,
    ) -> PortfolioPage:
        """Filter and paginate only portfolios visible to the signed-in user."""
        self._require_view(user)
        query: dict[str, Any] = {}
        scope = self._scope_query(user)
        if scope is not None:
            query.update(scope)
        if search:
            escaped = re.escape(search.strip())
            if escaped:
                query["$or"] = [
                    {"name": {"$regex": escaped, "$options": "i"}},
                    {"owner": {"$regex": escaped, "$options": "i"}},
                    {"description": {"$regex": escaped, "$options": "i"}},
                ]
        if portfolio_status:
            query["status"] = portfolio_status
        if product_area:
            query["productArea"] = product_area
        rows, total = await self.repository.list_portfolios(query, page, page_size)
        rollups = await self.repository.rollups([str(row["_id"]) for row in rows])
        items = [self._summary(row, rollups) for row in rows]
        return PortfolioPage(items=items, page=page, pageSize=page_size, total=total)

    async def get_portfolio(self, portfolio_id: str, user: dict[str, Any]) -> PortfolioDetail:
        """Return accessible portfolio details with source-derived measures."""
        self._require_view(user)
        row = await self.repository.get_portfolio(portfolio_id)
        if not row or not can_access_portfolio(user, portfolio_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Portfolio not found.")
        rollups = await self.repository.rollups([portfolio_id])
        summary = self._summary(row, rollups)
        return PortfolioDetail(**summary.model_dump(), description=row["description"])

    async def list_applications(
        self, portfolio_id: str, user: dict[str, Any], page: int, page_size: int
    ) -> ApplicationPage:
        """Return bounded linked applications only when their portfolio is visible."""
        self._require_view(user)
        portfolio = await self.repository.get_portfolio(portfolio_id)
        if not portfolio or not can_access_portfolio(user, portfolio_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Portfolio not found.")
        rows, total = await self.repository.list_applications(
            {"portfolioId": ObjectId(portfolio_id)}, page, page_size
        )
        return ApplicationPage(
            items=[self._application(row) for row in rows], page=page, pageSize=page_size, total=total
        )

    async def create_portfolio(
        self, payload: PortfolioCreate, actor: dict[str, Any]
    ) -> PortfolioDetail:
        """Create an administrator-owned portfolio and record one audit event."""
        self._require_admin(actor)
        document = self._validated_values(payload.model_dump())
        now = datetime.now(UTC)
        document.update({"createdAt": now, "updatedAt": now})
        try:
            row = await self.repository.create_portfolio(document)
        except DuplicateKeyError as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A portfolio already uses this name.") from exc
        await self.audit.record(actor, "create", "portfolio", str(row["_id"]), "Portfolio created", now)
        return PortfolioDetail(
            id=str(row["_id"]), name=row["name"], owner=row["owner"], description=row["description"],
            productArea=row["productArea"], status=row["status"], applicationCount=0, qualityScore=None,
        )

    async def update_portfolio(
        self, portfolio_id: str, payload: PortfolioUpdate, actor: dict[str, Any]
    ) -> PortfolioDetail:
        """Update an existing portfolio and audit only a completed database write."""
        self._require_admin(actor)
        existing = await self.repository.get_portfolio(portfolio_id)
        if not existing:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Portfolio not found.")
        changes = payload.model_dump(exclude_unset=True)
        if not changes:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="At least one portfolio field is required.")
        changes = self._validated_values(changes)
        try:
            row = await self.repository.update_portfolio(portfolio_id, changes)
        except DuplicateKeyError as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A portfolio already uses this name.") from exc
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Portfolio not found.")
        await self.audit.record(actor, "edit", "portfolio", portfolio_id, "Portfolio updated", datetime.now(UTC))
        rollups = await self.repository.rollups([portfolio_id])
        return PortfolioDetail(**self._summary(row, rollups).model_dump(), description=row["description"])

    async def delete_portfolio(self, portfolio_id: str, actor: dict[str, Any]) -> None:
        """Delete only unreferenced portfolios and audit the successful removal."""
        self._require_admin(actor)
        existing = await self.repository.get_portfolio(portfolio_id)
        if not existing:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Portfolio not found.")
        if await self.repository.linked_application_count(portfolio_id):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Portfolio has linked applications and cannot be deleted.")
        deleted = await self.repository.delete_portfolio(portfolio_id)
        if not deleted:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Portfolio not found.")
        await self.audit.record(actor, "delete", "portfolio", portfolio_id, "Portfolio deleted", datetime.now(UTC))

    @staticmethod
    def _require_view(user: dict[str, Any]) -> None:
        """Reject accounts whose current persisted permissions omit viewing."""
        if not has_permission(user, "view"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Portfolio inventory is not available to this account.")

    @staticmethod
    def _require_admin(user: dict[str, Any]) -> None:
        """Enforce the administrator-only portfolio mutation matrix."""
        if user.get("role") != "Administrator" or not has_permission(user, "administer"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only administrators may manage portfolios.")

    @staticmethod
    def _scope_query(user: dict[str, Any]) -> dict[str, Any] | None:
        """Build Mongo scope constraints before any list count or pagination."""
        assigned = [str(value) for value in user.get("portfolioAccess", [])]
        if assigned:
            ids = [ObjectId(value) for value in assigned if ObjectId.is_valid(value)]
            return {"_id": {"$in": ids}} if ids else {"_id": {"$in": []}}
        if str(user.get("role")) in {"Administrator", "Executive", "Auditor"}:
            return None
        return {"_id": {"$in": []}}

    @staticmethod
    def _validated_values(values: dict[str, Any]) -> dict[str, Any]:
        """Trim text fields and reject values that become blank."""
        cleaned = dict(values)
        for key in ("name", "owner", "description", "productArea"):
            value = cleaned.get(key)
            if value is not None:
                stripped = value.strip()
                if not stripped:
                    raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"{key} must not be blank.")
                cleaned[key] = stripped
        return cleaned

    @staticmethod
    def _summary(
        row: dict[str, Any], rollups: dict[str, dict[str, int | float | None]]
    ) -> PortfolioSummary:
        """Map a portfolio and its computed application measures safely."""
        values = rollups.get(str(row["_id"]), {})
        return PortfolioSummary(
            id=str(row["_id"]), name=row["name"], owner=row["owner"], productArea=row["productArea"],
            status=row["status"], applicationCount=int(values.get("applicationCount", 0)),
            qualityScore=values.get("qualityScore"),
        )

    @staticmethod
    def _application(row: dict[str, Any]) -> ApplicationListItem:
        """Map a linked Mongo application into its typed safe API response."""
        values = {key: value for key, value in row.items() if key != "_id"}
        values["id"] = str(row["_id"])
        values["portfolioId"] = str(row["portfolioId"])
        return ApplicationListItem.model_validate(values)
