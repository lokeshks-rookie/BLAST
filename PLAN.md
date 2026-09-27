# Blast Radius — Capability Research & Design Rationale

## Team: Import Claude — IBM Bob 2.0 Hackathon (LabLab AI, Sept 25–27, 2026)

---

## Design Decision

Antigravity builds everything **except** the five subagents' actual detection logic. Bob writes and runs that logic live during the demo, demonstrating its own agentic capability under Application of Technology scoring.

Antigravity is responsible for:
- The repo, the `.bob/` config and skill instructions Bob will read
- The exact input/output contract each subagent must satisfy
- Mock fixtures conforming to that contract
- The orchestrator, GitHub integration, voice bridge, and push logic
- The harness that swaps mock subagent output for real Bob output

This scope boundary ensures every phase through Phase 9 is buildable and testable at zero Bobcoin cost. Bob is only touched starting at Phase 10.

---

## Architecture

See `README.md` for the architecture diagram and `Project_context.md` for the full technical specification.

---

## Phases

| Phase | Description | Status |
|-------|-------------|--------|
| 1 | Repository & Environment Scaffolding | ✅ Complete |
| 2 | Bob Custom Mode, Skills & Rules Authoring | ✅ Complete |
| 3 | Shared Data Contracts & Local Test Fixtures | ✅ Complete |
| 4 | Orchestrator / Merge & Report Engine | ✅ Complete |
| 5 | GitHub Action / Webhook Wrapper | ✅ Complete |
| 6 | Fix-Verify Auto-Patch & Test-Rerun Harness | ✅ Complete |
| 7 | Voice Layer: Bhashini STT/TTS Bridge | ✅ Complete |
| 8 | Auto Git-Push Logic & Risk-Aware Commit Messages | ✅ Complete |
| 9 | Evidence, Bob Sessions & Documentation Scaffolding | ✅ Complete |
| 10 | First Live Bob Integration Run | ✅ Complete |
| 11 | Full Pipeline Integration Test & Rehearsal | ✅ Complete |
| 12 | Final Verification & Submission Packaging | ⬜ Pending |
