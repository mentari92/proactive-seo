import os

import pytest
from proactive_core.api.postgres_store import PostgresStore
from proactive_core.db.session import Database

DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="TEST_DATABASE_URL is not configured")


class RedisIdentityFake:
    """Minimal identity index used by the PostgreSQL repository test."""

    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    async def exists(self, key: str) -> int:
        return int(key in self.values)

    async def set(self, key: str, value: str) -> None:
        self.values[key] = value

    async def get(self, key: str) -> str | None:
        return self.values.get(key)


@pytest.mark.asyncio
async def test_postgres_identity_and_tenant_crud() -> None:
    database = Database(str(DATABASE_URL))
    store = PostgresStore(database, RedisIdentityFake())  # type: ignore[arg-type]
    organization, user = await store.register(
        email="postgres-store@example.com",
        password="correct-horse-battery-staple",  # noqa: S106 - deterministic test fixture
        name="Database Owner",
        organization_name="Database Organization",
    )
    authenticated = await store.authenticate("postgres-store@example.com", "correct-horse-battery-staple")
    assert authenticated is not None
    assert store.public_user(authenticated)["email"] == user["email"]
    project = await store.create(
        "projects",
        organization["id"],
        "prj",
        {"name": "Database Project", "domain": "database.example", "settings": {}},
    )
    assert project["id"].startswith("prj_")
    assert len(await store.list("projects", organization["id"])) == 1
    await database.close()
