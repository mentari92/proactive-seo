"""Reversible typed identifiers backed by UUIDs."""

import base64
import uuid
from typing import Final

PREFIXES: Final[set[str]] = {
    "usr",
    "org",
    "prj",
    "agt",
    "run",
    "tsk",
    "evt",
    "iss",
    "pg",
    "kw",
    "cmp",
    "msg",
    "int",
    "rpt",
    "whk",
    "inv",
    "sch",
}


class InvalidPublicId(ValueError):
    """Raised when a public identifier cannot be decoded safely."""


def encode_id(value: uuid.UUID, prefix: str) -> str:
    """Encode a UUID as a compact, reversible, type-prefixed public ID."""
    if prefix not in PREFIXES:
        raise InvalidPublicId(f"Unsupported ID prefix: {prefix}")
    token = base64.urlsafe_b64encode(value.bytes).rstrip(b"=").decode("ascii")
    return f"{prefix}_{token}"


def decode_id(value: str, expected_prefix: str | None = None) -> uuid.UUID:
    """Decode a public ID and optionally enforce its entity type."""
    try:
        prefix, token = value.split("_", 1)
    except ValueError as exc:
        raise InvalidPublicId("Identifier must contain a type prefix") from exc
    if prefix not in PREFIXES or (expected_prefix is not None and prefix != expected_prefix):
        raise InvalidPublicId("Identifier type does not match the requested resource")
    try:
        padded = token + "=" * (-len(token) % 4)
        raw = base64.urlsafe_b64decode(padded.encode("ascii"))
        return uuid.UUID(bytes=raw)
    except (ValueError, TypeError) as exc:
        raise InvalidPublicId("Identifier payload is invalid") from exc
