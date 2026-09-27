# Blast Radius — Orchestration Rules

These rules govern the Blast Radius mode's execution sequence and safety constraints. Bob must follow these rules exactly when operating in Blast Radius mode.

---

## Rule 1: Execution Sequence

The Blast Radius pipeline runs in a strict six-step sequence. No step may be skipped, and no step may begin before the previous step completes successfully.

### Step 1 — Gather
1. Parse the incoming diff to identify which manifest file(s) changed
2. For each changed dependency, extract: `package_name`, `old_version`, `new_version`, `ecosystem`
3. If multiple dependencies changed in the same diff, process each dependency independently through the full pipeline
4. If no dependency version change is detected (e.g., only a comment or formatting change), report "no actionable dependency change detected" and stop

### Step 2 — Dispatch (Parallel)
1. Launch three subagents **in parallel** — they have no dependencies on each other:
   - **Version-Diff**: extracts breaking changes from changelogs
   - **Vuln-Lookup**: queries OSV/GHSA for CVE data
   - **Usage-Impact**: searches the repo for call sites of affected APIs
2. Wait for all three to complete before proceeding
3. If any subagent fails, report the failure explicitly — do NOT silently skip it or substitute a guess

### Step 3 — Dispatch (Sequential, Dependent)
1. Launch **Fix-Verify** — it requires the output of both Version-Diff and Usage-Impact
2. Wait for Fix-Verify to complete
3. Launch **Risk-Rank** — it requires the output of all four preceding subagents
4. Wait for Risk-Rank to complete

### Step 4 — Merge
1. Reconcile all five subagent outputs into a single verdict using the Risk-Rank subagent's output as the authoritative tier
2. Assemble the rendered Markdown report (see Report Format below)
3. Attach the Fix-Verify patch if one exists

### Step 5 — Report
1. Post the rendered Markdown verdict as a PR review comment (if running via GitHub Action)
2. Print the verdict to the terminal (if running via Bob Shell)
3. Speak the verdict summary aloud (if the voice layer is active)

### Step 6 — Confirm & Push
1. Present the proposed patch (if any) for explicit developer confirmation
2. **Wait for confirmation** — never auto-apply. Confirmation may come via:
   - Typed "confirm" in Bob Shell
   - Spoken "confirm" via the voice layer
   - "yes" at the CLI prompt
3. On confirmation: apply the patch via `git apply`, rerun the target repo's test suite
4. If tests pass: display the branch/repo confirmation banner, then ask for push confirmation
5. On push confirmation: commit with a risk-aware message and push
6. If tests fail: report the failure, discard the patch, and stop — do NOT push

---

## Rule 2: Propose-Confirm-Execute Gate

**This is a non-negotiable safety constraint.**

Any action that modifies the target repository's files — applying a patch, running `git apply`, committing, pushing — MUST follow this exact sequence:

1. **Propose**: Show the developer exactly what will be changed (the diff, the commit message, the target branch)
2. **Confirm**: Wait for explicit confirmation. Do NOT proceed on timeout, on silence, or on ambiguous input
3. **Execute**: Only after unambiguous confirmation, perform the action

This gate applies even in CI/automated contexts. There is no "always yes" default at this layer — that toggle exists at a higher level (Phase 8) and must be explicitly set by the developer.

---

## Rule 3: CVE Severity Down-Weighting

When the Vulnerability Lookup subagent flags a CVE and the Usage-Impact subagent reports **zero call sites** for the affected API in the target repository:

- The CVE's practical severity MUST be reported as **lower** than its raw CVSS score suggests
- The finding type should be `cve_unreachable`, not `cve_reachable`
- The risk tier should reflect practical risk, not theoretical risk

A CVE in an unused code path is not the same as a CVE on a live authentication route. The orchestrator's entire value proposition depends on making this distinction correctly.

---

## Rule 4: Failure Handling

- If a subagent produces output that does not conform to its declared output schema: **fail loudly**. Report the schema violation, identify which fields are malformed, and stop the pipeline. Do NOT silently produce a plausible-looking wrong verdict.
- If a subagent times out: report the timeout, identify which subagent, and produce a partial verdict clearly labeled as incomplete.
- If the vulnerability databases (OSV, GHSA) are unreachable: report the outage, proceed with the other subagents, and clearly label the verdict as "missing vulnerability data."

---

## Rule 5: Branch/Repo Confirmation Banner

Before every `git push`, display a confirmation banner showing:

```
╔══════════════════════════════════════════════════════╗
║  PUSH CONFIRMATION                                   ║
║  Repository: {remote_url}                            ║
║  Branch:     {current_branch}                        ║
║  Commit:     {commit_message_first_line}             ║
╚══════════════════════════════════════════════════════╝
```

This banner must show the **actual** current branch and remote, not a hardcoded value. If the voice layer is active, this banner must also be spoken aloud.

---

## Rule 6: Report Format

The Markdown verdict posted as a PR comment must follow this structure:

```markdown
## 🔍 Blast Radius — Dependency Risk Report

**Package:** {package_name} {old_version} → {new_version}
**Risk Tier:** {risk_tier_emoji} {risk_tier}
**Confidence:** {confidence}%

### Summary
{summary}

### Findings
{for each finding:}
- {severity_emoji} **{title}** ({severity})
  {description}

### Recommended Action
{recommended_action}

### Proposed Patch
{if has_patch:}
\`\`\`diff
{diff}
\`\`\`

---
*Generated by Blast Radius — [view raw evidence](link)*
```

Risk tier emojis: `safe` → ✅, `merge-with-patch` → ⚠️, `do-not-merge` → 🛑
