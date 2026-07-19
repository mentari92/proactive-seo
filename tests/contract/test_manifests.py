from proactive_core.contracts import api_contract, platform_contract
from proactive_core.db.models import metadata


def test_api_manifest_is_exact_and_unique() -> None:
    endpoints = api_contract()
    assert len(endpoints) == 97
    assert len({(item.method, item.path) for item in endpoints}) == 97


def test_database_manifest_matches_metadata() -> None:
    contract = platform_contract()
    expected = set(contract["tables"]["seo"] + contract["tables"]["audit"])
    assert len(expected) == 37
    assert {table.name for table in metadata.tables.values()} == expected
    assert sum(table.schema == "audit" for table in metadata.tables.values()) == 1


def test_eight_agents_and_thirteen_execution_providers() -> None:
    contract = platform_contract()
    assert len(contract["agents"]) == 8
    assert len(contract["providers"]["execution"]) == 13
