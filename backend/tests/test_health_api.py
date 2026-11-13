"""Verify health routing and real MongoDB startup persistence."""

from typing import Any

import pytest
from bson import ObjectId
from httpx import ASGITransport, AsyncClient
from pymongo import AsyncMongoClient

from app.core.config import settings
from app.core.seed import seed_database
from app.main import app


@pytest.mark.asyncio
async def test_health_returns_ok_without_lifespan_or_database_access() -> None:
    """Return liveness JSON directly without initializing MongoDB."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_startup_indexes_and_seed_are_real_and_idempotent(
    started_app: AsyncMongoClient[dict[str, Any]],
) -> None:
    """Read seeded records back from Mongo and confirm reruns add no duplicates."""
    database = started_app.get_database("ketsip_test")
    expected_counts = {
        "roles": 6,
        "users": 7,
        "portfolios": 3,
        "applications": 10,
    }
    initial_counts = {
        collection_name: await database[collection_name].count_documents({})
        for collection_name in expected_counts
    }
    assert initial_counts == expected_counts
    index_names = await database["users"].index_information()
    assert any(index["key"] == [("email", 1)] and index.get("unique") for index in index_names.values())
    admin = await database["users"].find_one({"email": "admin@ketsip.local"})
    assert admin is not None
    assert admin["mustChangePassword"] is True
    assert admin["passwordHash"] != settings.SEED_ADMIN_PASSWORD

    async with app.router.lifespan_context(app):
        restarted_database = app.state.mongo_client.get_database("ketsip_test")
        final_counts = {
            collection_name: await restarted_database[collection_name].count_documents({})
            for collection_name in expected_counts
        }
        assert final_counts == expected_counts
        application = await restarted_database["applications"].find_one({"name": "Payment Gateway"})
        assert application is not None
        assert isinstance(application["portfolioId"], ObjectId)


@pytest.mark.asyncio
async def test_health_route_ignores_unrelated_query_parameters(api_client: AsyncClient) -> None:
    """Keep liveness status independent of unrecognized query data."""
    response = await api_client.get("/api/health?details=secrets")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
