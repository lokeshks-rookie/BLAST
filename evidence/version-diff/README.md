# Version-Diff Subagent Evidence

Drop the raw JSON output from the Version-Diff subagent here after Phase 10.

## What this subagent produces

```json
{
  "package_name": "axios",
  "old_version": "1.4.0",
  "new_version": "1.7.2",
  "ecosystem": "npm",
  "breaking_changes": [...],
  "changelog_url": "https://..."
}
```

## File naming

```
<YYYY-MM-DD>_<package>_<old>-to-<new>.json
Example: 2026-09-27_axios_1.4.0-to-1.7.2.json
```

## Schema reference

`fixtures/schemas/version-diff.schema.json` — validate output before saving.
