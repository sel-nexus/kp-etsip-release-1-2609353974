"""Apply application access policy, validation, persistence, and auditing."""

import re
from datetime import UTC, datetime
from typing import Any

from bson import ObjectId
from fastapi import HTTPException, status
from pymongo.errors import DuplicateKeyError

from app.repositories.applications import ApplicationsRepository
from app.repositories.audit import AuditRepository
from app.schemas.application import (
    ApplicationCreate,
    ApplicationDetail,
    ApplicationListItem,
    ApplicationPage,
    ApplicationUpdate,
    PortfolioReference,
)
from app.services.policy import can_access_portfolio, has_permission


class ApplicationsService:
    """Serve role-scoped application records with post-write audit events."""

    def __init__(self, repository: ApplicationsRepository, audit: AuditRepository) -> None:
        """Bind application business rules to real repositories."""
        self.repository = repository
        self.audit = audit

    async def list_applications(
        self,
        user: dict[str, Any],
        search: str | None,
        portfolio_id: str | None,
        criticality: str | None,
        risk_level: str | None,
        lifecycle_status: str | None,
        page: int,
        page_size: int,
    ) -> ApplicationPage:
        """Apply visibility scope before filters, total count, and pagination."""
        self._require_view(user)
        query: dict[str, Any] = {}
        self._apply_read_scope(user, query)
        if portfolio_id:
            if not ObjectId.is_valid(portfolio_id):
                query["$and"] = [{"portfolioId": {"$in": []}}]
            else:
                query.setdefault("$and", []).append({"portfolioId": ObjectId(portfolio_id)})
        if search and search.strip():
            term = re.escape(search.strip())
            query["$or"] = [
                {field: {"$regex": term, "$options": "i"}}
                for field in ("name", "description", "productArea", "businessOwner", "technologyOwner", "etsOwner", "technologyStack")
            ]
        if criticality:
            query["criticality"] = criticality
        if risk_level:
            query["riskLevel"] = risk_level
        if lifecycle_status:
            query["lifecycleStatus"] = lifecycle_status
        rows, total = await self.repository.list_applications(query, page, page_size)
        items = [self._list_item(row) for row in rows]
        return ApplicationPage(items=items, page=page, pageSize=page_size, total=total)

    async def get_application(self, application_id: str, user: dict[str, Any]) -> ApplicationDetail:
        """Return a complete record only when its linked portfolio is visible."""
        self._require_view(user)
        row = await self.repository.get_application(application_id)
        if not row or not self._can_access_portfolio(user, str(row.get("portfolioId", ""))):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found.")
        portfolio = await self.repository.get_portfolio(str(row["portfolioId"]))
        if not portfolio:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found.")
        return self._detail(row, portfolio)

    async def create_application(
        self, payload: ApplicationCreate, actor: dict[str, Any]
    ) -> ApplicationDetail:
        """Validate scope, persist a new application, then record one audit event."""
        self._require_mutation(actor, "create")
        values = self._clean_values(payload.model_dump(mode="python"))
        portfolio = await self._writable_portfolio(actor, values["portfolioId"])
        values["portfolioId"] = ObjectId(values["portfolioId"])
        now = datetime.now(UTC)
        values.update({"createdAt": now, "updatedAt": now})
        try:
            row = await self.repository.create_application(values)
        except DuplicateKeyError as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An application already uses this name.") from exc
        await self.audit.record(actor, "create", "application", str(row["_id"]), "Application created", now)
        return self._detail(row, portfolio)

    async def update_application(
        self, application_id: str, payload: ApplicationUpdate, actor: dict[str, Any]
    ) -> ApplicationDetail:
        """Replace an accessible record after checking source and target scopes."""
        self._require_mutation(actor, "edit")
        existing = await self.repository.get_application(application_id)
        if not existing or not self._can_access_portfolio(actor, str(existing.get("portfolioId", ""))):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found.")
        values = self._clean_values(payload.model_dump(mode="python"))
        portfolio = await self._writable_portfolio(actor, values["portfolioId"])
        values["portfolioId"] = ObjectId(values["portfolioId"])
        try:
            row = await self.repository.update_application(application_id, values)
        except DuplicateKeyError as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An application already uses this name.") from exc
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found.")
        await self.audit.record(actor, "edit", "application", application_id, "Application updated", datetime.now(UTC))
        return self._detail(row, portfolio)

    async def delete_application(self, application_id: str, actor: dict[str, Any]) -> None:
        """Delete an application only for an administrator and audit the success."""
        if actor.get("role") != "Administrator" or not has_permission(actor, "administer"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only administrators may delete applications.")
        existing = await self.repository.get_application(application_id)
        if not existing or not self._can_access_portfolio(actor, str(existing.get("portfolioId", ""))):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found.")
        if not await self.repository.delete_application(application_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found.")
        await self.audit.record(actor, "delete", "application", application_id, "Application deleted", datetime.now(UTC))

    async def _writable_portfolio(self, actor: dict[str, Any], portfolio_id: str) -> dict[str, Any]:
        """Require a real portfolio that the actor may write to."""
        portfolio = await self.repository.get_portfolio(portfolio_id)
        if not portfolio:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="The selected portfolio no longer exists.")
        if not self._can_access_portfolio(actor, portfolio_id, write=True):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Portfolio not found.")
        return portfolio

    @staticmethod
    def _require_view(user: dict[str, Any]) -> None:
        """Require the current persisted view permission."""
        if not has_permission(user, "view"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Application inventory is not available to this account.")

    @staticmethod
    def _require_mutation(actor: dict[str, Any], permission: str) -> None:
        """Allow only administrator, engineer, and portfolio leader writes."""
        if actor.get("role") not in {"Administrator", "Engineer", "Portfolio Leader"} or not has_permission(actor, permission):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This account may not manage applications.")

    @staticmethod
    def _apply_read_scope(user: dict[str, Any], query: dict[str, Any]) -> None:
        """Restrict Mongo reads to assigned portfolios before count or paging."""
        if user.get("role") == "Administrator" and has_permission(user, "administer"):
            return
        assigned = [str(value) for value in user.get("portfolioAccess", [])]
        if assigned:
            ids = [ObjectId(value) for value in assigned if ObjectId.is_valid(value)]
            query["portfolioId"] = {"$in": ids} if ids else {"$in": []}
        elif str(user.get("role")) not in {"Administrator", "Executive", "Auditor"}:
            query["portfolioId"] = {"$in": []}

    @staticmethod
    def _can_access_portfolio(user: dict[str, Any], portfolio_id: str, *, write: bool = False) -> bool:
        """Preserve administrator-wide access while applying portfolio grants to other roles."""
        if user.get("role") == "Administrator" and has_permission(user, "administer"):
            return True
        return can_access_portfolio(user, portfolio_id, write=write)

    @staticmethod
    def _clean_values(values: dict[str, Any]) -> dict[str, Any]:
        """Normalize whitespace and canonical URL values before persistence."""
        cleaned = dict(values)
        for key in ("name", "description", "productArea", "businessOwner", "technologyOwner", "etsOwner", "technologyStack"):
            cleaned[key] = cleaned[key].strip()
            if key != "technologyStack" and not cleaned[key]:
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"{key} must not be blank.")
        for key in ("repositoryLink", "pipelineLink"):
            if cleaned[key] is not None:
                cleaned[key] = str(cleaned[key])
        return cleaned

    @staticmethod
    def _list_item(row: dict[str, Any]) -> ApplicationListItem:
        """Map a Mongo application and its portfolio name to a typed response."""
        values = {
            key: value
            for key, value in row.items()
            if key not in {"_id", "portfolioId", "createdAt", "updatedAt"}
        }
        values.update({"id": str(row["_id"]), "portfolioId": str(row["portfolioId"])})
        return ApplicationListItem.model_validate(values)

    @staticmethod
    def _detail(row: dict[str, Any], portfolio: dict[str, Any]) -> ApplicationDetail:
        """Map source fields and the safe linked portfolio into detail output."""
        values = {key: value for key, value in row.items() if key not in {"_id", "portfolioId"}}
        values.update({
            "id": str(row["_id"]),
            "portfolioId": str(row["portfolioId"]),
            "portfolio": PortfolioReference(id=str(portfolio["_id"]), name=portfolio["name"]),
        })
        return ApplicationDetail.model_validate(values)
