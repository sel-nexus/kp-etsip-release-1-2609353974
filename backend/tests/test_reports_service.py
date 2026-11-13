"""Verify CSV safety and report services against the real Mongo fixture."""

import csv
import io
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi import HTTPException
from pymongo import AsyncMongoClient

from app.schemas.audit import AuditFilters
from app.services.reports import (
    APPLICATION_HEADERS,
    AUDIT_HEADERS,
    PORTFOLIO_HEADERS,
    build_reports_service,
    serialize_csv,
)


def _actor(role: str, permissions: list[str], portfolio_access: list[str] | None = None) -> dict[str, Any]:
    """Create a policy-shaped actor from seeded Mongo identity data."""
    return {
        "_id": "507f1f77bcf86cd799439011",
        "name": "Reports test actor",
        "role": role,
        "permissions": permissions,
        "portfolioAccess": portfolio_access or [],
    }


@pytest.mark.asyncio
async def test_application_page_uses_scoped_inventory_and_filters_before_total(
    started_app: AsyncMongoClient[dict[str, Any]],
) -> None:
    """Return a bounded, filtered page and count only assigned portfolio rows."""
    database = started_app.get_database("ketsip_test")
    portfolio = await database["portfolios"].find_one({"name": "Payments"})
    assert portfolio
    service = build_reports_service(database)
    actor = _actor("Portfolio Leader", ["view", "export"], [str(portfolio["_id"])])

    page = await service.application_page(actor, {"criticality": "Critical"}, 1, 1)

    assert page.page == 1 and page.pageSize == 1 and page.total == 1
    assert len(page.items) == 1 and page.items[0].portfolioName == "Payments"
    assert page.items[0].criticality == "Critical"


@pytest.mark.asyncio
async def test_portfolio_page_uses_role_scope_and_filter_before_total(
    started_app: AsyncMongoClient[dict[str, Any]],
) -> None:
    """Expose only the leader's assigned portfolio in the filtered report page."""
    database = started_app.get_database("ketsip_test")
    portfolio = await database["portfolios"].find_one({"name": "Payments"})
    assert portfolio
    service = build_reports_service(database)
    actor = _actor("Portfolio Leader", ["view", "export"], [str(portfolio["_id"])])

    page = await service.portfolio_page(actor, {"status": "Active", "productArea": "Payments"}, 1, 10)

    assert page.total == 1 and len(page.items) == 1
    assert page.items[0].name == "Payments" and page.items[0].applicationCount == 3


@pytest.mark.asyncio
async def test_application_export_is_complete_and_records_one_report_event(
    started_app: AsyncMongoClient[dict[str, Any]],
) -> None:
    """Export all visible applications and persist one success audit event."""
    database = started_app.get_database("ketsip_test")
    service = build_reports_service(database)
    actor = _actor("Executive", ["view", "export"])
    before = await database["audit_logs"].count_documents({"action": "export", "entityType": "report"})

    content = await service.export_applications(actor, {"search": "Payment Gateway"})

    rows = list(csv.DictReader(io.StringIO(content)))
    assert tuple(rows[0].keys()) == APPLICATION_HEADERS
    assert len(rows) == 1 and rows[0]["name"] == "Payment Gateway"
    assert await database["audit_logs"].count_documents({"action": "export", "entityType": "report"}) == before + 1


@pytest.mark.asyncio
async def test_portfolio_export_is_scoped_and_records_one_report_event(
    started_app: AsyncMongoClient[dict[str, Any]],
) -> None:
    """Export only the assigned portfolio and audit the successful download once."""
    database = started_app.get_database("ketsip_test")
    portfolio = await database["portfolios"].find_one({"name": "Payments"})
    assert portfolio
    actor = _actor("Portfolio Leader", ["view", "export"], [str(portfolio["_id"])])
    service = build_reports_service(database)
    before = await database["audit_logs"].count_documents({"action": "export", "entityType": "report"})

    content = await service.export_portfolios(actor, {})

    rows = list(csv.DictReader(io.StringIO(content)))
    assert tuple(rows[0].keys()) == PORTFOLIO_HEADERS
    assert [row["name"] for row in rows] == ["Payments"]
    assert await database["audit_logs"].count_documents({"action": "export", "entityType": "report"}) == before + 1


@pytest.mark.asyncio
async def test_audit_export_filters_and_writes_one_audit_event_after_generation(
    started_app: AsyncMongoClient[dict[str, Any]],
) -> None:
    """Export filtered history and append exactly one event after serialization."""
    database = started_app.get_database("ketsip_test")
    actor = _actor("Auditor", ["view", "export"])
    await database["audit_logs"].insert_one({
        "timestamp": datetime.now(UTC), "userId": actor["_id"], "userName": actor["name"],
        "action": "edit", "entityType": "portfolio", "entityId": None, "details": "Selected event",
    })
    service = build_reports_service(database)
    before = await database["audit_logs"].count_documents({"action": "export", "entityType": "audit"})

    content = await service.export_audit(actor, AuditFilters(action="edit"))

    rows = list(csv.DictReader(io.StringIO(content)))
    assert tuple(rows[0].keys()) == AUDIT_HEADERS
    assert all(row["action"] == "edit" for row in rows)
    assert await database["audit_logs"].count_documents({"action": "export", "entityType": "audit"}) == before + 1


@pytest.mark.asyncio
async def test_invalid_audit_filter_fails_without_export_audit(
    started_app: AsyncMongoClient[dict[str, Any]],
) -> None:
    """Reject invalid audit filters before producing or auditing an export."""
    database = started_app.get_database("ketsip_test")
    service = build_reports_service(database)
    actor = _actor("Auditor", ["view", "export"])
    before = await database["audit_logs"].count_documents({"action": "export", "entityType": "audit"})

    with pytest.raises(HTTPException) as failure:
        await service.export_audit(actor, AuditFilters(userId="not-an-object-id"))

    assert failure.value.status_code == 422
    assert await database["audit_logs"].count_documents({"action": "export", "entityType": "audit"}) == before


@pytest.mark.parametrize(
    ("dangerous", "safe"),
    [("=1+1", "'=1+1"), (" +SUM(A1)", "' +SUM(A1)"), ("-cmd", "'-cmd"), ("@name", "'@name")],
)
def test_csv_writer_protects_formula_leading_cells(dangerous: str, safe: str) -> None:
    """Prefix formula-leading text after whitespace without trimming its content."""
    content = serialize_csv(("value",), [{"value": dangerous}])
    rows = list(csv.reader(io.StringIO(content)))
    assert rows == [["value"], [safe]]


def test_csv_writer_quotes_commas_quotes_newlines_and_null_as_empty() -> None:
    """Preserve CSV field boundaries and null semantics with standard quoting."""
    content = serialize_csv(("quoted", "newline", "missing"), [{
        "quoted": 'one, "two"', "newline": "line one\nline two", "missing": None,
    }])
    rows = list(csv.reader(io.StringIO(content)))
    assert rows == [["quoted", "newline", "missing"], ['one, "two"', "line one\nline two", ""]]
    assert content.endswith("\r\n")
