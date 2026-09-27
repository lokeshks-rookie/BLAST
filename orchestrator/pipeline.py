"""Blast Radius — Phase 11: Full Pipeline Integration Test & Live Demo Rehearsal.

Executes the complete Blast Radius chain end-to-end:
  1. Trigger event simulation (Webhook / PR diff bump)
  2. Subagent output ingestion & schema validation
  3. Risk reconciliation & verdict rendering (merge.py)
  4. Voice narration of the verdict (voice/bridge.py)
  5. Voice / developer confirmation gate
  6. Fix-Verify auto-patch & test rerun harness (fix_verify.py)
  7. Push banner rendering with risk-aware commit message (auto_push.py)
  8. Push confirmation gate
  9. Push to disposable demo branch
 10. Wall-clock benchmark timing & before/after comparison metric

Usage:
    python orchestrator/pipeline.py [--dry-run] [--evidence-dir evidence/] [--demo-repo fixtures/demo-repo]
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import sys
import time
from pathlib import Path
from typing import Optional

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from orchestrator.merge import load_fixtures_from_dir, reconcile_verdict
from orchestrator.auto_push import (
    generate_commit_message,
    render_push_banner,
    get_current_branch,
    get_remote_url,
    PushGate,
    GitPusher,
    push_verified_patch,
)
from orchestrator.fix_verify import FixVerifyHarness
from voice.bridge import speak_verdict, voice_confirm


class PipelineResult:
    def __init__(self):
        self.start_time = time.time()
        self.end_time = 0.0
        self.verdict: Optional[dict] = None
        self.voice_confirmed = False
        self.patch_verified = False
        self.push_confirmed = False
        self.pushed = False
        self.elapsed_seconds = 0.0

    def finish(self) -> float:
        self.end_time = time.time()
        self.elapsed_seconds = round(self.end_time - self.start_time, 2)
        return self.elapsed_seconds


def run_pipeline(
    input_dir: Path,
    demo_repo_dir: Path,
    target_branch: str = "blast-radius/rehearsal-demo",
    dry_run: bool = False,
    auto_confirm: bool = False,
    voice_enabled: bool = True,
) -> PipelineResult:
    result = PipelineResult()

    print("\n" + "=" * 64)
    print("      BLAST RADIUS — END-TO-END PIPELINE REHEARSAL")
    print("=" * 64)
    print(f"Timestamp:       {datetime.datetime.now().isoformat()}")
    print(f"Input source:    {input_dir}")
    print(f"Target repo:     {demo_repo_dir}")
    print(f"Demo branch:     {target_branch}")
    print(f"Dry run mode:    {dry_run}")
    print(f"Auto confirm:    {auto_confirm}")
    print("=" * 64 + "\n")

    # -----------------------------------------------------------------------
    # Step 1: Ingestion & Subagent Validation
    # -----------------------------------------------------------------------
    print("[1/6] Ingesting subagent outputs...")
    try:
        vd, vl, ui, fv, rr = load_fixtures_from_dir(input_dir)
        print(f"      Loaded: version-diff, vuln-lookup, usage-impact, fix-verify, risk-rank")
    except Exception as e:
        # Fall back to fixtures/ if evidence/ is empty
        if input_dir != ROOT / "fixtures":
            print(f"      [NOTICE] No outputs in {input_dir}, falling back to fixtures/...")
            vd, vl, ui, fv, rr = load_fixtures_from_dir(ROOT / "fixtures")
        else:
            raise e

    # -----------------------------------------------------------------------
    # Step 2: Risk Reconciliation & Verdict
    # -----------------------------------------------------------------------
    print("\n[2/6] Reconciling risk signals across subagents...")
    verdict = reconcile_verdict(vd, vl, ui, fv, rr)
    result.verdict = verdict

    print(f"      Package:    {verdict['package_name']} ({verdict['old_version']} -> {verdict['new_version']})")
    print(f"      Risk Tier:  {verdict['risk_tier'].upper()}")
    print(f"      Confidence: {verdict['confidence'] * 100:.1f}%")
    print(f"      Has Patch:  {verdict['has_patch']}")

    # Save outputs to evidence/
    evidence_dir = ROOT / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    with open(evidence_dir / "verdict.json", "w", encoding="utf-8") as f:
        json.dump(verdict, f, indent=2)
    with open(evidence_dir / "verdict.md", "w", encoding="utf-8") as f:
        f.write(verdict["markdown_comment"])
    print(f"      Verdict saved to evidence/verdict.json & evidence/verdict.md")

    # -----------------------------------------------------------------------
    # Step 3: Voice Narration of Verdict
    # -----------------------------------------------------------------------
    print("\n[3/6] Spoken Verdict Narration (Bhashini Voice Bridge)...")
    if voice_enabled:
        speak_verdict(verdict)
    else:
        print("      [VOICE] Voice playback disabled for this run.")

    # -----------------------------------------------------------------------
    # Step 4 & 5: Patch Confirmation & Fix-Verify Verification Harness
    # -----------------------------------------------------------------------
    print("\n[4/6] Fix-Verify Confirmation Gate & Patch Application...")
    target_rel = "fixtures/demo-repo"
    harness = FixVerifyHarness(repo_dir=ROOT, target_dir_rel=target_rel)

    patch_data = fv.get("patches", [{}])[0] if fv.get("patches") else {}
    patch_data["package_name"] = fv.get("package_name", "axios")

    def confirm_cb() -> bool:
        if voice_enabled:
            return voice_confirm(prompt_phrase="Say 'confirm' to apply patch, or 'abort':")
        else:
            try:
                choice = input("      Apply patch to scratch branch and rerun tests? [y/N]: ").strip().lower()
                return choice in ("y", "yes")
            except (KeyboardInterrupt, EOFError, OSError):
                return False

    verify_report = harness.verify_patch(
        patch_data,
        confirm_callback=confirm_cb if not auto_confirm else None,
        auto_confirm=auto_confirm,
        use_scratch_branch=True,
    )

    result.voice_confirmed = verify_report.get("patch_applied", False)
    result.patch_verified = verify_report.get("verified", False)

    with open(evidence_dir / "fix_verification.json", "w", encoding="utf-8") as f:
        json.dump(verify_report, f, indent=2)

    if not verify_report.get("verified"):
        print("\n[FAIL] Test suite failed or patch was rejected! Auto-push gate is STRUCTURALLY LOCKED.")
        result.finish()
        return result

    print("\n[5/6] Verification Succeeded: All test suites GREEN on scratch branch.")
    print(f"      Verification report saved to evidence/fix_verification.json")

    # -----------------------------------------------------------------------
    # Step 6: Risk-Aware Commit & Push Gate
    # -----------------------------------------------------------------------
    print("\n[6/6] Auto Git-Push Gate & Confirmation Banner...")
    commit_msg = generate_commit_message(verdict, fv)
    remote_url = get_remote_url(ROOT, "origin")
    banner = render_push_banner(target_branch, remote_url, commit_msg)

    gate = PushGate(always_proceed=auto_confirm)
    proceed = gate.request_push_confirmation(banner)
    result.push_confirmed = proceed

    if not proceed:
        print("\n[CLEAN STOP] Push cancelled by developer. Zero changes pushed.")
        result.finish()
        return result

    if dry_run:
        print("\n[DRY RUN] Verified patch ready. Dry run enabled — skipped remote git push.")
        result.pushed = False
    else:
        print(f"\n[GIT] Pushing verified patch to branch: {target_branch}...")
        pusher = GitPusher(
            repo_dir=ROOT,
            remote="origin",
            push_gate=PushGate(always_proceed=True),
        )
        push_res = pusher.push(
            branch=target_branch,
            commit_message=commit_msg,
        )
        result.pushed = push_res.get("pushed", False)

    elapsed = result.finish()
    print("\n" + "=" * 64)
    print("      BLAST RADIUS REHEARSAL COMPLETE")
    print("=" * 64)
    print(f"Wall-Clock Pipeline Runtime:  {elapsed:.2f} seconds")
    print(f"Equivalent Manual Review:     ~45 minutes")
    print(f"Speedup Factor:               ~{int(2700 / max(elapsed, 0.1))}x faster")
    print(f"Risk Tier Verdict:            {verdict['risk_tier'].upper()}")
    print(f"Confidence:                   {verdict['confidence'] * 100:.1f}%")
    print(f"Tests Verified:               {'PASSED (GREEN)' if result.patch_verified else 'FAILED'}")
    print("=" * 64 + "\n")

    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Blast Radius Full Pipeline Rehearsal")
    parser.add_argument(
        "--input-dir",
        type=str,
        default="evidence",
        help="Directory with subagent JSON files (default: evidence, falls back to fixtures)",
    )
    parser.add_argument(
        "--demo-repo",
        type=str,
        default="fixtures/demo-repo",
        help="Target demo repository folder",
    )
    parser.add_argument(
        "--branch",
        type=str,
        default="blast-radius/rehearsal-demo",
        help="Target demo branch name",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run full rehearsal without actually pushing to remote git",
    )
    parser.add_argument(
        "--auto-confirm",
        action="store_true",
        help="Auto-confirm all confirmation gates for automated rehearsal",
    )
    parser.add_argument(
        "--no-voice",
        action="store_true",
        help="Disable voice playback (for headless or CI environments)",
    )
    args = parser.parse_args()

    in_dir = ROOT / args.input_dir
    demo_dir = ROOT / args.demo_repo

    res = run_pipeline(
        input_dir=in_dir,
        demo_repo_dir=demo_dir,
        target_branch=args.branch,
        dry_run=args.dry_run,
        auto_confirm=args.auto_confirm,
        voice_enabled=not args.no_voice,
    )

    sys.exit(0 if (res.patch_verified and (res.push_confirmed or args.dry_run)) else 1)


if __name__ == "__main__":
    main()
