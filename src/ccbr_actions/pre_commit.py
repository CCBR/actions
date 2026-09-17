"""
Helpers for reviewing pre-commit.ci autoupdate pull requests.
"""

import re
import warnings

import requests
from packaging.version import InvalidVersion, Version

from .github import GITHUB_API_URL, github_api_get
from .pr_review import (
    approve_pr,
    determine_reviewer,
    enable_auto_merge,
    get_pr_files,
    request_changes,
    request_reviewer,
)

PRE_COMMIT_CI_TITLE = "[pre-commit.ci] pre-commit autoupdate"
PRE_COMMIT_CONFIG_FILE = ".pre-commit-config.yaml"
_REV_PATTERN = re.compile(r"^\s+rev:\s+\S+\s*$")


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
        if line.startswith(("@@", "---", "+++")):
            continue
        if line.startswith(("-", "+")):
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


def review_pre_commit_pr(
    repo,
    pr_number,
    reviewer=None,
    token=None,
    session=None,
):
    """
    Evaluate and review a pre-commit.ci autoupdate pull request.

    Checks whether the PR satisfies two conditions:

    - **Condition 1** – only ``.pre-commit-config.yaml`` was changed.
    - **Condition 2** – the only changes are ``rev:`` version bumps.

    When both conditions are met the function approves the PR, enables squash
    auto-merge, and returns ``True``.  Otherwise it submits a *REQUEST_CHANGES*
    review explaining why the PR needs manual review, requests a human
    reviewer, and returns ``False``.  The reviewer is resolved via
    [](`~ccbr_actions.pr_review.determine_reviewer`): *reviewer* if given,
    otherwise the repo's ``CODEOWNERS`` entry for the config file, otherwise
    the most recent human committer to the config file.

    Args:
        repo (str): Repository full name (e.g. ``"CCBR/actions"``).
        pr_number (int | str): Pull request number.
        reviewer (str, optional): GitHub username or team to request when human
            review is required. If omitted, a reviewer is resolved automatically.
        token (str, optional): GitHub API token.
        session: Requests-compatible session object for dependency injection.

    Returns:
        bool: ``True`` if the PR was automatically approved, ``False`` if human
        review was requested.
    """
    pr_data = github_api_get(
        url=f"{GITHUB_API_URL}/repos/{repo}/pulls/{pr_number}",
        token=token,
        session=session,
    )
    # Re-verify the PR is actually a pre-commit.ci autoupdate PR rather than relying
    # solely on the calling workflow's `if:` gate.
    is_autoupdate_pr = is_pre_commit_autoupdate_pr(
        pr_data.get("title", ""), pr_data.get("user", {}).get("type", "")
    )

    pr_files = get_pr_files(repo, pr_number, token=token, session=session)

    only_config_changed = check_only_pre_commit_config_changed(pr_files)
    only_rev_bumps = False

    if only_config_changed:
        file_obj = next(
            (f for f in pr_files if f.get("filename") == PRE_COMMIT_CONFIG_FILE),
            {},
        )
        patch = file_obj.get("patch")
        only_rev_bumps = (
            isinstance(patch, str) and bool(patch) and check_only_version_bumps(patch)
        )

    auto_approval_error = None
    was_auto_approved = False

    if is_autoupdate_pr and only_config_changed and only_rev_bumps:
        try:
            approve_pr(repo, pr_number, token=token, session=session)
            enable_auto_merge(repo, pr_number, token=token, session=session)
            was_auto_approved = True
        except (KeyError, requests.exceptions.RequestException, RuntimeError) as exc:
            auto_approval_error = exc

    failed = []
    if not is_autoupdate_pr:
        failed.append(
            "the PR title/sender do not match the expected pre-commit.ci "
            "autoupdate bot pattern"
        )
    if not only_config_changed:
        failed.append(
            "only `.pre-commit-config.yaml` should be changed, "
            "but other files were modified"
        )
    if only_config_changed and not only_rev_bumps:
        failed.append(
            "the only changes in `.pre-commit-config.yaml` should be "
            "`rev:` version bumps, but other modifications were found"
        )
    if auto_approval_error is not None:
        failed.append(
            "automatic approval could not be completed because of a GitHub API "
            f"error: {auto_approval_error}"
        )

    if not was_auto_approved:
        reasons = "\n".join(f"- {r}" for r in failed)
        resolved_reviewer = determine_reviewer(
            repo,
            reviewer=reviewer,
            path=PRE_COMMIT_CONFIG_FILE,
            token=token,
            session=session,
        )
        reviewer_mention = f"@{resolved_reviewer} " if resolved_reviewer else ""
        comment = (
            f"{reviewer_mention}This pre-commit.ci autoupdate PR requires human review. "
            f"The changes were too complex for CCBR-bot to automatically approve "
            f"because the following conditions were not met:\n{reasons}"
        )
        try:
            request_changes(repo, pr_number, comment, token=token, session=session)
        except (requests.exceptions.RequestException, RuntimeError) as exc:
            warnings.warn(f"Could not submit request-changes review: {exc}")
        if resolved_reviewer:
            try:
                request_reviewer(
                    repo, pr_number, resolved_reviewer, token=token, session=session
                )
            except (requests.exceptions.RequestException, RuntimeError) as exc:
                warnings.warn(
                    f"Could not request reviewer {resolved_reviewer!r}: {exc}"
                )
    return was_auto_approved
