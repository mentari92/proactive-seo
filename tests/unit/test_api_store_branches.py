import time
import uuid

import pytest
from fastapi.testclient import TestClient
from proactive_core.api.app import create_app
from proactive_core.api.store import MemoryStore
from proactive_core.auth import AuthorizationError, Principal, require_role, verify_totp
from proactive_core.config import Settings


@pytest.mark.asyncio
async def test_memory_store_isolation_update_delete_and_auth_failures() -> None:
    store = MemoryStore()
    organization, user = await store.register(
        email="owner@example.com",
        password="correct-horse-battery-staple",  # noqa: S106 - deterministic test fixture
        name="Owner",
        organization_name="Example",
    )
    with pytest.raises(ValueError, match="already exists"):
        await store.register(
            email="OWNER@example.com",
            password="correct-horse-battery-staple",  # noqa: S106 - deterministic test fixture
            name="Duplicate",
            organization_name="Example",
        )
    assert await store.authenticate("missing@example.com", "incorrect") is None
    assert await store.authenticate("owner@example.com", "incorrect") is None
    authenticated = await store.authenticate("owner@example.com", "correct-horse-battery-staple")
    assert authenticated is not None
    assert store.public_user(authenticated)["email"] == "owner@example.com"
    assert store.token_identity(authenticated)[0] == store.token_identity(user)[0]

    org_id = organization["id"]
    project = await store.create("projects", org_id, "prj", {"name": "Before"})
    assert (await store.get("projects", project["id"], org_id))["name"] == "Before"  # type: ignore[index]
    assert await store.get("projects", project["id"], "org_other") is None
    updated = await store.update("projects", project["id"], org_id, {"name": "After", "id": "ignored"})
    assert updated is not None and updated["name"] == "After" and updated["id"] == project["id"]
    assert await store.update("projects", "prj_missing", org_id, {}) is None
    assert not await store.delete("projects", project["id"], "org_other")
    assert await store.delete("projects", project["id"], org_id)
    assert await store.get("projects", project["id"], org_id) is None


def test_role_hierarchy_and_totp() -> None:
    principal = Principal(
        user_id=uuid.uuid4(),
        org_id=uuid.uuid4(),
        role="viewer",
        session_id=uuid.uuid4(),
    )
    require_role(principal, "bearer")
    with pytest.raises(AuthorizationError, match="admin"):
        require_role(principal, "admin")
    assert not verify_totp("JBSWY3DPEHPK3PXP", "000000")


def _register(client: TestClient, email: str = "branches@example.com") -> str:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "correct-horse-battery-staple",
            "name": "Branch Owner",
            "organization_name": "Branch Organization",
        },
    )
    return response.json()["data"]["tokens"]["access_token"]


def test_api_validation_crud_refresh_webhook_and_rate_limit() -> None:
    app = create_app(settings=Settings(env="test"))
    with TestClient(app) as client:
        invalid = client.post("/api/v1/auth/register", json={"email": "invalid"})
        assert invalid.status_code == 422
        assert invalid.json()["errors"]

        token = _register(client)
        conflict = client.post(
            "/api/v1/auth/register",
            json={
                "email": "branches@example.com",
                "password": "correct-horse-battery-staple",
                "name": "Duplicate",
                "organization_name": "Duplicate",
            },
        )
        assert conflict.status_code == 409
        wrong_login = client.post(
            "/api/v1/auth/login", json={"email": "branches@example.com", "password": "wrong-password-value"}
        )
        assert wrong_login.status_code == 401

        headers = {"Authorization": f"Bearer {token}"}
        project = client.post("/api/v1/projects", headers=headers, json={"name": "Project"}).json()["data"]
        fetched = client.get(f"/api/v1/projects/{project['id']}", headers=headers)
        assert fetched.status_code == 200
        patched = client.put(f"/api/v1/projects/{project['id']}", headers=headers, json={"name": "Updated"})
        assert patched.json()["data"]["name"] == "Updated"
        assert client.delete(f"/api/v1/projects/{project['id']}", headers=headers).status_code == 204
        assert client.get(f"/api/v1/projects/{project['id']}", headers=headers).status_code == 404

        unsigned = client.post("/webhooks/gsc", json={"event": "updated"})
        assert unsigned.status_code == 401
        stale = str(int(time.time()) - 600)
        stale_webhook = client.post(
            "/webhooks/gsc",
            json={"event": "updated"},
            headers={"x-webhook-timestamp": stale, "x-webhook-signature": "sha256=invalid"},
        )
        assert stale_webhook.status_code == 401

        async def deny(*args: object, **kwargs: object) -> tuple[bool, int]:
            return False, 0

        app.state.limiter.allow = deny
        limited = client.get("/api/v1/projects", headers=headers)
        assert limited.status_code == 429
        assert limited.headers["retry-after"] == "60"
