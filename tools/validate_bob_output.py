#!/usr/bin/env python3
"""Blast Radius — Phase 10 Output Validator.

After Bob produces its five real subagent outputs, run this script to
validate each against its JSON Schema. Call this BEFORE running the
orchestrator against real output — catching schema mismatches here means
you can decide whether to patch the skill instruction or the orchestrator
without spending another Bobcoin.

Usage:
    python tools/validate_bob_output.py --dir evidence/

It will scan for any .json files in the five subagent evidence subfolders
and validate each against its corresponding schema.

Options:
    --dir DIR       Root directory to scan (default: evidence/)
    --strict        Exit with code 1 on any validation failure
    --save-report   Write a validation_report.json to the output dir
"""

from __future__ import annotations

import argparse
import json
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

SUBAGENT_SCHEMA_MAP = {
    "version-diff": ROOT / "fixtures" / "schemas" / "version-diff.schema.json",
    "vuln-lookup":  ROOT / "fixtures" / "schemas" / "vuln-lookup.schema.json",
    "usage-impact": ROOT / "fixtures" / "schemas" / "usage-impact.schema.json",
    "fix-verify":   ROOT / "fixtures" / "schemas" / "fix-verify.schema.json",
    "risk-rank":    ROOT / "fixtures" / "schemas" / "risk-rank.schema.json",
}


def load_schema(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def validate_file(json_path: Path, schema: dict) -> tuple[bool, str]:
    """Returns (passed, error_message)."""
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as err:
        return False, f"Invalid JSON: {err}"

    try:
        jsonschema.validate(data, schema)
        return True, ""
    except jsonschema.ValidationError as err:
        return False, f"{err.json_path}: {err.message}"
    except jsonschema.SchemaError as err:
        return False, f"Schema error: {err.message}"


def scan_and_validate(evidence_dir: Path) -> list[dict]:
    """Scan evidence_dir for real output JSON files and validate each."""
    report = []

    for subagent_name, schema_path in SUBAGENT_SCHEMA_MAP.items():
        subagent_dir = evidence_dir / subagent_name
        if not subagent_dir.is_dir():
            print(f"  [SKIP] {subagent_name}/ — directory not found")
            continue

        json_files = [f for f in subagent_dir.glob("*.json") if f.name != "README.md"]
        if not json_files:
            print(f"  [SKIP] {subagent_name}/ — no .json files yet (Phase 10 output goes here)")
            continue

        schema = load_schema(schema_path)
        for json_file in sorted(json_files):
            passed, err = validate_file(json_file, schema)
            status = "[PASS]" if passed else "[FAIL]"
            rel = json_file.relative_to(evidence_dir.parent)
            msg = f"  {status}  {rel}"
            if not passed:
                msg += f"\n         {err}"
            print(msg)
            report.append({
                "subagent": subagent_name,
                "file": str(json_file),
                "passed": passed,
                "error": err,
            })

    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate Bob real output against JSON Schemas")
    parser.add_argument("--dir", default="evidence", help="Evidence directory to scan")
    parser.add_argument("--strict", action="store_true", help="Exit 1 on any failure")
    parser.add_argument("--save-report", action="store_true",
                        help="Save validation_report.json to evidence dir")
    args = parser.parse_args()

    evidence_dir = ROOT / args.dir
    if not evidence_dir.is_dir():
        print(f"[ERROR] Evidence directory not found: {evidence_dir}")
        sys.exit(1)

    print(f"\n── Blast Radius — Bob Output Validator ─────────────────────────")
    print(f"   Scanning: {evidence_dir}")
    print(f"   Schemas:  {ROOT / 'fixtures' / 'schemas'}\n")

    report = scan_and_validate(evidence_dir)

    if not report:
        print("\n  [INFO] No real Bob output found yet.")
        print("         Run the live Bob integration (Phase 10), then drop the")
        print("         five subagent JSON outputs into evidence/<subagent-name>/")
        print("         and re-run this validator.\n")
        sys.exit(0)

    passed = sum(1 for r in report if r["passed"])
    failed = sum(1 for r in report if not r["passed"])
    total = len(report)

    print(f"\n── SUMMARY ─────────────────────────────────────────────────────")
    print(f"  {passed}/{total} outputs valid  |  {failed} failures\n")

    if failed > 0:
        print("  Mismatch decision tree:")
        print("  1. If the field is missing from Bob's output but the schema requires it:")
        print("     → Update the SKILL.md instruction to explicitly request that field.")
        print("  2. If the field is present but has the wrong type/format:")
        print("     → Update the orchestrator to coerce or accept the actual type.")
        print("  3. If the schema is wrong (over-specified):")
        print("     → Relax the schema constraint and document why.")
        print("  Never silently hand-edit Bob's output to force a fit.\n")

    if args.save_report:
        report_path = evidence_dir / "validation_report.json"
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        print(f"  Report saved: {report_path}\n")

    if args.strict and failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
