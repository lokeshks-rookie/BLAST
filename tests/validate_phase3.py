"""Validate Phase 3 fixtures against JSON Schemas and cross-reference integrity."""
import json
import os
import sys
import jsonschema

FIXTURES_DIR = "fixtures"
SCHEMAS_DIR = os.path.join(FIXTURES_DIR, "schemas")

subagents = [
    "version-diff",
    "vuln-lookup",
    "usage-impact",
    "fix-verify",
    "risk-rank"
]

print("=== 1. Validating Fixtures Against JSON Schemas ===")
fixtures = {}
schemas = {}
all_passed = True

for subagent in subagents:
    schema_path = os.path.join(SCHEMAS_DIR, f"{subagent}.schema.json")
    fixture_path = os.path.join(FIXTURES_DIR, f"{subagent}.json")

    if not os.path.exists(schema_path):
        print(f"  FAIL: Missing schema {schema_path}")
        all_passed = False
        continue

    if not os.path.exists(fixture_path):
        print(f"  FAIL: Missing fixture {fixture_path}")
        all_passed = False
        continue

    with open(schema_path, "r", encoding="utf-8") as f:
        schema = json.load(f)
        schemas[subagent] = schema

    with open(fixture_path, "r", encoding="utf-8") as f:
        fixture = json.load(f)
        fixtures[subagent] = fixture

    try:
        jsonschema.validate(instance=fixture, schema=schema)
        print(f"  OK: {subagent}.json conforms strictly to {subagent}.schema.json")
    except jsonschema.ValidationError as e:
        print(f"  FAIL: {subagent}.json schema validation error: {e.message}")
        all_passed = False
    except jsonschema.SchemaError as e:
        print(f"  FAIL: {subagent}.schema.json schema definition error: {e.message}")
        all_passed = False

print("\n=== 2. Cross-Fixture Integrity Checks ===")

# Package name & ecosystem consistency
pkgs = {s: fixtures[s].get("package_name") for s in subagents if s in fixtures}
ecos = {s: fixtures[s].get("ecosystem") for s in subagents if s in fixtures}

if len(set(pkgs.values())) == 1 and list(pkgs.values())[0] == "axios":
    print(f"  OK: Package name uniform across all fixtures: {list(pkgs.values())[0]}")
else:
    print(f"  FAIL: Inconsistent package names: {pkgs}")
    all_passed = False

if len(set(ecos.values())) == 1 and list(ecos.values())[0] == "npm":
    print(f"  OK: Ecosystem uniform across all fixtures: {list(ecos.values())[0]}")
else:
    print(f"  FAIL: Inconsistent ecosystems: {ecos}")
    all_passed = False

# Version continuity
vd = fixtures.get("version-diff", {})
vl = fixtures.get("vuln-lookup", {})
rr = fixtures.get("risk-rank", {})
fv = fixtures.get("fix-verify", {})

if vd.get("old_version") == vl.get("old_version") == rr.get("old_version") == "1.4.0":
    print("  OK: Old version uniform (1.4.0)")
else:
    print("  FAIL: Old versions mismatch")
    all_passed = False

if vd.get("new_version") == vl.get("new_version") == rr.get("new_version") == fv.get("new_version") == "1.7.2":
    print("  OK: New version uniform (1.7.2)")
else:
    print("  FAIL: New versions mismatch")
    all_passed = False

# Breaking change ID link
vd_bc_ids = [bc["id"] for bc in vd.get("breaking_changes", [])]
ui_bc_ids = [ir["breaking_change_id"] for ir in fixtures.get("usage-impact", {}).get("impact_results", [])]
fv_bc_ids = [p["breaking_change_id"] for p in fv.get("patches", [])]

if ui_bc_ids and all(uid in vd_bc_ids for uid in ui_bc_ids):
    print(f"  OK: usage-impact breaking_change_ids {ui_bc_ids} exist in version-diff {vd_bc_ids}")
else:
    print("  FAIL: usage-impact references unlisted breaking change")
    all_passed = False

if fv_bc_ids and all(fid in vd_bc_ids for fid in fv_bc_ids):
    print(f"  OK: fix-verify breaking_change_ids {fv_bc_ids} exist in version-diff {vd_bc_ids}")
else:
    print("  FAIL: fix-verify references unlisted breaking change")
    all_passed = False

# Risk Tier Valid
valid_tiers = {"safe", "merge-with-patch", "do-not-merge"}
tier = rr.get("risk_tier")
if tier in valid_tiers:
    print(f"  OK: risk_tier '{tier}' is valid")
else:
    print(f"  FAIL: risk_tier '{tier}' invalid")
    all_passed = False

print("\n=== 3. Secrets Scan on fixtures/ ===")
import re
secret_patterns = [
    r'API_KEY\s*=\s*[\'"][^\'"]+[\'"]',
    r'TOKEN\s*=\s*[\'"][^\'"]+[\'"]',
    r'SECRET\s*=\s*[\'"][^\'"]+[\'"]',
    r'PASSWORD\s*=\s*[\'"][^\'"]+[\'"]',
    r'ghp_[A-Za-z0-9]{30,}',
    r'gho_[A-Za-z0-9]{30,}',
    r'\bsk-[A-Za-z0-9]{20,}'
]
found_secret = False
for root, _, files in os.walk(FIXTURES_DIR):
    for fname in files:
        fpath = os.path.join(root, fname)
        with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
            for line_no, line in enumerate(f, 1):
                for pat in secret_patterns:
                    if re.search(pat, line):
                        print(f"  FAIL: Possible secret match '{pat}' in {fpath}:{line_no}")
                        found_secret = True
                        all_passed = False

if not found_secret:
    print("  OK: Zero secrets found in fixtures/")

if all_passed:
    print("\n=== ALL PHASE 3 CHECKS PASSED ===")
    sys.exit(0)
else:
    print("\n=== PHASE 3 VALIDATION FAILED ===")
    sys.exit(1)
