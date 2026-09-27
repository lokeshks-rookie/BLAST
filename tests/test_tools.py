"""Blast Radius — Unit tests for Phase 10 tools: validate_bob_output & ingest_bob_output."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.ingest_bob_output import (
    extract_json_payload,
    validate_against_schema,
    ingest,
    VALID_SUBAGENTS,
)
from tools.validate_bob_output import (
    load_schema,
    validate_file,
    scan_and_validate,
    SUBAGENT_SCHEMA_MAP,
)

ROOT = Path(__file__).resolve().parent.parent


def test_subagent_schema_map_all_exist():
    for name, schema_path in SUBAGENT_SCHEMA_MAP.items():
        assert schema_path.is_file(), f"Missing schema for {name}: {schema_path}"
        schema = load_schema(schema_path)
        assert isinstance(schema, dict)
        assert "$schema" in schema or "type" in schema


def test_validate_file_valid_fixture():
    fixture_path = ROOT / "fixtures" / "version-diff.json"
    schema_path = SUBAGENT_SCHEMA_MAP["version-diff"]
    schema = load_schema(schema_path)
    passed, err = validate_file(fixture_path, schema)
    assert passed is True
    assert err == ""


def test_validate_file_invalid_json(tmp_path):
    bad_json = tmp_path / "bad.json"
    bad_json.write_text("{ broken json", encoding="utf-8")
    schema = load_schema(SUBAGENT_SCHEMA_MAP["version-diff"])
    passed, err = validate_file(bad_json, schema)
    assert passed is False
    assert "Invalid JSON" in err


def test_validate_file_schema_mismatch(tmp_path):
    mismatch_json = tmp_path / "mismatch.json"
    mismatch_json.write_text(json.dumps({"wrong": "data"}), encoding="utf-8")
    schema = load_schema(SUBAGENT_SCHEMA_MAP["version-diff"])
    passed, err = validate_file(mismatch_json, schema)
    assert passed is False
    assert err != ""


def test_extract_json_payload_pure_json():
    data = {"hello": "world", "num": 42}
    raw = json.dumps(data)
    extracted = extract_json_payload(raw)
    assert extracted == data


def test_extract_json_payload_markdown_fences():
    data = {"package_name": "axios", "version": "1.7.2"}
    raw = f"""Here is the subagent analysis:
```json
{json.dumps(data, indent=2)}
```
Hope this helps!"""
    extracted = extract_json_payload(raw)
    assert extracted == data


def test_extract_json_payload_embedded():
    data = {"status": "ok"}
    raw = f"Prefix commentary {json.dumps(data)} trailing text."
    extracted = extract_json_payload(raw)
    assert extracted == data


def test_extract_json_payload_failure():
    with pytest.raises(ValueError):
        extract_json_payload("No json anywhere here!")


def test_validate_against_schema_all_fixtures():
    for subagent in VALID_SUBAGENTS:
        fixture_file = ROOT / "fixtures" / f"{subagent}.json"
        assert fixture_file.is_file(), f"Missing fixture {fixture_file}"
        with open(fixture_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        passed, err = validate_against_schema(subagent, data)
        assert passed is True, f"Fixture {subagent} failed validation: {err}"


def test_ingest_roundtrip(tmp_path):
    fixture_file = ROOT / "fixtures" / "vuln-lookup.json"
    raw_content = fixture_file.read_text(encoding="utf-8")
    wrapped_content = f"Bob output:\n```json\n{raw_content}\n```\nSession complete."

    dest = tmp_path / "output.json"
    success = ingest("vuln-lookup", wrapped_content, dest)
    assert success is True
    assert dest.is_file()

    with open(dest, "r", encoding="utf-8") as f:
        saved_data = json.load(f)
    assert saved_data["package_name"] == "axios"
