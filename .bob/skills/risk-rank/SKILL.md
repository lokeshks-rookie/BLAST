# Risk-Ranking Subagent

## Responsibility

Produce a single risk-tiered verdict for a dependency bump by combining the outputs of all four preceding subagents, scored by actual reachability from untrusted input — not by raw CVSS score alone.

## Inputs

| Field | Type | Description |
|-------|------|-------------|
| `package_name` | string | The dependency package name |
| `old_version` | string | The old version |
| `new_version` | string | The new version |
| `ecosystem` | string | Package ecosystem |
| `version_diff_output` | object | Complete output from the Version-Diff subagent |
| `vuln_lookup_output` | object | Complete output from the Vulnerability Lookup subagent |
| `usage_impact_output` | object | Complete output from the Usage-Impact subagent |
| `fix_verify_output` | object | Complete output from the Fix-Verify subagent |

## Execution

This subagent runs via Bob's **Execute permission**. It should:

1. Write and run its own Python script (optionally calling watsonx.ai for reachability scoring)
2. Analyze the combined evidence from all four subagents
3. Apply the following ranking logic:
   - **CVE with reachable call sites** → weight heavily (high risk)
   - **CVE with zero call sites** → weight DOWN (low practical risk despite CVE existence)
   - **Breaking change with reachable call sites + no mechanical fix** → high risk
   - **Breaking change with reachable call sites + mechanical fix available** → moderate risk (merge-with-patch)
   - **Breaking change with zero call sites** → low risk
   - **No CVEs + no breaking changes** → safe
4. Produce ONE of three risk tiers:
   - `safe` — no action needed, safe to merge as-is
   - `merge-with-patch` — safe to merge if the attached patch is applied first
   - `do-not-merge` — requires manual review before merging
5. Include a confidence score and the reasoning chain
6. Return structured output conforming to the schema below

**Key rule:** A CVE flagged by vuln-lookup with zero call sites reported by usage-impact should LOWER, not raise, the reported severity. This is the central distinction of Blast Radius.

## Output Schema

| Field | Type | Description |
|-------|------|-------------|
| `package_name` | string | Echo of input package name |
| `old_version` | string | Echo of input old version |
| `new_version` | string | Echo of input new version |
| `ecosystem` | string | Echo of input ecosystem |
| `risk_tier` | string | One of: `safe`, `merge-with-patch`, `do-not-merge` |
| `confidence` | number | Confidence score 0.0–1.0 |
| `summary` | string | One-paragraph human-readable verdict suitable for a PR comment |
| `findings` | array of objects | Individual findings that contributed to the verdict |
| `findings[].finding_type` | string | One of: `cve_reachable`, `cve_unreachable`, `breaking_change_fixable`, `breaking_change_manual`, `breaking_change_no_impact`, `cve_closed` |
| `findings[].severity` | string | One of: `critical`, `high`, `medium`, `low`, `info` |
| `findings[].title` | string | Short title of the finding |
| `findings[].description` | string | Detailed description |
| `findings[].references` | array of strings | CVE IDs, breaking change IDs, or advisory URLs relevant to this finding |
| `findings[].reachable_call_sites` | integer | Number of call sites reachable from untrusted input (0 if not applicable) |
| `findings[].total_call_sites` | integer | Total number of call sites (0 if not applicable) |
| `reasoning_chain` | array of strings | Step-by-step reasoning that led to the risk tier, in order |
| `recommended_action` | string | Specific action the developer should take |
| `has_patch` | boolean | Whether a mechanical fix patch is available from fix-verify |

## Example Output

```json
{
  "package_name": "axios",
  "old_version": "1.4.0",
  "new_version": "1.7.2",
  "ecosystem": "npm",
  "risk_tier": "merge-with-patch",
  "confidence": 0.87,
  "summary": "Bumping axios 1.4.0 → 1.7.2 closes a high-severity CSRF vulnerability (CVE-2023-45857) and introduces one breaking change to the auth config format. The breaking change affects 2 call sites, 1 of which is reachable from untrusted input (the /login endpoint). A mechanical fix is available. Recommend merging with the attached patch applied.",
  "findings": [
    {
      "finding_type": "cve_closed",
      "severity": "info",
      "title": "CVE-2023-45857 closed by this bump",
      "description": "CSRF vulnerability via XSRF-TOKEN cookie exposure is fixed in axios >=1.6.1. This bump to 1.7.2 resolves it.",
      "references": ["CVE-2023-45857", "GHSA-wf5p-g6vw-rhxx"],
      "reachable_call_sites": 0,
      "total_call_sites": 0
    },
    {
      "finding_type": "breaking_change_fixable",
      "severity": "medium",
      "title": "Auth config format change (BC-001) — mechanical fix available",
      "description": "The auth config option now requires an object instead of a string. 2 call sites found, 1 reachable from untrusted input. A mechanical patch is available to migrate both call sites.",
      "references": ["BC-001"],
      "reachable_call_sites": 1,
      "total_call_sites": 2
    }
  ],
  "reasoning_chain": [
    "1. CVE-2023-45857 (high severity) is CLOSED by this bump — positive signal, reduces risk.",
    "2. No new CVEs are introduced — no negative CVE signal.",
    "3. Breaking change BC-001 affects 2 call sites. 1 is reachable from untrusted input (/login handler).",
    "4. Fix-verify provides a mechanical patch for BC-001 — risk is mitigable without manual review.",
    "5. Combined: net positive (CVE closed) with one manageable breaking change. Tier: merge-with-patch."
  ],
  "recommended_action": "Apply the attached patch for BC-001, then run 'npm test' to verify. Once tests pass, this bump is safe to merge.",
  "has_patch": true
}
```
