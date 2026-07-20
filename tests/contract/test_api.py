import hashlib
import hmac
import json
import time

from fastapi.testclient import TestClient
from proactive_core.api.app import create_app
from proactive_core.config import Settings


def test_openapi_contains_all_public_operations() -> None:
    app = create_app(settings=Settings(env="test"))
    operations = 0
    for path, path_item in app.openapi()["paths"].items():
        if path.startswith("/api/v1") or path in {"/webhooks/gsc", "/webhooks/bing", "/webhooks/gmail"}:
            operations += sum(method in path_item for method in ("get", "post", "put", "patch", "delete"))
    assert operations == 97


def test_registration_login_and_tenant_crud() -> None:
    with TestClient(create_app(settings=Settings(env="test"))) as client:
        registered = client.post(
            "/api/v1/auth/register",
            json={
                "email": "owner@example.com",
                "password": "correct-horse-battery-staple",
                "name": "Owner User",
                "organization_name": "Example Organization",
            },
        )
        assert registered.status_code == 201
        assert registered.headers["x-request-id"]
        token = registered.json()["data"]["tokens"]["access_token"]
        headers = {"Authorization": f"Bearer {token}", "Idempotency-Key": "project-create-1"}
        project = client.post(
            "/api/v1/projects",
            headers=headers,
            json={"name": "Example", "domain": "example.com"},
        )
        assert project.status_code == 201
        listed = client.get("/api/v1/projects", headers=headers)
        assert listed.status_code == 200
        assert listed.json()["data"][0]["domain"] == "example.com"
        denied = client.get("/api/v1/projects")
        assert denied.status_code == 401
        assert denied.headers["content-type"].startswith("application/problem+json")


def test_async_agent_command_is_idempotent() -> None:
    with TestClient(create_app(settings=Settings(env="test"))) as client:
        registered = client.post(
            "/api/v1/auth/register",
            json={
                "email": "agent@example.com",
                "password": "correct-horse-battery-staple",
                "name": "Agent Owner",
                "organization_name": "Agent Organization",
            },
        )
        token = registered.json()["data"]["tokens"]["access_token"]
        headers = {"Authorization": f"Bearer {token}", "Idempotency-Key": "crawl-1"}
        first = client.post("/api/v1/agents/crawler/scan", headers=headers, json={"url": "https://example.com"})
        second = client.post("/api/v1/agents/crawler/scan", headers=headers, json={"url": "https://example.com"})
        assert first.status_code == second.status_code == 202
        assert first.json()["data"]["task_id"] == second.json()["data"]["task_id"]


def test_cursor_pagination_filters_and_sparse_fields() -> None:
    with TestClient(create_app(settings=Settings(env="test"))) as client:
        token = client.post(
            "/api/v1/auth/register",
            json={
                "email": "pagination@example.com",
                "password": "correct-horse-battery-staple",
                "name": "Pagination Owner",
                "organization_name": "Pagination Organization",
            },
        ).json()["data"]["tokens"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        for index in range(3):
            response = client.post(
                "/api/v1/projects",
                headers=headers,
                json={"name": f"Project {index}", "domain": f"project-{index}.example"},
            )
            assert response.status_code == 201

        first = client.get("/api/v1/projects?limit=2&fields=name", headers=headers)
        assert first.status_code == 200
        first_payload = first.json()
        assert len(first_payload["data"]) == 2
        assert first_payload["meta"]["has_more"] is True
        assert first_payload["meta"]["cursor"]
        assert set(first_payload["data"][0]) == {"id", "name"}

        second = client.get(
            "/api/v1/projects",
            params={"limit": 2, "cursor": first_payload["meta"]["cursor"]},
            headers=headers,
        )
        assert second.status_code == 200
        assert len(second.json()["data"]) == 1
        assert second.json()["meta"]["has_more"] is False
        assert second.json()["meta"]["cursor"] is None

        filtered = client.get("/api/v1/projects?domain=project-1.example", headers=headers)
        assert [item["domain"] for item in filtered.json()["data"]] == ["project-1.example"]
        malformed = client.get("/api/v1/projects?cursor=%21%21%21", headers=headers)
        assert malformed.status_code == 400
        assert malformed.headers["content-type"].startswith("application/problem+json")


def test_signed_webhooks_reject_replays() -> None:
    with TestClient(create_app(settings=Settings(env="test"))) as client:
        body = {"event": "updated", "resource": "property"}
        timestamp = str(int(time.time()))
        canonical = json.dumps(body, separators=(",", ":"), sort_keys=True)
        signature = hmac.new(
            b"local-webhook-secret",
            f"{timestamp}.{canonical}".encode(),
            hashlib.sha256,
        ).hexdigest()
        headers = {
            "x-webhook-timestamp": timestamp,
            "x-webhook-signature": f"sha256={signature}",
        }
        first = client.post("/webhooks/gsc", json=body, headers=headers)
        replay = client.post("/webhooks/gsc", json=body, headers=headers)
        assert first.status_code == 202
        assert replay.status_code == 401
