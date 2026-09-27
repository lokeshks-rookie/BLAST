# Blast Radius — Operational Tools & Phase 10 Harness

This directory contains verification, ingestion, and validation tools used for
live integration runs with IBM Bob 2.0 and pipeline orchestration.

---

## Tools Overview

| Tool | Purpose | When to Use |
|------|---------|-------------|
| [`pre_run_checklist.py`](file:///d:/BOB%202.0/tools/pre_run_checklist.py) | Validates all 74+ local checks (files, dirs, schemas, git state, credentials, unit tests) | **Before** starting any Bob run (Zero coin spend) |
| [`validate_bob_output.py`](file:///d:/BOB%202.0/tools/validate_bob_output.py) | Validates raw subagent JSON files against Phase 3 JSON Schemas | **After** Bob subagent runs complete |
| [`ingest_bob_output.py`](file:///d:/BOB%202.0/tools/ingest_bob_output.py) | Ingests text/markdown from Bob, extracts JSON, validates, and saves to `evidence/<subagent>/` | During or immediately after running each Bob subagent |

---

## Phase 10 Step-by-Step Live Bob Execution Guide

### 1. Pre-Run Sanity (Costs 0 Coins)
```bash
python tools/pre_run_checklist.py
```
Ensure all required checks pass with 0 failures before opening Bob.

### 2. Prepare the Staged Diff & Repository
- Target Repository: `lokeshks-rookie/BLAST`
- Demo Manifest: `fixtures/demo-repo/package.json` with `axios: ^1.7.2` bump.
- Call Site: `fixtures/demo-repo/src/api/client.js` with `axios.create({ auth: credentials })`.
- Ensure `.bob/custom_modes.yaml` and `.bob/skills/` are loaded in Bob.

### 3. Run Bob Subagents in `blast-radius` Mode
Run the 5 subagents in order:
1. **version-diff**: Extracts breaking change `BC-001` (auth signature change) and version delta `1.4.0 -> 1.7.2`.
2. **vuln-lookup**: Queries OSV/GHSA for `CVE-2023-45857` (closed) and verifies no new CVEs.
3. **usage-impact**: Analyzes call sites in `src/api/client.js` and assesses exposure.
4. **fix-verify**: Emits unified diff patch converting string `auth` to `{ username, password }`.
5. **risk-rank**: Combines evidence and emits verdict: `merge-with-patch` (confidence 0.87).

> [!IMPORTANT]
> **Capture Screenshots As You Go!**
> Take screenshots of Bob's task session summaries, thinking steps, and tool invocations.
> Save them directly into `bob_sessions/lokesh/` for the required hackathon deliverable.

### 4. Ingest and Validate Bob Output
Use `ingest_bob_output.py` to parse and validate outputs:
```bash
python tools/ingest_bob_output.py --subagent version-diff --input <file_or_paste>
python tools/ingest_bob_output.py --subagent vuln-lookup --input <file_or_paste>
python tools/ingest_bob_output.py --subagent usage-impact --input <file_or_paste>
python tools/ingest_bob_output.py --subagent fix-verify --input <file_or_paste>
python tools/ingest_bob_output.py --subagent risk-rank --input <file_or_paste>
```

Or validate all outputs in the evidence directory:
```bash
python tools/validate_bob_output.py --dir evidence/ --strict
```

### 5. Run the Orchestrator on Real Evidence
```bash
python orchestrator/merge.py --fixtures-dir evidence/
```
Verify `evidence/verdict.json` and `evidence/verdict.md` are produced with the expected `merge-with-patch` tier.
