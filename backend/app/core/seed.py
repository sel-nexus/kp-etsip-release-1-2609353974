"""Create the deterministic first-run role, user, and inventory dataset."""

import logging
from datetime import UTC, datetime
from typing import Any

from bson import ObjectId
from passlib.context import CryptContext
from pymongo.asynchronous.database import AsyncDatabase

from app.core.config import settings
from app.models.documents import ApplicationDocument, MongoDocument, PortfolioDocument, RoleDocument, UserDocument
from app.core.database import MongoRepositories

logger = logging.getLogger(__name__)
password_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

ROLE_DATA = [
    ("Administrator", "Full platform administration", ["view", "create", "edit", "delete", "export", "administer"]),
    ("Executive", "Cross-portfolio insight and export", ["view", "export"]),
    ("Portfolio Leader", "Assigned portfolio application stewardship", ["view", "create", "edit", "export"]),
    ("Engineer", "Application record maintenance", ["view", "create", "edit", "export"]),
    ("Auditor", "Read-only inventory and audit review", ["view", "export"]),
    ("Read Only", "Read-only inventory access", ["view"]),
]
PORTFOLIO_DATA = [
    {"name": "Payments", "owner": "Digital Payments", "description": "Payment processing and settlement capabilities.", "productArea": "Payments", "status": "Active"},
    {"name": "Customer Platform", "owner": "Customer Experience", "description": "Customer identity, service, and digital channels.", "productArea": "Customer Experience", "status": "Active"},
    {"name": "Data & Analytics", "owner": "Enterprise Data", "description": "Shared data products, analytics, and reporting.", "productArea": "Data & Analytics", "status": "Active"},
]
APPLICATION_DATA = [
    ("Payment Gateway", 0, "Critical", 1, 84, 78, 72, 76, 5, 1, "Medium"),
    ("Settlement Orchestrator", 0, "High", 2, 88, 86, 81, 79, 2, 0, "Low"),
    ("Merchant Portal", 0, "High", 2, 76, 73, 65, 69, 9, 2, "High"),
    ("Customer Identity Service", 1, "Critical", 1, 91, 89, 88, 86, 1, 0, "Low"),
    ("Service Requests Hub", 1, "Medium", 3, 79, 77, 70, 74, 6, 1, "Medium"),
    ("Mobile Experience API", 1, "High", 2, 82, 80, 75, 72, 8, 2, "High"),
    ("Enterprise Data Lake", 2, "High", 1, 86, 83, 68, 71, 4, 1, "Medium"),
    ("Quality Insights", 2, "Medium", 2, 93, 92, 91, 90, 0, 0, "Low"),
    ("Regulatory Reporting", 2, "Critical", 1, 73, 70, 58, 63, 12, 4, "High"),
    ("Customer 360 Analytics", 2, "High", 2, 87, 85, 77, 82, 3, 0, "Low"),
]


def _utc_now() -> datetime:
    """Return an aware UTC timestamp for persisted records."""
    return datetime.now(UTC)


def _password_hash(password: str) -> str:
    """Hash seed credentials using the configured bcrypt implementation."""
    return password_context.hash(password)


def _validated_payload(model_type: type[MongoDocument], payload: dict[str, Any]) -> dict[str, Any]:
    """Validate a seed document and restore BSON types for references."""
    document = model_type.model_validate(payload).model_dump(exclude_none=True)
    for reference_field in ("portfolioId", "userId", "entityId"):
        reference = document.get(reference_field)
        if isinstance(reference, str) and ObjectId.is_valid(reference):
            document[reference_field] = ObjectId(reference)
    portfolio_access = document.get("portfolioAccess")
    if isinstance(portfolio_access, list):
        document["portfolioAccess"] = [ObjectId(value) for value in portfolio_access if ObjectId.is_valid(value)]
    return document


async def seed_database(database: AsyncDatabase[dict[str, Any]]) -> None:
    """Upsert each baseline record by natural key without resetting edits."""
    repositories = MongoRepositories(database)
    now = _utc_now()
    for name, description, permissions in ROLE_DATA:
        role = _validated_payload(RoleDocument, {
            "name": name,
            "description": description,
            "permissions": permissions,
            "createdAt": now,
            "updatedAt": now,
        })
        await repositories.roles.upsert_by_name(role)

    portfolios = [
        _validated_payload(PortfolioDocument, dict(data, createdAt=now, updatedAt=now))
        for data in PORTFOLIO_DATA
    ]
    for portfolio in portfolios:
        await repositories.portfolios.upsert_by_name(portfolio)
    stored_portfolios = await database["portfolios"].find(
        {"name": {"$in": [row["name"] for row in PORTFOLIO_DATA]}}
    ).to_list(length=len(PORTFOLIO_DATA))
    portfolio_ids = {row["name"]: row["_id"] for row in stored_portfolios}

    demo_accounts = [
        ("admin@ketsip.local", "Platform Administrator", "Administrator", None),
        ("executive@ketsip.local", "Demo Executive", "Executive", None),
        ("portfolio.leader@ketsip.local", "Demo Portfolio Leader", "Portfolio Leader", [str(portfolio_ids["Payments"])]),
        ("engineer@ketsip.local", "Demo Engineer", "Engineer", [str(portfolio_ids["Customer Platform"])]),
        ("auditor@ketsip.local", "Demo Auditor", "Auditor", None),
        ("readonly@ketsip.local", "Demo Read Only", "Read Only", [str(portfolio_ids["Data & Analytics"])]),
    ]
    demo_accounts.append(("quality.engineer@ketsip.local", "Demo Quality Engineer", "Engineer", [str(portfolio_ids["Payments"])]))
    for email, name, role, access in demo_accounts:
        user: dict[str, Any] = {
            "email": email,
            "name": name,
            "passwordHash": _password_hash(settings.SEED_ADMIN_PASSWORD if role == "Administrator" else settings.SEED_DEMO_PASSWORD),
            "role": role,
            "portfolioAccess": access or [],
            "status": "Active",
            "lastLogin": None,
            "authSource": "local",
            "managerName": None,
            "vendorIndicator": False,
            "defaultLandingPage": None,
            "mustChangePassword": role == "Administrator",
            "createdAt": now,
            "updatedAt": now,
        }
        await repositories.users.upsert_by_email(_validated_payload(UserDocument, user))

    for name, portfolio_index, criticality, tier, health, quality, automation, unit_coverage, defects, critical_defects, risk in APPLICATION_DATA:
        application = {
            "name": name,
            "description": f"{name} supports {PORTFOLIO_DATA[portfolio_index]['productArea']} operations.",
            "portfolioId": portfolio_ids[PORTFOLIO_DATA[portfolio_index]["name"]],
            "productArea": PORTFOLIO_DATA[portfolio_index]["productArea"],
            "businessOwner": PORTFOLIO_DATA[portfolio_index]["owner"],
            "technologyOwner": "Platform Engineering",
            "etsOwner": "Quality Office",
            "criticality": criticality,
            "tier": tier,
            "lifecycleStatus": "Active",
            "technologyStack": "Python; React; MongoDB" if portfolio_index != 2 else "Python; TypeScript; MongoDB",
            "repositoryLink": None,
            "pipelineLink": None,
            "applicationHealthScore": health,
            "qualityScore": quality,
            "automationCoverage": automation,
            "unitTestCoverage": unit_coverage,
            "openDefects": defects,
            "openCriticalDefects": critical_defects,
            "riskLevel": risk,
            "createdAt": now,
            "updatedAt": now,
        }
        await repositories.applications.upsert_by_name(_validated_payload(ApplicationDocument, application))
    logger.info("Seeded platform baseline records")
