# Vulnerability Lookup Subagent

## Responsibility

Cross-reference the version delta of a dependency against OSV and GitHub Security Advisory (GHSA) databases to identify which CVEs are closed by the bump, which are introduced, and which remain unresolved across both versions.

## Inputs

| Field | Type | Description |
|-------|------|-------------|
| `package_name` | string | The dependency package name (e.g., `axios`, `flask`) |
| `old_version` | string | The currently pinned version before the bump (e.g., `1.4.0`) |
| `new_version` | string | The target version after the bump (e.g., `1.7.2`) |
| `ecosystem` | string | Package ecosystem: `npm`, `pypi`, `go`, `cargo`, `rubygems`, `docker` |

## Execution

This subagent runs via Bob's **Execute permission**. It should:

1. Write and run its own Python script to query vulnerability databases
2. Query the **OSV API** (`https://api.osv.dev/v1/query`) for advisories affecting the package in both the old and new version ranges
3. Query the **GitHub Security Advisory (GHSA)** API for additional coverage
4. Classify each advisory into one of three categories:
   - **Closed**: affects `old_version` but NOT `new_version` (the bump fixes it)
   - **Introduced**: affects `new_version` but NOT `old_version` (the bump introduces it)
   - **Unresolved**: affects BOTH versions (the bump doesn't change it)
5. Return structured output conforming to the schema below

**Important:** Run independently and in parallel with the version-diff subagent — the two draw from unrelated sources.

## Output Schema

| Field | Type | Description |
|-------|------|-------------|
| `package_name` | string | Echo of input package name |
| `old_version` | string | Echo of input old version |
| `new_version` | string | Echo of input new version |
| `ecosystem` | string | Echo of input ecosystem |
| `cves_closed` | array of objects | CVEs fixed by the version bump |
| `cves_closed[].cve_id` | string | CVE identifier (e.g., `CVE-2023-45857`) |
| `cves_closed[].ghsa_id` | string or null | GHSA identifier if available |
| `cves_closed[].summary` | string | One-line description of the vulnerability |
| `cves_closed[].severity` | string | One of: `critical`, `high`, `medium`, `low` |
| `cves_closed[].cvss_score` | number or null | CVSS v3 base score (0.0–10.0), null if unavailable |
| `cves_closed[].affected_range` | string | Version range affected (e.g., `>=1.3.2, <1.6.1`) |
| `cves_closed[].fixed_in` | string | Version that fixes this CVE |
| `cves_closed[].advisory_url` | string | URL to the full advisory |
| `cves_introduced` | array of objects | CVEs introduced by the version bump (same object shape as `cves_closed`) |
| `cves_unresolved` | array of objects | CVEs present in both versions (same object shape as `cves_closed`) |
| `summary` | string | One-paragraph plain-language summary of the vulnerability landscape for this bump |
| `query_timestamp` | string | ISO 8601 timestamp of when the queries were run |

## Example Output

```json
{
  "package_name": "axios",
  "old_version": "1.4.0",
  "new_version": "1.7.2",
  "ecosystem": "npm",
  "cves_closed": [
    {
      "cve_id": "CVE-2023-45857",
      "ghsa_id": "GHSA-wf5p-g6vw-rhxx",
      "summary": "Axios Cross-Site Request Forgery vulnerability due to XSRF-TOKEN cookie exposure in cross-site requests.",
      "severity": "high",
      "cvss_score": 7.1,
      "affected_range": ">=1.3.2, <1.6.1",
      "fixed_in": "1.6.1",
      "advisory_url": "https://github.com/advisories/GHSA-wf5p-g6vw-rhxx"
    }
  ],
  "cves_introduced": [],
  "cves_unresolved": [],
  "summary": "Bumping axios from 1.4.0 to 1.7.2 closes 1 high-severity CVE (CVE-2023-45857, CSRF via XSRF-TOKEN cookie exposure, fixed in 1.6.1). No new CVEs are introduced by this bump, and no CVEs remain unresolved across both versions.",
  "query_timestamp": "2026-09-27T10:30:00Z"
}
```
