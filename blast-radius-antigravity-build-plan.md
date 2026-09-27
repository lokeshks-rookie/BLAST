# Blast Radius — Antigravity Execution Plan
### Phased build instructions for Antigravity — Voice + Auto-Push edition
**Team: Import Claude — IBM Bob 2.0 Hackathon (LabLab AI, Sept 25–27, 2026)**

---

## Before Phase 1: The One Design Decision This Plan Makes

The original project context states that the OSV/GHSA/watsonx checks are **"code, run BY Bob"** via its Execute permission — meaning Bob itself is meant to write and run that subagent logic live, as part of demonstrating its own agentic capability under Application of Technology scoring. If Antigravity pre-writes that exact logic wholesale, Bob's live session reduces to running a script it didn't author, which undercuts the point being demonstrated.

This plan draws the line accordingly. **Antigravity builds everything except the five subagents' actual detection logic.** Concretely, Antigravity is responsible for:

- The repo, the `.bob/` config and skill instructions Bob will read
- The exact input/output contract each subagent must satisfy (so Bob's live output is checkable, not vibes)
- Mock fixtures conforming to that contract, so every downstream system — orchestrator, GitHub Action, voice layer, auto-push — can be built and fully tested *before* a single Bobcoin is spent
- The orchestrator, GitHub integration, voice bridge, and push logic — real glue code, not Bob's demonstrated capability
- The harness that swaps mock subagent output for real Bob output once it exists, with no other code changing

This also directly serves the 40-Bobcoin, no-top-up, two-person budget: every phase through Phase 9 is buildable and testable at zero coin cost. Bob is only touched starting at Phase 10, once everything it needs to slot into already works.

This scope boundary is fixed for the remainder of this plan: Antigravity does not author the version-diff, vuln-lookup, or risk-rank detection logic at any phase, including as a fallback or reference implementation. Phase 3's fixtures and Phase 4's orchestrator are built against mocked output for exactly this reason.

---

## Fixed Phase Protocol

Every phase below follows the same five-part shape. Antigravity should execute phases in order, and should not begin phase *N+1* until phase *N*'s Git Push Gate has been answered.

1. **Build Steps** — what Antigravity actually writes, runs, or scaffolds.
2. **Dependencies** — anything installed in this phase, and the exact command.
3. **Error Check** — how Antigravity verifies its own output before presenting it (syntax validity, a dry run, a lint pass, a schema check — never just "looks right").
4. **Test & Review (for you)** — concrete, mechanical steps you run yourself to confirm the phase actually did what it claims. Not "check it works" — specific commands and what you should see.
5. **Git Push Gate** — Antigravity asks, verbatim: *"Phase [N] complete and verified. Push to the repository? (yes/no)"* On **yes**: stage everything touched in this phase, commit with the message template below, push to the working branch. On **no**: leave the working tree as-is and wait for further instruction — do not proceed to the next phase automatically.

**Commit message template for every phase push:**
```
[Phase N] <one-line summary of what this phase built>

- <bullet per major file/component added or changed>
```

**Standing rules across all phases:**
- No API key, token, or credential is ever written into a committed file. Every secret lives in `.env` (git-ignored) with `.env.example` documenting the variable name only.
- Every phase's Error Check must explicitly include a secrets-scan step before the Git Push Gate is offered.
- Target repo for the staged demo diff is decided in Phase 3 and does not change after.

---

## Phase 1 — Repository & Environment Scaffolding

**Build Steps**
Create the repository with this exact structure:
```
.bob/
  custom_modes.yaml
  skills/
    version-diff/
    vuln-lookup/
    usage-impact/
    fix-verify/
    risk-rank/
  rules-blast-radius/
voice/
orchestrator/
.github/
  workflows/
tests/
fixtures/
evidence/
bob_sessions/
README.md
PLAN.md
.env.example
.gitignore
requirements.txt
```
Initialize git. Set up a Python virtual environment. Populate `.gitignore` with `.env`, `__pycache__/`, `*.pyc`, `.venv/`. Write `.env.example` listing every credential this project will eventually need: `GITHUB_TOKEN`, `WATSONX_API_KEY`, `WATSONX_PROJECT_ID`, `OSV_API_BASE`, `BHASHINI_API_KEY`, `BHASHINI_STT_ENDPOINT`, `BHASHINI_TTS_ENDPOINT`, `TARGET_REPO_URL`, `BOB_SHELL_PATH` — values left blank.

**Dependencies**
```
python -m venv .venv
source .venv/bin/activate
pip install python-dotenv pyyaml pytest
pip freeze > requirements.txt
```

**Error Check**
Confirm the directory tree matches the spec exactly (`find . -type d | sort`). Confirm the venv activates cleanly. Confirm `git status` shows only the intended new files. Confirm `.env` is absent from `git status` output and `.env.example` contains no real values.

**Test & Review (for you)**
- Run `tree -L 3` (or `find . -maxdepth 3`) and visually confirm it matches the structure above.
- Open `.env.example` and confirm every variable name listed above is present and every value is blank.
- Confirm `.gitignore` actually excludes `.env` by running `git check-ignore -v .env` after creating a dummy `.env` file — it should report the ignore rule, not error out.

**Git Push Gate**
*"Phase 1 complete and verified. Push to the repository? (yes/no)"*

---

## Phase 2 — Bob Custom Mode, Skills & Rules Authoring

**Build Steps**
Author `.bob/custom_modes.yaml`: mode name (`blast-radius`), trigger condition (diff touches any of `package.json`, `requirements.txt`, `go.mod`, `Dockerfile`, `*.yml`/`*.yaml` under CI paths — list explicitly, don't leave it fuzzy), and a reference to the five skills and the rules directory.

Author the five files under `.bob/skills/*/SKILL.md` — one per subagent (version-diff, vuln-lookup, usage-impact, fix-verify, risk-rank). Each file must specify, in enough detail that Bob has no ambiguity when it executes:
- The subagent's single responsibility (one sentence, non-negotiable scope)
- Its exact inputs (e.g., old version string, new version string, package name, repo path)
- Its exact output schema — this is the contract Phase 3's fixtures will conform to and Phase 4's orchestrator will consume, so it must be precise: field names, types, and an example JSON object
- Explicit instruction that it runs via Bob's Execute permission and should write/run its own Python for the actual lookup logic

Author `.bob/rules-blast-radius/` covering the full sequence: gather → dispatch (parallel) → merge → report → confirm → push, and the propose-confirm-execute gating rule for anything that touches the target repo's files.

**Dependencies**
None new — this phase is pure YAML/Markdown authoring.

**Error Check**
Validate `custom_modes.yaml` parses as valid YAML (`python -c "import yaml; yaml.safe_load(open('.bob/custom_modes.yaml'))"`). Confirm all five skill files exist and each contains an explicit, well-formed JSON example in its output-schema section — malformed example JSON here will silently propagate into every downstream phase.

**Test & Review (for you)**
- Read all five `SKILL.md` files back to back and confirm the five responsibilities don't overlap — if two subagents could plausibly answer the same question, the scope isn't narrow enough.
- Confirm each output schema example is internally consistent (field names used in the "inputs" section of one subagent's downstream consumer match the field names in the producing subagent's output schema).
- Confirm the trigger file-pattern list in `custom_modes.yaml` actually covers your intended demo manifest type before moving on.

**Git Push Gate**
*"Phase 2 complete and verified. Push to the repository? (yes/no)"*

---

## Phase 3 — Shared Data Contracts & Local Test Fixtures

**Build Steps**
Formalize the five output schemas from Phase 2 as actual JSON Schema files under `fixtures/schemas/`. Select and lock in the target repository and the specific staged dependency bump for the demo — a real package, a real prior version, a real new version, with a genuine historical CVE closed or reintroduced by the bump, and a genuine breaking API change in the delta. Document this choice in `fixtures/demo-case.md` (package name, versions, CVE ID, the specific breaking change, and why this bump was chosen). Hand-write one realistic mock JSON output per subagent, conforming to its schema, representing what Bob should plausibly produce for this exact staged case — these mocks are what every phase through Phase 9 builds and tests against.

**Dependencies**
```
pip install jsonschema
```

**Error Check**
Validate every mock fixture against its corresponding JSON Schema programmatically (`jsonschema.validate`) — not by eye. A fixture that doesn't validate now will produce a confusing failure two phases from now with no clear cause.

**Test & Review (for you)**
- Independently verify the chosen CVE is real: look it up on the NVD or GHSA database yourself and confirm the version range matches your staged bump.
- Independently verify the breaking change is real: read the actual changelog entry for the version delta and confirm it says what your fixture claims it says.
- Run the schema validation script yourself and confirm all five fixtures pass with zero errors.

**Git Push Gate**
*"Phase 3 complete and verified. Push to the repository? (yes/no)"*

---

## Phase 4 — Orchestrator / Merge & Report Engine

**Build Steps**
Build `orchestrator/merge.py`: ingests the five subagents' JSON outputs (from `fixtures/` in this phase, from real Bob output starting Phase 10), reconciles them into one risk-tiered verdict. Implement the reconciliation logic explicitly — most importantly, the down-weighting case: a CVE flagged by vuln-lookup with zero call sites reported by usage-impact should lower, not raise, the reported severity. Output format: a single structured verdict object (risk tier — safe / merge-with-patch / do-not-merge — plus a short human-readable summary plus the attached patch if one exists) and a rendered Markdown version suitable for posting as a PR comment.

**Dependencies**
No new external dependencies — standard library plus `jsonschema` already installed.

**Error Check**
Run `orchestrator/merge.py` against the Phase 3 fixtures end to end and confirm it produces a non-empty, correctly-tiered verdict without exceptions. Write and run at least three unit tests under `tests/test_orchestrator.py`: one where all signals agree, one where the CVE/call-site conflict case applies, and one with a missing/malformed subagent output to confirm the orchestrator fails loudly rather than silently producing a wrong verdict.

**Test & Review (for you)**
- Run `pytest tests/test_orchestrator.py -v` yourself and confirm all three tests pass.
- Read the rendered Markdown verdict output for the Phase 3 fixture case and confirm it reads the way you'd want a PR comment to read — this is the artifact judges see, so eyeball it for clarity, not just correctness.
- Deliberately feed the orchestrator a malformed fixture (delete a required field) and confirm it errors clearly instead of producing a plausible-looking wrong verdict.

**Git Push Gate**
*"Phase 4 complete and verified. Push to the repository? (yes/no)"*

---

## Phase 5 — GitHub Action / Webhook Wrapper for Live PR Integration

**Build Steps**
Write `.github/workflows/blast-radius.yml`: triggers on `pull_request` events where the diff touches the manifest file patterns from Phase 2. The action invokes Bob Shell in non-interactive mode (placeholder command for now, wired to the real Bob Shell path once Phase 10 confirms it), passes the diff, and — for now — runs the orchestrator against the Phase 3 fixture to validate the *plumbing* rather than the live logic. Posts the orchestrator's rendered Markdown verdict as a PR review comment via `gh pr comment` or the GitHub REST API, attaching the patch as a suggested change if one exists.

**Dependencies**
```
# GitHub CLI, system-level, not pip
# confirm availability: gh --version
```
If `gh` is unavailable in the environment, fall back to direct calls against the GitHub REST API using `requests` (already available via `pip install requests`, add to `requirements.txt`).

**Error Check**
Validate the workflow YAML with `gh workflow view` or a YAML linter. Dry-run the posting logic against a real (throwaway) PR on the target repo using the Phase 3 fixture's rendered verdict, and confirm a comment actually appears — do not consider this phase done on the strength of "the script ran without errors" alone; confirm the artifact landed where it's supposed to.

**Test & Review (for you)**
- Open a real test PR on the target repository that touches a manifest file.
- Confirm the Action fires (check the Actions tab) and confirm a comment appears on the PR itself, not just in logs.
- Confirm the suggested-patch formatting is actually clickable/applyable in GitHub's UI, not just correctly formatted text.

**Git Push Gate**
*"Phase 5 complete and verified. Push to the repository? (yes/no)"*

---

## Phase 6 — Fix-Verify Auto-Patch & Test-Rerun Harness

**Build Steps**
Build `orchestrator/fix_verify.py`: takes a proposed patch (from the fix-verify subagent's output schema), presents it for explicit confirmation (CLI prompt for now; wired to voice confirmation in Phase 7), applies it via `git apply` on a scratch branch, reruns the target repository's own test suite, and reports pass/fail with the diff attached. This must never apply a patch without an explicit confirm step, including in fully-scripted/CI contexts — no "always yes" default at this layer, since that toggle is a Phase 8 decision, not a default.

**Dependencies**
Install the target repo's actual test runner as needed (e.g. `pip install pytest` if Python, or `npm install` if the target repo is Node — determined by what you locked in during Phase 3).

**Error Check**
Run the harness against the Phase 3 fixture's patch on a disposable scratch branch of the target repo, confirm it applies cleanly, confirm the test suite actually executes (not skipped, not erroring out before reaching real tests), and confirm the pass/fail report matches the real test outcome.

**Test & Review (for you)**
- Run the harness yourself on the scratch branch and read the actual test output alongside the harness's reported summary — confirm they agree.
- Deliberately give it a patch that breaks a test on purpose, and confirm the harness correctly reports failure rather than optimistically reporting success.
- Confirm the scratch branch is disposable and cleanly discardable — you do not want a broken test-branch artifact contaminating your real demo branch later.

**Git Push Gate**
*"Phase 6 complete and verified. Push to the repository? (yes/no)"*

---

## Phase 7 — Voice Layer: Bhashini STT/TTS Bridge

**Build Steps**
Build `voice/bridge.py`, adapted from the existing Healix Bhashini integration: mic capture → Bhashini STT → text → piped via `subprocess` into Bob Shell (non-interactive) → Bob's text output → Bhashini TTS → spoken back. Implement the four use cases from the project context: speaking the risk-ranking verdict aloud, voice confirmation of the fix-verify patch ("confirm"), periodic spoken status updates during long multi-subagent runs, and the spoken intent-check ("still reviewing the axios bump, correct?") if a run drifts long.

**Dependencies**
```
pip install sounddevice requests
# or, if sounddevice has portaudio issues in the build environment:
pip install pyaudio requests
```

**Error Check**
Confirm the Bhashini API key loads correctly from `.env` (never hardcoded) and a trivial STT round-trip (short test audio clip in, expected text out) succeeds before wiring it to anything else. Confirm the TTS half independently: known text in, audible/valid audio file out. Confirm the `subprocess` call to Bob Shell is isolated and testable with a mocked Bob Shell response before touching the real one.

**Test & Review (for you)**
- Run the STT half standalone with your own voice and confirm the transcribed text is accurate enough to be usable, in at least one non-English language given the multilingual accessibility goal.
- Run the TTS half standalone and actually listen to the output — confirm it's intelligible, not just "a file was produced."
- Run the full round trip once with a scripted, low-stakes phrase and confirm the loop completes without hanging — this component has the highest live-demo failure risk of anything in the project, so budget real testing time here, not just a single happy-path run.

**Git Push Gate**
*"Phase 7 complete and verified. Push to the repository? (yes/no)"*

---

## Phase 8 — Auto Git-Push Logic & Risk-Aware Commit Messages

**Build Steps**
Extend `orchestrator/fix_verify.py`'s confirmed-and-tested path with the push step: propose → confirm → apply → test-pass → **push**. Build the commit-message generator that pulls from the risk-ranking subagent's verdict (e.g. `fix: patch axios 1.4→1.7 breaking change in auth call site, closes CVE-XXXX`) rather than a generic message. Implement the branch/repo confirmation banner — printed and spoken via the Phase 7 bridge — stated before every push, showing the exact branch and repo being pushed to. Implement both confirmation modes: per-push confirmation (default) and an explicit "always proceed" toggle the developer sets deliberately, not by default.

**Dependencies**
None new.

**Error Check**
Confirm the push step only ever fires after the test-rerun step reports pass — trace the code path and confirm there is no route to push on a failing test. Confirm the branch/repo confirmation banner renders the *actual* current branch and remote, not a hardcoded placeholder — test this by pushing from two different branches and confirming the banner text changes accordingly.

**Test & Review (for you)**
- Deliberately trigger a failing-test scenario and confirm the push step is unreachable, not just "unlikely to run."
- Confirm the generated commit message on a real test push actually reads as risk-aware and specific, not templated boilerplate with the CVE ID swapped in.
- Test the "always proceed" toggle explicitly off (default) and confirm every single push still asks for confirmation — this is a safety property worth being paranoid about, especially live on stage.

**Git Push Gate**
*"Phase 8 complete and verified. Push to the repository? (yes/no)"*

---

## Phase 9 — Evidence, Bob Sessions & Documentation Scaffolding

**Build Steps**
Build out the four required hackathon deliverables' skeletons:
- `bob_sessions/` — one subfolder per team member, with a `README.md` inside each explaining exactly what to screenshot (task session summaries) and a naming convention for the files.
- `evidence/` — one subfolder per subagent, matching the five skills, with instructions for what run evidence goes where.
- `README.md` — finalized: problem statement, architecture diagram, before/after metric placeholder (to be filled after Phase 11's rehearsal), demo video link placeholder.
- `PLAN.md` — capability research and design rationale, including the Phase 0 design decision documented at the top of this plan.
- A separate `SUBMISSION.md` covering the two written deliverables explicitly required by the event: the problem/solution statement and the "how Bob was used" statement, as clean standalone documents a judge can read without opening the repo tree.

**Dependencies**
None.

**Error Check**
Confirm every folder that's supposed to exist per the Phase 1 structure actually has content or an explicit instructions file in it — an empty required folder with no explanation reads as incomplete to a reviewer skimming the repo.

**Test & Review (for you)**
- Read `SUBMISSION.md` cold, as if you were a judge who has not seen this conversation, and confirm it stands alone.
- Confirm the `bob_sessions/` instructions are clear enough that your teammate can follow them without asking you what to screenshot.
- Cross-check this phase's output against the four required deliverables list from the event facts — confirm all four have a concrete home in the repo right now, even if some content is still a placeholder.

**Git Push Gate**
*"Phase 9 complete and verified. Push to the repository? (yes/no)"*

---

## Phase 10 — First Live Bob Integration Run (Coin-Budgeted)

**Build Steps**
This is the first phase that touches the real Bob account (`ibm-coding-challenge-uat`) and spends real Bobcoins, out of a 40-coin total, shared across both of you, with no top-up. Antigravity's role here is preparation and validation, not execution — it cannot operate Bob directly. Prepare: the exact staged diff from Phase 3, loaded onto the target repo; the finalized `.bob/` config from Phase 2, confirmed present in the repo Bob will operate on; a pre-run checklist confirming every fixture, schema, and downstream consumer is already working against mocks, so this run is validating Bob's real output, not debugging your own plumbing on the clock.

Run the Blast Radius mode in Bob against the staged diff. Capture the five subagents' real JSON output.

**Dependencies**
None new for Antigravity's side. Confirm the Bob CLI/IDE access and account credentials are ready before starting the clock on this phase.

**Error Check**
Immediately validate each of the five real outputs against the Phase 3 JSON Schemas — this is the entire point of having formalized the contract early. Any mismatch here is Bob's actual output not matching the skill instructions from Phase 2, and needs a decision: patch the skill instructions, or patch the orchestrator's consumption logic, but do not silently hand-edit Bob's output to force a fit.

**Test & Review (for you)**
- Confirm the actual Bobcoin spend for this run against your remaining budget before running it a second time for any reason.
- Read Bob's own reasoning/task-session output, not just the final JSON — this is also your `bob_sessions/` evidence capture moment, so screenshot as you go rather than trying to reconstruct it afterward.
- If any subagent's output fails schema validation, decide and document which side is wrong (skill instruction ambiguity vs. orchestrator assumption) before spending another coin re-running it.

**Git Push Gate**
*"Phase 10 complete and verified. Push to the repository? (yes/no)"*

---

## Phase 11 — Full Pipeline Integration Test & Live Demo Rehearsal

**Build Steps**
Swap every mock fixture reference in the orchestrator, GitHub Action, and fix-verify harness for the real Phase 10 Bob output. Run the complete flow end to end, in order: webhook trigger → Bob subagents (real) → orchestrator verdict → voice narration of the verdict → patch confirmation by voice → test rerun → branch/repo confirmation banner → push confirmation → actual push to a disposable demo branch. This is the dress rehearsal — run it enough times to be confident, not just once.

**Dependencies**
None new.

**Error Check**
Confirm the entire chain completes with zero manual intervention beyond the intended confirmation points (voice "confirm," push yes/no). Confirm timing: measure the pipeline's actual wall-clock runtime on this real run, since this number is your headline before/after metric.

**Test & Review (for you)**
- Time yourself doing the equivalent manual review (changelog read, CVE lookup, call-site grep) on the identical staged diff, by hand, with a stopwatch — this is the "before" figure your README has been waiting on since Phase 9.
- Run the full rehearsal at least twice, ideally with your teammate operating it the second time — a flow only you can operate correctly is a demo risk, not a finished feature.
- Deliberately say "no" at the push confirmation once during rehearsal and confirm the system stops cleanly rather than pushing anyway or crashing.

**Git Push Gate**
*"Phase 11 complete and verified. Push to the repository? (yes/no)"*

---

## Phase 12 — Final Verification & Submission Packaging (Project Complete)

**Build Steps**
Fill in every placeholder left open since Phase 9: the before/after metric in `README.md` (from Phase 11's timed comparison), the demo video link once recorded, final pass over `SUBMISSION.md`. Confirm `bob_sessions/` contains both team members' actual screenshots, not instructions-only folders. Confirm `evidence/` contains real captures from Phase 10's live run, not fixture-era placeholders.

**Dependencies**
None.

**Error Check**
Run a full secrets scan across the entire repository history, not just the working tree (`git log -p | grep -i` against key patterns, or a tool like `gitleaks` if available) — a key committed and later removed is still in history. Confirm every file in the Phase 1 structure has real, final content. Confirm the repository is set to public.

**Test & Review (for you)**
- Walk through all four required deliverables one final time against the event facts list: demo video, problem/solution statement, "how Bob was used" statement, public repo with populated `bob_sessions/`. Confirm each exists and is findable without you explaining where to look.
- Have your teammate independently clone the public repo fresh and confirm the README alone gives them (and by extension, a judge) enough to understand the project without this conversation as context.
- Confirm the demo video actually shows what Phase 11 rehearsed — a live PR receiving a comment, the verdict, the patch, the tests passing, the push — not a narrated slide deck standing in for it.

**Git Push Gate**
*"Phase 12 complete and verified. Push to the repository? (yes/no)"*

**This phase, once pushed, is project completion.**
