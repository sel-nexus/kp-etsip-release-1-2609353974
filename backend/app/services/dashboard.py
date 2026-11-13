"""Aggregate authorized executive measures directly in MongoDB."""

import math
from typing import Any

from bson import ObjectId
from fastapi import HTTPException, status
from pymongo.asynchronous.database import AsyncDatabase

from app.schemas.dashboard import ExecutiveDashboardResponse, PortfolioComparison
from app.services.policy import can_access_portfolio, has_permission


class DashboardService:
    """Build permission-scoped dashboard metrics using Mongo pipelines."""

    def __init__(self, database: AsyncDatabase[dict[str, Any]]) -> None:
        """Bind dashboard queries to the real application database."""
        self.database = database
        self.portfolios = database["portfolios"]
        self.applications = database["applications"]

    async def executive(
        self,
        user: dict[str, Any],
        portfolio_id: str | None = None,
        product_area: str | None = None,
        risk_level: str | None = None,
    ) -> ExecutiveDashboardResponse:
        """Aggregate filtered application measures after enforcing portfolio visibility."""
        self._require_view(user)
        visible_portfolios = await self._visible_portfolios(user)
        if portfolio_id is not None:
            if not ObjectId.is_valid(portfolio_id):
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Portfolio not found.")
            visible_portfolios = [row for row in visible_portfolios if str(row["_id"]) == portfolio_id]
            if not visible_portfolios:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Portfolio not found.")

        visible_ids = [row["_id"] for row in visible_portfolios]
        match: dict[str, Any] = {"portfolioId": {"$in": visible_ids}}
        if product_area is not None:
            match["productArea"] = product_area
        if risk_level is not None:
            match["riskLevel"] = risk_level

        pipeline: list[dict[str, Any]] = [
            {"$match": match},
            {
                "$facet": {
                    "metrics": [
                        {
                            "$group": {
                                "_id": None,
                                "totalApplications": {"$sum": 1},
                                "enterpriseQuality": {"$avg": "$qualityScore"},
                                "averageHealth": {"$avg": "$applicationHealthScore"},
                                "automationMaturity": {"$avg": "$automationCoverage"},
                                "openCriticalDefects": {"$sum": "$openCriticalDefects"},
                                "applicationsAtRisk": {
                                    "$sum": {"$cond": [{"$eq": ["$riskLevel", "High"]}, 1, 0]}
                                },
                            }
                        }
                    ],
                    "portfolios": [
                        {
                            "$group": {
                                "_id": "$portfolioId",
                                "qualityScore": {"$avg": "$qualityScore"},
                                "highRiskApplications": {
                                    "$sum": {"$cond": [{"$eq": ["$riskLevel", "High"]}, 1, 0]}
                                },
                            }
                        }
                    ],
                }
            },
        ]
        cursor = await self.applications.aggregate(pipeline)
        aggregate_rows = await cursor.to_list(length=1)
        facets = aggregate_rows[0] if aggregate_rows else {"metrics": [], "portfolios": []}
        metrics = facets["metrics"][0] if facets["metrics"] else {}
        grouped = {str(row["_id"]): row for row in facets["portfolios"]}
        comparison = [
            PortfolioComparison(
                id=str(portfolio["_id"]),
                name=portfolio["name"],
                productArea=portfolio["productArea"],
                qualityScore=self._rounded(grouped.get(str(portfolio["_id"]), {}).get("qualityScore")),
                highRiskApplications=int(grouped.get(str(portfolio["_id"]), {}).get("highRiskApplications", 0)),
            )
            for portfolio in visible_portfolios
        ]
        return ExecutiveDashboardResponse(
            enterpriseQuality=self._rounded(metrics.get("enterpriseQuality")),
            averageHealth=self._rounded(metrics.get("averageHealth")),
            automationMaturity=self._rounded(metrics.get("automationMaturity")),
            openCriticalDefects=int(metrics.get("openCriticalDefects", 0)),
            applicationsAtRisk=int(metrics.get("applicationsAtRisk", 0)),
            totalApplications=int(metrics.get("totalApplications", 0)),
            totalPortfolios=len(visible_portfolios),
            portfolios=comparison,
        )

    async def _visible_portfolios(self, user: dict[str, Any]) -> list[dict[str, Any]]:
        """Read only portfolio records visible under the persisted role policy."""
        assigned = [str(value) for value in user.get("portfolioAccess", [])]
        if user.get("role") == "Administrator" and has_permission(user, "administer"):
            query: dict[str, Any] = {}
        elif assigned:
            valid_ids = [ObjectId(value) for value in assigned if ObjectId.is_valid(value)]
            query = {"_id": {"$in": valid_ids}}
        elif str(user.get("role")) in {"Administrator", "Executive", "Auditor"}:
            query = {}
        else:
            query = {"_id": {"$in": []}}
        rows = await self.portfolios.find(query, {"name": 1, "productArea": 1}).sort("name", 1).to_list(length=None)
        if user.get("role") == "Administrator" and has_permission(user, "administer"):
            return rows
        return [row for row in rows if can_access_portfolio(user, str(row["_id"]))]

    @staticmethod
    def _require_view(user: dict[str, Any]) -> None:
        """Reject accounts whose persisted permissions omit dashboard viewing."""
        if not has_permission(user, "view"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="The executive dashboard is not available to this account.")

    @staticmethod
    def _rounded(value: Any) -> int | None:
        """Round a nonnegative arithmetic mean to the nearest integer, half up."""
        if value is None:
            return None
        return math.floor(float(value) + 0.5)


__all__ = ["DashboardService"]
