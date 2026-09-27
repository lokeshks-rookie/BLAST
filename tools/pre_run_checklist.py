#!/usr/bin/env python3
"""Blast Radius — Phase 10 Pre-Run Checklist.

Run this script BEFORE starting the Bob live run to confirm everything is
ready. It costs zero Bobcoins — it only validates the local scaffolding.

Usage:
    python tools/pre_run_checklist.py

All checks must PASS before opening Bob and spending a coin.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parent.parent

PASS = "[PASS]"
FAIL = "[FAIL]"
WARN = "[WARN]"
SKIP = "[SKIP]"

results: list[tuple[str, str]] = []


def check(label: str, passed: bool, detail: str = "", warn_only: bool = False) -> bool:
    tag = PASS if passed else (WARN if warn_only else FAIL)
    msg = f"{tag}  {label}"
    if detail:
        msg += f"\n       {detail}"
    print(msg)
    results.append((tag, label))
    return passed


# ---------------------------------------------------------------------------
# 1. Required directory structure
# ---------------------------------------------------------------------------
print("\n── STRUCTURE ──────────────────────────────────────────────────")

REQUIRED_DIRS = [
    ".bob",
    ".bob/skills/version-diff",
    ".bob/skills/vuln-lookup",
    ".bob/skills/usage-impact",
    ".bob/skills/fix-verify",
    ".bob/skills/risk-rank",
    ".bob/rules-blast-radius",
    "orchestrator",
    "voice",
    "fixtures",
    "fixtures/schemas",
    "evidence",
    "evidence/version-diff",
    "evidence/vuln-lookup",
    "evidence/usage-impact",
    "evidence/fix-verify",
    "evidence/risk-rank",
    "bob_sessions",
    "bob_sessions/lokesh",
    ".github/workflows",
    "tests",
]

for d in REQUIRED_DIRS:
    check(f"dir exists: {d}", (ROOT / d).is_dir())

REQUIRED_FILES = [
    ".bob/custom_modes.yaml",
    ".bob/rules-blast-radius/RULES.md",
    ".bob/skills/version-diff/SKILL.md",
    ".bob/skills/vuln-lookup/SKILL.md",
    ".bob/skills/usage-impact/SKILL.md",
    ".bob/skills/fix-verify/SKILL.md",
    ".bob/skills/risk-rank/SKILL.md",
    "orchestrator/merge.py",
    "orchestrator/post_comment.py",
    "orchestrator/fix_verify.py",
    "orchestrator/auto_push.py",
    "voice/bridge.py",
    ".github/workflows/blast-radius.yml",
    "fixtures/version-diff.json",
    "fixtures/vuln-lookup.json",
    "fixtures/usage-impact.json",
    "fixtures/fix-verify.json",
    "fixtures/risk-rank.json",
    "fixtures/schemas/version-diff.schema.json",
    "fixtures/schemas/vuln-lookup.schema.json",
    "fixtures/schemas/usage-impact.schema.json",
    "fixtures/schemas/fix-verify.schema.json",
    "fixtures/schemas/risk-rank.schema.json",
    "SUBMISSION.md",
    "README.md",
    "PLAN.md",
]

for f in REQUIRED_FILES:
    check(f"file exists: {f}", (ROOT / f).is_file())

# ---------------------------------------------------------------------------
# 2. All unit tests pass
# ---------------------------------------------------------------------------
print("\n── UNIT TESTS ─────────────────────────────────────────────────")

proc = subprocess.run(
    [sys.executable, "-m", "pytest", "--tb=no", "-q"],
    cwd=ROOT,
    capture_output=True,
    text=True,
)
test_output = (proc.stdout + proc.stderr).strip()
passed_line = [l for l in test_output.splitlines() if "passed" in l]
passed_summary = passed_line[-1] if passed_line else test_output[-200:]
check("pytest suite passes", proc.returncode == 0, detail=passed_summary)

# ---------------------------------------------------------------------------
# 3. JSON Schemas are valid JSON
# ---------------------------------------------------------------------------
print("\n── SCHEMA VALIDITY ─────────────────────────────────────────────")

SCHEMA_DIR = ROOT / "fixtures" / "schemas"
for schema_file in sorted(SCHEMA_DIR.glob("*.schema.json")):
    try:
        with open(schema_file, "r", encoding="utf-8") as f:
            json.load(f)
        check(f"valid JSON: {schema_file.name}", True)
    except json.JSONDecodeError as err:
        check(f"valid JSON: {schema_file.name}", False, detail=str(err))

# ---------------------------------------------------------------------------
# 4. Mock fixtures validate against their own schemas
# ---------------------------------------------------------------------------
print("\n── FIXTURE VALIDATION ──────────────────────────────────────────")

try:
    import jsonschema
    JSONSCHEMA_OK = True
except ImportError:
    JSONSCHEMA_OK = False
    check("jsonschema package available", False,
          detail="pip install jsonschema", warn_only=True)

if JSONSCHEMA_OK:
    fixture_map = {
        "version-diff": ROOT / "fixtures" / "version-diff.json",
        "vuln-lookup": ROOT / "fixtures" / "vuln-lookup.json",
        "usage-impact": ROOT / "fixtures" / "usage-impact.json",
        "fix-verify": ROOT / "fixtures" / "fix-verify.json",
        "risk-rank": ROOT / "fixtures" / "risk-rank.json",
    }
    for name, fixture_path in fixture_map.items():
        schema_path = ROOT / "fixtures" / "schemas" / f"{name}.schema.json"
        try:
            with open(fixture_path, "r", encoding="utf-8") as f:
                fixture = json.load(f)
            with open(schema_path, "r", encoding="utf-8") as f:
                schema = json.load(f)
            jsonschema.validate(fixture, schema)
            check(f"fixture validates: {name}", True)
        except jsonschema.ValidationError as err:
            check(f"fixture validates: {name}", False, detail=err.message)
        except Exception as err:
            check(f"fixture validates: {name}", False, detail=str(err))

# ---------------------------------------------------------------------------
# 5. .env credentials check (keys present, never values printed)
# ---------------------------------------------------------------------------
print("\n── CREDENTIALS (.env) ──────────────────────────────────────────")

env_file = ROOT / ".env"
env_example = ROOT / ".env.example"

check(".env file exists", env_file.is_file(),
      detail="Copy .env.example to .env and fill in your credentials")

if env_file.is_file():
    from dotenv import load_dotenv
    load_dotenv(env_file)

    VOICE_ENVS = [
        ("BHASHINI_API_KEY", "Bhashini STT/TTS voice bridge (text fallback if empty)"),
        ("BHASHINI_STT_ENDPOINT", "Bhashini STT endpoint (text fallback if empty)"),
        ("BHASHINI_TTS_ENDPOINT", "Bhashini TTS endpoint (text fallback if empty)"),
    ]
    OPTIONAL_ENVS = [
        ("GITHUB_TOKEN", "GitHub PR comment posting"),
        ("BOB_SHELL_PATH", "Bob Shell non-interactive mode (Phase 10 wiring)"),
    ]

    for key, purpose in VOICE_ENVS:
        val = os.getenv(key, "")
        present = bool(val and val != f"your_{key.lower()}_here")
        check(f"env set: {key} ({purpose})", present,
              detail="Set in .env for live voice; text-only fallback used if omitted" if not present else "",
              warn_only=True)

    for key, purpose in OPTIONAL_ENVS:
        val = os.getenv(key, "")
        present = bool(val and not val.startswith("your_"))
        check(f"env set: {key} ({purpose})", present,
              detail="Optional — set if available", warn_only=True)

# ---------------------------------------------------------------------------
# 6. Git repo state
# ---------------------------------------------------------------------------
print("\n── GIT STATE ───────────────────────────────────────────────────")

# Current branch
branch_proc = subprocess.run(
    ["git", "rev-parse", "--abbrev-ref", "HEAD"],
    cwd=ROOT, capture_output=True, text=True,
)
branch = branch_proc.stdout.strip()
check("git repo responsive", branch_proc.returncode == 0, detail=branch)

# No uncommitted changes
status_proc = subprocess.run(
    ["git", "status", "--porcelain"],
    cwd=ROOT, capture_output=True, text=True,
)
clean = status_proc.stdout.strip() == ""
check("working tree clean (no uncommitted changes)", clean,
      detail=status_proc.stdout.strip()[:200] if not clean else "",
      warn_only=True)

# Remote is reachable
remote_proc = subprocess.run(
    ["git", "remote", "get-url", "origin"],
    cwd=ROOT, capture_output=True, text=True,
)
remote_url = remote_proc.stdout.strip()
check("origin remote configured", bool(remote_url), detail=remote_url)

# Secrets scan — look for common key patterns in tracked files
print("\n── SECRETS SCAN (tracked files only) ──────────────────────────")
PATTERNS = [
    ("hardcoded API key pattern", r"AKIA[0-9A-Z]{16}"),    # AWS key
    ("private key header", r"BEGIN (RSA|EC|PRIVATE) KEY"),
    ("Bhashini key literal", r"blt_[a-zA-Z0-9]{20,}"),     # generic token pattern
]
grep_proc = subprocess.run(
    ["git", "grep", "-rn", "-E",
     "|".join(p for _, p in PATTERNS),
     "--", ":(exclude).env", ":(exclude).env.example"],
    cwd=ROOT, capture_output=True, text=True,
)
secrets_found = grep_proc.stdout.strip()
check("no hardcoded secrets in tracked files",
      not bool(secrets_found),
      detail=secrets_found[:400] if secrets_found else "")

# ---------------------------------------------------------------------------
# 7. Bob config completeness
# ---------------------------------------------------------------------------
print("\n── BOB CONFIG ──────────────────────────────────────────────────")

custom_modes = ROOT / ".bob" / "custom_modes.yaml"
if custom_modes.is_file():
    content = custom_modes.read_text(encoding="utf-8")
    check("custom_modes.yaml references blast-radius mode", "blast-radius" in content)
    check("custom_modes.yaml references all 5 skills",
          all(s in content for s in
              ["version-diff", "vuln-lookup", "usage-impact", "fix-verify", "risk-rank"]))

rules_md = ROOT / ".bob" / "rules-blast-radius" / "RULES.md"
if rules_md.is_file():
    rules_content = rules_md.read_text(encoding="utf-8")
    check("RULES.md contains propose-confirm-execute gate",
          any(kw in rules_content.lower() for kw in ["confirm", "propose", "explicit"]))
    check("RULES.md contains push gating rule",
          any(kw in rules_content.lower() for kw in ["push", "branch", "remote"]))

# ---------------------------------------------------------------------------
# 8. Demo diff / staged change is loadable
# ---------------------------------------------------------------------------
print("\n── DEMO DIFF ───────────────────────────────────────────────────")

demo_pkg = ROOT / "fixtures" / "demo-repo" / "package.json"
if demo_pkg.is_file():
    with open(demo_pkg, "r", encoding="utf-8") as f:
        pkg = json.load(f)
    axios_version = pkg.get("dependencies", {}).get("axios", "(not found)")
    check("demo-repo/package.json has axios dependency", "axios" in pkg.get("dependencies", {}),
          detail=f"Current version in fixture: {axios_version}")

fix_verify_fixture = ROOT / "fixtures" / "fix-verify.json"
if fix_verify_fixture.is_file():
    with open(fix_verify_fixture, "r", encoding="utf-8") as f:
        fv = json.load(f)
    patches = fv.get("patches", [])
    has_diff = any(p.get("diff") for p in patches)
    check("fix-verify fixture has unified diff", has_diff,
          detail="Diff content present for patch application")

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
print("\n── SUMMARY ─────────────────────────────────────────────────────")
total = len(results)
passed = sum(1 for tag, _ in results if tag == PASS)
warned = sum(1 for tag, _ in results if tag == WARN)
failed = sum(1 for tag, _ in results if tag == FAIL)

print(f"\n  {passed}/{total} checks passed  |  {warned} warnings  |  {failed} failures\n")

if failed == 0:
    print("  ✅  ALL REQUIRED CHECKS PASSED — safe to start the Bob live run.")
    print("  ⚠️   Check any warnings above before spending a Bobcoin.\n")
    print("  Bobcoin budget reminder: 40 coins total for the whole team.")
    print("  Screenshot Bob's task session summary AS YOU GO — not afterward.\n")
else:
    print(f"  🚫  {failed} FAILURE(S) — fix these before opening Bob.\n")
    failing = [label for tag, label in results if tag == FAIL]
    for label in failing:
        print(f"     - {label}")
    print()

sys.exit(0 if failed == 0 else 1)
