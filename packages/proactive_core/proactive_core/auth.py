"""Password, MFA, JWT, refresh-family, and RBAC primitives."""

from __future__ import annotations

import hashlib
import json
import secrets
import uuid
from collections.abc import Awaitable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol, cast

import jwt
import pyotp
from argon2 import PasswordHasher
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from pydantic import BaseModel, Field
from redis.asyncio import Redis

from proactive_core.config import Settings


class AuthenticationError(ValueError):
    """Raised for invalid, expired, or revoked credentials."""


class AuthorizationError(PermissionError):
    """Raised when a principal lacks a required role or permission."""


class TokenPair(BaseModel):
    """Short-lived access token and rotating refresh token."""

    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int = 900


class Principal(BaseModel):
    """Validated request identity and active tenant context."""

    user_id: uuid.UUID
    org_id: uuid.UUID
    role: str
    scopes: list[str] = Field(default_factory=list)
    session_id: uuid.UUID


@dataclass(slots=True)
class RefreshSession:
    """Server-side refresh token family member."""

    session_id: uuid.UUID
    family_id: uuid.UUID
    user_id: uuid.UUID
    org_id: uuid.UUID
    role: str
    token_hash: str
    expires_at: datetime
    used: bool = False
    revoked: bool = False


class SessionStore(Protocol):
    """Persistence contract for rotating refresh-token families."""

    async def put(self, session: RefreshSession) -> None:
        """Persist a refresh session."""

    async def get(self, token_hash: str) -> RefreshSession | None:
        """Find a refresh session by one-way token hash."""

    async def revoke_family(self, family_id: uuid.UUID) -> None:
        """Revoke every member of a compromised token family."""


class MemorySessionStore:
    """Deterministic session store for local development and tests."""

    def __init__(self) -> None:
        self.sessions: dict[str, RefreshSession] = {}

    async def put(self, session: RefreshSession) -> None:
        """Persist one session in memory."""
        self.sessions[session.token_hash] = session

    async def get(self, token_hash: str) -> RefreshSession | None:
        """Return one session by token hash."""
        return self.sessions.get(token_hash)

    async def revoke_family(self, family_id: uuid.UUID) -> None:
        """Revoke all sessions sharing a family ID."""
        for session in self.sessions.values():
            if session.family_id == family_id:
                session.revoked = True


class RedisSessionStore:
    """Redis-backed refresh sessions and revocation families."""

    def __init__(self, redis: Redis, prefix: str = "proactive:sessions") -> None:
        self.redis = redis
        self.prefix = prefix

    def _key(self, token_hash: str) -> str:
        return f"{self.prefix}:token:{token_hash}"

    def _family_key(self, family_id: uuid.UUID) -> str:
        return f"{self.prefix}:family:{family_id}"

    async def put(self, session: RefreshSession) -> None:
        """Persist one session with a TTL bounded by its expiry."""
        ttl = max(1, int((session.expires_at - datetime.now(UTC)).total_seconds()))
        payload = {
            "session_id": str(session.session_id),
            "family_id": str(session.family_id),
            "user_id": str(session.user_id),
            "org_id": str(session.org_id),
            "role": session.role,
            "token_hash": session.token_hash,
            "expires_at": session.expires_at.isoformat(),
            "used": session.used,
            "revoked": session.revoked,
        }
        async with self.redis.pipeline(transaction=True) as pipeline:
            pipeline.set(self._key(session.token_hash), json.dumps(payload), ex=ttl)
            pipeline.sadd(self._family_key(session.family_id), session.token_hash)
            pipeline.expire(self._family_key(session.family_id), ttl)
            await pipeline.execute()

    async def get(self, token_hash: str) -> RefreshSession | None:
        """Load one refresh session."""
        raw = await self.redis.get(self._key(token_hash))
        if raw is None:
            return None
        payload = json.loads(raw)
        return RefreshSession(
            session_id=uuid.UUID(payload["session_id"]),
            family_id=uuid.UUID(payload["family_id"]),
            user_id=uuid.UUID(payload["user_id"]),
            org_id=uuid.UUID(payload["org_id"]),
            role=payload["role"],
            token_hash=payload["token_hash"],
            expires_at=datetime.fromisoformat(payload["expires_at"]),
            used=payload["used"],
            revoked=payload["revoked"],
        )

    async def revoke_family(self, family_id: uuid.UUID) -> None:
        """Atomically mark every known family token as revoked."""
        family_key = self._family_key(family_id)
        hashes = await cast(Awaitable[set[Any]], self.redis.smembers(family_key))
        for token_hash_raw in hashes:
            token_hash = token_hash_raw.decode() if isinstance(token_hash_raw, bytes) else token_hash_raw
            session = await self.get(token_hash)
            if session is not None:
                session.revoked = True
                await self.put(session)


