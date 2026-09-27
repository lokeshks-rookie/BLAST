"""Blast Radius — GitHub PR Comment Poster.

Posts the orchestrator's rendered Markdown verdict to a GitHub Pull Request
using the GitHub REST API (or dry-runs locally when credentials are absent).
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Optional

# Reconfigure stdout/stderr for Windows console unicode safety
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from dotenv import load_dotenv
import requests

# Load local .env if present
load_dotenv()

BLAST_RADIUS_HEADER_TAG = "<!-- blast-radius-verdict -->"


class GitHubCommentError(Exception):
    """Raised when posting a comment fails."""


def post_or_update_pr_comment(
    repo: str,
    pr_number: int,
    comment_body: str,
    token: Optional[str] = None,
    dry_run: bool = False,
) -> dict:
    """Post or update a PR review comment on GitHub.

    Args:
        repo: 'owner/repo' (e.g., 'lokeshks-rookie/BLAST')
        pr_number: The pull request number
        comment_body: Markdown content of the verdict
        token: GitHub API token (defaults to GITHUB_TOKEN env var)
        dry_run: If True, simulates posting and returns mock response

    Returns:
        dict with status and comment URL/data
    """
    token = token or os.getenv("GITHUB_TOKEN")
    tagged_body = f"{BLAST_RADIUS_HEADER_TAG}\n{comment_body}"

    if dry_run or not token:
        print("[DRY RUN] GitHub token not provided or dry-run requested.")
        print(f"[DRY RUN] Target: {repo}#PR-{pr_number}")
        print(f"[DRY RUN] Comment length: {len(tagged_body)} characters")
        print("[DRY RUN] First 200 chars:\n" + tagged_body[:200] + "...\n")
        return {
            "status": "dry_run",
            "repo": repo,
            "pr_number": pr_number,
            "html_url": f"https://github.com/{repo}/pull/{pr_number}#issuecomment-mock",
        }

    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "Blast-Radius-CI",
    }

    base_url = f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments"

    # 1. Check for existing comment with our tag to update instead of creating duplicates
    existing_comment_id = None
    try:
        get_res = requests.get(base_url, headers=headers, timeout=15)
        if get_res.status_code == 200:
            for item in get_res.json():
                if BLAST_RADIUS_HEADER_TAG in item.get("body", ""):
                    existing_comment_id = item.get("id")
                    break
    except requests.RequestException as err:
        print(f"Warning: Failed to list existing comments ({err}), falling back to creating new.")

    # 2. Update existing comment if found
    if existing_comment_id:
        update_url = f"https://api.github.com/repos/{repo}/issues/comments/{existing_comment_id}"
        patch_res = requests.patch(update_url, headers=headers, json={"body": tagged_body}, timeout=15)
        if patch_res.status_code == 200:
            data = patch_res.json()
            print(f"Successfully updated Blast Radius comment on {repo}#{pr_number}: {data.get('html_url')}")
            return {"status": "updated", "id": existing_comment_id, "html_url": data.get("html_url")}
        else:
            raise GitHubCommentError(
                f"Failed to update comment {existing_comment_id}: HTTP {patch_res.status_code}: {patch_res.text}"
            )

    # 3. Create a new comment
    post_res = requests.post(base_url, headers=headers, json={"body": tagged_body}, timeout=15)
    if post_res.status_code in (200, 201):
        data = post_res.json()
        print(f"Successfully posted Blast Radius comment to {repo}#{pr_number}: {data.get('html_url')}")
        return {"status": "created", "id": data.get("id"), "html_url": data.get("html_url")}
    else:
        raise GitHubCommentError(
            f"Failed to post comment to {repo}#{pr_number}: HTTP {post_res.status_code}: {post_res.text}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Post Blast Radius Verdict to GitHub PR")
    parser.add_argument("--repo", type=str, default=os.getenv("TARGET_REPO", "lokeshks-rookie/BLAST"), help="target repo (owner/name)")
    parser.add_argument("--pr-number", type=int, default=int(os.getenv("PR_NUMBER", "1")), help="PR number")
    parser.add_argument("--comment-file", type=str, default="evidence/verdict.md", help="Path to verdict markdown")
    parser.add_argument("--dry-run", action="store_true", help="Dry run without calling API")
    args = parser.parse_args()

    comment_path = Path(args.comment_file)
    if not comment_path.is_file():
        print(f"Error: Comment file '{comment_path}' not found.", file=sys.stderr)
        sys.exit(1)

    with open(comment_path, "r", encoding="utf-8") as f:
        body = f.read()

    try:
        res = post_or_update_pr_comment(
            repo=args.repo,
            pr_number=args.pr_number,
            comment_body=body,
            dry_run=args.dry_run,
        )
        print(f"Result: {res}")
    except GitHubCommentError as err:
        print(f"Error: {err}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
