# Usage-Impact Subagent

## Responsibility

Identify the exact files and line numbers in the target repository where the APIs affected by a dependency bump's breaking changes are actually called, and assess whether each call site is reachable from untrusted input.

## Inputs

| Field | Type | Description |
|-------|------|-------------|
| `package_name` | string | The dependency package name |
| `ecosystem` | string | Package ecosystem: `npm`, `pypi`, `go`, `cargo`, `rubygems`, `docker` |
| `repo_path` | string | Absolute path to the root of the target repository |
| `breaking_changes` | array of objects | The `breaking_changes` array from the Version-Diff subagent's output — each object contains at minimum `id`, `affected_api`, and `change_type` |

## Execution

This subagent runs via Bob's **Execute permission**. It should:

1. Write and run its own Python script to search the repository
2. For each entry in `breaking_changes`, grep/search the repository for real call sites of `affected_api`
3. For each call site found, determine:
   - The exact file path and line number
   - The function/method containing the call
   - Whether the call site is reachable from untrusted input (HTTP request handlers, user input parsing, deserialization of external data, etc.)
4. Report zero-call-site findings explicitly — a breaking change with zero call sites is a critical signal for the risk-ranking step (it means the breaking change is technically irrelevant to this codebase)
5. Return structured output conforming to the schema below

**Important:** This subagent is what separates Blast Radius from a changelog summarizer. It reports WHERE a function is called in THIS codebase, not just that the function changed.

## Output Schema

| Field | Type | Description |
|-------|------|-------------|
| `package_name` | string | Echo of input package name |
| `ecosystem` | string | Echo of input ecosystem |
| `repo_path` | string | Echo of input repo path |
| `impact_results` | array of objects | One entry per breaking change analyzed |
| `impact_results[].breaking_change_id` | string | References `breaking_changes[].id` from Version-Diff output |
| `impact_results[].affected_api` | string | Echo of the affected API from the breaking change |
| `impact_results[].call_site_count` | integer | Total number of call sites found in the repo |
| `impact_results[].call_sites` | array of objects | Details of each call site |
| `impact_results[].call_sites[].file` | string | Relative file path from repo root |
| `impact_results[].call_sites[].line` | integer | Line number of the call site |
| `impact_results[].call_sites[].column` | integer | Column number (start of the call) |
| `impact_results[].call_sites[].function_context` | string | Name of the enclosing function/method/class |
| `impact_results[].call_sites[].code_snippet` | string | The relevant line(s) of code |
| `impact_results[].call_sites[].reachable_from_untrusted_input` | boolean | Whether this call site is reachable from HTTP handlers, user input, or external data |
| `impact_results[].call_sites[].reachability_reasoning` | string | Brief explanation of why the call site is or is not reachable from untrusted input |
| `summary` | string | One-paragraph plain-language summary of usage impact across all breaking changes |

## Example Output

```json
{
  "package_name": "axios",
  "ecosystem": "npm",
  "repo_path": "/home/user/my-project",
  "impact_results": [
    {
      "breaking_change_id": "BC-001",
      "affected_api": "axios.create({ auth })",
      "call_site_count": 2,
      "call_sites": [
        {
          "file": "src/api/client.js",
          "line": 42,
          "column": 5,
          "function_context": "createAuthenticatedClient",
          "code_snippet": "const client = axios.create({ auth: credentials });",
          "reachable_from_untrusted_input": true,
          "reachability_reasoning": "Called from the /login endpoint handler, which receives credentials from the HTTP request body."
        },
        {
          "file": "scripts/seed-data.js",
          "line": 15,
          "column": 3,
          "function_context": "seedDatabase",
          "code_snippet": "const admin = axios.create({ auth: ADMIN_CREDS });",
          "reachable_from_untrusted_input": false,
          "reachability_reasoning": "Only called from a local CLI seed script, not reachable from any HTTP handler or user input path."
        }
      ]
    }
  ],
  "summary": "The breaking change to axios.create({ auth }) (BC-001) affects 2 call sites in this repo. One is in the authentication client (src/api/client.js:42) and IS reachable from untrusted input via the /login endpoint. The other is in a local seed script and is not reachable. This breaking change requires migration for at least the production call site."
}
```
