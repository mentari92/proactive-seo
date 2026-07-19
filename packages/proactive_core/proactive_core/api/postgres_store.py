"""PostgreSQL repository implementing tenant-safe API persistence."""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from datetime import UTC, datetime
from typing import Any, cast

from redis.asyncio import Redis
from sqlalchemy import delete, insert, select, update
from sqlalchemy.engine import CursorResult, RowMapping

from proactive_core.auth import PasswordService
from proactive_core.db.models import roles, tables
from proactive_core.db.session import Database
from proactive_core.ids import decode_id, encode_id

RESOURCE_TABLE = {
    "users": "users",
    "organizations": "organizations",
    "projects": "projects",
    "agents": "agents",
    "agent_runs": "agent_runs",
    "campaigns": "backlink_campaigns",
    "integrations": "oauth_connections",
    "reports": "reports",
    "pages": "pages",
    "keywords": "keywords",
    "issues": "page_issues",
}
TABLE_PREFIX = {
    "users": "usr",
    "organizations": "org",
    "projects": "prj",
    "agents": "agt",
    "agent_runs": "run",
    "backlink_campaigns": "cmp",
    "oauth_connections": "int",
    "reports": "rpt",
    "pages": "pg",
    "keywords": "kw",
    "page_issues": "iss",
}


