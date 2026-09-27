# Version-Diff Subagent

## Responsibility

Extract all breaking API changes, deprecations, and notable behavioral changes from the changelog or release notes spanning the old and new pinned versions of a dependency.

## Inputs

| Field | Type | Description |
|-------|------|-------------|
| `package_name` | string | The dependency package name (e.g., `axios`, `flask`, `lodash`) |
| `old_version` | string | The currently pinned version before the bump (e.g., `1.4.0`) |
| `new_version` | string | The target version after the bump (e.g., `1.7.2`) |
| `ecosystem` | string | Package ecosystem: `npm`, `pypi`, `go`, `cargo`, `rubygems`, `docker` |

## Execution

This subagent runs via Bob's **Execute permission**. It should:

1. Write and run its own Python script to fetch the changelog/release notes for the version range
2. Parse the changelog entries between `old_version` and `new_version` (inclusive of new, exclusive of old)
3. Identify and extract breaking changes, deprecations, renamed APIs, changed defaults, and removed features
4. Return structured output conforming to the schema below

**Sources to check (in priority order):**
- GitHub Releases API (`/repos/{owner}/{repo}/releases`)
- CHANGELOG.md / CHANGES.md / HISTORY.md in the package repository
- PyPI / npm registry metadata for release notes

## Output Schema

| Field | Type | Description |
|-------|------|-------------|
| `package_name` | string | Echo of input package name |
| `old_version` | string | Echo of input old version |
| `new_version` | string | Echo of input new version |
| `ecosystem` | string | Echo of input ecosystem |
| `breaking_changes` | array of objects | List of breaking changes found in the version delta |
| `breaking_changes[].id` | string | Unique identifier for this change (e.g., `BC-001`) |
| `breaking_changes[].description` | string | Human-readable description of the breaking change |
| `breaking_changes[].change_type` | string | One of: `api_rename`, `api_removal`, `signature_change`, `default_change`, `behavior_change`, `import_relocation` |
| `breaking_changes[].affected_api` | string | The specific function, class, method, or module affected |
| `breaking_changes[].old_signature` | string or null | Previous API signature/usage (null if not applicable) |
| `breaking_changes[].new_signature` | string or null | New API signature/usage (null if not applicable) |
| `breaking_changes[].migration_notes` | string | How to migrate from old to new usage |
| `breaking_changes[].version_introduced` | string | The specific version in the delta where this change was introduced |
| `deprecations` | array of objects | List of deprecations (not yet removed but warned) |
| `deprecations[].affected_api` | string | The deprecated API surface |
| `deprecations[].description` | string | What is deprecated and the recommended alternative |
| `deprecations[].removal_version` | string or null | Version where removal is planned (null if unspecified) |
| `summary` | string | One-paragraph plain-language summary of the version delta |
| `source_urls` | array of strings | URLs of the changelogs/release notes consulted |

## Example Output

```json
{
  "package_name": "axios",
  "old_version": "1.4.0",
  "new_version": "1.7.2",
  "ecosystem": "npm",
  "breaking_changes": [
    {
      "id": "BC-001",
      "description": "The 'auth' config option no longer accepts a plain string. It now requires an object with 'username' and 'password' fields.",
      "change_type": "signature_change",
      "affected_api": "axios.create({ auth })",
      "old_signature": "auth: 'user:pass'",
      "new_signature": "auth: { username: 'user', password: 'pass' }",
      "migration_notes": "Replace any string-form auth config with the object form: { username, password }.",
      "version_introduced": "1.6.0"
    }
  ],
  "deprecations": [
    {
      "affected_api": "axios.defaults.transformRequest",
      "description": "Direct mutation of defaults.transformRequest is deprecated. Use axios.create() with a custom transformRequest instead.",
      "removal_version": "2.0.0"
    }
  ],
  "summary": "The axios 1.4.0 → 1.7.2 delta includes one breaking change to the auth config format (now requires an object instead of a string) introduced in 1.6.0, and one deprecation of direct defaults mutation planned for removal in 2.0.0.",
  "source_urls": [
    "https://github.com/axios/axios/releases/tag/v1.6.0",
    "https://github.com/axios/axios/blob/main/CHANGELOG.md"
  ]
}
```
