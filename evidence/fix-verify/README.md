# Fix-Verify Subagent Evidence

Drop the raw JSON output from the Fix-Verify subagent here after Phase 10.

The `fix_verification.json` in the parent `evidence/` folder is the
**harness execution report** (patch apply + test rerun result).
This folder holds the **subagent's proposed patch JSON** itself.

## What this subagent produces

```json
{
  "package_name": "axios",
  "old_version": "1.4.0",
  "new_version": "1.7.2",
  "ecosystem": "npm",
  "patches": [
    {
      "patch_type": "mechanical_fix",
      "affected_api": "...",
      "diff": "--- a/...\n+++ b/...",
      "test_commands": ["npm test"]
    }
  ]
}
```

## File naming

```
<YYYY-MM-DD>_<package>_<old>-to-<new>.json
Example: 2026-09-27_axios_1.4.0-to-1.7.2.json
```

## Schema reference

`fixtures/schemas/fix-verify.schema.json` — validate against this before saving.
