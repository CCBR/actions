"""
Helpers for reviewing pre-commit.ci autoupdate pull requests.
"""

import re
import warnings

import requests
from packaging.version import InvalidVersion, Version

from .github import GITHUB_API_URL, github_api_get, github_api_post, github_graphql_post

PRE_COMMIT_CI_TITLE = "[pre-commit.ci] pre-commit autoupdate"
PRE_COMMIT_CONFIG_FILE = ".pre-commit-config.yaml"
_REV_PATTERN = re.compile(r"^\s+rev:\s+\S+")


def is_pre_commit_autoupdate_pr(pr_title, pr_sender_type):
    """
    Check whether a PR is a pre-commit.ci autoupdate PR.

    The check passes when the PR title matches the standard pre-commit.ci
    autoupdate title exactly and the sender is a GitHub App (Bot).

    Args:
        pr_title (str): Title of the pull request.
        pr_sender_type (str): Type of the PR sender (e.g. ``"Bot"``).

    Returns:
        bool: ``True`` if the PR looks like a pre-commit.ci autoupdate PR.
    """
    return pr_title == PRE_COMMIT_CI_TITLE and pr_sender_type == "Bot"


def get_pr_files(repo, pr_number, token=None, session=None):
    """
    Return the list of file objects changed in a pull request.

    Args:
        repo (str): Repository full name (e.g. ``"CCBR/actions"``).
        pr_number (int | str): Pull request number.
        token (str, optional): GitHub API token.
        session: Requests-compatible session object for dependency injection.

    Returns:
        list[dict]: File objects from the GitHub pull request files API.
    """
    url = f"{GITHUB_API_URL}/repos/{repo}/pulls/{pr_number}/files"
    return github_api_get(url=url, token=token, session=session)


def check_only_pre_commit_config_changed(pr_files):
    """
    Check that only ``.pre-commit-config.yaml`` was changed in the PR.

    This is *condition 1* from the pre-commit.ci review policy: the only
    file with changes must be ``.pre-commit-config.yaml``.

    Args:
        pr_files (list[dict]): File objects as returned by [](`~ccbr_actions.pre_commit.get_pr_files`).

    Returns:
        bool: ``True`` if the only changed file is ``.pre-commit-config.yaml``.
    """
    filenames = [f["filename"] for f in pr_files]
    return filenames == [PRE_COMMIT_CONFIG_FILE]


def check_only_version_bumps(patch):
    """
    Verify that a diff patch for ``.pre-commit-config.yaml`` contains only ``rev:`` version bumps.

    This is *condition 2* from the pre-commit.ci review policy.  The function
    checks two things:

    1. Every added or removed line in the patch is a ``rev:`` line – no new
       repos, removed repos, or other field changes are present.
    2. Each changed ``rev:`` value is either a newer semantic version or at
       least a different tag/hash than the original.

    Args:
        patch (str): Unified diff patch string for ``.pre-commit-config.yaml``.

    Returns:
        bool: ``True`` if the patch contains only ``rev:`` version bumps.
    """
    removed_revs = []
    added_revs = []

    for line in patch.splitlines():
        if line.startswith("@@") or line.startswith("---") or line.startswith("+++"):
            continue
        if line.startswith("-") or line.startswith("+"):
            content = line[1:]
            if not _REV_PATTERN.match(content):
                return False
            rev_value = content.strip().removeprefix("rev:").strip()
            if line.startswith("-"):
                removed_revs.append(rev_value)
            else:
                added_revs.append(rev_value)

    if len(removed_revs) != len(added_revs):
        return False

    for old_rev, new_rev in zip(removed_revs, added_revs):
        if not _is_version_bumped(old_rev, new_rev):
            return False

    return True


def _is_version_bumped(old_rev, new_rev):
    """
    Return whether *new_rev* represents a version bump relative to *old_rev*.

    Attempts to parse both values as PEP 440 versions (stripping a leading
    ``v`` prefix).  Falls back to a simple inequality check when either value
    cannot be parsed.

    Args:
        old_rev (str): Previous revision tag or hash.
        new_rev (str): New revision tag or hash.

    Returns:
        bool: ``True`` if *new_rev* is newer than (or different from) *old_rev*.
    """
    try:
        old_v = Version(old_rev.lstrip("v"))
        new_v = Version(new_rev.lstrip("v"))
        return new_v > old_v
    except InvalidVersion:
        return old_rev != new_rev


def approve_pr(repo, pr_number, token=None, session=None):
    """
    Submit an *APPROVE* review on a pull request.

    Args:
        repo (str): Repository full name (e.g. ``"CCBR/actions"``).
        pr_number (int | str): Pull request number.
        token (str, optional): GitHub API token.
        session: Requests-compatible session object for dependency injection.

    Returns:
        requests.Response: Response from the GitHub reviews API.
    """
    url = f"{GITHUB_API_URL}/repos/{repo}/pulls/{pr_number}/reviews"
    return github_api_post(
        url=url,
        token=token,
        session=session,
        json={"event": "APPROVE"},
    )


