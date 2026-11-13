"""Build filtered report pages, safe CSV files, and durable export events."""

import csv
import io
import logging
from datetime import UTC, date, datetime
from typing import Any, Iterable

from fastapi import HTTPException, status
from pymongo.errors import PyMongoError

from app.repositories.audit import AuditRepository
from app.repositories.applications import ApplicationsRepository
from app.repositories.portfolios import PortfoliosRepository
from app.schemas.audit import AuditFilters
from app.schemas.report import (
    ApplicationReportPage,
    ApplicationReportRow,
    PortfolioReportPage,
    PortfolioReportRow,
)
from app.services.applications import ApplicationsService
from app.services.audit import AuditService
from app.services.portfolios import PortfoliosService

logger = logging.getLogger(__name__)

APPLICATION_HEADERS = (
    "id", "name", "description", "portfolioId", "portfolioName", "productArea", "businessOwner",
    "technologyOwner", "etsOwner", "criticality", "tier", "lifecycleStatus", "technologyStack",
    "repositoryLink", "pipelineLink", "applicationHealthScore", "qualityScore", "automationCoverage",
    "unitTestCoverage", "openDefects", "openCriticalDefects", "riskLevel",
)
PORTFOLIO_HEADERS = ("id", "name", "owner", "productArea", "status", "applicationCount", "qualityScore")
AUDIT_HEADERS = ("id", "timestamp", "userId", "userName", "action", "entityType", "entityId", "details")


class ReportsService:
    """Apply existing inventory visibility and generate report downloads."""

    def __init__(
        self,
        applications: ApplicationsService,
        portfolios: PortfoliosService,
        audit_repository: AuditRepository,
    ) -> None:
        """Bind report queries and successful-export events to live repositories."""
        self.applications = applications
        self.portfolios = portfolios
        self.audit_repository = audit_repository

    async def application_page(
        self, user: dict[str, Any], filters: dict[str, Any], page: int, page_size: int
    ) -> ApplicationReportPage:
        """Return one bounded application report page using inventory policy."""
        result = await self.applications.list_applications(
            user, filters.get("search"), filters.get("portfolioId"), filters.get("criticality"),
            filters.get("riskLevel"), filters.get("lifecycleStatus"), page, page_size,
        )
        return ApplicationReportPage(
            items=[ApplicationReportRow.model_validate(item.model_dump()) for item in result.items],
            page=page, pageSize=page_size, total=result.total,
        )

    async def portfolio_page(
        self, user: dict[str, Any], filters: dict[str, Any], page: int, page_size: int
    ) -> PortfolioReportPage:
        """Return one bounded portfolio report page using inventory policy."""
        result = await self.portfolios.list_portfolios(
            user, filters.get("search"), filters.get("status"), filters.get("productArea"), page, page_size,
        )
        return PortfolioReportPage(
            items=[PortfolioReportRow.model_validate(item.model_dump()) for item in result.items],
            page=page, pageSize=page_size, total=result.total,
        )

    async def export_applications(self, user: dict[str, Any], filters: dict[str, Any]) -> str:
        """Generate and audit a complete CSV of visible filtered applications."""
        rows = await self._all_application_rows(user, filters)
        content = serialize_csv(APPLICATION_HEADERS, (row.model_dump() for row in rows))
        await self._record_export(user, "report", "applications")
        return content

    async def export_portfolios(self, user: dict[str, Any], filters: dict[str, Any]) -> str:
        """Generate and audit a complete CSV of visible filtered portfolios."""
        rows = await self._all_portfolio_rows(user, filters)
        content = serialize_csv(PORTFOLIO_HEADERS, (row.model_dump() for row in rows))
        await self._record_export(user, "report", "portfolios")
        return content

    async def export_audit(self, user: dict[str, Any], filters: AuditFilters) -> str:
        """Generate a filtered full audit CSV before recording its own export event."""
        audit_service = AuditService(self.audit_repository)
        rows: list[dict[str, Any]] = []
        page = 1
        total = 0
        while page == 1 or len(rows) < total:
            result = await audit_service.search(filters.model_copy(update={"page": page, "pageSize": 100}))
            total = result.total
            rows.extend(item.model_dump() for item in result.items)
            page += 1
        content = serialize_csv(AUDIT_HEADERS, rows)
        await self._record_export(user, "audit", "audit history")
        return content

    async def _all_application_rows(
        self, user: dict[str, Any], filters: dict[str, Any]
    ) -> list[ApplicationReportRow]:
        """Read all authorized application rows by bounded inventory pages."""
        rows: list[ApplicationReportRow] = []
        page = 1
        total = 0
        while page == 1 or len(rows) < total:
            result = await self.application_page(user, filters, page, 100)
            total = result.total
            rows.extend(result.items)
            page += 1
        return rows

    async def _all_portfolio_rows(
        self, user: dict[str, Any], filters: dict[str, Any]
    ) -> list[PortfolioReportRow]:
        """Read all authorized portfolio rows by bounded inventory pages."""
        rows: list[PortfolioReportRow] = []
        page = 1
        total = 0
        while page == 1 or len(rows) < total:
            result = await self.portfolio_page(user, filters, page, 100)
            total = result.total
            rows.extend(result.items)
            page += 1
        return rows

    async def _record_export(self, user: dict[str, Any], entity_type: str, details: str) -> None:
        """Persist exactly one safe export event or fail the download closed."""
        try:
            await self.audit_repository.record(user, "export", entity_type, None, f"CSV export: {details}", datetime.now(UTC))
        except PyMongoError as exc:
            logger.exception("Could not persist CSV export audit event")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="The export could not be completed.",
            ) from exc


def build_reports_service(database: Any) -> ReportsService:
    """Bind report queries and audits to the active Mongo database."""
    audit_repository = AuditRepository(database)
    return ReportsService(
        ApplicationsService(ApplicationsRepository(database), audit_repository),
        PortfoliosService(PortfoliosRepository(database), audit_repository),
        audit_repository,
    )


def serialize_csv(headers: Iterable[str], rows: Iterable[dict[str, Any]]) -> str:
    """Serialize documented report fields with RFC-style quoting and formula safety.

    Notes:
        Missing and null values become empty cells. CSV quoting and CRLF row
        endings are supplied by the standard-library writer. Text beginning
        with a spreadsheet formula marker after leading whitespace is prefixed
        with an apostrophe; the original whitespace and remaining text remain.
    """
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\r\n", quoting=csv.QUOTE_MINIMAL)
    selected_headers = tuple(headers)
    writer.writerow(selected_headers)
    for row in rows:
        writer.writerow([_csv_value(row.get(header)) for header in selected_headers])
    return output.getvalue()


def _csv_value(value: Any) -> str:
    """Convert a source scalar to a safe CSV cell without inventing values."""
    if value is None:
        return ""
    if isinstance(value, (datetime, date)):
        rendered = value.isoformat()
    elif isinstance(value, bool):
        rendered = "true" if value else "false"
    else:
        rendered = str(value)
    leading_trimmed = rendered.lstrip()
    if leading_trimmed.startswith(("=", "+", "-", "@")):
        return "'" + rendered
    return rendered


__all__ = [
    "APPLICATION_HEADERS", "AUDIT_HEADERS", "PORTFOLIO_HEADERS", "ReportsService",
    "build_reports_service", "serialize_csv",
]
