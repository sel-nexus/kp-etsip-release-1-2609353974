"""Define MongoDB document contracts and real collection repositories."""

from datetime import UTC, datetime
from typing import Annotated, Any, Generic, TypeVar

from bson import ObjectId
from pydantic import BaseModel, BeforeValidator, ConfigDict, Field
from pymongo import ReturnDocument
from pymongo.asynchronous.collection import AsyncCollection

PyObjectId = Annotated[str, BeforeValidator(str)]


class MongoDocument(BaseModel):
    """Share BSON identifier conversion and UTC timestamp conventions."""

    model_config = ConfigDict(populate_by_name=True, from_attributes=True, extra="ignore")
    id: PyObjectId | None = Field(default=None, validation_alias="_id", serialization_alias="id")
    createdAt: datetime | None = None
    updatedAt: datetime | None = None


class UserDocument(MongoDocument):
    """Validate persisted account fields while keeping password material private."""

    name: str
    email: str
    passwordHash: str
    role: str
    portfolioAccess: list[PyObjectId] = Field(default_factory=list)
    status: str = "Active"
    lastLogin: datetime | None = None
    authSource: str = "local"
    managerName: str | None = None
    vendorIndicator: bool = False
    defaultLandingPage: str | None = None
    mustChangePassword: bool = False


class RoleDocument(MongoDocument):
    """Validate a supported role record."""

    name: str
    description: str
    permissions: list[str]


class PortfolioDocument(MongoDocument):
    """Validate a portfolio record without persisted derived rollups."""

    name: str
    owner: str
    description: str
    productArea: str
    status: str


class ApplicationDocument(MongoDocument):
    """Validate application inventory data and its ObjectId reference."""

    name: str
    description: str
    portfolioId: PyObjectId
    productArea: str
    businessOwner: str
    technologyOwner: str
    etsOwner: str
    criticality: str
    tier: int = Field(ge=1, le=4)
    lifecycleStatus: str
    technologyStack: str
    repositoryLink: str | None = None
    pipelineLink: str | None = None
    applicationHealthScore: int = Field(ge=0, le=100)
    qualityScore: int = Field(ge=0, le=100)
    automationCoverage: float = Field(ge=0, le=100)
    unitTestCoverage: float = Field(ge=0, le=100)
    openDefects: int = Field(ge=0)
    openCriticalDefects: int = Field(ge=0)
    riskLevel: str


class AuditLogDocument(MongoDocument):
    """Validate a durable audit event and ObjectId references."""

    timestamp: datetime
    userId: PyObjectId
    userName: str
    action: str
    entityType: str
    entityId: PyObjectId | None = None
    details: str


TDocument = TypeVar("TDocument", bound=dict[str, Any])


class MongoRepository(Generic[TDocument]):
    """Provide bounded access to one real MongoDB collection."""

    def __init__(self, collection: AsyncCollection[TDocument]) -> None:
        """Bind repository operations to a pooled-client collection."""
        self.collection = collection

    async def find_by_id(self, document_id: str) -> TDocument | None:
        """Retrieve one record by a validated ObjectId string."""
        if not ObjectId.is_valid(document_id):
            return None
        return await self.collection.find_one({"_id": ObjectId(document_id)})

    async def count(self, query: dict[str, Any] | None = None) -> int:
        """Count matching records using an explicit Mongo query."""
        return await self.collection.count_documents(query or {})

    async def list_page(self, query: dict[str, Any] | None = None, page: int = 1, page_size: int = 25) -> list[TDocument]:
        """Return a bounded page of matching documents."""
        cursor = self.collection.find(query or {}).skip((page - 1) * page_size).limit(page_size)
        return await cursor.to_list(length=page_size)

    async def upsert_seed(self, natural_key: dict[str, Any], document: TDocument) -> None:
        """Insert seed data only when its natural key is absent."""
        await self.collection.update_one(natural_key, {"$setOnInsert": document}, upsert=True)


class UserRepository(MongoRepository[dict[str, Any]]):
    """Access stored user accounts through MongoDB."""

    async def upsert_by_email(self, document: dict[str, Any]) -> None:
        """Ensure a seed user exists without overwriting account changes."""
        await self.upsert_seed({"email": document["email"]}, document)


class RoleRepository(MongoRepository[dict[str, Any]]):
    """Access persisted role and permission definitions."""

    async def upsert_by_name(self, document: dict[str, Any]) -> None:
        """Ensure a supported role exists without overwriting permission edits."""
        await self.upsert_seed({"name": document["name"]}, document)


class PortfolioRepository(MongoRepository[dict[str, Any]]):
    """Access persisted portfolio records."""

    async def upsert_by_name(self, document: dict[str, Any]) -> None:
        """Ensure a demo portfolio exists without overwriting later edits."""
        await self.upsert_seed({"name": document["name"]}, document)


class ApplicationRepository(MongoRepository[dict[str, Any]]):
    """Access persisted application inventory records."""

    async def upsert_by_name(self, document: dict[str, Any]) -> None:
        """Ensure a demo application exists without overwriting later edits."""
        await self.upsert_seed({"name": document["name"]}, document)


class AuditLogRepository(MongoRepository[dict[str, Any]]):
    """Access durable audit history records."""

    async def record(self, document: dict[str, Any]) -> str:
        """Persist one audit event and return its safe identifier."""
        result = await self.collection.insert_one(document)
        return str(result.inserted_id)


async def replace_by_id(repository: MongoRepository[dict[str, Any]], document_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
    """Atomically update a document while refreshing its UTC timestamp."""
    if not ObjectId.is_valid(document_id):
        return None
    updates = {**updates, "updatedAt": datetime.now(UTC)}
    return await repository.collection.find_one_and_update(
        {"_id": ObjectId(document_id)}, {"$set": updates}, return_document=ReturnDocument.AFTER
    )
