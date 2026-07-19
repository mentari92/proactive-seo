"""Fail fast when code and machine-readable product contracts drift."""

from proactive_core.api.app import create_app
from proactive_core.config import Settings
from proactive_core.contracts import api_contract, platform_contract
from proactive_core.db.models import metadata


def main() -> None:
    """Validate endpoint, table, agent, and provider cardinality."""
    contract = platform_contract()
    app = create_app(settings=Settings(env="test"))
    operations = sum(
        method in path_item
        for path, path_item in app.openapi()["paths"].items()
        if path.startswith("/api/v1") or path.startswith("/webhooks/")
        for method in ("get", "post", "put", "patch", "delete")
    )
    assert operations == len(api_contract()) == 97
    assert len(metadata.tables) == 37
    assert len(contract["agents"]) == 8
    assert len(contract["providers"]["execution"]) == 13
    print("contracts verified: 97 endpoints, 37 tables, 8 agents, 13 execution providers")


if __name__ == "__main__":
    main()
