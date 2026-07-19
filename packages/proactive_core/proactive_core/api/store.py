"""Thread-safe local store implementing credential-free development behavior."""

from __future__ import annotations

import asyncio
import re
import uuid
from collections import defaultdict
from copy import deepcopy
from typing import Any

from proactive_core.auth import PasswordService
from proactive_core.ids import encode_id


class MemoryStore:
    """Tenant-isolated local repository; production services use PostgreSQL repositories."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self.passwords = PasswordService()
        self.resources: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
        self.users_by_email: dict[str, str] = {}

    async def register(
        self, *, email: str, password: str, name: str, organization_name: str
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Atomically create a tenant and owner."""
        normalized = email.casefold()
        async with self._lock:
            if normalized in self.users_by_email:
                raise ValueError("An account with this email already exists")
            org_uuid = uuid.uuid4()
            user_uuid = uuid.uuid4()
            org_id = encode_id(org_uuid, "org")
            user_id = encode_id(user_uuid, "usr")
            slug = re.sub(r"[^a-z0-9]+", "-", organization_name.casefold()).strip("-")
            org = {
                "id": org_id,
                "uuid": org_uuid,
                "name": organization_name,
                "slug": f"{slug}-{org_uuid.hex[:6]}",
                "plan": "starter",
                "status": "active",
            }
            user = {
                "id": user_id,
                "uuid": user_uuid,
                "org_id": org_id,
                "org_uuid": org_uuid,
                "email": normalized,
                "name": name,
                "role": "owner",
                "status": "active",
                "password_hash": self.passwords.hash(password),
                "mfa_enabled": False,
            }
            self.resources["organizations"][org_id] = org
            self.resources["users"][user_id] = user
            self.users_by_email[normalized] = user_id
            return self._public(org), self._public(user)

    async def authenticate(self, email: str, password: str) -> dict[str, Any] | None:
        """Validate local credentials and return a public user record."""
        user_id = self.users_by_email.get(email.casefold())
        if user_id is None:
            self.passwords.verify("$argon2id$v=19$m=65536,t=3,p=4$invalid$invalid", password)
            return None
        user = self.resources["users"][user_id]
        if not self.passwords.verify(user["password_hash"], password):
            return None
        return deepcopy(user)

    def token_identity(self, user: dict[str, Any]) -> tuple[uuid.UUID, uuid.UUID]:
        """Resolve internal token subjects without exposing them in API payloads."""
        stored = self.resources["users"][user["id"]]
        return stored["uuid"], stored["org_uuid"]

    def public_user(self, user: dict[str, Any]) -> dict[str, Any]:
        """Remove credential and internal identity fields from a user record."""
        return self._public(user)

    async def list(self, resource: str, org_id: str) -> list[dict[str, Any]]:
        """List records visible to one tenant."""
        return [
            self._public(item) for item in self.resources[resource].values() if item.get("org_id", org_id) == org_id
        ]

    async def get(self, resource: str, item_id: str, org_id: str) -> dict[str, Any] | None:
        """Get one tenant-owned record."""
        item = self.resources[resource].get(item_id)
        if item is None or item.get("org_id", org_id) != org_id:
            return None
        return self._public(item)

    async def create(self, resource: str, org_id: str, prefix: str, values: dict[str, Any]) -> dict[str, Any]:
        """Create one tenant-owned resource."""
        async with self._lock:
            item_id = encode_id(uuid.uuid4(), prefix)
            item = {"id": item_id, "org_id": org_id, **values}
            self.resources[resource][item_id] = item
            return self._public(item)

    async def update(self, resource: str, item_id: str, org_id: str, values: dict[str, Any]) -> dict[str, Any] | None:
        """Update an existing tenant resource."""
        async with self._lock:
            item = self.resources[resource].get(item_id)
            if item is None or item.get("org_id", org_id) != org_id:
                return None
            item.update(values)
            item["id"] = item_id
            item["org_id"] = org_id
            return self._public(item)

    async def delete(self, resource: str, item_id: str, org_id: str) -> bool:
        """Delete one tenant resource from the local store."""
        async with self._lock:
            item = self.resources[resource].get(item_id)
            if item is None or item.get("org_id", org_id) != org_id:
                return False
            del self.resources[resource][item_id]
            return True

    @staticmethod
    def _public(item: dict[str, Any]) -> dict[str, Any]:
        private = {"password_hash", "uuid", "org_uuid"}
        return {key: deepcopy(value) for key, value in item.items() if key not in private}
