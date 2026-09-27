# Blast Radius — Staged Demo Case Specification

## 1. Locked Dependency Bump

| Attribute | Value |
|-----------|-------|
| **Package Name** | `axios` |
| **Ecosystem** | `npm` |
| **Prior Version (Old)** | `1.4.0` |
| **Target Version (New)** | `1.7.2` |
| **Target Repository** | `lokeshks-rookie/BLAST` (demo test harness in `fixtures/demo-repo`) |
| **Demo Manifest** | `package.json` |

---

## 2. Real Historical Vulnerability Closed

- **CVE ID**: `CVE-2023-45857`
- **GHSA ID**: `GHSA-wf5p-g6vw-rhxx`
- **Severity**: High (CVSS v3.1: 7.1)
- **Vulnerability Type**: Cross-Site Request Forgery (CSRF) / Information Disclosure
- **Affected Range**: `>= 1.3.2, < 1.6.0` (fixed in `1.6.0`, patch release `1.6.1`)
- **Root Cause**: When following cross-site redirects, Axios inadvertently exposed the `XSRF-TOKEN` cookie to the redirect destination, allowing malicious cross-origin targets to capture anti-CSRF tokens.
- **Resolution**: Upgrading from `1.4.0` to `1.7.2` completely closes this CVE.
- **Advisory Link**: [GHSA-wf5p-g6vw-rhxx](https://github.com/advisories/GHSA-wf5p-g6vw-rhxx)

---

## 3. Real Breaking Change in the Version Delta

- **Identifier**: `BC-001`
- **Version Introduced**: `1.6.0`
- **Affected API**: `axios.create({ auth })` / Request Config `auth` option
- **Change Type**: `signature_change`
- **Description**: The `auth` config option no longer permits a colon-delimited string (e.g., `auth: 'username:password'`). It strictly enforces an object schema: `{ username: string, password: string }`. Passing a string results in invalid header serialization or runtime type rejection.
- **Old Usage**:
  ```javascript
  const client = axios.create({ auth: credentials }); // where credentials is "user:pass"
  ```
- **New Required Usage**:
  ```javascript
  const [username, password] = credentials.split(':');
  const client = axios.create({ auth: { username, password } });
  ```
- **Deprecation**: `axios.defaults.transformRequest` direct modification is also deprecated in favor of instance-level transforms (planned removal in 2.0.0).

---

## 4. Why This Case Was Chosen for the Demo

1. **Realistic Security vs. Stability Dilemma**:
   - The developer *must* upgrade to eliminate the high-severity CSRF vulnerability (`CVE-2023-45857`).
   - However, standard automated tools (like naive Dependabot PRs) would either blindly merge and break the production login endpoint, or cause the developer to defer the security patch out of fear of breaking changes.

2. **Demonstrates Blast Radius's Multi-Subagent Synthesis**:
   - **`version-diff`**: Extracts the auth signature change and the changelog diff from 1.4.0 to 1.7.2.
   - **`vuln-lookup`**: Queries OSV/GHSA and confirms that `CVE-2023-45857` is closed by the bump, with zero new CVEs introduced.
   - **`usage-impact`**: Pinpoints real call sites in `src/api/client.js` and evaluates reachability (the `/login` call site is exposed to untrusted input).
   - **`fix-verify`**: Recognizes `BC-001` as a mechanical fix, generates a unified diff, and prepares test commands (`npm test`).
   - **`risk-rank`**: Weighs the closed CVE against the fixable breaking change, producing the optimal verdict: `merge-with-patch` (confidence 0.87).

3. **Enables the End-to-End Voice & Auto-Push Workflow**:
   - The user hears the verdict spoken via Bhashini TTS.
   - The user gives voice confirmation ("confirm").
   - The harness applies the patch, verifies the test suite, and automatically pushes a risk-aware commit.