class PasswordService:
    """Argon2id password hashing and verification."""

    def __init__(self) -> None:
        self._hasher = PasswordHasher(time_cost=3, memory_cost=65_536, parallelism=4)

    def hash(self, password: str) -> str:
        """Hash a policy-validated password."""
        if len(password) < 12:
            raise AuthenticationError("Password must contain at least 12 characters")
        return self._hasher.hash(password)

    def verify(self, password_hash: str, password: str) -> bool:
        """Verify a password without leaking comparison timing."""
        try:
            return self._hasher.verify(password_hash, password)
        except Exception:
            return False


class TokenManager:
    """Issue and verify RS256 access tokens with rotating refresh families."""

    def __init__(self, settings: Settings, store: SessionStore) -> None:
        self.settings = settings
        self.store = store
        self._private_key, self._public_key = self._load_keys(settings)

    @staticmethod
    def _load_keys(settings: Settings) -> tuple[str, str]:
        private = settings.jwt_private_key.get_secret_value() if settings.jwt_private_key else None
        public = settings.jwt_public_key.get_secret_value() if settings.jwt_public_key else None
        if private and public:
            return private.replace("\\n", "\n"), public.replace("\\n", "\n")
        if settings.env in {"staging", "production"}:
            raise RuntimeError("RS256 signing keys are required outside development and test")
        key = rsa.generate_private_key(public_exponent=65_537, key_size=2048)
        private_bytes = key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
        public_bytes = key.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
        )
        return private_bytes.decode(), public_bytes.decode()

    async def issue(
        self,
        *,
        user_id: uuid.UUID,
        org_id: uuid.UUID,
        role: str,
        scopes: list[str] | None = None,
        family_id: uuid.UUID | None = None,
    ) -> TokenPair:
        """Create an access token and one server-tracked refresh token."""
        now = datetime.now(UTC)
        session_id = uuid.uuid4()
        family = family_id or uuid.uuid4()
        claims = {
            "iss": self.settings.jwt_issuer,
            "aud": self.settings.jwt_audience,
            "sub": str(user_id),
            "org": str(org_id),
            "role": role,
            "scope": scopes or [],
            "sid": str(session_id),
            "iat": now,
            "nbf": now,
            "exp": now + timedelta(minutes=self.settings.access_token_minutes),
            "jti": str(uuid.uuid4()),
        }
        access = jwt.encode(claims, self._private_key, algorithm="RS256")
        refresh = secrets.token_urlsafe(48)
        token_hash = hashlib.sha256(refresh.encode()).hexdigest()
        await self.store.put(
            RefreshSession(
                session_id=session_id,
                family_id=family,
                user_id=user_id,
                org_id=org_id,
                role=role,
                token_hash=token_hash,
                expires_at=now + timedelta(days=self.settings.refresh_token_days),
            )
        )
        return TokenPair(access_token=access, refresh_token=refresh)

    def verify_access(self, token: str) -> Principal:
        """Validate signature, issuer, audience, lifetime, and required claims."""
        try:
            claims: dict[str, Any] = jwt.decode(
                token,
                self._public_key,
                algorithms=["RS256"],
                audience=self.settings.jwt_audience,
                issuer=self.settings.jwt_issuer,
                options={"require": ["exp", "iat", "sub", "org", "sid"]},
            )
            return Principal(
                user_id=uuid.UUID(claims["sub"]),
                org_id=uuid.UUID(claims["org"]),
                role=claims["role"],
                scopes=claims.get("scope", []),
                session_id=uuid.UUID(claims["sid"]),
            )
        except (jwt.PyJWTError, KeyError, ValueError) as exc:
            raise AuthenticationError("Access token is invalid or expired") from exc

    async def rotate(self, refresh_token: str) -> TokenPair:
        """Consume a refresh token once and issue a successor in its family."""
        token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
        session = await self.store.get(token_hash)
        if session is None or session.revoked or session.expires_at <= datetime.now(UTC):
            raise AuthenticationError("Refresh token is invalid or expired")
        if session.used:
            await self.store.revoke_family(session.family_id)
            raise AuthenticationError("Refresh token reuse detected; token family revoked")
        session.used = True
        await self.store.put(session)
        return await self.issue(
            user_id=session.user_id,
            org_id=session.org_id,
            role=session.role,
            family_id=session.family_id,
        )


ROLE_LEVEL = {"viewer": 0, "billing": 0, "analyst": 1, "manager": 2, "admin": 3, "owner": 4}


def require_role(principal: Principal, required: str) -> None:
    """Enforce the documented role hierarchy."""
    normalized = "viewer" if required == "bearer" else required
    if ROLE_LEVEL.get(principal.role, -1) < ROLE_LEVEL.get(normalized, 99):
        raise AuthorizationError(f"The {required} role is required")


def verify_totp(secret: str, code: str) -> bool:
    """Verify a TOTP with one step of clock skew."""
    return pyotp.TOTP(secret).verify(code, valid_window=1)