class PostgresStore:
    """SQLAlchemy repository that always executes in a tenant RLS transaction."""

    def __init__(self, database: Database, redis: Redis) -> None:
        self.database = database
        self.redis = redis
        self.passwords = PasswordService()

    @staticmethod
    def _identity_key(email: str) -> str:
        digest = hashlib.sha256(email.casefold().encode()).hexdigest()
        return f"proactive:identity:email:{digest}"

    async def register(
        self, *, email: str, password: str, name: str, organization_name: str
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Create a tenant, owner role, and user in one RLS-scoped transaction."""
        normalized = email.casefold()
        if await self.redis.exists(self._identity_key(normalized)):
            raise ValueError("An account with this email already exists")
        org_uuid, role_uuid, user_uuid = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        slug_base = re.sub(r"[^a-z0-9]+", "-", organization_name.casefold()).strip("-")
        async with self.database.session(org_uuid, user_uuid) as session:
            await session.execute(
                insert(tables["organizations"]).values(
                    id=org_uuid,
                    name=organization_name,
                    slug=f"{slug_base}-{org_uuid.hex[:6]}",
                    plan="starter",
                    status="active",
                    settings={},
                )
            )
            await session.execute(
                insert(roles).values(
                    id=role_uuid,
                    org_id=org_uuid,
                    name="owner",
                    description="Organization owner",
                    is_system=True,
                )
            )
            await session.execute(
                insert(tables["users"]).values(
                    id=user_uuid,
                    org_id=org_uuid,
                    role_id=role_uuid,
                    email=normalized,
                    name=name,
                    password_hash=self.passwords.hash(password),
                    status="active",
                )
            )
        await self.redis.set(
            self._identity_key(normalized),
            json.dumps({"org_id": str(org_uuid), "user_id": str(user_uuid)}),
        )
        organization = {
            "id": encode_id(org_uuid, "org"),
            "name": organization_name,
            "slug": f"{slug_base}-{org_uuid.hex[:6]}",
            "plan": "starter",
            "status": "active",
        }
        user = {
            "id": encode_id(user_uuid, "usr"),
            "org_id": encode_id(org_uuid, "org"),
            "email": normalized,
            "name": name,
            "role": "owner",
            "status": "active",
        }
        return organization, user

    async def authenticate(self, email: str, password: str) -> dict[str, Any] | None:
        """Resolve email through the Redis identity index, then query inside tenant RLS."""
        raw_identity = await self.redis.get(self._identity_key(email.casefold()))
        if raw_identity is None:
            return None
        identity = json.loads(raw_identity)
        org_id, user_id = uuid.UUID(identity["org_id"]), uuid.UUID(identity["user_id"])
        async with self.database.session(org_id, user_id) as session:
            query = (
                select(tables["users"], roles.c.name.label("role"))
                .join(roles, roles.c.id == tables["users"].c.role_id)
                .where(tables["users"].c.id == user_id, tables["users"].c.deleted_at.is_(None))
            )
            row = (await session.execute(query)).mappings().one_or_none()
        if row is None or not self.passwords.verify(row["password_hash"], password):
            return None
        return {
            **self._public_row("users", row),
            "uuid": user_id,
            "org_uuid": org_id,
            "password_hash": row["password_hash"],
            "role": row["role"],
        }

    @staticmethod
    def token_identity(user: dict[str, Any]) -> tuple[uuid.UUID, uuid.UUID]:
        """Resolve internal token subjects from a repository user record."""
        if "uuid" in user and "org_uuid" in user:
            return user["uuid"], user["org_uuid"]
        return decode_id(user["id"], "usr"), decode_id(user["org_id"], "org")

    @staticmethod
    def public_user(user: dict[str, Any]) -> dict[str, Any]:
        """Remove internal authentication material from a user record."""
        private = {"uuid", "org_uuid", "password_hash"}
        return {key: value for key, value in user.items() if key not in private}

    async def list(self, resource: str, org_id: str) -> list[dict[str, Any]]:
        """List tenant-visible records for one public resource."""
        table_name = RESOURCE_TABLE.get(resource)
        if table_name is None:
            return []
        table = tables[table_name]
        org_uuid = decode_id(org_id, "org")
        async with self.database.session(org_uuid) as session:
            query = select(table)
            if "deleted_at" in table.c:
                query = query.where(table.c.deleted_at.is_(None))
            rows = (await session.execute(query.limit(100))).mappings().all()
        return [self._public_row(table_name, row) for row in rows]

    async def get(self, resource: str, item_id: str, org_id: str) -> dict[str, Any] | None:
        """Get one tenant-owned record by its typed public ID."""
        table_name = RESOURCE_TABLE.get(resource)
        if table_name is None:
            return None
        table = tables[table_name]
        org_uuid, item_uuid = decode_id(org_id, "org"), decode_id(item_id)
        async with self.database.session(org_uuid) as session:
            query = select(table).where(table.c.id == item_uuid)
            if "deleted_at" in table.c:
                query = query.where(table.c.deleted_at.is_(None))
            row = (await session.execute(query)).mappings().one_or_none()
        return self._public_row(table_name, row) if row else None

    async def create(self, resource: str, org_id: str, prefix: str, values: dict[str, Any]) -> dict[str, Any]:
        """Create one record after filtering input to real columns."""
        table_name = RESOURCE_TABLE.get(resource)
        if table_name is None:
            raise ValueError(f"Resource {resource} has no persistent table")
        table = tables[table_name]
        org_uuid, item_uuid = decode_id(org_id, "org"), uuid.uuid4()
        cleaned = self._clean_values(table_name, values)
        cleaned.update({"id": item_uuid, "org_id": org_uuid})
        async with self.database.session(org_uuid) as session:
            row = (await session.execute(insert(table).values(**cleaned).returning(table))).mappings().one()
        return self._public_row(table_name, row)

    async def update(self, resource: str, item_id: str, org_id: str, values: dict[str, Any]) -> dict[str, Any] | None:
        """Update mutable columns on one tenant-owned record."""
        table_name = RESOURCE_TABLE.get(resource)
        if table_name is None:
            return None
        table = tables[table_name]
        org_uuid, item_uuid = decode_id(org_id, "org"), decode_id(item_id)
        cleaned = self._clean_values(table_name, values)
        if not cleaned:
            return await self.get(resource, item_id, org_id)
        async with self.database.session(org_uuid) as session:
            row = (
                (await session.execute(update(table).where(table.c.id == item_uuid).values(**cleaned).returning(table)))
                .mappings()
                .one_or_none()
            )
        return self._public_row(table_name, row) if row else None

    async def delete(self, resource: str, item_id: str, org_id: str) -> bool:
        """Soft-delete when supported and hard-delete only ephemeral records."""
        table_name = RESOURCE_TABLE.get(resource)
        if table_name is None:
            return False
        table = tables[table_name]
        org_uuid, item_uuid = decode_id(org_id, "org"), decode_id(item_id)
        statement = (
            update(table).where(table.c.id == item_uuid).values(deleted_at=datetime.now(UTC))
            if "deleted_at" in table.c
            else delete(table).where(table.c.id == item_uuid)
        )
        async with self.database.session(org_uuid) as session:
            result = await session.execute(statement)
        return bool(cast(CursorResult[Any], result).rowcount)

    @staticmethod
    def _clean_values(table_name: str, values: dict[str, Any]) -> dict[str, Any]:
        table = tables[table_name]
        immutable = {"id", "org_id", "created_at", "updated_at", "deleted_at"}
        cleaned: dict[str, Any] = {}
        for key, value in values.items():
            if key in immutable or key not in table.c:
                continue
            if key.endswith("_id") and isinstance(value, str) and "_" in value:
                value = decode_id(value)
            cleaned[key] = value
        return cleaned

    @staticmethod
    def _public_row(table_name: str, row: RowMapping) -> dict[str, Any]:
        prefix = TABLE_PREFIX[table_name]
        result: dict[str, Any] = {}
        for key, value in row.items():
            if key in {"password_hash", "mfa_secret_encrypted", "access_token_encrypted", "refresh_token_encrypted"}:
                continue
            if key == "id" and isinstance(value, uuid.UUID):
                result[key] = encode_id(value, prefix)
            elif key == "org_id" and isinstance(value, uuid.UUID):
                result[key] = encode_id(value, "org")
            elif isinstance(value, uuid.UUID):
                result[key] = str(value)
            else:
                result[key] = value
        return result