def enable_auto_merge(repo, pr_number, token=None, session=None):
    """
    Enable squash auto-merge on a pull request via the GitHub GraphQL API.

    Args:
        repo (str): Repository full name (e.g. ``"CCBR/actions"``).
        pr_number (int | str): Pull request number.
        token (str, optional): GitHub API token.
        session: Requests-compatible session object for dependency injection.

    Returns:
        dict: Parsed GraphQL response data.

    Raises:
        RuntimeError: If the GraphQL mutation returns errors.
    """
    pr_url = f"{GITHUB_API_URL}/repos/{repo}/pulls/{pr_number}"
    pr_data = github_api_get(url=pr_url, token=token, session=session)
    node_id = pr_data["node_id"]

    mutation = """
    mutation EnableAutoMerge($pullRequestId: ID!, $mergeMethod: PullRequestMergeMethod!) {
      enablePullRequestAutoMerge(input: {
        pullRequestId: $pullRequestId
        mergeMethod: $mergeMethod
      }) {
        pullRequest {
          autoMergeRequest {
            enabledAt
          }
        }
      }
    }
    """
    return github_graphql_post(
        query=mutation,
        variables={"pullRequestId": node_id, "mergeMethod": "SQUASH"},
        token=token,
        session=session,
    )


def request_reviewer(repo, pr_number, reviewer, token=None, session=None):
    """
    Request a reviewer on a pull request.

    Args:
        repo (str): Repository full name (e.g. ``"CCBR/actions"``).
        pr_number (int | str): Pull request number.
        reviewer (str): GitHub username to request as reviewer.
        token (str, optional): GitHub API token.
        session: Requests-compatible session object for dependency injection.

    Returns:
        requests.Response: Response from the GitHub requested reviewers API.
    """
    url = f"{GITHUB_API_URL}/repos/{repo}/pulls/{pr_number}/requested_reviewers"
    return github_api_post(
        url=url,
        token=token,
        session=session,
        json={"reviewers": [reviewer]},
    )


def post_pr_comment(repo, pr_number, comment, token=None, session=None):
    """
    Post a comment on a pull request.

    Args:
        repo (str): Repository full name (e.g. ``"CCBR/actions"``).
        pr_number (int | str): Pull request number.
        comment (str): Comment body text (Markdown supported).
        token (str, optional): GitHub API token.
        session: Requests-compatible session object for dependency injection.

    Returns:
        requests.Response: Response from the GitHub issue comments API.
    """
    url = f"{GITHUB_API_URL}/repos/{repo}/issues/{pr_number}/comments"
    return github_api_post(
        url=url,
        token=token,
        session=session,
        json={"body": comment},
    )


def review_pre_commit_pr(
    repo,
    pr_number,
    reviewer,
    token=None,
    session=None,
):
    """
    Evaluate and review a pre-commit.ci autoupdate pull request.

    Checks whether the PR satisfies two conditions:

    - **Condition 1** – only ``.pre-commit-config.yaml`` was changed.
    - **Condition 2** – the only changes are ``rev:`` version bumps.

    When both conditions are met the function approves the PR, enables squash
    auto-merge, and returns ``True``.  Otherwise it requests *reviewer* as a
    human reviewer, posts a comment explaining why the PR needs manual review,
    and returns ``False``.

    Args:
        repo (str): Repository full name (e.g. ``"CCBR/actions"``).
        pr_number (int | str): Pull request number.
        reviewer (str): GitHub username to assign when human review is required.
        token (str, optional): GitHub API token.
        session: Requests-compatible session object for dependency injection.

    Returns:
        bool: ``True`` if the PR was automatically approved, ``False`` if human
        review was requested.
    """
    pr_files = get_pr_files(repo, pr_number, token=token, session=session)

    condition1 = check_only_pre_commit_config_changed(pr_files)
    condition2 = False

    if condition1:
        patch = next(
            (
                f.get("patch", "")
                for f in pr_files
                if f["filename"] == PRE_COMMIT_CONFIG_FILE
            ),
            "",
        )
        condition2 = check_only_version_bumps(patch)

    if condition1 and condition2:
        approve_pr(repo, pr_number, token=token, session=session)
        enable_auto_merge(repo, pr_number, token=token, session=session)
        return True

    failed = []
    if not condition1:
        failed.append(
            "only `.pre-commit-config.yaml` should be changed, "
            "but other files were modified"
        )
    if not condition2:
        failed.append(
            "the only changes in `.pre-commit-config.yaml` should be "
            "`rev:` version bumps, but other modifications were found"
        )

    reasons = "\n".join(f"- {r}" for r in failed)
    comment = (
        f"@{reviewer} This pre-commit.ci autoupdate PR requires human review. "
        f"The changes were too complex for CCBR-bot to automatically approve "
        f"because the following conditions were not met:\n{reasons}"
    )
    try:
        request_reviewer(repo, pr_number, reviewer, token=token, session=session)
    except (requests.exceptions.RequestException, RuntimeError) as exc:
        warnings.warn(f"Could not request reviewer {reviewer!r}: {exc}")
    post_pr_comment(repo, pr_number, comment, token=token, session=session)
    return False
