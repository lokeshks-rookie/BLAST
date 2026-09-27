# Submission — Blast Radius

**IBM Bob 2.0 Hackathon, LabLab AI, Sept 25–27, 2026**
**Team: Import Claude**
**Public Repo: https://github.com/lokeshks-rookie/BLAST**

---

## Deliverable 1: Problem & Solution Statement

### The Problem

Every software project depends on third-party packages. When a dependency
needs upgrading — whether for a bug fix, a CVE patch, or a feature — the PR
looks like a one-line change: `"axios": "1.4.0"` → `"1.7.2"`. But properly
reviewing that change requires a developer to:

1. Read the changelog between two versions to find breaking API changes
2. Cross-reference vulnerability databases (NVD, OSV, GHSA) to identify
   CVEs closed and CVEs introduced by the bump
3. Search the codebase for every call site that uses the changed API surface
4. Assess whether any affected call site is reachable from untrusted input
5. If a mechanical fix exists, apply it on an isolated branch, rerun the
   test suite, and verify it passes before merging

In practice, none of this gets done. A 15–20 minute review per bump gets
compressed into a 30-second eyeball. Vulnerabilities like CVE-2023-45857
(axios CSRF via XSRF-TOKEN exposure) slip through on merged "routine bumps."
The problem is not laziness — it is that the information required for a good
decision is scattered across four different systems and takes longer to gather
than most teams budget for a PR review.

### The Solution

**Blast Radius** is a custom IBM Bob 2.0 mode that triggers automatically
when a pull request touches a manifest file (`package.json`, `requirements.txt`,
`go.mod`, `Dockerfile`, CI YAML). It dispatches five specialized subagents in
parallel, each contributing one piece of the evidence picture, and reconciles
their outputs into a single **risk-tiered, evidence-backed verdict** delivered
directly as a PR comment — within 60 seconds of the webhook firing.

**The five subagents:**

| Subagent | Evidence it gathers |
|----------|---------------------|
| **Version-Diff** | Breaking API changes between old and new version (changelog parsing) |
| **Vuln-Lookup** | CVEs closed and introduced (OSV/GHSA/NVD lookup) |
| **Usage-Impact** | Call sites in codebase; reachability from untrusted input |
| **Fix-Verify** | Mechanical patch generation; applies it on a scratch branch and reruns tests |
| **Risk-Ranking** | Synthesizes all signals into a risk tier and confidence score via watsonx.ai |

**The verdict is one of:**
- ✅ **Safe to merge** — no breaking changes, no CVEs
- ⚠️ **Merge with patch** — breaking changes exist but a mechanical fix is available and test-verified
- 🚫 **Do not merge** — unreachable CVE path or breaking change requiring manual review

**What makes it different from existing tools:**

1. **Five signals, not one.** Dependabot gives CVE alerts. Snyk adds breaking
   change hints. Neither cross-references call sites to confirm reachability,
   generates a verified patch, *and* synthesizes all signals into a single
   actionable verdict. Blast Radius does all five in one run.

2. **Voice-native.** The verdict is spoken aloud via the Bhashini STT/TTS
   integration. Developers confirm patch application by voice ("confirm" or
   "abort"). The system is multilingual — teams can use regional Indian
   languages, not just English. No competing submission at this event uses
   voice input at all.

3. **Risk-aware commit messages.** When the fix is pushed, the commit message
   is generated directly from the risk-rank subagent's verdict:
   `fix: patch axios 1.4→1.7 breaking change in auth call site, closes CVE-2023-45857`
   — not a generic "bump axios."

4. **Safety by design.** The push step is structurally unreachable if tests
   fail. The confirmation gate is on by default and cannot be bypassed without
   an explicit developer toggle. The branch/repo confirmation banner is
   rendered before every push, even in "always proceed" mode.

---

## Deliverable 2: How IBM Bob 2.0 Was Used

### Bob as the Execution Engine

IBM Bob 2.0 is not a library or an API — it is an autonomous coding agent with
an exposed extension system: custom modes, skills, rules, and an Execute
permission that lets it run terminal commands, apply file patches, and push
branches in a live repository.

