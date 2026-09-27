# Vuln-Lookup Subagent Evidence

Drop the raw JSON output from the Vulnerability Lookup subagent here after Phase 10.

## What this subagent produces

```json
{
  "package_name": "axios",
  "old_version": "1.4.0",
  "new_version": "1.7.2",
  "ecosystem": "npm",
  "cves_closed": [...],
  "cves_introduced": [...],
  "ghsa_ids": [...]
}
```

## File naming

```
<YYYY-MM-DD>_<package>_<old>-to-<new>.json
Example: 2026-09-27_axios_1.4.0-to-1.7.2.json
```

## Schema reference

`fixtures/schemas/vuln-lookup.schema.json` — validate against this before saving.
