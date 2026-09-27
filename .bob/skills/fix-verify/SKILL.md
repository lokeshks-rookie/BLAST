# Fix-Verify Subagent

## Responsibility

For each mechanical breaking change that has at least one call site in the repository, propose a concrete patch that migrates the code from the old API to the new API — limited to mechanical fixes (renamed parameters, changed defaults, relocated imports), NOT logic rewrites.

## Inputs

| Field | Type | Description |
|-------|------|-------------|
| `package_name` | string | The dependency package name |
| `new_version` | string | The target version after the bump |
| `ecosystem` | string | Package ecosystem |
| `breaking_changes` | array of objects | The `breaking_changes` array from Version-Diff output |
| `impact_results` | array of objects | The `impact_results` array from Usage-Impact output |

## Execution

This subagent runs via Bob's **Execute permission**. It should:

1. Write and run its own Python script to generate patches
2. For each breaking change that has `call_site_count > 0` in `impact_results`:
   - Determine if the change is **mechanically fixable** (renamed parameter, changed default, relocated import) vs. requiring **manual logic review**
   - If mechanically fixable: generate a unified diff patch for each affected call site
   - If not mechanically fixable: flag it as requiring manual review with an explanation
3. Each patch must be a valid unified diff that can be applied with `git apply`
4. **Never auto-apply patches** — this subagent only PROPOSES patches. Application happens only after explicit developer confirmation via the orchestrator's propose → confirm → execute loop.
5. Return structured output conforming to the schema below

**Critical rule:** This subagent does NOT apply any patch. It does NOT run `git apply`. It does NOT modify any files. It only generates the patch content. The orchestrator handles confirmation and application.

## Output Schema

| Field | Type | Description |
|-------|------|-------------|
| `package_name` | string | Echo of input package name |
| `new_version` | string | Echo of input new version |
| `ecosystem` | string | Echo of input ecosystem |
| `patches` | array of objects | One entry per breaking change that has call sites |
| `patches[].breaking_change_id` | string | References `breaking_changes[].id` from Version-Diff output |
| `patches[].affected_api` | string | The API being patched |
| `patches[].patch_type` | string | One of: `mechanical_fix`, `manual_review_required` |
| `patches[].description` | string | What this patch does, in plain language |
| `patches[].diff` | string or null | Unified diff content (null if `patch_type` is `manual_review_required`) |
| `patches[].files_modified` | array of strings | Relative file paths this patch modifies |
| `patches[].manual_review_reason` | string or null | Explanation of why manual review is needed (null if mechanically fixable) |
| `patches[].test_commands` | array of strings | Commands to run to verify the patch doesn't break anything |
| `total_mechanical_fixes` | integer | Count of patches with type `mechanical_fix` |
| `total_manual_review` | integer | Count of patches requiring manual review |
| `summary` | string | One-paragraph summary of all proposed patches |

## Example Output

```json
{
  "package_name": "axios",
  "new_version": "1.7.2",
  "ecosystem": "npm",
  "patches": [
    {
      "breaking_change_id": "BC-001",
      "affected_api": "axios.create({ auth })",
      "patch_type": "mechanical_fix",
      "description": "Migrate auth config from string format to object format with username and password fields.",
      "diff": "--- a/src/api/client.js\n+++ b/src/api/client.js\n@@ -40,3 +40,3 @@\n function createAuthenticatedClient(credentials) {\n-  const client = axios.create({ auth: credentials });\n+  const client = axios.create({ auth: { username: credentials.split(':')[0], password: credentials.split(':')[1] } });\n   return client;\n",
      "files_modified": [
        "src/api/client.js"
      ],
      "manual_review_reason": null,
      "test_commands": [
        "npm test",
        "npm run test:integration"
      ]
    }
  ],
  "total_mechanical_fixes": 1,
  "total_manual_review": 0,
  "summary": "1 mechanical fix proposed for the auth config format change (BC-001) affecting src/api/client.js. The patch converts the string-form auth to the required object form. Run 'npm test' after applying to verify."
}
```