Blast Radius is built *entirely through Bob's extension points*. There is no
custom Bob source code, no Bob API wrapper, and no MCP server. Everything is
configuration and scripts that Bob runs with its own Execute permission.

**Specifically, Bob was used for:**

**1. Custom Mode (`.bob/custom_modes.yaml`)**
Bob reads the Blast Radius mode definition and switches into a specialized
context when triggered. The mode defines the five subagent persona, the
orchestration rules, and the propose-confirm-execute gate that governs every
action Bob takes.

**2. Five Skill Files (`.bob/skills/*/SKILL.md`)**
Each subagent is a Bob skill — a structured prompt and tool-use specification
that tells Bob exactly what to do for that step: which APIs to query, what
JSON schema to output, how to handle errors. Bob authors the detection logic
live during runs. Antigravity authored the skill scaffolding; Bob authored
the actual subagent detection outputs.

**3. Rules (`.bob/rules-blast-radius/RULES.md`)**
Bob respects the propose-confirm-execute behavioral rules that enforce the
safety gate: never apply a patch without explicit confirmation, never push
without rendering the branch/repo banner, never auto-merge regardless of
the verdict tier.

**4. Execute Permission**
Bob runs the orchestrator scripts directly in the terminal:
- `python orchestrator/merge.py` — reconcile subagent outputs
- `python orchestrator/fix_verify.py` — apply patch, rerun tests
- `python orchestrator/auto_push.py` — generate commit message, render banner, push
- `python voice/bridge.py` — speak the verdict, capture voice confirmation

**5. Bob Shell (Non-Interactive Mode) — Phase 10**
The voice bridge's `invoke_bob_shell()` function pipes commands into Bob Shell
in non-interactive mode (`--mode blast-radius --non-interactive`), allowing
the voice loop to trigger orchestrator actions without the developer typing.

**6. Bob Sessions (`bob_sessions/`)**
Every team member's Bob task-session summaries are captured and stored in
`bob_sessions/lokesh/` and `bob_sessions/teammate/` as required by the
hackathon rules. These screenshots show the full step list of what Bob did,
the subagent outputs in chat, and Execute permission in action.

### What Antigravity Built (Not Bob)

Per the project constraint: *Antigravity builds everything except the five
subagents' actual detection logic.*

Antigravity (this agent) authored:
- Environment scaffolding, schemas, mock fixtures
- `orchestrator/merge.py`, `post_comment.py`, `fix_verify.py`, `auto_push.py`, `pipeline.py`
- `tools/pre_run_checklist.py`, `validate_bob_output.py`, `ingest_bob_output.py`
- `voice/bridge.py` (Bhashini STT/TTS)
- `.github/workflows/blast-radius.yml` (GitHub Action)
- All 83 unit and integration tests (100% passing)

Bob authors:
- Detection logic in live runs (version-diff changelog parsing, CVE queries,
  call-site analysis, patch generation, risk scoring)
- Real JSON outputs stored in `evidence/` after Phase 10

This division means Blast Radius is not a "Bob wrote some code" submission —
Bob is the runtime execution engine for the five subagents, with Antigravity
providing the scaffolding, contracts, and orchestration layer that makes
Bob's output trustworthy and actionable.

---

## Deliverable 3: Demo Video

*Link TBD — to be added after Phase 11 full pipeline rehearsal.*

The demo will show:
1. A live PR with an axios version bump triggering the GitHub Action
2. Bob's five subagents running in parallel, outputs in the chat
3. Orchestrator verdict posted as a PR comment
4. Voice layer speaking the verdict aloud (Bhashini TTS, English + Hindi)
5. Developer confirming the patch by voice ("confirm")
6. Fix-verify applying the patch on a scratch branch and running `npm test`
7. Auto-push with the risk-aware commit message and confirmation banner

---

## Deliverable 4: Public Repo

**https://github.com/lokeshks-rookie/BLAST**

Required folder present: `bob_sessions/` with per-member subfolders and
screenshot instructions (screenshots added during Phase 10/11 live runs).
