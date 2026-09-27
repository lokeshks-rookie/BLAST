"""Blast Radius — Fix-Verify Auto-Patch & Test-Rerun Harness.

Takes a proposed patch, presents it for explicit developer confirmation
(CLI prompt or voice callback), applies it on a scratch branch via git apply,
reruns the repository's test suite, and reports verifiable results.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


class FixVerifyError(Exception):
    """Raised when fix-verify harness encounters an error."""


class FixVerifyHarness:
    """Harness that guides proposed patches through confirmation, scratch-branch application, and test verification."""

    def __init__(self, repo_dir: Path, target_dir_rel: Optional[str] = None):
        self.repo_dir = repo_dir.resolve()
        self.target_dir_rel = target_dir_rel or ""

    def present_patch(self, patch_data: dict) -> None:
        """Display the proposed patch clearly to the developer."""
        print("\n========================================================")
        print("          BLAST RADIUS — PROPOSED PATCH REVIEW          ")
        print("========================================================")
        print(f"Package:       {patch_data.get('package_name', 'N/A')}")
        print(f"Target API:    {patch_data.get('affected_api', 'N/A')}")
        print(f"Patch Type:    {patch_data.get('patch_type', 'N/A')}")
        print(f"Files to Edit: {', '.join(patch_data.get('files_modified', []))}")
        print(f"Description:   {patch_data.get('description', 'N/A')}")
        print("--------------------------------------------------------")
        print("Unified Diff:")
        diff = patch_data.get("diff") or "(No diff content provided)"
        print(diff.strip())
        print("--------------------------------------------------------")
        test_cmds = patch_data.get("test_commands", [])
        if test_cmds:
            print("Verification commands to rerun:")
            for cmd in test_cmds:
                print(f"  $ {cmd}")
        print("========================================================\n")

    def request_confirmation(
        self,
        prompt_text: str = "Apply this patch to a scratch branch and rerun tests? [y/N]: ",
        confirm_callback: Optional[Callable[[], bool]] = None,
        auto_confirm: bool = False,
    ) -> bool:
        """Explicit confirmation gate.

        By default, requires explicit user confirmation.
        Never defaults to True unless auto_confirm is explicitly passed
        (which is only enabled by the developer in Phase 8).
        """
        if auto_confirm:
            print("[CONFIRMATION] Auto-confirm explicitly enabled by developer toggle.")
            return True

        if confirm_callback is not None:
            return confirm_callback()

        try:
            choice = input(prompt_text).strip().lower()
            return choice in ("y", "yes")
        except (KeyboardInterrupt, EOFError):
            print("\nAborted by user.")
            return False

    def get_current_branch(self) -> str:
        """Get the current active git branch name."""
        proc = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=self.repo_dir,
            capture_output=True,
            text=True,
            check=True,
        )
        return proc.stdout.strip()

    def create_scratch_branch(self, base_name: str = "blast-radius/scratch-patch") -> str:
        """Create and checkout an isolated scratch branch."""
        timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        scratch_branch = f"{base_name}-{timestamp}"
        print(f"[GIT] Creating scratch verification branch: {scratch_branch}")
        subprocess.run(
            ["git", "checkout", "-b", scratch_branch],
            cwd=self.repo_dir,
            capture_output=True,
            text=True,
            check=True,
        )
        return scratch_branch

    def discard_scratch_branch(self, original_branch: str, scratch_branch: str) -> None:
        """Return to the original branch and discard the scratch branch."""
        print(f"[GIT] Resetting any uncommitted changes on scratch branch...")
        subprocess.run(
            ["git", "checkout", "--", "."],
            cwd=self.repo_dir,
            capture_output=True,
            text=True,
        )
        print(f"[GIT] Returning to original branch '{original_branch}'...")
        subprocess.run(
            ["git", "checkout", original_branch],
            cwd=self.repo_dir,
            capture_output=True,
            text=True,
            check=True,
        )
        print(f"[GIT] Deleting scratch branch '{scratch_branch}'...")
        subprocess.run(
            ["git", "branch", "-D", scratch_branch],
            cwd=self.repo_dir,
            capture_output=True,
            text=True,
            check=True,
        )

    def apply_patch(self, diff_text: str) -> Tuple[bool, str]:
        """Apply a unified diff via git apply."""
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".patch", newline="\n", encoding="utf-8") as f:
            f.write(diff_text)
            patch_file = f.name

        try:
            cmd = ["git", "apply", "-v"]
            if self.target_dir_rel:
                cmd.append(f"--directory={self.target_dir_rel}")
            cmd.append(patch_file)

            proc = subprocess.run(cmd, cwd=self.repo_dir, capture_output=True, text=True)
            log = (proc.stdout + "\n" + proc.stderr).strip()
            return proc.returncode == 0, log
        finally:
            if os.path.exists(patch_file):
                os.remove(patch_file)

    def run_test_suite(self, test_commands: List[str], cwd_path: Optional[Path] = None) -> Tuple[bool, List[dict]]:
        """Run the repository test suite and record results."""
        work_dir = cwd_path or (self.repo_dir / self.target_dir_rel if self.target_dir_rel else self.repo_dir)
        results = []
        all_passed = True

        for cmd_str in test_commands:
            print(f"[TEST RUNNER] Executing: {cmd_str} (in {work_dir})")
            start = datetime.datetime.now()
            proc = subprocess.run(
                cmd_str,
                cwd=work_dir,
                shell=True,
                capture_output=True,
                text=True,
            )
            duration_ms = int((datetime.datetime.now() - start).total_seconds() * 1000)

            passed = (proc.returncode == 0)
            if not passed:
                all_passed = False

            results.append({
                "command": cmd_str,
                "exit_code": proc.returncode,
                "passed": passed,
                "duration_ms": duration_ms,
                "stdout": proc.stdout.strip(),
                "stderr": proc.stderr.strip(),
            })

            print(f"  Exit code: {proc.returncode} ({'PASSED' if passed else 'FAILED'}) in {duration_ms}ms")
            if not passed and proc.stderr:
                print(f"  Error details: {proc.stderr[:300]}")

        return all_passed, results

    def verify_patch(
        self,
        patch_data: dict,
        confirm_callback: Optional[Callable[[], bool]] = None,
        auto_confirm: bool = False,
        use_scratch_branch: bool = True,
        keep_scratch_branch: bool = False,
    ) -> dict:
        """Full pipeline: present -> confirm -> scratch branch -> apply -> test -> report."""
        diff_text = patch_data.get("diff")
        if not diff_text or patch_data.get("patch_type") != "mechanical_fix":
            return {
                "status": "skipped_not_mechanical",
                "message": "Patch requires manual review or has no unified diff content.",
                "verified": False,
            }

        # 1. Present the patch
        self.present_patch(patch_data)

        # 2. Explicit Confirmation Gate
        confirmed = self.request_confirmation(
            confirm_callback=confirm_callback,
            auto_confirm=auto_confirm,
        )

        if not confirmed:
            print("\n[VERIFICATION HALTED] Developer did not confirm patch application.")
            return {
                "status": "aborted_user_rejected",
                "message": "Explicit confirmation was denied or not provided.",
                "verified": False,
                "patch_applied": False,
            }

        print("\n[CONFIRMED] Proceeding with isolated scratch verification...")
        original_branch = None
        scratch_branch = None

        if use_scratch_branch:
            try:
                original_branch = self.get_current_branch()
                scratch_branch = self.create_scratch_branch()
            except subprocess.CalledProcessError as err:
                raise FixVerifyError(f"Failed to setup scratch branch: {err}")

        try:
            # 3. Apply the patch
            apply_ok, apply_log = self.apply_patch(diff_text)
            if not apply_ok:
                print(f"[ERROR] Patch failed to apply:\n{apply_log}")
                return {
                    "status": "patch_failed",
                    "message": f"git apply failed: {apply_log}",
                    "verified": False,
                    "patch_applied": False,
                    "apply_log": apply_log,
                }

            print("[GIT] Patch applied cleanly to scratch workspace.")

            # 4. Run test commands
            test_cmds = patch_data.get("test_commands", ["npm test"])
            tests_passed, test_results = self.run_test_suite(test_cmds)

            report = {
                "status": "verified_passed" if tests_passed else "tests_failed",
                "verified": tests_passed,
                "patch_applied": True,
                "scratch_branch": scratch_branch,
                "test_results": test_results,
                "diff": diff_text,
                "files_modified": patch_data.get("files_modified", []),
                "timestamp": datetime.datetime.now().isoformat(),
            }

            if tests_passed:
                print("\n========================================================")
                print("   VERIFICATION SUCCESS: All tests passed with patch!   ")
                print("========================================================\n")
            else:
                print("\n========================================================")
                print("   VERIFICATION FAILED: Test suite failed after patch!  ")
                print("========================================================\n")

            return report

        finally:
            if use_scratch_branch and original_branch and scratch_branch and not keep_scratch_branch:
                try:
                    self.discard_scratch_branch(original_branch, scratch_branch)
                except Exception as err:
                    print(f"Warning: Error cleaning up scratch branch: {err}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Blast Radius Fix-Verify Harness")
    parser.add_argument(
        "--fixture",
        type=str,
        default="fixtures/fix-verify.json",
        help="Path to fix-verify JSON fixture",
    )
    parser.add_argument(
        "--target-dir",
        type=str,
        default="fixtures/demo-repo",
        help="Relative path to target demo repo directory",
    )
    parser.add_argument(
        "--auto-confirm",
        action="store_true",
        help="Explicitly bypass CLI confirmation prompt (use only for automated tests)",
    )
    parser.add_argument(
        "--output-report",
        type=str,
        default="evidence/fix_verification.json",
        help="Output report JSON destination",
    )
    args = parser.parse_args()

    fixture_path = Path(args.fixture)
    if not fixture_path.is_file():
        print(f"Error: Fixture file not found: {fixture_path}", file=sys.stderr)
        sys.exit(1)

    with open(fixture_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    patches = data.get("patches", [])
    if not patches:
        print("No patches found in fixture.", file=sys.stderr)
        sys.exit(1)

    patch_to_verify = patches[0]
    if "package_name" not in patch_to_verify:
        patch_to_verify["package_name"] = data.get("package_name", "axios")
    harness = FixVerifyHarness(
        repo_dir=Path.cwd(),
        target_dir_rel=args.target_dir,
    )

    report = harness.verify_patch(
        patch_to_verify,
        auto_confirm=args.auto_confirm,
        use_scratch_branch=True,
    )

    out_path = Path(args.output_report)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(f"Saved verification report to: {out_path}")

    if not report.get("verified"):
        sys.exit(1)


if __name__ == "__main__":
    main()
