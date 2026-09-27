"""Unit tests for GitHub Action workflow and post_comment.py helper."""
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest
import yaml

from orchestrator.post_comment import (
    BLAST_RADIUS_HEADER_TAG,
    GitHubCommentError,
    post_or_update_pr_comment,
)

WORKFLOW_FILE = Path(__file__).resolve().parent.parent / ".github" / "workflows" / "blast-radius.yml"


def test_workflow_yaml_syntax():
    """Verify that blast-radius.yml parses cleanly as valid YAML."""
    assert WORKFLOW_FILE.is_file(), f"Workflow file missing: {WORKFLOW_FILE}"
    with open(WORKFLOW_FILE, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    assert data["name"] == "Blast Radius Reviewer"
    on_block = data.get("on") or data.get(True)
    assert on_block is not None
    assert "pull_request" in on_block
    paths = on_block["pull_request"]["paths"]
    assert "package.json" in paths
    assert "requirements.txt" in paths
    assert "Dockerfile" in paths
    assert ".github/workflows/*.yml" in paths

    # Verify permissions
    perms = data.get("permissions", {})
    assert perms.get("pull-requests") == "write"
    assert perms.get("issues") == "write"


def test_post_comment_dry_run():
    """Dry run mode simulates comment posting without making network calls."""
    res = post_or_update_pr_comment(
        repo="test-owner/test-repo",
        pr_number=42,
        comment_body="### Test Markdown Comment",
        dry_run=True,
    )
    assert res["status"] == "dry_run"
    assert res["repo"] == "test-owner/test-repo"
    assert res["pr_number"] == 42
    assert "issuecomment-mock" in res["html_url"]


@patch("orchestrator.post_comment.requests.get")
@patch("orchestrator.post_comment.requests.post")
def test_post_new_comment_live(mock_post, mock_get):
    """Test creating a new comment via GitHub REST API."""
    mock_get.return_value = MagicMock(status_code=200, json=lambda: [])
    mock_post.return_value = MagicMock(
        status_code=201,
        json=lambda: {"id": 12345, "html_url": "https://github.com/test/repo/pull/1#issuecomment-12345"},
    )

    res = post_or_update_pr_comment(
        repo="test/repo",
        pr_number=1,
        comment_body="## Sample Verdict",
        token="ghp_mock_token_for_testing",
        dry_run=False,
    )

    assert res["status"] == "created"
    assert res["id"] == 12345
    assert mock_post.called
    called_body = mock_post.call_args[1]["json"]["body"]
    assert BLAST_RADIUS_HEADER_TAG in called_body
    assert "## Sample Verdict" in called_body


@patch("orchestrator.post_comment.requests.get")
@patch("orchestrator.post_comment.requests.patch")
def test_update_existing_comment_live(mock_patch, mock_get):
    """Test updating an existing Blast Radius comment on the PR (idempotency)."""
    mock_get.return_value = MagicMock(
        status_code=200,
        json=lambda: [
            {"id": 999, "body": f"Old comment with {BLAST_RADIUS_HEADER_TAG}"}
        ],
    )
    mock_patch.return_value = MagicMock(
        status_code=200,
        json=lambda: {"id": 999, "html_url": "https://github.com/test/repo/pull/1#issuecomment-999"},
    )

    res = post_or_update_pr_comment(
        repo="test/repo",
        pr_number=1,
        comment_body="## Updated Verdict",
        token="ghp_mock_token_for_testing",
        dry_run=False,
    )

    assert res["status"] == "updated"
    assert res["id"] == 999
    assert mock_patch.called
    called_body = mock_patch.call_args[1]["json"]["body"]
    assert "## Updated Verdict" in called_body


@patch("orchestrator.post_comment.requests.get")
@patch("orchestrator.post_comment.requests.post")
def test_post_comment_failure_raises(mock_post, mock_get):
    """Test that HTTP errors from GitHub API raise GitHubCommentError."""
    mock_get.return_value = MagicMock(status_code=200, json=lambda: [])
    mock_post.return_value = MagicMock(status_code=403, text="Bad credentials")

    with pytest.raises(GitHubCommentError) as exc_info:
        post_or_update_pr_comment(
            repo="test/repo",
            pr_number=1,
            comment_body="## Fail",
            token="ghp_invalid_token",
            dry_run=False,
        )
    assert "HTTP 403" in str(exc_info.value)
