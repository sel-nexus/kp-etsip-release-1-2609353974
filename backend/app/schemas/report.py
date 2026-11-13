"""Define typed report row and bounded page contracts."""

from pydantic import BaseModel

from app.schemas.application import ApplicationListItem
from app.schemas.portfolio import PortfolioSummary


class ApplicationReportRow(ApplicationListItem):
    """Expose safe application inventory fields for a report row."""


class PortfolioReportRow(PortfolioSummary):
    """Expose safe portfolio inventory fields for a report row."""


class ApplicationReportPage(BaseModel):
    """Return a bounded page of visible application report rows."""

    items: list[ApplicationReportRow]
    page: int
    pageSize: int
    total: int


class PortfolioReportPage(BaseModel):
    """Return a bounded page of visible portfolio report rows."""

    items: list[PortfolioReportRow]
    page: int
    pageSize: int
    total: int


__all__ = ["ApplicationReportPage", "ApplicationReportRow", "PortfolioReportPage", "PortfolioReportRow"]
