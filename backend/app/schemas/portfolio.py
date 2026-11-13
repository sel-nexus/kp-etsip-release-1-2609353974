"""Define typed requests and safe responses for portfolio inventory."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.common import PageResponse

PortfolioStatus = Literal["Active", "Archived"]


class PortfolioCreate(BaseModel):
    """Validate all fields required to create a portfolio."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    owner: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=1000)
    productArea: str = Field(min_length=1, max_length=120)
    status: PortfolioStatus


class PortfolioUpdate(BaseModel):
    """Validate the fields that may change on an existing portfolio."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=120)
    owner: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, min_length=1, max_length=1000)
    productArea: str | None = Field(default=None, min_length=1, max_length=120)
    status: PortfolioStatus | None = None

    @model_validator(mode="after")
    def reject_explicit_nulls(self) -> "PortfolioUpdate":
        """Reject null updates while allowing omitted fields to remain unchanged."""
        for field_name in self.model_fields_set:
            if getattr(self, field_name) is None:
                raise ValueError(f"{field_name} must not be null.")
        return self


class PortfolioSummary(BaseModel):
    """Expose inventory fields and source-derived rollups for a list row."""

    id: str
    name: str
    owner: str
    productArea: str
    status: PortfolioStatus
    applicationCount: int
    qualityScore: float | None


class PortfolioDetail(PortfolioSummary):
    """Expose the complete safe portfolio description and derived measures."""

    description: str


class ApplicationListItem(BaseModel):
    """Expose safe application inventory fields linked to a portfolio."""

    id: str
    name: str
    description: str
    portfolioId: str
    productArea: str
    businessOwner: str
    technologyOwner: str
    etsOwner: str
    criticality: str
    tier: int
    lifecycleStatus: str
    technologyStack: str
    repositoryLink: str | None = None
    pipelineLink: str | None = None
    applicationHealthScore: int
    qualityScore: int
    automationCoverage: float
    unitTestCoverage: float
    openDefects: int
    openCriticalDefects: int
    riskLevel: str


PortfolioPage = PageResponse[PortfolioSummary]
ApplicationPage = PageResponse[ApplicationListItem]


__all__ = [
    "ApplicationListItem",
    "ApplicationPage",
    "PortfolioCreate",
    "PortfolioDetail",
    "PortfolioPage",
    "PortfolioStatus",
    "PortfolioSummary",
    "PortfolioUpdate",
]
