# Evidence — Blast Radius Pipeline Outputs

This folder stores the verifiable run evidence for the Blast Radius pipeline.
Every subagent has its own subfolder — evidence is never mixed.

---

## Structure

```
evidence/
  version-diff/        # Version-Diff subagent output
  vuln-lookup/         # Vulnerability Lookup subagent output
  usage-impact/        # Usage-Impact subagent output
  fix-verify/          # Fix-Verify subagent output
  risk-rank/           # Risk-Ranking subagent output
  fix_verification.json  # Fix-Verify harness test execution report (Phase 6)
  verdict.json           # Orchestrator merged verdict (Phase 4)
  verdict.md             # Human-readable verdict summary (Phase 4)
```

---

## What Goes Where

| Folder | Content | Produced By |
|--------|---------|-------------|
| `version-diff/` | Raw JSON from the Version-Diff subagent | Bob (Phase 10) |
| `vuln-lookup/` | Raw JSON from the Vulnerability Lookup subagent | Bob (Phase 10) |
| `usage-impact/` | Raw JSON from the Usage-Impact subagent | Bob (Phase 10) |
| `fix-verify/` | Raw JSON from the Fix-Verify subagent | Bob (Phase 10) |
| `risk-rank/` | Raw JSON from the Risk-Ranking subagent | Bob (Phase 10) |
| `fix_verification.json` | Patch apply + test execution report | orchestrator/fix_verify.py |
| `verdict.json` | Final merged risk-tier verdict | orchestrator/merge.py |
| `verdict.md` | Plain-English verdict summary | orchestrator/merge.py |

---

## Naming Convention (Phase 10 real runs)

When you save Bob's real subagent output, name files:

```
evidence/<subagent>/<YYYY-MM-DD>_<package>_<old>-to-<new>.json

Example:
  evidence/risk-rank/2026-09-27_axios_1.4.0-to-1.7.2.json
```

Keep the mock fixtures in `fixtures/` — evidence is for real run output only.
