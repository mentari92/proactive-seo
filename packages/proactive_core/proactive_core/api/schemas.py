"""Public request and response schemas."""

from datetime import datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, EmailStr, Field, HttpUrl

T = TypeVar("T")


class Meta(BaseModel):
    """Response metadata shared by every JSON envelope."""

    request_id: str
    timestamp: datetime
    cursor: str | None = None
    has_more: bool | None = None


class Envelope(BaseModel, Generic[T]):
    """Canonical successful response envelope."""

    data: T
    meta: Meta


class Problem(BaseModel):
    """RFC 7807 error response."""

    type: str
    title: str
    status: int
    detail: str
    instance: str
    request_id: str
    errors: list[dict[str, Any]] = Field(default_factory=list)


class RegisterRequest(BaseModel):
    """Create an organization owner account."""

    email: EmailStr
    password: str = Field(min_length=12, max_length=256)
    name: str = Field(min_length=2, max_length=255)
    organization_name: str = Field(min_length=2, max_length=255)


class LoginRequest(BaseModel):
    """Authenticate a user with optional MFA."""

    email: EmailStr
    password: str
    mfa_code: str | None = Field(default=None, min_length=6, max_length=8)


class RefreshRequest(BaseModel):
    """Rotate a refresh token."""

    refresh_token: str = Field(min_length=32)


class PasswordEmailRequest(BaseModel):
    """Request a password-reset email without revealing account existence."""

    email: EmailStr


class ResetPasswordRequest(BaseModel):
    """Consume a reset token and set a new password."""

    token: str
    password: str = Field(min_length=12, max_length=256)


class OperationRequest(BaseModel):
    """Extensible command schema used by versioned agent and provider operations."""

    project_id: str | None = None
    url: HttpUrl | None = None
    idempotency_key: str | None = Field(default=None, max_length=255)
    parameters: dict[str, Any] = Field(default_factory=dict)
