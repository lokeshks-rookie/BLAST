# Bob Sessions — Required Hackathon Deliverable

This folder holds task-session summary screenshots from each team member's
Bob 2.0 runs. Screenshots are a **required deliverable** for the IBM Bob 2.0
Hackathon on LabLab AI.

---

## What to Screenshot

For each Bob run you do, capture **all three** of these:

1. **Task Session Summary panel**
   - In the Bob IDE, at the end of a session, open the "Session Summary" or
     "Task Summary" panel and screenshot the full list of steps Bob took.
   - This shows the judges that Bob was actively used to write and run code,
     not just consulted for ideas.

2. **Subagent output in chat**
   - Screenshot the section of the Bob chat window where one of the five
     subagents (version-diff, vuln-lookup, usage-impact, fix-verify,
     risk-rank) returned its JSON verdict.
   - Crop to show the output clearly. You don't need the full window.

3. **Execute permission in action**
   - Screenshot any moment where Bob ran a terminal command, applied a patch,
     or pushed a branch — confirming Bob's Execute permission was active.

---

## File Naming Convention

```
bob_sessions/
  <your-name>/
    <YYYY-MM-DD>_<short-description>.png

Examples:
  bob_sessions/lokesh/
    2026-09-27_version-diff-subagent-output.png
    2026-09-27_fix-verify-patch-applied.png
    2026-09-27_session-summary-phase10.png
```

- Use lowercase with hyphens, no spaces.
- One subfolder per team member — do NOT mix names.
- Every screenshot must be a real run, not a staged re-creation.

---

## Minimum Required Screenshots (per person)

| # | What | When to Capture |
|---|------|-----------------|
| 1 | Bob session summary (full list of steps) | End of every Phase 10/11 run |
| 2 | A subagent returning structured JSON | During Phase 10 live Bob run |
| 3 | Orchestrator verdict printed in terminal | During Phase 11 rehearsal |
| 4 | Voice bridge speaking a verdict (or TTS log) | During Phase 11 rehearsal |
| 5 | Push confirmation banner before git push | During Phase 11 rehearsal |

---

## After the Demo

Once screenshots are captured, add a one-line description comment inside
each team member's subfolder `README.md` (or this file) listing which file
covers which deliverable requirement.
