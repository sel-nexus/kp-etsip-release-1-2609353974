"""Expose dependency-free API liveness for container probes."""

from fastapi import APIRouter

from app.schemas.common import HealthResponse

router = APIRouter()


@router.get("/api/health", response_model=HealthResponse, tags=["health"], summary="Check API liveness")
async def health() -> HealthResponse:
    """Return minimal liveness status without reading MongoDB."""
    return HealthResponse(status="ok")
