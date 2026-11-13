"""Expose authorized searchable audit history to administrators and auditors."""

from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from pymongo.asynchronous.database import AsyncDatabase

from app.repositories.audit import AuditRepository
from app.schemas.audit import AuditAction, AuditFilters, AuditPage
from app.services.audit import AuditService
from app.services.policy import require_audit_access
from app.services.reports import ReportsService, build_reports_service

router = APIRouter(prefix="/api/audit-logs", tags=["audit"])
AuditReader = Annotated[dict[str, Any], Depends(require_audit_access())]


def get_audit_service(request: Request) -> AuditService:
    """Bind audit searches to the active Mongo database."""
    database: AsyncDatabase[dict[str, Any]] = request.app.state.mongo_database
    return AuditService(AuditRepository(database))


@router.get("", response_model=AuditPage, summary="Search audit history")
async def list_audit_logs(
    request: Request,
    actor: AuditReader,
    service: Annotated[AuditService, Depends(get_audit_service)],
    user_id: str | None = Query(default=None, alias="userId"),
    action: AuditAction | None = None,
    from_: datetime | None = Query(default=None, alias="from"),
    to: datetime | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, alias="pageSize", ge=1, le=100),
    format: str | None = Query(default=None),
) -> AuditPage | Response:
    """Search a bounded page of audit events with optional filters."""
    filters = {
        "userId": user_id, "action": action, "from": from_, "to": to,
        "page": page, "pageSize": page_size,
    }
    validated_filters = AuditFilters.model_validate(filters)
    if format is not None and format != "csv":
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="format must be csv.")
    if format == "csv":
        database: AsyncDatabase[dict[str, Any]] = request.app.state.mongo_database
        report_service: ReportsService = build_reports_service(database)
        content = await report_service.export_audit(actor, validated_filters)
        return Response(
            content,
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": 'attachment; filename="audit-logs.csv"'},
        )
    return await service.search(validated_filters)
