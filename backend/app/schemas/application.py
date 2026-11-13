"""Define validated application inventory requests and safe response models."""

from datetime import UTC, datetime
from typing import Literal

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, field_validator

from app.schemas.common import PageResponse

Criticality = Literal["Low", "Medium", "High", "Critical"]
LifecycleStatus = Literal["Active", "Deprecated", "Retired"]
RiskLevel = Literal["Low", "Medium", "High"]


class ApplicationFields(BaseModel):
    """Validate source fields shared by create, update, and response records."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=160)
    description: str = Field(min_length=1, max_length=2000)
    portfolioId: str = Field(min_length=1, max_length=64)
    productArea: str = Field(min_length=1, max_length=120)
    businessOwner: str = Field(min_length=1, max_length=120)
    technologyOwner: str = Field(min_length=1, max_length=120)
    etsOwner: str = Field(min_length=1, max_length=120)
    criticality: Criticality
    tier: int = Field(ge=1, le=4)
    lifecycleStatus: LifecycleStatus
    technologyStack: str = Field(max_length=1000)
    repositoryLink: AnyHttpUrl | None = None
    pipelineLink: AnyHttpUrl | None = None
    applicationHealthScore: int = Field(ge=0, le=100)
    qualityScore: int = Field(ge=0, le=100)
    automationCoverage: float = Field(ge=0, le=100, allow_inf_nan=False)
    unitTestCoverage: float = Field(ge=0, le=100, allow_inf_nan=False)
    openDefects: int = Field(ge=0)
    openCriticalDefects: int = Field(ge=0)
    riskLevel: RiskLevel

    @field_validator("name", "description", "productArea", "businessOwner", "technologyOwner", "etsOwner")
    @classmethod
    def reject_blank_text(cls, value: str) -> str:
        """Trim human-entered text and reject values containing only whitespace."""
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("This field must not be blank.")
        return cleaned


class ApplicationCreate(ApplicationFields):
    """Validate the complete source record required for application creation."""


class ApplicationUpdate(ApplicationFields):
    """Validate complete replacement fields for an existing application."""


class PortfolioReference(BaseModel):
    """Expose a safe application portfolio link."""

    id: str
    name: str


class ApplicationListItem(ApplicationFields):
    """Return safe application fields alongside its portfolio display name."""

    id: str
    portfolioName: str


class ApplicationDetail(ApplicationFields):
    """Return complete source fields, portfolio reference, and UTC timestamps."""

    id: str
    portfolio: PortfolioReference
    createdAt: datetime
    updatedAt: datetime

    @field_validator("createdAt", "updatedAt", mode="before")
    @classmethod
    def ensure_utc(cls, value: datetime) -> datetime:
        """Treat legacy naive BSON dates as UTC and preserve aware timestamps."""
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)


ApplicationPage = PageResponse[ApplicationListItem]


__all__ = [
    "ApplicationCreate",
    "ApplicationDetail",
    "ApplicationFields",
    "ApplicationListItem",
    "ApplicationPage",
    "ApplicationUpdate",
    "Criticality",
    "LifecycleStatus",
    "PortfolioReference",
    "RiskLevel",
]
