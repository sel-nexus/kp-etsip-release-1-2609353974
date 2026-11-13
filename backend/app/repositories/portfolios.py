"""Query and mutate portfolio and linked application Mongo collections."""

from datetime import UTC, datetime
from typing import Any

from bson import ObjectId
from pymongo import ASCENDING, ReturnDocument
from pymongo.asynchronous.database import AsyncDatabase


class PortfoliosRepository:
    """Access real portfolio and application collections with bounded queries."""

    def __init__(self, database: AsyncDatabase[dict[str, Any]]) -> None:
        """Bind inventory queries to the application-owned database."""
        self.portfolios = database["portfolios"]
        self.applications = database["applications"]

    async def list_portfolios(
        self, query: dict[str, Any], page: int, page_size: int
    ) -> tuple[list[dict[str, Any]], int]:
        """Return a filtered portfolio page and count after all filters apply."""
        total = await self.portfolios.count_documents(query)
        cursor = (
            self.portfolios.find(query, {"name": 1, "owner": 1, "description": 1, "productArea": 1, "status": 1})
            .sort([("name", ASCENDING), ("_id", ASCENDING)])
            .skip((page - 1) * page_size)
            .limit(page_size)
        )
        return await cursor.to_list(length=page_size), total

    async def get_portfolio(self, portfolio_id: str) -> dict[str, Any] | None:
        """Find one portfolio by a valid Mongo ObjectId string."""
        if not ObjectId.is_valid(portfolio_id):
            return None
        return await self.portfolios.find_one({"_id": ObjectId(portfolio_id)})

    async def rollups(self, portfolio_ids: list[str]) -> dict[str, dict[str, int | float | None]]:
        """Aggregate linked-application counts and arithmetic quality means."""
        if not portfolio_ids:
            return {}
        ids = [ObjectId(value) for value in portfolio_ids if ObjectId.is_valid(value)]
        if not ids:
            return {}
        pipeline = [
            {"$match": {"portfolioId": {"$in": ids}}},
            {
                "$group": {
                    "_id": "$portfolioId",
                    "applicationCount": {"$sum": 1},
                    "qualityScore": {"$avg": "$qualityScore"},
                }
            },
        ]
        cursor = await self.applications.aggregate(pipeline)
        rows = await cursor.to_list(length=len(ids))
        return {
            str(row["_id"]): {
                "applicationCount": int(row["applicationCount"]),
                "qualityScore": float(row["qualityScore"]) if row.get("qualityScore") is not None else None,
            }
            for row in rows
        }

    async def list_applications(
        self, query: dict[str, Any], page: int, page_size: int
    ) -> tuple[list[dict[str, Any]], int]:
        """Return a scoped and bounded linked-application page and total."""
        total = await self.applications.count_documents(query)
        cursor = (
            self.applications.find(query, {"passwordHash": 0})
            .sort([("name", ASCENDING), ("_id", ASCENDING)])
            .skip((page - 1) * page_size)
            .limit(page_size)
        )
        return await cursor.to_list(length=page_size), total

    async def create_portfolio(self, document: dict[str, Any]) -> dict[str, Any]:
        """Insert a portfolio and read back the persisted record."""
        result = await self.portfolios.insert_one(document)
        return await self.portfolios.find_one({"_id": result.inserted_id}) or {}

    async def update_portfolio(
        self, portfolio_id: str, changes: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Apply a portfolio edit and return its persisted result."""
        if not ObjectId.is_valid(portfolio_id):
            return None
        changes["updatedAt"] = datetime.now(UTC)
        return await self.portfolios.find_one_and_update(
            {"_id": ObjectId(portfolio_id)},
            {"$set": changes},
            return_document=ReturnDocument.AFTER,
        )

    async def delete_portfolio(self, portfolio_id: str) -> bool:
        """Delete one portfolio document without affecting linked applications."""
        if not ObjectId.is_valid(portfolio_id):
            return False
        result = await self.portfolios.delete_one({"_id": ObjectId(portfolio_id)})
        return result.deleted_count == 1

    async def linked_application_count(self, portfolio_id: str) -> int:
        """Count references before a portfolio deletion is attempted."""
        return await self.applications.count_documents({"portfolioId": ObjectId(portfolio_id)})
