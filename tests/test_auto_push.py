"""Unit tests for orchestrator/auto_push.py — Phase 8.

Tests cover:
  - generate_commit_message():  extracts CVEs, BCs, APIs; no boilerplate placeholders
  - render_push_banner():       shows actual branch and remote URL (not hardcoded)
  - PushGate:                   per-push confirmation (default) and always_proceed toggle
  - GitPusher.push():           banner always rendered; aborts on deny; calls confirm
  - push_verified_patch():      hard gate: push is UNREACHABLE when tests fail
"""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, call
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator.auto_push import (
    generate_commit_message,
    render_push_banner,
    get_current_branch,
    get_remote_url,
    PushGate,
    GitPusher,
    push_verified_patch,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

RISK_RANK_FIXTURE = Path("fixtures/risk-rank.json")
FIX_VERIFY_FIXTURE = Path("fixtures/fix-verify.json")


def load_fixture(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture()
def rr():
    return load_fixture(RISK_RANK_FIXTURE)


@pytest.fixture()
def fv():
    return load_fixture(FIX_VERIFY_FIXTURE)


@pytest.fixture()
def passed_verify_report():
    """Simulates a verify_report where tests passed."""
    return {
        "verified": True,
        "status": "verified_passed",
        "patch_applied": True,
        "files_modified": ["src/api/client.js"],
        "test_results": [{"command": "npm test", "passed": True, "exit_code": 0}],
    }


@pytest.fixture()
def failed_verify_report():
    """Simulates a verify_report where tests failed."""
    return {
        "verified": False,
        "status": "tests_failed",
        "patch_applied": True,
        "files_modified": ["src/api/client.js"],
    }


@pytest.fixture()
def aborted_verify_report():
    """Simulates a verify_report where the developer rejected the patch."""
    return {
        "verified": False,
        "status": "aborted_user_rejected",
        "patch_applied": False,
    }


# ---------------------------------------------------------------------------
# generate_commit_message
# ---------------------------------------------------------------------------

class TestGenerateCommitMessage:
    def test_subject_contains_package_and_versions(self, rr, fv):
        msg = generate_commit_message(rr, fv)
        assert "axios" in msg
        assert "1.4.0" in msg
        assert "1.7.2" in msg

    def test_subject_starts_with_fix(self, rr, fv):
        subject = generate_commit_message(rr, fv).split("\n")[0]
        assert subject.startswith("fix:")

    def test_cve_id_in_commit_message(self, rr, fv):
        msg = generate_commit_message(rr, fv)
        assert "CVE-2023-45857" in msg

    def test_breaking_change_ref_in_commit_message(self, rr, fv):
        msg = generate_commit_message(rr, fv)
        assert "BC-001" in msg or "GHSA" in msg or "BC" in msg

    def test_commit_message_no_placeholder_text(self, rr, fv):
        """Message must not contain template placeholders like CVE-XXXX."""
        msg = generate_commit_message(rr, fv)
        assert "CVE-XXXX" not in msg
        assert "<package>" not in msg
        assert "TODO" not in msg

    def test_subject_under_72_chars(self, rr, fv):
        subject = generate_commit_message(rr, fv).split("\n")[0]
        assert len(subject) <= 72, f"Subject too long ({len(subject)} chars): {subject}"

    def test_body_contains_risk_tier(self, rr, fv):
        msg = generate_commit_message(rr, fv)
        assert "merge-with-patch" in msg or "merge with patch" in msg.lower()

    def test_body_contains_confidence(self, rr, fv):
        msg = generate_commit_message(rr, fv)
        assert "87%" in msg or "confidence" in msg.lower()

    def test_body_contains_reasoning(self, rr, fv):
        msg = generate_commit_message(rr, fv)
        assert "CVE-2023-45857" in msg  # part of the reasoning chain

    def test_body_contains_recommended_action(self, rr, fv):
        msg = generate_commit_message(rr, fv)
        assert "npm test" in msg.lower() or "recommended" in msg.lower() or "action" in msg.lower()

    def test_closes_trailer_present(self, rr, fv):
        msg = generate_commit_message(rr, fv)
        assert "Closes: CVE-2023-45857" in msg

    def test_empty_risk_rank_produces_valid_message(self, fv):
        """Handles partial/minimal risk_rank dicts gracefully."""
        minimal_rr = {"package_name": "lodash", "old_version": "4.0", "new_version": "4.17"}
        msg = generate_commit_message(minimal_rr, fv)
        assert "lodash" in msg
        assert "fix:" in msg


# ---------------------------------------------------------------------------
# render_push_banner
# ---------------------------------------------------------------------------

class TestRenderPushBanner:
    def test_banner_contains_branch(self):
        banner = render_push_banner("main", "https://github.com/org/repo.git", "fix: test")
        assert "main" in banner

    def test_banner_contains_remote_url(self):
        banner = render_push_banner("main", "https://github.com/org/repo.git", "fix: test")
        assert "github.com/org/repo" in banner

    def test_banner_contains_commit_subject(self):
        banner = render_push_banner("main", "https://github.com/org/repo.git", "fix: patch axios 1.4->1.7")
        assert "fix: patch axios" in banner

    def test_banner_changes_with_different_branch(self):
        b1 = render_push_banner("main", "https://github.com/org/repo.git", "fix: test")
        b2 = render_push_banner("feature/my-fix", "https://github.com/org/repo.git", "fix: test")
        assert "feature/my-fix" in b2
        assert "feature/my-fix" not in b1

    def test_banner_title_present(self):
        banner = render_push_banner("main", "https://github.com/org/repo.git", "fix: test")
        assert "BLAST RADIUS" in banner
        assert "GIT PUSH CONFIRMATION" in banner


# ---------------------------------------------------------------------------
# PushGate
# ---------------------------------------------------------------------------

class TestPushGate:
    def test_default_mode_is_per_push(self):
        gate = PushGate()
        assert gate.always_proceed is False

    def test_always_proceed_must_be_explicit(self):
        """always_proceed=True must be set deliberately — not the default."""
        gate = PushGate()
        assert gate.always_proceed is False

        gate_explicit = PushGate(always_proceed=True)
        assert gate_explicit.always_proceed is True

    def test_always_proceed_skips_prompt(self, capsys):
        gate = PushGate(always_proceed=True)
        result = gate.request_push_confirmation("BANNER", tts_speak=None)
        assert result is True
        captured = capsys.readouterr()
        assert "always_proceed" in captured.out

    def test_confirm_callback_used_when_provided(self):
        gate = PushGate(confirm_callback=lambda banner: True)
        result = gate.request_push_confirmation("BANNER")
        assert result is True

    def test_confirm_callback_abort(self):
        gate = PushGate(confirm_callback=lambda banner: False)
        result = gate.request_push_confirmation("BANNER")
        assert result is False

    def test_tts_speak_called_with_banner_text(self):
        spoken = []
        gate = PushGate(confirm_callback=lambda b: True)
        gate.request_push_confirmation(
            "║  Branch : main                                            ║\n"
            "║  Remote : https://github.com/org/repo.git                ║\n"
            "║  Commit : fix: test                                       ║\n",
            tts_speak=lambda t: spoken.append(t),
        )
        assert len(spoken) == 1
        assert "main" in spoken[0] or "github" in spoken[0].lower()

    def test_tts_speak_failure_does_not_abort(self):
        gate = PushGate(confirm_callback=lambda b: True)
        # Even if tts_speak raises, push confirmation should still proceed
        result = gate.request_push_confirmation(
            "BANNER",
            tts_speak=lambda t: (_ for _ in ()).throw(RuntimeError("TTS down")),
        )
        assert result is True


# ---------------------------------------------------------------------------
# GitPusher — mocked git commands
# ---------------------------------------------------------------------------

class TestGitPusher:
    def _mock_run(self, returncode=0, stdout="", stderr=""):
        m = MagicMock()
        m.returncode = returncode
        m.stdout = stdout
        m.stderr = stderr
        return m

    def test_banner_always_rendered_before_push(self, tmp_path, capsys):
        """No code path reaches git push without banner being printed.

        The confirm_callback receives the rendered banner text — if the
        banner was NOT rendered before push, the callback would get an empty
        string and return False, causing the test to fail differently.
        """
        banners_seen = []

        def capturing_callback(banner):
            banners_seen.append(banner)
            return True  # Confirm so we can trace execution

        gate = PushGate(confirm_callback=capturing_callback)
        pusher = GitPusher(repo_dir=tmp_path, push_gate=gate)

        with patch("orchestrator.auto_push.get_current_branch", return_value="main"), \
             patch("orchestrator.auto_push.get_remote_url", return_value="https://github.com/x/y.git"), \
             patch("orchestrator.auto_push.subprocess.run") as mock_run:
            # Provide two successful responses: git push + rev-parse HEAD
            mock_run.side_effect = [
                self._mock_run(0, ""),              # git push
                self._mock_run(0, "abc123def456\n"),  # rev-parse HEAD
            ]
            result = pusher.push(branch="main", commit_message="fix: test push")

        # Banner was definitely rendered and passed to the callback
        assert len(banners_seen) == 1
        assert "BLAST RADIUS" in banners_seen[0]
        assert "main" in banners_seen[0]
        assert "github.com/x/y.git" in banners_seen[0]
        assert result["pushed"] is True

    def test_push_aborted_when_gate_denies(self, tmp_path):
        gate = PushGate(confirm_callback=lambda banner: False)
        pusher = GitPusher(repo_dir=tmp_path, push_gate=gate)

        with patch("orchestrator.auto_push.get_current_branch", return_value="main"), \
             patch("orchestrator.auto_push.get_remote_url", return_value="https://github.com/x/y.git"):
            result = pusher.push(branch="main", commit_message="fix: test")

        assert result["pushed"] is False
        assert result["reason"] == "aborted_by_developer"

    def test_push_result_contains_branch_and_remote(self, tmp_path):
        gate = PushGate(confirm_callback=lambda banner: False)
        pusher = GitPusher(repo_dir=tmp_path, push_gate=gate)

        with patch("orchestrator.auto_push.get_current_branch", return_value="feature/test"), \
             patch("orchestrator.auto_push.get_remote_url", return_value="https://github.com/x/y"):
            result = pusher.push(branch="feature/test", commit_message="fix: test")

        assert result["branch"] == "feature/test"
        assert "github.com" in result["remote_url"]


# ---------------------------------------------------------------------------
# push_verified_patch — hard gate tests
# ---------------------------------------------------------------------------

class TestPushVerifiedPatch:
    def test_push_unreachable_when_tests_fail(self, rr, fv, failed_verify_report, tmp_path):
        """When tests failed, push step is unreachable — no git operations possible."""
        result = push_verified_patch(
            verify_report=failed_verify_report,
            risk_rank=rr,
            fix_verify=fv,
            repo_dir=tmp_path,
            always_proceed=True,  # Even if someone sets always_proceed, still blocked
        )
        assert result["pushed"] is False
        assert result["reason"] == "tests_did_not_pass"

    def test_push_unreachable_when_aborted(self, rr, fv, aborted_verify_report, tmp_path):
        """When developer rejected the patch, push step is unreachable."""
        result = push_verified_patch(
            verify_report=aborted_verify_report,
            risk_rank=rr,
            fix_verify=fv,
            repo_dir=tmp_path,
        )
        assert result["pushed"] is False
        assert result["reason"] == "tests_did_not_pass"

    def test_push_unreachable_message_in_output(self, rr, fv, failed_verify_report, tmp_path, capsys):
        push_verified_patch(
            verify_report=failed_verify_report,
            risk_rank=rr,
            fix_verify=fv,
            repo_dir=tmp_path,
        )
        captured = capsys.readouterr()
        assert "unreachable" in captured.out.lower() or "blocked" in captured.out.lower()

    def test_push_proceeds_when_tests_pass_and_confirmed(self, rr, fv, passed_verify_report, tmp_path):
        """When tests pass and developer confirms, push_verified_patch calls git push."""
        commit_banners_seen = []

        def mock_commit_callback(banner):
            commit_banners_seen.append(banner)
            return True  # Confirm

        with patch("orchestrator.auto_push.subprocess.run") as mock_run:
            # Simulate git add, git commit, git push, rev-parse HEAD all succeeding
            mock_run.return_value = MagicMock(returncode=0, stdout="abc123\n", stderr="")
            with patch("orchestrator.auto_push.get_current_branch", return_value="main"), \
                 patch("orchestrator.auto_push.get_remote_url", return_value="https://github.com/x/y.git"):
                result = push_verified_patch(
                    verify_report=passed_verify_report,
                    risk_rank=rr,
                    fix_verify=fv,
                    repo_dir=tmp_path,
                    commit_callback=mock_commit_callback,
                )

        # Banner must have been shown before push was attempted
        assert len(commit_banners_seen) == 1
        assert "BLAST RADIUS" in commit_banners_seen[0]

    def test_commit_message_in_result(self, rr, fv, passed_verify_report, tmp_path):
        """push_verified_patch result always includes the generated commit message."""
        with patch("orchestrator.auto_push.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="deadbeef\n", stderr="")
            with patch("orchestrator.auto_push.get_current_branch", return_value="main"), \
                 patch("orchestrator.auto_push.get_remote_url", return_value="https://github.com/x/y"):
                result = push_verified_patch(
                    verify_report=passed_verify_report,
                    risk_rank=rr,
                    fix_verify=fv,
                    repo_dir=tmp_path,
                    commit_callback=lambda b: True,
                )

        assert "commit_message" in result
        assert "axios" in result["commit_message"]
        assert "CVE-2023-45857" in result["commit_message"]

    def test_always_proceed_still_blocked_by_test_failure(self, rr, fv, failed_verify_report, tmp_path):
        """always_proceed=True cannot bypass the test-failure hard gate."""
        result = push_verified_patch(
            verify_report=failed_verify_report,
            risk_rank=rr,
            fix_verify=fv,
            repo_dir=tmp_path,
            always_proceed=True,
        )
        assert result["pushed"] is False
        assert result["reason"] == "tests_did_not_pass"
