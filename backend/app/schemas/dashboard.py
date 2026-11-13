"""Define validated executive dashboard filters and response contracts."""

from pydantic import BaseModel, ConfigDict, Field


class PortfolioComparison(BaseModel):
    """Expose filtered quality and risk measures for one visible portfolio."""

    id: str
    name: str
    productArea: str
    qualityScore: int | None
    highRiskApplications: int


class ExecutiveDashboardResponse(BaseModel):
    """Expose source-derived enterprise measures and portfolio comparisons."""

    model_config = ConfigDict(extra="forbid")

    enterpriseQuality: int | None
    averageHealth: int | None
    automationMaturity: int | None
    openCriticalDefects: int
    applicationsAtRisk: int
    totalApplications: int
    totalPortfolios: int
    portfolios: list[PortfolioComparison] = Field(default_factory=list)


__all__ = ["ExecutiveDashboardResponse", "PortfolioComparison"]
