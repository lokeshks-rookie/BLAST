"""Blast Radius — Phase 8: Auto Git-Push Logic & Risk-Aware Commit Messages.

Extends the fix-verify pipeline with:
  1. generate_commit_message()  — builds a risk-aware commit from the risk-rank verdict,
                                   not boilerplate. Every field comes from subagent output.
  2. push_gate()                — branch/repo confirmation banner (printed & optionally spoken)
                                   before every push. NEVER pushes without a banner render.
  3. GitPusher.push()           — full propose→confirm→push flow with two confirmation modes:
                                     - per_push (default): confirmation required every single time
                                     - always_proceed: explicit developer toggle, never set by default
  4. push_verified_patch()      — convenience: attach push to fix_verify.py's confirmed-and-tested
                                   path. Push fires ONLY after tests pass. No route to push on fail.

Credentials come from environment only (GITHUB_TOKEN for remote auth if needed).
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Callable, Optional

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Commit message generator
# ---------------------------------------------------------------------------

def generate_commit_message(
    risk_rank: dict,
    fix_verify: dict,
) -> str:
    """Build a risk-aware, specific commit message from subagent outputs.

    Pulls: package, versions, CVE IDs, breaking-change refs, affected APIs.
    Never produces a generic template with placeholders.

    Args:
        risk_rank: The risk-rank subagent output dict (from risk-rank.json or live).
        fix_verify: The fix-verify subagent output dict (from fix-verify.json or live).

    Returns:
        A conventional-commit style message string.
    """
    pkg = risk_rank.get("package_name", "dependency")
    old_v = risk_rank.get("old_version", "?")
    new_v = risk_rank.get("new_version", "?")
    tier = risk_rank.get("risk_tier", "unknown-tier")
    confidence = risk_rank.get("confidence", 0.0)
    summary = risk_rank.get("summary", "").strip()

    # Gather CVE IDs from findings
    cve_ids = []
    bc_refs = []
    affected_apis = []
    for finding in risk_rank.get("findings", []):
        for ref in finding.get("references", []):
            if ref.startswith("CVE-"):
                cve_ids.append(ref)
            elif ref.startswith("BC-") or ref.startswith("GHSA-"):
                bc_refs.append(ref)

    # Gather affected APIs from fix-verify patches
    for patch in fix_verify.get("patches", []):
        api = patch.get("affected_api", "")
        if api and api not in affected_apis:
            affected_apis.append(api)

    # Build the short subject line (50 chars guideline)
    cve_part = f", closes {', '.join(cve_ids)}" if cve_ids else ""
    bc_part = f" (BC: {', '.join(bc_refs)})" if bc_refs else ""
    api_part = f" in {', '.join(affected_apis)}" if affected_apis else ""

    subject = f"fix: patch {pkg} {old_v}\u2192{new_v}{api_part}{bc_part}{cve_part}"
    # Truncate subject to ~72 chars if necessary
    if len(subject) > 72:
        subject = subject[:69] + "..."

    # Build the body — full reasoning from the risk-rank chain
    body_lines = []
    body_lines.append(f"Risk tier: {tier} (confidence: {confidence:.0%})")
    body_lines.append("")
    if summary:
        # Word-wrap the summary at 72 chars
        words = summary.split()
        line = ""
        for word in words:
            if len(line) + len(word) + 1 > 72:
                body_lines.append(line.rstrip())
                line = word + " "
            else:
                line += word + " "
        if line.strip():
            body_lines.append(line.rstrip())

    body_lines.append("")
    reasoning = risk_rank.get("reasoning_chain", [])
    if reasoning:
        body_lines.append("Reasoning:")
        for step in reasoning:
            body_lines.append(f"  {step}")

    recommended = risk_rank.get("recommended_action", "")
    if recommended:
        body_lines.append("")
        body_lines.append(f"Action: {recommended}")

    # Add closes/fixes trailers
    for cve in cve_ids:
        body_lines.append(f"Closes: {cve}")
    for bc in bc_refs:
        body_lines.append(f"Refs: {bc}")

    return subject + "\n\n" + "\n".join(body_lines)


# ---------------------------------------------------------------------------
# Branch / remote resolution
# ---------------------------------------------------------------------------

def get_current_branch(repo_dir: Path) -> str:
    """Return the current git branch name."""
    proc = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=repo_dir,
        capture_output=True,
        text=True,
        check=True,
    )
    return proc.stdout.strip()


def get_remote_url(repo_dir: Path, remote: str = "origin") -> str:
    """Return the remote URL (e.g. https://github.com/org/repo.git)."""
    try:
        proc = subprocess.run(
            ["git", "remote", "get-url", remote],
            cwd=repo_dir,
            capture_output=True,
            text=True,
            check=True,
        )
        return proc.stdout.strip()
    except subprocess.CalledProcessError:
        return "(remote URL unavailable)"


def render_push_banner(branch: str, remote_url: str, commit_message: str) -> str:
    """Render the full branch/repo confirmation banner as a string.

    Always called before every push — this is a safety invariant.
    The banner text is also the input to the voice layer's speak_status().
    """
    short_msg = commit_message.split("\n")[0]
    banner = (
        "\n"
        "╔══════════════════════════════════════════════════════════════╗\n"
        "║          BLAST RADIUS — GIT PUSH CONFIRMATION               ║\n"
        "╠══════════════════════════════════════════════════════════════╣\n"
        f"║  Branch : {branch:<51} ║\n"
        f"║  Remote : {remote_url:<51} ║\n"
        f"║  Commit : {short_msg:<51} ║\n"
        "╚══════════════════════════════════════════════════════════════╝\n"
    )
    return banner


# ---------------------------------------------------------------------------
# Push gate (confirmation layer)
# ---------------------------------------------------------------------------

class PushGate:
    """Controls whether a push proceeds.

    Two modes:
      - per_push (default): confirmation required before every single push
      - always_proceed: developer explicitly sets this toggle; no auto-default

    Never silently defaults to True. The safety property: no push without consent.
    """

    def __init__(
        self,
        always_proceed: bool = False,
        confirm_callback: Optional[Callable[[str], bool]] = None,
    ) -> None:
        self.always_proceed = always_proceed  # Must be set deliberately, never by default
        self.confirm_callback = confirm_callback

    def request_push_confirmation(
        self,
        banner: str,
        tts_speak: Optional[Callable[[str], None]] = None,
    ) -> bool:
        """Print banner, optionally speak it, then ask for confirmation.

        Returns True only if developer explicitly confirms.
        """
        print(banner)

        # Optionally speak the branch/repo/commit info via Phase 7 bridge
        if tts_speak is not None:
            branch_line = [l for l in banner.split("\n") if "Branch" in l]
            remote_line = [l for l in banner.split("\n") if "Remote" in l]
            commit_line = [l for l in banner.split("\n") if "Commit" in l]
            spoken = " ".join([
                f"Branch: {branch_line[0].split(':',1)[-1].strip(' ║')}" if branch_line else "",
                f"Remote: {remote_line[0].split(':',1)[-1].strip(' ║')}" if remote_line else "",
                f"Commit: {commit_line[0].split(':',1)[-1].strip(' ║')}" if commit_line else "",
            ]).strip()
            try:
                tts_speak(spoken)
            except Exception as err:
                print(f"[PUSH GATE] Voice banner failed: {err}")

        if self.always_proceed:
            print("[PUSH GATE] 'always_proceed' toggle active — proceeding without prompt.")
            print("            (Set explicitly by developer, not by default.)")
            return True

        if self.confirm_callback is not None:
            return self.confirm_callback(banner)

        try:
            answer = input("Push to this branch/remote? [y/N]: ").strip().lower()
            return answer in ("y", "yes")
        except (KeyboardInterrupt, EOFError):
            print("\n[PUSH GATE] Aborted by developer.")
            return False


# ---------------------------------------------------------------------------
# GitPusher: the actual push execution
# ---------------------------------------------------------------------------

class GitPusher:
    """Executes a git commit + push after test-pass gate."""

    def __init__(
        self,
        repo_dir: Path,
        remote: str = "origin",
        push_gate: Optional[PushGate] = None,
    ) -> None:
        self.repo_dir = repo_dir.resolve()
        self.remote = remote
        self.gate = push_gate or PushGate()  # Defaults to per-push confirmation

    def commit(self, commit_message: str, paths: Optional[list] = None) -> str:
        """Stage changed files and create a git commit with the risk-aware message.

        Args:
            commit_message: The full commit message (subject + body).
            paths: Specific paths to stage. If None, stages all tracked changes.

        Returns:
            The new commit SHA.
        """
        if paths:
            subprocess.run(["git", "add", "--"] + paths, cwd=self.repo_dir, check=True,
                           capture_output=True, text=True)
        else:
            subprocess.run(["git", "add", "-u"], cwd=self.repo_dir, check=True,
                           capture_output=True, text=True)

        proc = subprocess.run(
            ["git", "commit", "-m", commit_message],
            cwd=self.repo_dir,
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"git commit failed:\n{proc.stderr.strip()}")

        sha_proc = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=self.repo_dir,
            capture_output=True,
            text=True,
            check=True,
        )
        sha = sha_proc.stdout.strip()
        print(f"[GIT] Committed: {sha[:12]}  {commit_message.split(chr(10))[0]}")
        return sha

    def push(
        self,
        branch: Optional[str] = None,
        commit_message: str = "",
        tts_speak: Optional[Callable[[str], None]] = None,
    ) -> dict:
        """Full propose→banner→confirm→push pipeline.

        SAFETY CONTRACT: This method ALWAYS renders the branch/remote banner.
        There is NO code path that reaches git push without calling push_gate first.

        Returns a result dict with keys: pushed (bool), branch, remote_url, sha.
        """
        branch = branch or get_current_branch(self.repo_dir)
        remote_url = get_remote_url(self.repo_dir, self.remote)
        banner = render_push_banner(branch, remote_url, commit_message)

        confirmed = self.gate.request_push_confirmation(banner, tts_speak=tts_speak)

        if not confirmed:
            print("[PUSH GATE] Push aborted by developer.")
            return {
                "pushed": False,
                "reason": "aborted_by_developer",
                "branch": branch,
                "remote_url": remote_url,
            }

        print(f"[GIT] Pushing branch '{branch}' to '{self.remote}'...")
        proc = subprocess.run(
            ["git", "push", self.remote, branch],
            cwd=self.repo_dir,
            capture_output=True,
            text=True,
        )

        if proc.returncode != 0:
            err = proc.stderr.strip()
            print(f"[GIT] Push failed:\n{err}")
            return {
                "pushed": False,
                "reason": "git_push_failed",
                "error": err,
                "branch": branch,
                "remote_url": remote_url,
            }

        sha_proc = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=self.repo_dir,
            capture_output=True,
            text=True,
        )
        sha = sha_proc.stdout.strip()
        print(f"[GIT] Pushed successfully. HEAD={sha[:12]}")
        return {
            "pushed": True,
            "branch": branch,
            "remote_url": remote_url,
            "sha": sha,
            "commit_subject": commit_message.split("\n")[0],
        }


