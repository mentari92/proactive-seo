"""Load and validate the machine-readable product contracts."""

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, cast

import yaml


@dataclass(frozen=True, slots=True)
class EndpointContract:
    """One public API operation from the canonical v1 manifest."""

    method: str
    path: str
    authorization: str
    rate_limit: str


def repository_root() -> Path:
    """Locate the repository in editable installs and container images."""
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "contracts" / "api-v1.yaml").exists():
            return parent
    return Path.cwd()


@lru_cache
def api_contract() -> tuple[EndpointContract, ...]:
    """Return the immutable, validated set of 97 API operations."""
    path = repository_root() / "contracts" / "api-v1.yaml"
    raw = cast(dict[str, Any], yaml.safe_load(path.read_text(encoding="utf-8")))
    endpoints = tuple(EndpointContract(*item) for item in raw["endpoints"])
    if len(endpoints) != 97:
        raise RuntimeError(f"Public API contract must contain 97 endpoints, got {len(endpoints)}")
    keys = {(item.method, item.path) for item in endpoints}
    if len(keys) != len(endpoints):
        raise RuntimeError("Public API contract contains duplicate operations")
    return endpoints


@lru_cache
def platform_contract() -> dict[str, Any]:
    """Return the canonical platform manifest."""
    path = repository_root() / "contracts" / "platform.yaml"
    return cast(dict[str, Any], yaml.safe_load(path.read_text(encoding="utf-8")))
