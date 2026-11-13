"""Configure an isolated real-Mongo test database and app fixtures."""

import os
from collections.abc import AsyncIterator
from typing import Any

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from pymongo import AsyncMongoClient

os.environ["MONGODB_DB"] = "ketsip_test"
os.environ.setdefault("MONGODB_URI", "mongodb://127.0.0.1:27017")
os.environ.setdefault("SEED_ADMIN_PASSWORD", "TestAdminPassword123!")
os.environ.setdefault("JWT_SECRET", "unit-test-signing-key-that-is-not-a-default-secret-2026")
os.environ["SEED_ON_STARTUP"] = "true"

from app.core.config import settings
from app.main import app


@pytest_asyncio.fixture(loop_scope="function")
async def clean_test_database() -> AsyncIterator[None]:
    """Clear the dedicated real-Mongo test database and remove it after use."""
    client: AsyncMongoClient[dict[str, Any]] = AsyncMongoClient(settings.MONGODB_URI)
    await client.admin.command("ping")
    await client.drop_database("ketsip_test")
    try:
        yield
    finally:
        await client.drop_database("ketsip_test")
        await client.close()


@pytest_asyncio.fixture(loop_scope="function")
async def running_app(clean_test_database: None) -> AsyncIterator[AsyncMongoClient[dict[str, Any]]]:
    """Run one application lifespan on the test loop and expose its Mongo client."""
    async with app.router.lifespan_context(app):
        yield app.state.mongo_client


@pytest_asyncio.fixture(loop_scope="function")
async def api_client(running_app: AsyncMongoClient[dict[str, Any]]) -> AsyncIterator[AsyncClient]:
    """Expose the live API while its database client shares the same event loop."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


@pytest_asyncio.fixture(loop_scope="function")
async def started_app(running_app: AsyncMongoClient[dict[str, Any]]) -> AsyncIterator[AsyncMongoClient[dict[str, Any]]]:
    """Expose the lifespan-owned Mongo client for state-transition assertions."""
    yield running_app
