"""Exercise user and role administration through real Mongo-backed HTTP routes."""

from typing import Any

import pytest
from bson import ObjectId
from fastapi import HTTPException
from httpx import AsyncClient
from pymongo import AsyncMongoClient

from app.repositories.administration import AdministrationRepository
from app.repositories.audit import AuditRepository
from app.schemas.admin import AdminUserUpdate, RoleUpdateRequest
from app.services.administration import AdministrationService


async def _admin_headers(client: AsyncClient) -> dict[str, str]:
    """Sign in using the isolated fixture's seeded platform administrator."""
    response = await client.post("/api/auth/login", json={"email": "admin@ketsip.local", "password": "TestAdminPassword123!"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['token']}"}


async def _login_headers(client: AsyncClient, email: str) -> dict[str, str]:
    """Sign in a seeded non-administrator for direct-route authorization checks."""
    response = await client.post("/api/auth/login", json={"email": email, "password": "KetsipDemo2025!"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['token']}"}


async def _documents(collection: Any) -> list[dict[str, Any]]:
    """Read a collection in stable order for exact persistence comparisons."""
    return await collection.find({}).sort("_id", 1).to_list(length=None)


@pytest.mark.asyncio
async def test_user_crud_reactivation_and_safe_responses(api_client: AsyncClient, started_app: AsyncMongoClient[dict[str, Any]]) -> None:
    """Create, read, edit, deactivate, and reactivate while preserving history."""
    headers = await _admin_headers(api_client)
    created = await api_client.post("/api/users", headers=headers, json={
        "name": "Managed Person", "email": "managed@example.com", "role": "Engineer", "password": "ManagedPassword123!",
    })
    assert created.status_code == 201
    account = created.json()
    assert account["status"] == "Active"
    assert "passwordHash" not in account and "password" not in account
    user_id = account["id"]
    assert (await api_client.get(f"/api/users/{user_id}", headers=headers)).json()["email"] == "managed@example.com"
    changed = await api_client.put(f"/api/users/{user_id}", headers=headers, json={"name": "Managed Updated", "role": "Portfolio Leader"})
    assert changed.status_code == 200 and changed.json()["role"] == "Portfolio Leader"
    database = started_app.get_database("ketsip_test")
    stored_after_update = await database["users"].find_one({"_id": ObjectId(user_id)})
    assert stored_after_update is not None
    assert stored_after_update["name"] == "Managed Updated"
    assert stored_after_update["role"] == "Portfolio Leader"
    assert stored_after_update["status"] == "Active"
    deactivated = await api_client.delete(f"/api/users/{user_id}", headers=headers)
    assert deactivated.status_code == 200 and deactivated.json()["status"] == "Inactive"
    reactivated = await api_client.put(f"/api/users/{user_id}", headers=headers, json={"status": "Active"})
    assert reactivated.status_code == 200 and reactivated.json()["status"] == "Active"
    stored = await database["users"].find_one({"_id": ObjectId(user_id)})
    assert stored is not None and stored["passwordHash"] != "ManagedPassword123!"
    assert stored["name"] == "Managed Updated" and stored["role"] == "Portfolio Leader" and stored["status"] == "Active"
    assert await database["audit_logs"].count_documents({"entityType": "user", "entityId": ObjectId(user_id)}) == 4


@pytest.mark.asyncio
async def test_user_create_rejects_each_missing_or_wrongly_typed_required_field_without_writes(
    api_client: AsyncClient, started_app: AsyncMongoClient[dict[str, Any]]
) -> None:
    """Reject each omitted or non-string required account field before Mongo writes."""
    headers = await _admin_headers(api_client)
    database = started_app.get_database("ketsip_test")
    user_count = await database["users"].count_documents({})
    audit_count = await database["audit_logs"].count_documents({"entityType": "user"})
    valid = {
        "name": "Validation User",
        "email": "validation@example.com",
        "role": "Engineer",
        "password": "ValidationPassword123!",
    }
    rejected = []
    for field in ("name", "email", "role", "password"):
        payload = dict(valid)
        payload.pop(field)
        rejected.append(payload)
    rejected.extend((
        valid | {"name": ["not", "a", "string"]},
        valid | {"email": {"$ne": ""}},
        valid | {"role": ["Engineer"]},
        valid | {"password": True},
    ))

    for payload in rejected:
        response = await api_client.post("/api/users", headers=headers, json=payload)
        assert response.status_code == 422
        assert await database["users"].count_documents({}) == user_count
        assert await database["audit_logs"].count_documents({"entityType": "user"}) == audit_count


@pytest.mark.asyncio
async def test_user_creation_rejects_over_limit_name_email_and_password_without_mongo_changes(
    api_client: AsyncClient, started_app: AsyncMongoClient[dict[str, Any]]
) -> None:
    """Reject oversized account fields with exact 422 and preserve all Mongo documents."""
    headers = await _admin_headers(api_client)
    database = started_app.get_database("ketsip_test")
    users_before = await _documents(database["users"])
    audit_before = await _documents(database["audit_logs"])
    valid = {
        "name": "Within Limits",
        "email": "within-limits@example.com",
        "role": "Engineer",
        "password": "WithinLimitsPassword123!",
    }

    for field, value in (
        ("name", "n" * 121),
        ("email", f"{'e' * 243}@example.com"),
        ("password", "p" * 129),
    ):
        response = await api_client.post("/api/users", headers=headers, json=valid | {field: value})
        assert response.status_code == 422
        assert await _documents(database["users"]) == users_before
        assert await _documents(database["audit_logs"]) == audit_before


@pytest.mark.asyncio
async def test_partial_user_update_rejects_over_limit_name_email_and_password_without_mongo_changes(
    api_client: AsyncClient, started_app: AsyncMongoClient[dict[str, Any]]
) -> None:
    """Reject oversized partial account edits with exact 422 and preserve Mongo state."""
    headers = await _admin_headers(api_client)
    database = started_app.get_database("ketsip_test")
    target = await database["users"].find_one({"email": "quality.engineer@ketsip.local"})
    assert target is not None
    users_before = await _documents(database["users"])
    audit_before = await _documents(database["audit_logs"])

    for field, value in (
        ("name", "n" * 121),
        ("email", f"{'e' * 243}@example.com"),
        ("password", "p" * 129),
    ):
        response = await api_client.put(f"/api/users/{target['_id']}", headers=headers, json={field: value})
        assert response.status_code == 422
        assert await _documents(database["users"]) == users_before
        assert await _documents(database["audit_logs"]) == audit_before


@pytest.mark.asyncio
async def test_user_list_is_bounded_and_never_exposes_hash(api_client: AsyncClient) -> None:
    """Return stable page fields and safe user entries."""
    response = await api_client.get("/api/users?page=1&pageSize=2", headers=await _admin_headers(api_client))
    assert response.status_code == 200
    payload = response.json()
    assert set(payload) == {"items", "page", "pageSize", "total"}
    assert payload["pageSize"] == 2 and len(payload["items"]) == 2
    assert all("passwordHash" not in item for item in payload["items"])


@pytest.mark.asyncio
async def test_user_creation_rejects_bad_role_and_invalid_portfolio_reference(api_client: AsyncClient) -> None:
    """Reject unsupported role names and nonexistent portfolio references before persistence."""
    headers = await _admin_headers(api_client)
    base = {"name": "Invalid User", "email": "invalid@example.com", "password": "ManagedPassword123!"}
    bad_role = await api_client.post("/api/users", headers=headers, json={**base, "role": "Superuser"})
    assert bad_role.status_code == 422
    bad_portfolio = await api_client.post("/api/users", headers=headers, json={**base, "role": "Engineer", "portfolioAccess": [str(ObjectId())]})
    assert bad_portfolio.status_code == 422


@pytest.mark.asyncio
async def test_user_missing_ids_duplicate_email_and_invalid_page_are_rejected(api_client: AsyncClient) -> None:
    """Return appropriate not-found, conflict, and bounded-pagination errors."""
    headers = await _admin_headers(api_client)
    assert (await api_client.get("/api/users/not-an-id", headers=headers)).status_code == 404
    assert (await api_client.put("/api/users/not-an-id", headers=headers, json={"status": "Active"})).status_code == 404
    assert (await api_client.delete("/api/users/not-an-id", headers=headers)).status_code == 404
    duplicate = await api_client.post("/api/users", headers=headers, json={
        "name": "Duplicate", "email": "executive@ketsip.local", "role": "Engineer", "password": "ManagedPassword123!",
    })
    assert duplicate.status_code == 409
    assert (await api_client.get("/api/users?pageSize=101", headers=headers)).status_code == 422


@pytest.mark.asyncio
async def test_only_administer_role_can_access_user_and_role_management(api_client: AsyncClient) -> None:
    """Reject direct user and role management calls for every non-admin role sample."""
    for email in ("executive@ketsip.local", "engineer@ketsip.local", "auditor@ketsip.local", "readonly@ketsip.local"):
        headers = await _login_headers(api_client, email)
        assert (await api_client.get("/api/users", headers=headers)).status_code == 403
        assert (await api_client.get("/api/roles", headers=headers)).status_code == 403
        assert (await api_client.post("/api/users", headers=headers, json={})).status_code == 403
        assert (await api_client.post("/api/roles", headers=headers, json={"name": "Engineer", "description": "Engineer role"})).status_code == 403


@pytest.mark.asyncio
async def test_user_and_role_management_require_authentication(api_client: AsyncClient) -> None:
    """Reject requests without bearer credentials before management work."""
    assert (await api_client.get("/api/users")).status_code == 401
    assert (await api_client.get("/api/roles")).status_code == 401
    assert (await api_client.post("/api/roles", json={"name": "Engineer", "description": "Engineer role"})).status_code == 401


@pytest.mark.asyncio
async def test_role_edit_changes_persist_and_emit_one_permission_audit(api_client: AsyncClient, started_app: AsyncMongoClient[dict[str, Any]]) -> None:
    """List only six roles and audit exactly one changed permission set."""
    headers = await _admin_headers(api_client)
    listing = await api_client.get("/api/roles", headers=headers)
    assert listing.status_code == 200 and len(listing.json()) == 6
    engineer = next(role for role in listing.json() if role["name"] == "Engineer")
    permissions = list(engineer["permissions"])
    updated = await api_client.put("/api/roles/Engineer", headers=headers, json={"description": engineer["description"], "permissions": ["view", "edit"]})
    assert updated.status_code == 200 and updated.json()["permissions"] == ["view", "edit"]
    database = started_app.get_database("ketsip_test")
    assert await database["roles"].count_documents({}) == 6
    stored_role = await database["roles"].find_one({"name": "Engineer"})
    assert stored_role is not None and stored_role["permissions"] == ["view", "edit"]
    assert await database["audit_logs"].count_documents({"action": "permissionChange", "entityType": "role"}) == 1
    await api_client.put("/api/roles/Engineer", headers=headers, json={"description": engineer["description"], "permissions": permissions})


@pytest.mark.asyncio
async def test_role_provision_creates_supported_role_and_repeat_is_idempotent(
    api_client: AsyncClient, started_app: AsyncMongoClient[dict[str, Any]]
) -> None:
    """Create an absent supported role once, then preserve it on repeated provisioning."""
    headers = await _admin_headers(api_client)
    database = started_app.get_database("ketsip_test")
    roles = database["roles"]
    original = await roles.find_one({"name": "Engineer"})
    assert original is not None
    audit_before = await database["audit_logs"].count_documents({"entityType": "role", "action": "create"})
    payload = {"name": "Engineer", "description": "Provisioned engineer", "permissions": ["view", "edit"]}
    try:
        await roles.delete_one({"_id": original["_id"]})
        created = await api_client.post("/api/roles", headers=headers, json=payload)
        assert created.status_code == 201
        body = created.json()
        assert body["name"] == "Engineer" and body["description"] == payload["description"]
        assert body["permissions"] == payload["permissions"]
        assert set(body) == {"id", "name", "description", "permissions"}
        assert await roles.count_documents({"name": "Engineer"}) == 1
        stored = await roles.find_one({"name": "Engineer"})
        assert stored is not None

        repeated = await api_client.post("/api/roles", headers=headers, json={
            "name": "Engineer", "description": "Must not overwrite", "permissions": ["view"],
        })
        assert repeated.status_code == 200
        assert repeated.json() == body
        assert await roles.count_documents({"name": "Engineer"}) == 1
        assert await roles.find_one({"name": "Engineer"}) == stored
        assert await database["audit_logs"].count_documents({"entityType": "role", "action": "create"}) == audit_before + 1
    finally:
        await roles.delete_one({"name": "Engineer"})
        await roles.insert_one(original)


@pytest.mark.asyncio
async def test_role_provision_rejects_missing_name_without_mongo_changes(
    api_client: AsyncClient, started_app: AsyncMongoClient[dict[str, Any]]
) -> None:
    """Reject role provisioning without its required name before any Mongo writes."""
    headers = await _admin_headers(api_client)
    database = started_app.get_database("ketsip_test")
    roles_before = await _documents(database["roles"])
    audit_before = await _documents(database["audit_logs"])

    response = await api_client.post("/api/roles", headers=headers, json={
        "description": "Provisioned engineer", "permissions": ["view", "edit"],
    })

    assert response.status_code == 422
    assert await _documents(database["roles"]) == roles_before
    assert await _documents(database["audit_logs"]) == audit_before


@pytest.mark.asyncio
async def test_role_provision_rejects_missing_description_without_mongo_changes(
    api_client: AsyncClient, started_app: AsyncMongoClient[dict[str, Any]]
) -> None:
    """Reject role provisioning without its required description before any Mongo writes."""
    headers = await _admin_headers(api_client)
    database = started_app.get_database("ketsip_test")
    roles_before = await _documents(database["roles"])
    audit_before = await _documents(database["audit_logs"])

    response = await api_client.post("/api/roles", headers=headers, json={
        "name": "Engineer", "permissions": ["view", "edit"],
    })

    assert response.status_code == 422
    assert await _documents(database["roles"]) == roles_before
    assert await _documents(database["audit_logs"]) == audit_before


@pytest.mark.asyncio
async def test_role_update_rejects_missing_description_without_mongo_changes(
    api_client: AsyncClient, started_app: AsyncMongoClient[dict[str, Any]]
) -> None:
    """Reject role updates without their required description before any Mongo writes."""
    headers = await _admin_headers(api_client)
    database = started_app.get_database("ketsip_test")
    roles_before = await _documents(database["roles"])
    audit_before = await _documents(database["audit_logs"])

    response = await api_client.put("/api/roles/Engineer", headers=headers, json={"permissions": ["view", "edit"]})

    assert response.status_code == 422
    assert await _documents(database["roles"]) == roles_before
    assert await _documents(database["audit_logs"]) == audit_before


@pytest.mark.asyncio
async def test_role_update_rejects_missing_permissions_without_mongo_changes(
    api_client: AsyncClient, started_app: AsyncMongoClient[dict[str, Any]]
) -> None:
    """Reject role updates without their required permissions before any Mongo writes."""
    headers = await _admin_headers(api_client)
    database = started_app.get_database("ketsip_test")
    roles_before = await _documents(database["roles"])
    audit_before = await _documents(database["audit_logs"])

    response = await api_client.put(
        "/api/roles/Engineer", headers=headers, json={"description": "Updated engineer role"}
    )

    assert response.status_code == 422
    assert await _documents(database["roles"]) == roles_before
    assert await _documents(database["audit_logs"]) == audit_before


@pytest.mark.asyncio
async def test_role_provision_rejects_unsupported_names_and_permissions_outside_defaults(
    api_client: AsyncClient, started_app: AsyncMongoClient[dict[str, Any]]
) -> None:
    """Reject a seventh role and permissions outside a supported role's default set."""
    headers = await _admin_headers(api_client)
    roles = started_app.get_database("ketsip_test")["roles"]
    count_before = await roles.count_documents({})
    unsupported = await api_client.post("/api/roles", headers=headers, json={"name": "Superuser", "description": "Unsupported"})
    assert unsupported.status_code == 422
    invalid_subset = await api_client.post("/api/roles", headers=headers, json={
        "name": "Read Only", "description": "Invalid permission grant", "permissions": ["administer"],
    })
    assert invalid_subset.status_code == 422
    assert await roles.count_documents({}) == count_before


@pytest.mark.asyncio
async def test_role_provision_and_update_reject_over_limit_description_and_permissions_without_mongo_changes(
    api_client: AsyncClient, started_app: AsyncMongoClient[dict[str, Any]]
) -> None:
    """Reject oversized role descriptions and permission lists before any role or audit write."""
    headers = await _admin_headers(api_client)
    database = started_app.get_database("ketsip_test")
    roles_before = await _documents(database["roles"])
    audit_before = await _documents(database["audit_logs"])
    valid_description = "Valid role description"
    seven_permissions = ["view", "create", "edit", "delete", "export", "administer", "view"]

    provision_payloads = (
        {"name": "Engineer", "description": "d" * 241, "permissions": ["view"]},
        {"name": "Engineer", "description": valid_description, "permissions": seven_permissions},
    )
    for payload in provision_payloads:
        response = await api_client.post("/api/roles", headers=headers, json=payload)
        assert response.status_code == 422
        assert await _documents(database["roles"]) == roles_before
        assert await _documents(database["audit_logs"]) == audit_before

    update_payloads = (
        {"description": "d" * 241, "permissions": ["view"]},
        {"description": valid_description, "permissions": seven_permissions},
    )
    for payload in update_payloads:
        response = await api_client.put("/api/roles/Engineer", headers=headers, json=payload)
        assert response.status_code == 422
        assert await _documents(database["roles"]) == roles_before
        assert await _documents(database["audit_logs"]) == audit_before


@pytest.mark.asyncio
async def test_roles_reject_unsupported_role_permissions_duplicates_and_missing_role(api_client: AsyncClient) -> None:
    """Reject new role names, unsupported capabilities, duplicates, and missing role records."""
    headers = await _admin_headers(api_client)
    payload = {"description": "Known role", "permissions": ["view"]}
    assert (await api_client.put("/api/roles/Unrecognized", headers=headers, json=payload)).status_code == 404
    assert (await api_client.put("/api/roles/Engineer", headers=headers, json={"description": "x", "permissions": ["admin"]})).status_code == 422
    assert (await api_client.put("/api/roles/Engineer", headers=headers, json={"description": "x", "permissions": ["view", "view"]})).status_code == 422
    assert (await api_client.put("/api/roles/Engineer", headers=headers, json={"description": "x", "permissions": ["view"], "extra": True})).status_code == 422


@pytest.mark.asyncio
async def test_account_duplicate_email_update_and_concurrent_missing_update_are_rejected_without_audit(
    started_app: AsyncMongoClient[dict[str, Any]],
) -> None:
    """Exercise account uniqueness and the missing-row result after an update race."""
    database = started_app.get_database("ketsip_test")
    repository = AdministrationRepository(database)
    audit = AuditRepository(database)
    service = AdministrationService(repository, audit)
    actor_row = await database["users"].find_one({"email": "admin@ketsip.local"})
    target = await database["users"].find_one({"email": "quality.engineer@ketsip.local"})
    assert actor_row is not None and target is not None
    actor = {"_id": actor_row["_id"], "name": actor_row["name"]}
    audit_count = await database["audit_logs"].count_documents({"entityType": "user"})

    with pytest.raises(HTTPException) as duplicate:
        await service.update_user(str(target["_id"]), AdminUserUpdate(email="executive@ketsip.local"), actor)
    assert duplicate.value.status_code == 409
    unchanged = await database["users"].find_one({"_id": target["_id"]})
    assert unchanged is not None and unchanged["email"] == "quality.engineer@ketsip.local"
    assert await database["audit_logs"].count_documents({"entityType": "user"}) == audit_count

    class DeletingAdministrationRepository(AdministrationRepository):
        """Remove the target in Mongo between service lookup and conditional update."""

        async def update_user(self, user_id: str, changes: dict[str, Any]) -> dict[str, Any] | None:
            await self.users.delete_one({"_id": ObjectId(user_id)})
            return await super().update_user(user_id, changes)

    raced_service = AdministrationService(DeletingAdministrationRepository(database), audit)
    with pytest.raises(HTTPException) as missing:
        await raced_service.update_user(str(target["_id"]), AdminUserUpdate(name="Raced update"), actor)
    assert missing.value.status_code == 404
    assert await database["users"].find_one({"_id": target["_id"]}) is None
    assert await database["audit_logs"].count_documents({"entityType": "user"}) == audit_count


@pytest.mark.asyncio
async def test_role_update_missing_row_and_audit_failure_are_observable_in_mongo(
    started_app: AsyncMongoClient[dict[str, Any]],
) -> None:
    """Return not-found on a lost role row and expose post-write audit failure state."""
    database = started_app.get_database("ketsip_test")
    actor_row = await database["users"].find_one({"email": "admin@ketsip.local"})
    assert actor_row is not None
    actor = {"_id": actor_row["_id"], "name": actor_row["name"]}
    engineer = await database["roles"].find_one({"name": "Engineer"})
    assert engineer is not None

    class DeletingRoleRepository(AdministrationRepository):
        """Remove the role after its service-level existence check."""

        async def update_role(self, name: str, changes: dict[str, Any]) -> dict[str, Any] | None:
            await self.roles.delete_one({"name": name})
            return await super().update_role(name, changes)

    missing_service = AdministrationService(DeletingRoleRepository(database), AuditRepository(database))
    missing_audits = await database["audit_logs"].count_documents({"entityType": "role"})
    with pytest.raises(HTTPException) as missing:
        await missing_service.update_role(
            "Engineer", RoleUpdateRequest(description=engineer["description"], permissions=["view"]), actor
        )
    assert missing.value.status_code == 404
    assert await database["roles"].find_one({"name": "Engineer"}) is None
    assert await database["audit_logs"].count_documents({"entityType": "role"}) == missing_audits

    await database["roles"].insert_one(engineer)

    class FailingAuditRepository(AuditRepository):
        """Simulate an audit-store failure after a successful role write."""

        async def record(self, actor: dict[str, Any], action: str, entity_type: str, entity_id: str | None, details: str, at: Any) -> None:
            raise RuntimeError("simulated audit persistence failure")

    failure_service = AdministrationService(AdministrationRepository(database), FailingAuditRepository(database))
    before = await database["audit_logs"].count_documents({"entityType": "role"})
    with pytest.raises(RuntimeError, match="audit persistence failure"):
        await failure_service.update_role(
            "Engineer", RoleUpdateRequest(description=engineer["description"], permissions=["view"]), actor
        )
    persisted = await database["roles"].find_one({"name": "Engineer"})
    assert persisted is not None and persisted["permissions"] == ["view"]
    assert await database["audit_logs"].count_documents({"entityType": "role"}) == before