# ---------------------------------------------------------------------------
# Convenience: push_verified_patch()
# ---------------------------------------------------------------------------

def push_verified_patch(
    verify_report: dict,
    risk_rank: dict,
    fix_verify: dict,
    repo_dir: Path,
    remote: str = "origin",
    always_proceed: bool = False,
    tts_speak: Optional[Callable[[str], None]] = None,
    commit_callback: Optional[Callable[[str], bool]] = None,
) -> dict:
    """Attach auto-push to the end of fix_verify.py's pipeline.

    ONLY fires if verify_report["verified"] is True.
    There is NO code path here that can push on a failing test — the first
    guard is a hard return that makes the push step unreachable.

    Args:
        verify_report:   The dict returned by FixVerifyHarness.verify_patch()
        risk_rank:       The risk-rank subagent's output dict
        fix_verify:      The fix-verify subagent's output dict
        repo_dir:        Path to the git repo root
        remote:          Remote name (default: origin)
        always_proceed:  If True, skip per-push CLI prompt (must be set explicitly)
        tts_speak:       Optional callable — called with banner text for voice output
        commit_callback: Optional callable for confirmation override (testing only)

    Returns:
        dict with push result and commit message.
    """
    # --- HARD GATE: push step is UNREACHABLE when tests fail ---
    if not verify_report.get("verified"):
        status = verify_report.get("status", "unknown")
        print(f"\n[AUTO-PUSH] Push blocked — verification status: '{status}'.")
        print("[AUTO-PUSH] Tests must pass before pushing. Push step is unreachable from this state.")
        return {
            "pushed": False,
            "reason": "tests_did_not_pass",
            "verification_status": status,
        }
    # -----------------------------------------------------------

    commit_msg = generate_commit_message(risk_rank, fix_verify)
    print("\n[AUTO-PUSH] Generated risk-aware commit message:")
    print("─" * 60)
    print(commit_msg)
    print("─" * 60)

    gate = PushGate(
        always_proceed=always_proceed,
        confirm_callback=(lambda banner: commit_callback(banner)) if commit_callback else None,
    )
    pusher = GitPusher(repo_dir=Path(repo_dir), remote=remote, push_gate=gate)

    # Commit the patch files that were applied
    files_modified = verify_report.get("files_modified", [])
    try:
        pusher.commit(commit_msg, paths=files_modified if files_modified else None)
    except RuntimeError as err:
        print(f"[AUTO-PUSH] Commit step failed: {err}")
        return {"pushed": False, "reason": "commit_failed", "error": str(err)}

    result = pusher.push(commit_message=commit_msg, tts_speak=tts_speak)
    result["commit_message"] = commit_msg
    return result


