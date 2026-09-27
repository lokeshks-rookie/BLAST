"""Unit tests for orchestrator/fix_verify.py."""
import json
from pathlib import Path
import pytest

from orchestrator.fix_verify import FixVerifyHarness

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURE_PATH = REPO_ROOT / "fixtures" / "fix-verify.json"
TARGET_DIR_REL = "fixtures/demo-repo"


@pytest.fixture
def patch_data():
    with open(FIXTURE_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    patch = data["patches"][0]
    patch["package_name"] = data.get("package_name", "axios")
    return patch


def test_harness_happy_path(patch_data):
    """Test that a valid patch on scratch branch applies, runs tests, and passes."""
    harness = FixVerifyHarness(repo_dir=REPO_ROOT, target_dir_rel=TARGET_DIR_REL)
    original_branch = harness.get_current_branch()

    report = harness.verify_patch(
        patch_data,
        auto_confirm=True,
        use_scratch_branch=True,
    )

    assert report["verified"] is True
    assert report["status"] == "verified_passed"
    assert report["patch_applied"] is True
    assert len(report["test_results"]) == 2
    assert all(t["passed"] for t in report["test_results"])

    # Confirm we returned to the original branch cleanly
    assert harness.get_current_branch() == original_branch


def test_harness_rejection_halts(patch_data):
    """Test that explicit user rejection immediately halts before touching git."""
    harness = FixVerifyHarness(repo_dir=REPO_ROOT, target_dir_rel=TARGET_DIR_REL)
    original_branch = harness.get_current_branch()

    report = harness.verify_patch(
        patch_data,
        confirm_callback=lambda: False,  # Explicitly rejected
        use_scratch_branch=True,
    )

    assert report["verified"] is False
    assert report["status"] == "aborted_user_rejected"
    assert report["patch_applied"] is False
    assert harness.get_current_branch() == original_branch


def test_harness_failing_tests_reported(patch_data):
    """Test that if a test fails, the harness truthfully reports failure."""
    harness = FixVerifyHarness(repo_dir=REPO_ROOT, target_dir_rel=TARGET_DIR_REL)
    original_branch = harness.get_current_branch()

    # Pass an invalid command that exits with code 1
    bad_patch = dict(patch_data)
    bad_patch["test_commands"] = ['node -e "process.exit(1)"']

    report = harness.verify_patch(
        bad_patch,
        auto_confirm=True,
        use_scratch_branch=True,
    )

    assert report["verified"] is False
    assert report["status"] == "tests_failed"
    assert report["test_results"][0]["passed"] is False
    assert report["test_results"][0]["exit_code"] == 1
    assert harness.get_current_branch() == original_branch


def test_harness_non_mechanical_patch_skipped():
    """Non-mechanical patches requiring manual review are skipped without applying."""
    harness = FixVerifyHarness(repo_dir=REPO_ROOT, target_dir_rel=TARGET_DIR_REL)
    manual_patch = {
        "patch_type": "manual_review_required",
        "diff": None,
        "affected_api": "complexLogic()",
    }

    report = harness.verify_patch(manual_patch)
    assert report["verified"] is False
    assert report["status"] == "skipped_not_mechanical"
