"""Approve pending workflow runs for a post-release cleanup pull request."""

import os
from urllib.parse import urlparse

from .pr_review import approve_pending_workflow_runs_for_pr


def approve_post_release_workflow_runs(pr_url, repo, token):
    """Approve pending workflow runs for a post-release PR.

    Args:
        pr_url (str): URL of the pull request created by post-release cleanup.
        repo (str): Repository full name (e.g. ``"CCBR/actions"``).
        token (str): GitHub API token with Actions write permission.

    Returns:
        list[int]: IDs of workflow runs approved for the pull request head.

    Raises:
        ValueError: If ``pr_url`` does not end with a numeric pull request ID.
    """
    pr_number = urlparse(pr_url).path.rstrip("/").rsplit("/", 1)[-1]
    if not pr_number.isdecimal():
        raise ValueError(f"Invalid post-release PR URL: {pr_url}")

    approved_run_ids = approve_pending_workflow_runs_for_pr(
        repo=repo,
        pr_number=pr_number,
        token=token,
    )
    return approved_run_ids


def main():
    """Read workflow environment variables and approve pending PR runs."""
    approved_run_ids = approve_post_release_workflow_runs(
        pr_url=os.environ["PR_URL"],
        repo=os.environ["REPO"],
        token=os.environ["GH_TOKEN"],
    )
    print(f"Approved pending workflow runs: {approved_run_ids}")


if __name__ == "__main__":
    main()
