"""Blast Radius — Unit & Integration tests for orchestrator/pipeline.py."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from orchestrator.pipeline import run_pipeline

ROOT = Path(__file__).resolve().parent.parent


def test_pipeline_dry_run_happy_path():
    """Test full pipeline end-to-end rehearsal in dry run mode with auto-confirm."""
    res = run_pipeline(
        input_dir=ROOT / "fixtures",
        demo_repo_dir=ROOT / "fixtures" / "demo-repo",
        target_branch="blast-radius/test-dry-run",
        dry_run=True,
        auto_confirm=True,
        voice_enabled=False,
    )

    assert res.verdict is not None
    assert res.verdict["package_name"] == "axios"
    assert res.verdict["risk_tier"] == "merge-with-patch"
    assert res.voice_confirmed is True
    assert res.patch_verified is True
    assert res.push_confirmed is True
    assert res.pushed is False  # Dry run skipped push
    assert res.elapsed_seconds > 0.0

    # Confirm evidence files were written
    verdict_json = ROOT / "evidence" / "verdict.json"
    verdict_md = ROOT / "evidence" / "verdict.md"
    fix_json = ROOT / "evidence" / "fix_verification.json"

    assert verdict_json.is_file()
    assert verdict_md.is_file()
    assert fix_json.is_file()


def test_pipeline_aborts_cleanly_on_patch_decline():
    """Test that declining patch application stops pipeline cleanly."""
    res = run_pipeline(
        input_dir=ROOT / "fixtures",
        demo_repo_dir=ROOT / "fixtures" / "demo-repo",
        target_branch="blast-radius/test-abort",
        dry_run=True,
        auto_confirm=False,
        voice_enabled=False,
    )

    assert res.verdict is not None
    assert res.patch_verified is False
    assert res.pushed is False


def test_pipeline_evidence_fallback(tmp_path):
    """Test that pipeline gracefully falls back to fixtures if evidence dir is empty."""
    empty_evidence = tmp_path / "empty_evidence"
    empty_evidence.mkdir()

    res = run_pipeline(
        input_dir=empty_evidence,
        demo_repo_dir=ROOT / "fixtures" / "demo-repo",
        target_branch="blast-radius/test-fallback",
        dry_run=True,
        auto_confirm=True,
        voice_enabled=False,
    )

    assert res.verdict is not None
    assert res.verdict["package_name"] == "axios"
    assert res.patch_verified is True
