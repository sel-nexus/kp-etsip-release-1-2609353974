"""Own MongoDB startup, indexes, and typed collection repositories."""

import logging
from typing import Any

from pymongo import ASCENDING, DESCENDING, AsyncMongoClient
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import OperationFailure

from app.core.config import settings
from app.models.documents import (
    ApplicationRepository,
    AuditLogRepository,
    PortfolioRepository,
    RoleRepository,
    UserRepository,
)

logger = logging.getLogger(__name__)


class MongoRepositories:
    """Group real collection repositories backed by the active database."""

    def __init__(self, database: AsyncDatabase[dict[str, Any]]) -> None:
        """Build one repository for each persisted collection."""
        self.users = UserRepository(database["users"])
        self.roles = RoleRepository(database["roles"])
        self.portfolios = PortfolioRepository(database["portfolios"])
        self.applications = ApplicationRepository(database["applications"])
        self.audit_logs = AuditLogRepository(database["audit_logs"])


async def create_indexes(database: AsyncDatabase[dict[str, Any]]) -> None:
    """Create unique and query-supporting indexes before the API serves."""
    specifications = {
        "users": [([("email", ASCENDING)], True)],
        "roles": [([("name", ASCENDING)], True)],
        "portfolios": [([("name", ASCENDING)], True)],
        "applications": [
            ([("name", ASCENDING)], True),
            ([("portfolioId", ASCENDING)], False),
        ],
        "audit_logs": [
            ([("timestamp", DESCENDING)], False),
            ([("userId", ASCENDING), ("timestamp", DESCENDING)], False),
            ([("action", ASCENDING), ("timestamp", DESCENDING)], False),
        ],
    }
    for collection_name, indexes in specifications.items():
        collection = database[collection_name]
        for index_keys, unique in indexes:
            kwargs = {"unique": True} if unique else {}
            try:
                await collection.create_index(index_keys, **kwargs)
            except OperationFailure as exc:
                if exc.code not in (85, 86):
                    raise
                index_name = "_".join(f"{key}_{order}" for key, order in index_keys)
                await collection.drop_index(index_name)
                await collection.create_index(index_keys, **kwargs)
    logger.info("MongoDB indexes are ready")


def get_database(client: AsyncMongoClient[dict[str, Any]]) -> AsyncDatabase[dict[str, Any]]:
    """Select the separately configured database from the shared client."""
    return client.get_database(settings.MONGODB_DB)


async def verify_database(client: AsyncMongoClient[dict[str, Any]]) -> None:
    """Verify MongoDB connectivity without logging connection details."""
    await client.admin.command("ping")
