# Project Build Reference
## Blast Radius + Voice + Auto-Push — IBM Bob 2.0 Hackathon

This document has two parts: **Part 1** is what's been added on top of the original Blast Radius plan (voice layer, auto git-push, tech stack, build order, event facts). **Part 2** is the original Blast Radius plan, preserved exactly as written — nothing summarized or cut — since it's the core of the submission.

---

# PART 1 — Additions & Build Context

## 1. Event Facts

- **Event:** IBM Bob 2.0 Hackathon, hosted by LabLab AI
- **Dates:** Sept 25–27, 2026
- **Team:** 2 people ("Import Claude")
- **Bob account:** `ibm-coding-challenge-uat` (region: US-East), Enterprise plan
- **Budget:** 40 Bobcoins **total for the whole team** (not per person) — no top-up once exhausted
- **Judging criteria:** Application of Technology, Business Value, Originality, Presentation
- **Required deliverables:**
  1. Demo video
  2. Written problem/solution statement
  3. Written statement on how Bob was used
  4. Public code repo, including a `bob_sessions/` folder with each team member's Bob task-session summary screenshots

---

## 2. Added Feature: Voice Layer

- **Tech:** Bhashini (Indian Gov't STT/TTS API — key already held, valid ~6 months), reused from the Healix (healthcare-chatbot) project's existing integration
- **Flow:** mic input → Bhashini STT → text → piped into **Bob Shell (non-interactive mode)** → Bob's text output → Bhashini TTS → spoken back
- **Cost:** $0 Bobcoins — entirely external to Bob, doesn't touch the 40-coin budget
- **Why it matters:** multilingual accessibility (dictate commands in regional Indian languages, not just English) + hands-free workflow
- **How it plugs into Blast Radius:**
  - Bob speaks the Risk-Ranking subagent's verdict aloud instead of (or alongside) printing it
  - Developer confirms the Fix-Verify subagent's proposed patch by voice ("confirm") instead of clicking
  - Periodic spoken status updates during long multi-subagent runs
  - Optional: spoken intent-check ("still reviewing the axios bump, correct?") if a run drifts long

## 3. Added Feature: Auto Git-Push

- **Not a separate system** — it's the natural extension of Fix-Verify's existing propose → confirm → execute loop: propose patch → confirm → apply → tests pass → **push**
- **Mechanism:** Bob already has Execute permission (runs terminal commands, including `git`) — no new engineering required for the push mechanic itself
- **Confirmation:** gated by the mode's own rules (spoken via the voice layer, or typed) — either per-push confirmation, or an "always proceed" toggle the developer sets
- **Repo/branch switching:** native VS Code/git functionality already inside Bob IDE — nothing custom to build
- **Uniqueness layered on top:**
  - Risk-aware commit messages generated from the Risk-Ranking subagent's verdict (documents *why* the fix was made, e.g. "fix: patch axios 1.4→1.7 breaking change in auth call site, closes CVE-XXXX")
  - Spoken push confirmation in the developer's own language
  - Branch/repo confirmation banner stated before every push (prevents wrong-branch mistakes, especially live on stage)

## 4. Tech Stack (config vs. actual code)

| Layer | Type | Tech |
|---|---|---|
| Custom Mode | Config only | `.bob/custom_modes.yaml` |
| Skills (5 subagents) | Config/Markdown only | `.bob/skills/*/SKILL.md` |
| Rules (propose-confirm-execute, push gating) | Markdown | `.bob/rules-blast-radius/` |
| OSV / GHSA / watsonx.ai checks | Code, run BY Bob | Python scripts, run via Bob's Execute permission — no custom MCP server needed |
| GitHub PR integration | Code | GitHub Action (YAML) → triggers Bob Shell non-interactive → posts verdict via `gh pr comment` / REST API |
| Voice layer | Code | Standalone Python script — `sounddevice`/`pyaudio` for mic, `requests` for Bhashini REST calls, `subprocess` to call Bob Shell |
| Testing | Existing | Target repo's own test suite (pytest/Jest/etc.) |

**Important:** Bob's own source code is never touched — it's closed-source. Everything above is built *on top of* Bob through its exposed extension points (modes, skills, rules, Execute permission, Bob Shell CLI).

## 5. Build Priority (given limited remaining time)

1. Write the Custom Mode + 5 Skill files (pure config, zero coin cost until run)
2. Have Bob write/run its own OSV/GHSA/watsonx API-check scripts via Execute
3. **Test the full pipeline on ONE staged diff first** (real historical CVE + real breaking change) — this is the safety-net demo
4. Add the GitHub Action wrapper for live PR integration (highest risk/payoff — attempt only after step 3 is solid)
5. Build and test the voice script independently, wire in last
6. Add push-confirmation logic to the mode's rules (no new UI needed)

**Fallback if time runs out:** staged-diff pipeline run + spoken verdict + demoed push to a test branch, honestly presented as the MVP with live webhook integration as documented next step.

## 6. Competitive Differentiation

Reviewed ~30 other submissions from this event. Closest overlaps and how this avoids them:
- **Inbin Gate** (auto-approve safety hook) — different problem (authorization vs. dependency risk); no direct overlap
- **PACT ContextLease**, **MergeWitness**, **BurnRate** — adjacent but scoped to different failure modes (stale context, merge conflicts, cloud cost)
- **Onboarding / general code review / release safety** categories are heavily saturated (5–8 competitors each) — Blast Radius avoids all three by targeting manifest/dependency changes specifically
- **No other submission mentions voice input at all** — genuine white space

## 7. Updated Repo Structure

```
.bob/
  custom_modes.yaml          # Blast Radius mode definition
  skills/
    version-diff/
    vuln-lookup/
    usage-impact/
    fix-verify/
    risk-rank/
  rules-blast-radius/        # gather -> dispatch -> merge -> report -> confirm -> push
voice/                       # standalone Bhashini <-> Bob Shell wrapper script
evidence/                    # Bob task-session screenshots, per subagent run
bob_sessions/                # required hackathon deliverable — task session summaries per team member
PLAN.md                      # capability research + design rationale
README.md                    # problem, before/after metric, architecture, demo link
```

---

# PART 2 — Original Blast Radius Plan (verbatim)

# Blast Radius
### An evidence-grounded dependency and configuration risk reviewer, built on IBM Bob 2.0
**Team: Import Claude — IBM Bob 2.0 Hackathon**

---

## 1. Problem Statement

Every engineering team has tooling for two categories of pull request review: static linting, which is automatic and trusted, and logic review, which is manual and human. A third category falls into a gap that almost no team's process actually covers — **dependency and configuration manifest changes**: a version bump in `package.json`, `requirements.txt`, `go.mod`, a `Dockerfile` base image tag, or a CI pipeline YAML.

These diffs look trivial. A single-line change from `"axios": "^1.4.0"` to `"axios": "^1.7.2"` gives a reviewer almost nothing to evaluate by eye. Doing the review properly requires three separate lookups that nobody has time for on every dependency bump:

1. Reading the changelog or release notes for the version delta to find breaking API changes.
2. Cross-referencing the delta against a vulnerability database to see which CVEs are closed and which are introduced.
3. Checking whether the changed API surface is actually called anywhere in the codebase, and if so, whether that call site is reachable from untrusted input.

Because this takes fifteen to twenty minutes done properly, and teams ship dozens of these diffs a week, the near-universal outcome is that dependency bumps get approved on trust rather than evidence. This is a well-documented failure mode — it is how breaking API changes reach production silently, how already-patched CVEs get reintroduced by a downgrade, and how a "worked in CI, broke in prod" incident traces back to a manifest line nobody actually read.

This is not a general code-review problem. It is a specific, high-frequency, high-blast-radius blind spot that exists because the review process for manifest changes is structurally different from the review process for logic changes, and no team has built dedicated tooling for it — general AI review tools treat it as one weak signal among many, if they surface it at all.

**The cost this imposes, in concrete terms:** manual review time of roughly 15–20 minutes per non-trivial dependency bump, multiplied across every bump a team ships; a nonzero rate of breaking-change incidents that a five-minute changelog read would have caught; and a nonzero rate of CVE reintroduction that a five-minute advisory lookup would have caught. None of this is hypothetical — it is the standard shape of a supply-chain review fatigue incident.

---

## 2. Proposed Solution

**Blast Radius** is a custom IBM Bob 2.0 mode that triggers specifically on diffs touching dependency or configuration manifests, and produces a single risk-tiered, evidence-backed verdict per change — not a wall of raw findings, and never a vague "looks fine."

The core design principle: **orchestrate existing signal sources through Bob's agent and subagent architecture rather than build a new detection engine from scratch.** Changelog data, vulnerability advisory data, and the codebase itself already contain everything needed for a correct verdict. The value Blast Radius adds is dispatching the right isolated subagent at each source, cross-referencing their outputs against each other, and presenting the result at a level a human reviewer can act on in seconds rather than minutes.

### 2.1 Architecture overview

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
  (changelog/     (OSV/GHSA      (repo grep for  (patch +       (watsonx.ai —
  release notes)  advisory data)  real call sites) test rerun)   reachability
                                                                   scoring)
        └──────────────┴──────────────┼──────────────┴──────────────┘
                                       ▼
                         ┌─────────────────────────┐
                         │   Merge & Report Step     │
                         │  risk-tiered verdict +    │
                         │  suggested patch          │
                         └───────────┬─────────────┘
                                       ▼
                         ┌─────────────────────────┐
                         │  Posted as a live PR      │
                         │  review comment            │
                         └─────────────────────────┘
```

### 2.2 The five subagents

**Version-Diff Subagent**
Reads the changelog or release notes spanning the old and new pinned version and extracts breaking API changes in plain language. This is Bob's document-understanding capability applied to something a reviewer actually needs, not a demonstration for its own sake — most breaking-change information already exists in prose form and is simply never read under time pressure.

**Vulnerability Subagent**
Cross-references the version delta against OSV and GHSA advisory data: which CVEs does this bump close, and which does it introduce or leave unresolved. Runs independently and in parallel with the version-diff subagent — the two draw from unrelated sources and have no reason to block each other.

**Usage-Impact Subagent**
Greps the actual repository for real call sites of whatever API surface the bump changes. This is the subagent that separates Blast Radius from a changelog summarizer: it does not report "this function's signature changed," it reports the exact files and line numbers where that function is actually called in this codebase. A finding with zero call sites and a finding with call sites in an authentication path are not the same finding, and this subagent is what makes that distinction possible.

**Fix-Verify Subagent**
For mechanical breaks — a renamed parameter, a changed default value, a relocated import — proposes a concrete patch. On developer confirmation, applies the patch and reruns the test suite, reporting pass or fail with the diff attached. This follows a propose → confirm → execute loop rather than auto-committing anything unreviewed.

**Risk-Ranking Subagent (watsonx.ai)**
Takes the combined output of the four subagents above and produces a single ranked verdict, scored not merely by "has a CVE" but by actual reachability — is the affected code path reachable from untrusted input in this specific codebase. This is what turns four separate findings into one decision: safe to merge, merge with the attached patch, or do not merge pending manual review.

### 2.3 The orchestration layer

The Merge & Report step is where Bob's Agent mode does its real work — not generating any one subagent's output, but reconciling five independent outputs into a single coherent verdict, resolving disagreement (for example, a vulnerability subagent flagging a CVE that the usage-impact subagent shows has zero reachable call sites, which should lower rather than raise the reported severity), and formatting the result for a human who has ten seconds, not ten minutes, to read it.

### 2.4 Live integration, not a staged demo

Blast Radius runs against a real, live pull request on a real repository through a GitHub webhook or Action, and posts its risk-tiered verdict as an actual PR review comment, with the Fix-Verify subagent's patch attached as a suggested change a maintainer can apply with one click. This is deliberately not a script run against a staged diff with terminal output read aloud — the deliverable is a bot commenting on a real PR the way a very fast, very thorough human reviewer would.

---

## 3. Unique Features

| Feature | What it actually does | Why it matters |
|---|---|---|
| **Narrow trigger surface** | Activates only on manifest/dependency file changes, not general PRs | Avoids the crowded "AI code reviewer" category entirely; the tool does one job completely instead of many jobs shallowly |
| **Call-site grounding** | Every vulnerability or breaking-change finding is checked against real usage in the target repo before being surfaced | Eliminates noise — a CVE in an unused code path is reported as low-priority, not flagged identically to one on a live auth route |
| **Reachability-based ranking, not severity-based** | The watsonx.ai layer scores findings by whether the vulnerable path is reachable from untrusted input, not by raw CVSS score alone | Produces one actionable verdict instead of a list a reviewer still has to triage themselves |
| **Propose-confirm-execute patching** | Fix-Verify subagent never auto-commits; it proposes, waits for explicit confirmation, then applies and reruns tests | Keeps a human in the loop on anything that touches the actual codebase, which is non-negotiable for a tool operating on dependency changes |
| **Consolidated single verdict, not five reports** | The orchestrator's entire job is reconciling five subagent outputs into one risk tier | This is the deliverable a reviewer actually reads — raw subagent output is an implementation detail, not the product |
| **Live PR integration** | Posts directly as a GitHub PR review comment with an applyable suggested patch | Demonstrates real workflow integration rather than a standalone CLI report |
| **Document understanding used on real prose** | Changelog and release-note parsing is functional, not cosmetic | Most breaking changes are already documented in text nobody has time to read — this is the actual use case for the capability, not a checkbox |

---

## 4. Final Deliverable

By the end of the build window, the submission includes:

1. **A working Bob 2.0 custom mode** (`.bob/custom_modes.yaml`) defining the Blast Radius review pipeline, with five subagent skill definitions under `.bob/skills/`.
2. **A live GitHub integration** — a webhook or Action that triggers the pipeline on real pull requests against a real target repository and posts the resulting verdict as an actual PR comment.
3. **A demonstrated before/after comparison**: manual review time for a staged dependency bump (containing at least one real historical CVE and one real breaking API change) timed by hand, set against the pipeline's actual runtime on the identical diff.
4. **Evidence of Bob task-session usage** — screenshots or recordings of each subagent's Bob-orchestrated run, stored under `evidence/`.
5. **A demo video** walking through: the problem, a live PR receiving a Blast Radius review comment, the risk-tiered verdict, the applied patch, and the tests passing afterward.
6. **This document and a PLAN.md** covering capability research and design decisions, submitted alongside the repository.

### Repository structure

```
.bob/
  custom_modes.yaml          # Blast Radius mode definition
  skills/
    version-diff/
    vuln-lookup/
    usage-impact/
    fix-verify/
    risk-rank/
  rules-blast-radius/        # orchestration: gather -> dispatch -> merge -> report
evidence/                    # Bob task-session screenshots, per subagent run
PLAN.md                      # capability research + design rationale
README.md                    # problem, before/after metric, architecture, demo link
```

---

## 5. Tech Stack

| Layer | Technology | Purpose |
|---|---|---|
| **Orchestration** | IBM Bob 2.0 — Agent mode, parallel tasks, subagents, custom modes | Core orchestration of the five-subagent pipeline and verdict merging |
| **Document understanding** | IBM Bob 2.0 document understanding | Parsing changelogs and release notes for breaking-change extraction |
| **Vulnerability data** | OSV API, GitHub Security Advisory (GHSA) database | Ground-truth CVE data for the Vulnerability subagent |
| **Risk ranking** | watsonx.ai | Reachability-based scoring and consolidation of subagent findings into one verdict |
| **Repository analysis** | Bob's repo-context tooling + targeted grep/AST search | Usage-Impact subagent's call-site detection |
| **Live integration** | GitHub Webhooks / GitHub Actions, GitHub REST API | Triggering the pipeline on real PRs and posting review comments with suggested patches |
| **Testing** | The target repository's own test suite (pytest, Jest, or equivalent, matched to the demo repo's stack) | Fix-Verify subagent's post-patch verification |
| **Language** | Python (pipeline orchestration and subagent glue code) | Matches existing team proficiency; fastest path to a working integration in the build window |

---

## 6. Alignment with Judging Criteria

- **Application of technology** — every listed Bob 2.0 capability (Agent mode, parallel tasks, subagents, document understanding, custom modes) is used for a distinct, necessary function in the pipeline, not bolted on for coverage.
- **Business value** — directly reduces manual review time on a diff category every team ships continuously, and directly reduces the incidence of two well-known, costly failure modes: breaking-change regressions and CVE reintroduction.
- **Originality** — targets a specific, underserved review gap rather than general code review, which is the most saturated category in this hackathon's submission pool.
- **Demonstrated impact** — a timed manual baseline against the pipeline's actual runtime on an identical diff, shown live rather than claimed.

---

## 7. Risks and Fallbacks

- **watsonx.ai reachability scoring proves too ambitious in the time available** — fall back to a severity-plus-call-site-count heuristic rather than dropping the ranking layer entirely; the consolidated single-verdict output is the part that must not be cut.
- **Live GitHub integration slips past the halfway point of the build window** — this is the highest-risk, highest-payoff component; if it is not stable by then, fall back to running the full pipeline against a staged diff with terminal output, and cut Fix-Verify's auto-patch step first, since a correct verdict matters more than an automated fix nobody sees applied live.
- **Target repository selection** — must be decided early; a real, moderately active open-source repository with a genuine historical CVE and a genuine breaking change in its history is significantly more credible to judges than a staged or self-authored example.
