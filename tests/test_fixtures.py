"""Unit tests ensuring Phase 3 schemas and fixtures are valid."""
import json
import os
import jsonschema
import pytest

FIXTURES_DIR = "fixtures"
SCHEMAS_DIR = os.path.join(FIXTURES_DIR, "schemas")

SUBAGENTS = [
    "version-diff",
    "vuln-lookup",
    "usage-impact",
    "fix-verify",
    "risk-rank"
]

@pytest.mark.parametrize("subagent", SUBAGENTS)
def test_fixture_against_schema(subagent):
    schema_path = os.path.join(SCHEMAS_DIR, f"{subagent}.schema.json")
    fixture_path = os.path.join(FIXTURES_DIR, f"{subagent}.json")

    assert os.path.isfile(schema_path), f"Schema file missing: {schema_path}"
    assert os.path.isfile(fixture_path), f"Fixture file missing: {fixture_path}"

    with open(schema_path, "r", encoding="utf-8") as f:
        schema = json.load(f)

    with open(fixture_path, "r", encoding="utf-8") as f:
        fixture = json.load(f)

    # Must validate without raising jsonschema.ValidationError
    jsonschema.validate(instance=fixture, schema=schema)

def test_cross_fixture_consistency():
    fixtures = {}
    for subagent in SUBAGENTS:
        with open(os.path.join(FIXTURES_DIR, f"{subagent}.json"), "r", encoding="utf-8") as f:
            fixtures[subagent] = json.load(f)

    # Package name & ecosystem
    assert fixtures["version-diff"]["package_name"] == "axios"
    assert fixtures["vuln-lookup"]["package_name"] == "axios"
    assert fixtures["usage-impact"]["package_name"] == "axios"
    assert fixtures["fix-verify"]["package_name"] == "axios"
    assert fixtures["risk-rank"]["package_name"] == "axios"

    # Versions
    assert fixtures["version-diff"]["old_version"] == "1.4.0"
    assert fixtures["version-diff"]["new_version"] == "1.7.2"
    assert fixtures["fix-verify"]["new_version"] == "1.7.2"

    # Breaking change IDs
    vd_bcs = [bc["id"] for bc in fixtures["version-diff"]["breaking_changes"]]
    for impact in fixtures["usage-impact"]["impact_results"]:
        assert impact["breaking_change_id"] in vd_bcs

    for patch in fixtures["fix-verify"]["patches"]:
        assert patch["breaking_change_id"] in vd_bcs

    # Risk tier
    assert fixtures["risk-rank"]["risk_tier"] in {"safe", "merge-with-patch", "do-not-merge"}