# ---------------------------------------------------------------------------
# CLI entrypoint for standalone testing
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Blast Radius Auto-Push — Standalone Test")
    parser.add_argument("--risk-rank", default="fixtures/risk-rank.json")
    parser.add_argument("--fix-verify", default="fixtures/fix-verify.json")
    parser.add_argument("--mode", choices=["commit-msg", "banner", "push"], default="commit-msg")
    parser.add_argument("--always-proceed", action="store_true",
                        help="Bypass per-push confirmation (explicit developer toggle)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print banner and commit message, skip actual git operations")
    args = parser.parse_args()

    with open(args.risk_rank, "r", encoding="utf-8") as f:
        rr = json.load(f)
    with open(args.fix_verify, "r", encoding="utf-8") as f:
        fv = json.load(f)

    if args.mode == "commit-msg":
        msg = generate_commit_message(rr, fv)
        print("\n--- GENERATED COMMIT MESSAGE ---")
        print(msg)

    elif args.mode == "banner":
        branch = get_current_branch(Path("."))
        remote_url = get_remote_url(Path("."))
        msg = generate_commit_message(rr, fv)
        banner = render_push_banner(branch, remote_url, msg)
        print(banner)

    elif args.mode == "push":
        if args.dry_run:
            branch = get_current_branch(Path("."))
            remote_url = get_remote_url(Path("."))
            msg = generate_commit_message(rr, fv)
            banner = render_push_banner(branch, remote_url, msg)
            print("[DRY RUN] Would display banner:")
            print(banner)
            print("[DRY RUN] Would push after confirmation — no actual git operations.")
        else:
            print("[PUSH MODE] Use push_verified_patch() in combination with fix_verify.py.")
            print("            Standalone push from here requires a verified test report.")
