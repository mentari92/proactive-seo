"""Export the aggregate v1 OpenAPI contract for drift review."""

import json
from pathlib import Path

from proactive_core.api.app import create_app
from proactive_core.config import Settings


def main() -> None:
    """Write stable, sorted OpenAPI JSON into the contracts directory."""
    schema = create_app(settings=Settings(env="test")).openapi()
    target = Path(__file__).resolve().parents[1] / "contracts" / "openapi-v1.json"
    target.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
