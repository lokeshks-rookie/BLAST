## ![Merge With Patch](https://img.shields.io/badge/Blast%20Radius-MERGE%20WITH%20PATCH-orange)

**Package:** `axios` | **Delta:** `1.4.0` → `1.7.2` (`npm`)
**Risk Tier:** `MERGE-WITH-PATCH` | **Confidence:** `87%`

### Verdict Summary
Bumping axios 1.4.0 → 1.7.2 closes a high-severity CSRF vulnerability (CVE-2023-45857) and introduces one breaking change to the auth config format. The breaking change affects 2 call sites, 1 of which is reachable from untrusted input (the /login endpoint). A mechanical fix is available. Recommend merging with the attached patch applied.

### Evidence & Findings
| Severity | Finding | Reachability | References |
|:---|:---|:---|:---|
| ℹ️ Info | **CVE-2023-45857 resolved**<br>Axios Cross-Site Request Forgery vulnerability due to XSRF-TOKEN cookie exposure in cross-site requests. (Fixed in 1.6.1). | N/A | `CVE-2023-45857`, `GHSA-wf5p-g6vw-rhxx` |
| 🟡 Medium | **BC-001: axios.create({ auth }) (Patch available)**<br>The 'auth' config option no longer accepts a plain string. It now requires an object with 'username' and 'password' fields. Found 2 call site(s) (1 reachable). Mechanical patch provided. | 1/2 call sites | `BC-001` |

### Reasoning Chain
- Vulnerability CVE-2023-45857 (high severity) is resolved by 1.7.2.
- Breaking change BC-001 affects 2 call site(s). Mechanical patch is available.

### Recommended Action
> Apply the attached patch, run verification tests, then merge.

### Suggested Patch (Unified Diff)
```diff
--- a/src/api/client.js
+++ b/src/api/client.js
@@ -40,3 +40,3 @@
 function createAuthenticatedClient(credentials) {
-  const client = axios.create({ auth: credentials });
+  const client = axios.create({ auth: { username: credentials.split(':')[0], password: credentials.split(':')[1] } });
   return client;
```

**Verification commands to run after applying:**
```bash
npm run test:integration
npm test
```

---
*Generated automatically by **Blast Radius** — Evidence-Grounded Dependency Reviewer.*