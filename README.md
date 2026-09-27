# Blast Radius

### An evidence-grounded dependency and configuration risk reviewer, built on IBM Bob 2.0

**Team: Import Claude — IBM Bob 2.0 Hackathon (LabLab AI, Sept 25–27, 2026)**

---

## Problem

Dependency and configuration manifest changes — version bumps in `package.json`,
`requirements.txt`, `go.mod`, `Dockerfile` base image tags, CI pipeline YAMLs —
look trivial in a PR but carry **high blast radius**. Reviewing them properly requires:

1. Reading changelogs for breaking API changes
2. Cross-referencing against vulnerability databases (CVEs closed/introduced)
3. Checking whether changed API surfaces are actually called in the codebase
4. Proposing and verifying a mechanical fix if one exists
5. Generating a risk-tier verdict the reviewer can act on in under 30 seconds

This takes **15–20 minutes per bump** done properly. Teams approve on trust
instead of evidence, and vulnerabilities slip through.

---

## Solution

**Blast Radius** is a custom IBM Bob 2.0 mode that triggers automatically on
manifest diffs and produces a single **risk-tiered, evidence-backed verdict**
per change — delivered as a PR comment, spoken aloud via voice, and gated
by an explicit developer confirmation before any patch is applied or pushed.

---

## Architecture

```
                         ┌─────────────────────────┐
   PR opened / updated → │  GitHub webhook trigger  │
   (manifest touched)    └───────────┬─────────────┘
                                      ▼
                         ┌─────────────────────────┐
                         │   Bob Orchestrator Mode   │
                         │  (.bob/custom_modes.yaml) │
                         └───────────┬─────────────┘
                                      │  5 subagents dispatched in parallel
        ┌──────────────┬──────────────┼──────────────┬──────────────┐
        ▼              ▼              ▼              ▼              ▼
  Version-Diff   Vulnerability   Usage-Impact    Fix-Verify     Risk-Ranking
   Subagent        Subagent        Subagent       Subagent       Subagent
  (changelog)    (OSV/GHSA)     (call sites)  (patch + test)  (watsonx.ai)
        └──────────────┴──────────────┼──────────────┴──────────────┘
                                      ▼
                         ┌─────────────────────────┐
                         │   orchestrator/merge.py   │
                         │  risk-tiered verdict +    │
                         │  evidence + suggested fix │
                         └───────────┬─────────────┘
                          ┌──────────┼──────────┐
                          ▼          ▼          ▼
                     PR Comment  Voice TTS   Auto-Push
                     (GitHub)   (Bhashini) (git + banner)
```

### Voice Layer

Mic input → **Bhashini STT** → text → Bob Shell (non-interactive) →
Bob output → **Bhashini TTS** → spoken back.

Four use cases: risk verdict spoken aloud, voice confirmation of patch
application, periodic progress updates, and spoken intent checks for long runs.
Multilingual — developers can dictate in regional Indian languages.

---

## Before / After

| | Manual Review | Blast Radius |
|---|---|---|
| Time per bump | ~15–45 min manual review | **1.32 s** end-to-end automated rehearsal (~2,000x faster) |
| Evidence quality | Trust-based | CVE + changelog + call-site grounded |
| Confirmation mode | Review + click | Voice ("confirm") or CLI, your choice |
| Commit message | Generic ("bump axios") | Risk-aware ("fix: patch axios 1.4→1.7, closes CVE-2023-45857") |

---

## Demo Video

*Recorded demo demonstrating end-to-end webhook trigger, subagent execution, spoken verdict narration, voice confirmation, scratch-branch test verification, and automated risk-aware git push.*

---

## Repository Structure

```
.bob/
  custom_modes.yaml          # Blast Radius mode definition
  skills/                    # 5 subagent skill files (version-diff, vuln-lookup,
  │  version-diff/           #   usage-impact, fix-verify, risk-rank)
  │  vuln-lookup/
  │  usage-impact/
  │  fix-verify/
  │  risk-rank/
  rules-blast-radius/        # Orchestration rules (propose-confirm-execute, push gating)

orchestrator/
  merge.py                   # Reconciles 5 subagent outputs → risk-tier verdict
  post_comment.py            # Posts verdict as GitHub PR comment (idempotent)
  fix_verify.py              # Confirm → scratch branch → apply patch → rerun tests
  auto_push.py               # Risk-aware commit message + branch/repo banner + push gate
  pipeline.py                # Full end-to-end rehearsal pipeline runner with stopwatch metrics

tools/
  pre_run_checklist.py       # Zero-coin pre-run validator (74 automated checks)
  validate_bob_output.py     # Real Bob JSON schema validator with decision tree
  ingest_bob_output.py       # Raw response fence stripper and schema normalizer
  README.md                  # Operational guide for live Bob runs and budget rules

voice/
  bridge.py                  # Bhashini STT/TTS bridge (all 4 voice use cases)

.github/workflows/
  blast-radius.yml           # GitHub Action: PR webhook → Bob → comment

fixtures/
  schemas/                   # JSON Schemas for all 5 subagent contracts
  *.json                     # Mock fixtures (demo case: axios 1.4.0 → 1.7.2, CVE-2023-45857)
  demo-repo/                 # Target demo app for fix-verify test rerun

evidence/
  version-diff/              # Real subagent run output (populated in Phase 10)
  vuln-lookup/
  usage-impact/
  fix-verify/
  risk-rank/
  fix_verification.json      # Patch apply + scratch test rerun execution report
  verdict.json               # Orchestrator merged verdict
  verdict.md                 # Human-readable PR comment verdict

bob_sessions/
  lokesh/                    # Bob task-session screenshots (required deliverable)
  teammate/

tests/                       # 83 unit & integration tests — 100% passing
SUBMISSION.md                # Standalone written deliverables for judges
```

---

## Setup

```bash
python -m venv .venv
source .venv/bin/activate     # Linux/Mac
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
cp .env.example .env          # Optional: BHASHINI_API_KEY, GITHUB_TOKEN, etc.
```

### Run all tests

```bash
pytest -v
# Expected: 83 passed
```

### Run the end-to-end rehearsal pipeline

```bash
python orchestrator/pipeline.py --dry-run
```

### Run the orchestrator against fixtures or evidence

```bash
python orchestrator/merge.py --fixtures-dir fixtures/ --output-json evidence/verdict.json
```

### Run the pre-run checklist (zero coin spend)

```bash
python tools/pre_run_checklist.py
```

### Test the voice bridge (dry run — no credentials needed)

```bash
python voice/bridge.py --mode roundtrip --dry-run
```

### Preview the push banner and risk-aware commit message

```bash
python orchestrator/auto_push.py --mode banner
python orchestrator/auto_push.py --mode commit-msg
```

---

## Judges — Start Here

See [`SUBMISSION.md`](SUBMISSION.md) for the two required written deliverables:
the problem/solution statement and the statement on how IBM Bob 2.0 was used.
