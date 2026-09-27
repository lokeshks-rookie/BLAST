# Blast Radius

### An evidence-grounded dependency and configuration risk reviewer, built on IBM Bob 2.0

**Team: Import Claude — IBM Bob 2.0 Hackathon (LabLab AI, Sept 25–27, 2026)**

---

## Problem

Dependency and configuration manifest changes (version bumps in `package.json`, `requirements.txt`, `go.mod`, `Dockerfile` base image tags, CI pipeline YAMLs) look trivial but carry high blast radius. Reviewing them properly requires:

1. Reading changelogs for breaking API changes
2. Cross-referencing against vulnerability databases (CVEs closed/introduced)
3. Checking whether changed API surfaces are actually called in the codebase

This takes 15–20 minutes per bump done properly. Teams approve on trust instead of evidence.

## Solution

**Blast Radius** is a custom IBM Bob 2.0 mode that triggers on manifest diffs and produces a single **risk-tiered, evidence-backed verdict** per change.

### Architecture

```
                         ┌─────────────────────────┐
   PR opened / updated → │  GitHub webhook trigger  │
   (manifest file touched)└───────────┬─────────────┘
                                       ▼
                         ┌─────────────────────────┐
                         │   Bob Orchestrator Mode   │
                         │   (.bob/custom_modes.yaml)│
                         └───────────┬─────────────┘
                                       │  dispatches in parallel
        ┌──────────────┬──────────────┼──────────────┬──────────────┐
        ▼              ▼              ▼              ▼              ▼
  Version-Diff   Vulnerability   Usage-Impact    Fix-Verify     Risk-Ranking
   Subagent        Subagent        Subagent       Subagent       Subagent
  (changelog)    (OSV/GHSA)     (call sites)    (patch+test)   (watsonx.ai)
        └──────────────┴──────────────┼──────────────┴──────────────┘
                                       ▼
                         ┌─────────────────────────┐
                         │   Merge & Report Step     │
                         │  risk-tiered verdict +    │
                         │  suggested patch           │
                         └───────────┬─────────────┘
                                       ▼
                         ┌─────────────────────────┐
                         │  Posted as a live PR      │
                         │  review comment + voice   │
                         └─────────────────────────┘
```

## Before/After Metric

| | Manual Review | Blast Radius |
|---|---|---|
| Time per bump | ~15–20 min | *TBD (Phase 11)* |
| Evidence quality | Trust-based | CVE + changelog + call-site grounded |

## Demo Video

*Link TBD*

---

## Repository Structure

```
.bob/                    # Bob 2.0 configuration
  custom_modes.yaml      # Blast Radius mode definition
  skills/                # 5 subagent skill definitions
  rules-blast-radius/    # Orchestration rules
voice/                   # Bhashini STT/TTS bridge
orchestrator/            # Merge & report engine
.github/workflows/       # GitHub Action for live PR integration
tests/                   # Unit and integration tests
fixtures/                # Mock data & JSON schemas
evidence/                # Bob task-session evidence
bob_sessions/            # Required deliverable — session summaries
```

## Setup

```bash
python -m venv .venv
source .venv/bin/activate     # Linux/Mac
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
cp .env.example .env          # Fill in your credentials
```
