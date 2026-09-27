# Risk-Rank Subagent Evidence

Drop the raw JSON output from the Risk-Ranking subagent here after Phase 10.

## What this subagent produces

```json
{
  "package_name": "axios",
  "old_version": "1.4.0",
  "new_version": "1.7.2",
  "ecosystem": "npm",
  "risk_tier": "merge-with-patch",
  "confidence": 0.87,
  "summary": "...",
  "findings": [...],
  "reasoning_chain": [...],
  "recommended_action": "...",
  "has_patch": true
}
```

## File naming

```
<YYYY-MM-DD>_<package>_<old>-to-<new>.json
Example: 2026-09-27_axios_1.4.0-to-1.7.2.json
```

## Schema reference

`fixtures/schemas/risk-rank.schema.json` — validate against this before saving.
