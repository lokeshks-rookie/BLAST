#!/usr/bin/env python3
"""Blast Radius — Phase 10 Subagent Output Ingestion & Normalizer.

When Bob executes a subagent (either via Bob Shell or Bob 2.0 IDE), this
tool ingests the output, extracts the JSON (handling markdown fences if present),
validates against the subagent's schema, and saves to evidence/<subagent>/output.json.

Usage:
    python tools/ingest_bob_output.py --subagent version-diff --input raw_output.txt
    python tools/ingest_bob_output.py --subagent vuln-lookup --json-string '{"package_name": ...}'
    python tools/ingest_bob_output.py --subagent fix-verify --input evidence/fix-verify/raw.json

Supported subagents:
    - version-diff
    - vuln-lookup
    - usage-impact
    - fix-verify
    - risk-rank
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

try:
    import jsonschema
except ImportError:
    print("[ERROR] jsonschema not installed. Run: pip install jsonschema")
    sys.exit(1)

ROOT = Path(__file__).resolve().parent.parent

VALID_SUBAGENTS = [
    "version-diff",
    "vuln-lookup",
    "usage-impact",
    "fix-verify",
    "risk-rank",
]


def extract_json_payload(raw_text: str) -> dict:
    """Extract valid JSON from raw text, handling markdown fences or leading/trailing commentary."""
    text = raw_text.strip()

    # Case 1: Pure JSON directly
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Case 2: Markdown code fence ```json ... ``` or ``` ... ```
    pattern = r"```(?:json)?\s*([\s\S]*?)\s*```"
    matches = re.findall(pattern, text, re.IGNORECASE)
    for block in matches:
        try:
            return json.loads(block.strip())
        except json.JSONDecodeError:
            continue

    # Case 3: Find outermost { ... }
    first_brace = text.find("{")
    last_brace = text.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        snippet = text[first_brace : last_brace + 1]
        try:
            return json.loads(snippet)
        except json.JSONDecodeError:
            pass

    raise ValueError("Could not locate or parse valid JSON in provided input.")


def validate_against_schema(subagent: str, data: dict) -> tuple[bool, str]:
    """Validate parsed JSON against the subagent schema."""
    schema_path = ROOT / "fixtures" / "schemas" / f"{subagent}.schema.json"
    if not schema_path.is_file():
        return False, f"Schema file not found: {schema_path}"

    with open(schema_path, "r", encoding="utf-8") as f:
        schema = json.load(f)

    try:
        jsonschema.validate(instance=data, schema=schema)
        return True, ""
    except jsonschema.ValidationError as err:
        return False, f"Field error at {list(err.path)}: {err.message}"
    except Exception as err:
        return False, f"Validation error: {err}"


def ingest(subagent: str, raw_input: str, output_path: Path | None = None) -> bool:
    """Ingest, validate, and save output for a subagent."""
    if subagent not in VALID_SUBAGENTS:
        print(f"[ERROR] Invalid subagent '{subagent}'. Must be one of: {VALID_SUBAGENTS}")
        return False

    print(f"\n── Ingesting output for subagent: {subagent} ─────────────")

    try:
        payload = extract_json_payload(raw_input)
    except Exception as e:
        print(f"  [FAIL] JSON parse error: {e}")
        return False

    passed, err = validate_against_schema(subagent, payload)
    if not passed:
        print(f"  [FAIL] Schema validation error: {err}")
        print("\n  Decision guidance:")
        print("  - If Bob omitted a required field: update .bob/skills/<subagent>/SKILL.md")
        print("  - If Bob used an alternate type/format: adapt orchestrator logic")
        print("  - Do not silently hand-edit Bob's output without adjusting contract.")
        return False

    print(f"  [PASS] Successfully validated against {subagent}.schema.json")

    # Determine destination
    dest = output_path
    if dest is None:
        target_dir = ROOT / "evidence" / subagent
        target_dir.mkdir(parents=True, exist_ok=True)
        dest = target_dir / "output.json"
    else:
        dest.parent.mkdir(parents=True, exist_ok=True)

    with open(dest, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    try:
        display_dest = dest.resolve().relative_to(ROOT)
    except ValueError:
        display_dest = dest.resolve()
    print(f"  [SAVED] Output saved to: {display_dest}")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest and validate Bob subagent outputs")
    parser.add_argument(
        "--subagent",
        required=True,
        choices=VALID_SUBAGENTS,
        help="Subagent name",
    )
    parser.add_argument(
        "--input",
        type=str,
        help="File path containing raw Bob output or JSON",
    )
    parser.add_argument(
        "--json-string",
        type=str,
        help="Direct JSON or raw text string",
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Target output file path (default: evidence/<subagent>/output.json)",
    )
    args = parser.parse_args()

    raw_text = ""
    if args.input:
        in_file = Path(args.input)
        if not in_file.is_file():
            print(f"[ERROR] Input file not found: {in_file}")
            sys.exit(1)
        raw_text = in_file.read_text(encoding="utf-8")
    elif args.json_string:
        raw_text = args.json_string
    else:
        print("[ERROR] Must provide either --input <file> or --json-string '<text>'")
        sys.exit(1)

    out_p = Path(args.output) if args.output else None
    ok = ingest(args.subagent, raw_text, out_p)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
