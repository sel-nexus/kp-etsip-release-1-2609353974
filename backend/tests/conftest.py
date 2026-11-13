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
os.environ["SEED_ON_STARTUP"] = "true"

from app.core.config import settings
from app.main import app


@pytest_asyncio.fixture
async def clean_test_database() -> AsyncIterator[None]:
    """Clear the dedicated test database and remove it after use."""
    client: AsyncMongoClient[dict[str, Any]] = AsyncMongoClient(settings.MONGODB_URI)
    database = client.get_database("ketsip_test")
    await database.client.admin.command("ping")
    await client.drop_database("ketsip_test")
    try:
        yield
    finally:
        await client.drop_database("ketsip_test")
        await client.close()


@pytest_asyncio.fixture
async def api_client(clean_test_database: None) -> AsyncIterator[AsyncClient]:
    """Expose the live FastAPI routing stack through its ASGI transport."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


@pytest_asyncio.fixture
async def started_app(clean_test_database: None) -> AsyncIterator[AsyncMongoClient[dict[str, Any]]]:
    """Run the application lifespan against real MongoDB and yield its client."""
    async with app.router.lifespan_context(app):
        yield app.state.mongo_client
