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
    is_pr_approved,
    post_pr_comment,
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
    force_review=False,
):
    """
    Evaluate and review a pre-commit.ci autoupdate pull request.

    Checks whether the PR satisfies two conditions:

    - **Condition 1** – only ``.pre-commit-config.yaml`` was changed.
    - **Condition 2** – the only changes are ``rev:`` version bumps.

    When both conditions are met the function approves the PR, attempts to
    enable squash auto-merge, and returns ``True``. If auto-merge cannot be
    enabled, it leaves a separate comment with the GitHub API error. Otherwise
    it submits a *REQUEST_CHANGES* review explaining why the PR needs manual
    review, requests a human reviewer, and returns ``False``. The reviewer is resolved via
    [](`~ccbr_actions.pr_review.determine_reviewer`): *reviewer* if given,
    otherwise the repo's ``CODEOWNERS`` entry for the config file, otherwise
    the most recent human committer to the config file.

    If the PR already has an APPROVED review, no new review is submitted and
    the function returns ``True`` immediately unless *force_review* is true.

    Args:
        repo (str): Repository full name (e.g. ``"CCBR/actions"``).
        pr_number (int | str): Pull request number.
        reviewer (str, optional): GitHub username or team to request when human
            review is required. If omitted, a reviewer is resolved automatically.
        force_review (bool, optional): Re-submit the review and reviewer request
            even when the PR already has an approval. Defaults to ``False``.
        token (str, optional): GitHub API token.
        session: Requests-compatible session object for dependency injection.

    Returns:
        bool: ``True`` if the PR was already approved or was automatically
        approved, ``False`` if human review was requested.
    """
    print(f"Reviewing pre-commit.ci PR {repo}#{pr_number}")
    # Skip PRs that are already approved so re-running (e.g. via workflow_dispatch)
    # doesn't submit duplicate approvals or auto-merge calls.
    if not force_review and is_pr_approved(
        repo, pr_number, token=token, session=session
    ):
        print("Result: PR already has an APPROVED review; no action was taken")
        return True

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
    filenames = [file_obj.get("filename", "<unknown>") for file_obj in pr_files]
    print(f"PR title: {pr_data.get('title', '<missing>')!r}")
    print(f"PR sender type: {pr_data.get('user', {}).get('type', '<missing>')!r}")
    print(f"Changed files ({len(filenames)}): {', '.join(filenames) or '<none>'}")
    print(f"Matches pre-commit.ci autoupdate: {is_autoupdate_pr}")

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
    print(f"Only {PRE_COMMIT_CONFIG_FILE} changed: {only_config_changed}")
    print(f"Only rev bumps found: {only_rev_bumps}")

    approval_error = None
    was_auto_approved = False

    if is_autoupdate_pr and only_config_changed and only_rev_bumps:
        print("Policy result: eligible for automatic approval")
        try:
            response = approve_pr(repo, pr_number, token=token, session=session)
            was_auto_approved = True
            print(f"Approval submitted successfully (HTTP {response.status_code})")
        except (KeyError, requests.exceptions.RequestException, RuntimeError) as exc:
            approval_error = exc
            print(f"Approval failed: {exc}")

        if was_auto_approved:
            try:
                enable_auto_merge(repo, pr_number, token=token, session=session)
                print("Squash auto-merge enabled successfully")
            except (
                KeyError,
                requests.exceptions.RequestException,
                RuntimeError,
            ) as exc:
                reviewer_mention = f"@{reviewer} " if reviewer else ""
                comment = (
                    f"{reviewer_mention}CCBR-bot approved this pre-commit.ci "
                    "autoupdate PR, but could not enable auto-merge because of "
                    f"a GitHub API error: {exc}"
                )
                try:
                    post_pr_comment(
                        repo, pr_number, comment, token=token, session=session
                    )
                    print(
                        "Posted a comment explaining that auto-merge could not be enabled"
                    )
                except (
                    requests.exceptions.RequestException,
                    RuntimeError,
                ) as comment_exc:
                    print(
                        f"Could not post the auto-merge failure comment: {comment_exc}"
                    )
                    warnings.warn(
                        f"Could not post auto-merge failure comment: {comment_exc}"
                    )

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
    if approval_error is not None:
        failed.append(
            "automatic approval could not be completed because of a GitHub API "
            f"error: {approval_error}"
        )

    if not was_auto_approved:
        print("Policy result: automatic approval not performed")
        reasons = "\n".join(f"- {r}" for r in failed)
        print(f"Reasons requiring human review: {reasons.replace(chr(10), '; ')}")
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
            response = request_changes(
                repo, pr_number, comment, token=token, session=session
            )
            print(f"Submitted REQUEST_CHANGES review (HTTP {response.status_code})")
        except (requests.exceptions.RequestException, RuntimeError) as exc:
            print(f"Could not submit REQUEST_CHANGES review: {exc}")
            warnings.warn(f"Could not submit request-changes review: {exc}")
        if resolved_reviewer:
            try:
                response = request_reviewer(
                    repo, pr_number, resolved_reviewer, token=token, session=session
                )
                print(
                    f"Requested reviewer {resolved_reviewer!r} "
                    f"(HTTP {response.status_code})"
                )
            except (requests.exceptions.RequestException, RuntimeError) as exc:
                print(f"Could not request reviewer {resolved_reviewer!r}: {exc}")
                warnings.warn(
                    f"Could not request reviewer {resolved_reviewer!r}: {exc}"
                )
        else:
            print("No reviewer could be resolved")
        print("Result: human review requested")
    else:
        print("Result: automatically approved")
    return was_auto_approved
