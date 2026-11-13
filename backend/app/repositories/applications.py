"""Query and mutate application and portfolio MongoDB collections."""

from datetime import UTC, datetime
from typing import Any

from bson import ObjectId
from pymongo import ASCENDING, ReturnDocument
from pymongo.asynchronous.database import AsyncDatabase


class ApplicationsRepository:
    """Provide bounded application persistence using the real Mongo database."""

    def __init__(self, database: AsyncDatabase[dict[str, Any]]) -> None:
        """Bind the repository to application and portfolio collections."""
        self.applications = database["applications"]
        self.portfolios = database["portfolios"]

    async def list_applications(
        self, query: dict[str, Any], page: int, page_size: int
    ) -> tuple[list[dict[str, Any]], int]:
        """Return matching application rows and total before pagination."""
        total = await self.applications.count_documents(query)
        cursor = (
            self.applications.find(query)
            .sort([("name", ASCENDING), ("_id", ASCENDING)])
            .skip((page - 1) * page_size)
            .limit(page_size)
        )
        rows = await cursor.to_list(length=page_size)
        portfolio_ids = list({row["portfolioId"] for row in rows})
        names: dict[ObjectId, str] = {}
        if portfolio_ids:
            portfolios = await self.portfolios.find(
                {"_id": {"$in": portfolio_ids}}, {"name": 1}
            ).to_list(length=len(portfolio_ids))
            names = {row["_id"]: row["name"] for row in portfolios}
        for row in rows:
            row["portfolioName"] = names.get(row["portfolioId"], "Unavailable portfolio")
        return rows, total

    async def get_application(self, application_id: str) -> dict[str, Any] | None:
        """Find one application by a valid Mongo identifier."""
        if not ObjectId.is_valid(application_id):
            return None
        return await self.applications.find_one({"_id": ObjectId(application_id)})

    async def get_portfolio(self, portfolio_id: str) -> dict[str, Any] | None:
        """Find a referenced portfolio by a valid Mongo identifier."""
        if not ObjectId.is_valid(portfolio_id):
            return None
        return await self.portfolios.find_one({"_id": ObjectId(portfolio_id)})

    async def create_application(self, document: dict[str, Any]) -> dict[str, Any]:
        """Persist a new application and return the stored document."""
        result = await self.applications.insert_one(document)
        return await self.applications.find_one({"_id": result.inserted_id}) or {}

    async def update_application(
        self, application_id: str, values: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Replace every mutable source field and return the stored result."""
        if not ObjectId.is_valid(application_id):
            return None
        values["updatedAt"] = datetime.now(UTC)
        return await self.applications.find_one_and_update(
            {"_id": ObjectId(application_id)},
            {"$set": values},
            return_document=ReturnDocument.AFTER,
        )

    async def delete_application(self, application_id: str) -> bool:
        """Delete exactly one application document without cascading references."""
        if not ObjectId.is_valid(application_id):
            return False
        result = await self.applications.delete_one({"_id": ObjectId(application_id)})
        return result.deleted_count == 1
