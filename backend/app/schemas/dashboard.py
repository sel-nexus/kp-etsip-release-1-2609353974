"""Define validated executive dashboard filters and response contracts."""

from pydantic import BaseModel, ConfigDict, Field


class PortfolioComparison(BaseModel):
    """Expose filtered quality and risk measures for one visible portfolio."""

    portfolioId: str
    portfolioName: str
    qualityScore: int | None
    highRiskApplicationCount: int


class ExecutiveDashboardResponse(BaseModel):
    """Expose source-derived enterprise measures and portfolio comparisons."""

    model_config = ConfigDict(extra="forbid")

    enterpriseQualityScore: int | None
    averageApplicationHealthScore: int | None
    automationMaturityScore: int | None
    openCriticalDefects: int
    applicationsAtRisk: int
    totalApplications: int
    totalPortfolios: int
    portfolioQualityScores: list[PortfolioComparison] = Field(default_factory=list)


__all__ = ["ExecutiveDashboardResponse", "PortfolioComparison"]
