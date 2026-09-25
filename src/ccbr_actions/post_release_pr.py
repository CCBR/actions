"""
Helpers for reviewing post-release cleanup pull requests opened by the
``post-release`` action.
"""

import os
import re
import warnings

import requests

from .github import GITHUB_API_URL, github_api_get
from .pr_review import (
    approve_pending_workflow_runs,
    approve_pr,
    enable_auto_merge,
    get_codeowners_content,
    get_last_workflow_run_actor,
    get_pr_files,
    is_pr_approved,
    match_codeowners,
    post_pr_comment,
    request_reviewer,
)

POST_RELEASE_PR_TITLE_PATTERN = re.compile(r"^chore: post-release cleanup for (\S+)$")
DRAFT_RELEASE_WORKFLOW_FILE = "draft-release.yml"
_TOKEN_PATTERN = re.compile(r"\d+(?:[.\-]\d+)*")


def is_post_release_pr(pr_title, pr_sender_type):
    """
    Check whether a PR is a post-release cleanup PR.

    Args:
        pr_title (str): Title of the pull request.
        pr_sender_type (str): Type of the PR sender (e.g. ``"Bot"``).

    Returns:
        bool: ``True`` if the PR title matches the post-release cleanup
        pattern and the sender is a GitHub App (Bot).
    """
    return (
        bool(POST_RELEASE_PR_TITLE_PATTERN.match(pr_title)) and pr_sender_type == "Bot"
    )


def extract_release_tag(pr_title):
    """
    Extract the release tag from a post-release cleanup PR title.

    Args:
        pr_title (str): Title of the pull request.

    Returns:
        str | None: The release tag, or ``None`` if *pr_title* doesn't match
        the expected pattern.
    """
    match = POST_RELEASE_PR_TITLE_PATTERN.match(pr_title)
    return match.group(1) if match else None


def get_release_by_tag(repo, tag, token=None, session=None):
    """
    Fetch a GitHub release by its tag name.

    Args:
        repo (str): Repository full name (e.g. ``"CCBR/actions"``).
        tag (str): Release tag name (e.g. ``"v0.7.1"``).
        token (str, optional): GitHub API token.
        session: Requests-compatible session object for dependency injection.

    Returns:
        dict | None: The release object, or ``None`` if no release with that
        tag exists.
    """
    url = f"{GITHUB_API_URL}/repos/{repo}/releases/tags/{tag}"
    try:
        release = github_api_get(url=url, token=token, session=session)
    except requests.exceptions.RequestException:
        release = None
    return release


def _allowed_basenames(
    version_filepath, citation_filepath, changelog_filepath, description_filepath
):
    """
    Build the set of file basenames a post-release cleanup PR may change.

    Args:
        version_filepath (str): Path to the version file.
        citation_filepath (str): Path to the citation file.
        changelog_filepath (str): Path to the changelog file.
        description_filepath (str): Path to the R DESCRIPTION file.

    Returns:
        set[str]: Allowed file basenames (README files are matched separately
        by prefix).
    """
    return {
        os.path.basename(version_filepath),
        os.path.basename(citation_filepath),
        os.path.basename(changelog_filepath),
        os.path.basename(description_filepath),
        "codemeta.json",
        "NEWS.md",
        "NEWS",
    }


def is_allowed_filename(filename, allowed_basenames):
    """
    Check whether a changed file is allowed in a post-release cleanup PR.

    Args:
        filename (str): Changed file's path, relative to the repo root.
        allowed_basenames (set[str]): Allowed file basenames, from
            [](`~ccbr_actions.post_release_pr._allowed_basenames`).

    Returns:
        bool: ``True`` if *filename*'s basename is allowed, including any
        README file (matched case-insensitively by prefix).
    """
    basename = os.path.basename(filename)
    return basename in allowed_basenames or basename.lower().startswith("readme")


def check_only_allowed_files_changed(pr_files, allowed_basenames):
    """
    Check that every changed file in the PR is an allowed post-release file.

    Args:
        pr_files (list[dict]): File objects as returned by
            [](`~ccbr_actions.pr_review.get_pr_files`).
        allowed_basenames (set[str]): Allowed file basenames, from
            [](`~ccbr_actions.post_release_pr._allowed_basenames`).

    Returns:
        bool: ``True`` if *pr_files* is non-empty and every file is allowed.
    """
    return bool(pr_files) and all(
        is_allowed_filename(f.get("filename", ""), allowed_basenames) for f in pr_files
    )


def _release_bump_values(release_tag, release):
    """
    Build the set of token values allowed as a version/date bump target.

    Args:
        release_tag (str): The release tag name (e.g. ``"v0.7.1"``).
        release (dict): Release object from
            [](`~ccbr_actions.post_release_pr.get_release_by_tag`).

    Returns:
        set[str]: Acceptable new numeric/version tokens, derived from the
        release's tag and its published/created date.
    """
    version = release_tag.lstrip("v")
    values = {release_tag, version, f"{version}-dev"}
    for date_key in ("published_at", "created_at"):
        date_part = (release.get(date_key) or "")[:10]
        if len(date_part) == 10 and date_part[4] == "-" and date_part[7] == "-":
            year, month, day = date_part.split("-")
            values.update({date_part, str(int(year)), str(int(month)), str(int(day))})
    return values


def _split_tokens(line):
    """
    Split a line into its non-numeric text segments and numeric tokens.

    Args:
        line (str): A single diff line's content (without the leading +/-).

    Returns:
        tuple[list[str], list[str]]: The text segments surrounding each
        numeric/version-like token, and the tokens themselves.
    """
    return _TOKEN_PATTERN.split(line), _TOKEN_PATTERN.findall(line)


def _is_valid_bump_line(old_line, new_line, valid_values):
    """
    Check whether a modified line is only a version/date bump.

    Args:
        old_line (str): The removed line's content.
        new_line (str): The added line's content.
        valid_values (set[str]): Acceptable new token values, from
            [](`~ccbr_actions.post_release_pr._release_bump_values`).

    Returns:
        bool: ``True`` if the surrounding text is unchanged and every
        differing numeric token is an acceptable bump value.
    """
    old_text, old_tokens = _split_tokens(old_line)
    new_text, new_tokens = _split_tokens(new_line)
    if old_text != new_text or len(old_tokens) != len(new_tokens):
        result = False
    else:
        result = all(
            old_tok == new_tok or new_tok in valid_values
            for old_tok, new_tok in zip(old_tokens, new_tokens)
        )
    return result


def _is_valid_insertion(new_line, release_version):
    """
    Check whether a pure line insertion is an allowed post-release addition.

    Args:
        new_line (str): The added line's content.
        release_version (str): The release version (without leading ``v``).

    Returns:
        bool: ``True`` if the line is blank or references the release
        version (e.g. a new changelog heading).
    """
    stripped = new_line.strip()
    return not stripped or release_version in new_line


def _flush_diff_buffer(removed_buffer, added_buffer, valid_values, release_version):
    """
    Validate a buffered block of consecutive removed/added diff lines.

    Removed and added lines are paired positionally. Extra removed lines must
    be blank, and extra added lines must be blank or reference the release
    version.

    Args:
        removed_buffer (list[str]): Buffered removed line contents.
        added_buffer (list[str]): Buffered added line contents.
        valid_values (set[str]): Acceptable new token values, from
            [](`~ccbr_actions.post_release_pr._release_bump_values`).
        release_version (str): The release version (without leading ``v``).

    Returns:
        bool: ``True`` if the buffered block only contains valid bumps and/or
        allowed insertions.
    """
    pair_count = min(len(removed_buffer), len(added_buffer))
    pairs_valid = all(
        _is_valid_bump_line(removed_buffer[i], added_buffer[i], valid_values)
        for i in range(pair_count)
    )
    extra_removed_valid = all(not line.strip() for line in removed_buffer[pair_count:])
    extra_added_valid = all(
        _is_valid_insertion(line, release_version) for line in added_buffer[pair_count:]
    )
    return pairs_valid and extra_removed_valid and extra_added_valid


def check_patch_is_version_bump(patch, valid_values, release_version):
    """
    Verify a unified diff patch only contains version/date bump changes.

    Args:
        patch (str): Unified diff patch string for a single file.
        valid_values (set[str]): Acceptable new token values, from
            [](`~ccbr_actions.post_release_pr._release_bump_values`).
        release_version (str): The release version (without leading ``v``),
            allowed in pure line insertions such as a new changelog heading.

    Returns:
        bool: ``True`` if every change in the patch is a valid version/date
        bump or an allowed insertion.
    """
    removed_buffer = []
    added_buffer = []
    is_valid = True
    for line in patch.splitlines():
        if line.startswith(("---", "+++")):
            pass
        elif line.startswith("-"):
            removed_buffer.append(line[1:])
        elif line.startswith("+"):
            added_buffer.append(line[1:])
        else:
            is_valid = (
                _flush_diff_buffer(
                    removed_buffer, added_buffer, valid_values, release_version
                )
                and is_valid
            )
            removed_buffer = []
            added_buffer = []
    is_valid = (
        _flush_diff_buffer(removed_buffer, added_buffer, valid_values, release_version)
        and is_valid
    )
    return is_valid


def check_version_date_bumps(pr_files, valid_values, release_version):
    """
    Verify every changed file's patch is only a version/date bump.

    Args:
        pr_files (list[dict]): File objects as returned by
            [](`~ccbr_actions.pr_review.get_pr_files`).
        valid_values (set[str]): Acceptable new token values, from
            [](`~ccbr_actions.post_release_pr._release_bump_values`).
        release_version (str): The release version (without leading ``v``).

    Returns:
        bool: ``True`` if *pr_files* is non-empty and every file's patch only
        contains valid version/date bumps.
    """
    return bool(pr_files) and all(
        isinstance(f.get("patch"), str)
        and check_patch_is_version_bump(f["patch"], valid_values, release_version)
        for f in pr_files
    )


def determine_post_release_reviewer(
    repo,
    reviewer=None,
    workflow_file=DRAFT_RELEASE_WORKFLOW_FILE,
    token=None,
    session=None,
):
    """
    Determine which GitHub user to request for human review.

    Resolution order:

    1. Use *reviewer* if explicitly provided.
    2. Otherwise, use the actor that triggered the most recent
       *workflow_file* run (typically ``draft-release.yml``).
    3. Otherwise, fall back to the repository's default (catch-all ``*``)
       ``CODEOWNERS`` entry.

    Args:
        repo (str): Repository full name (e.g. ``"CCBR/actions"``).
        reviewer (str, optional): Explicit reviewer override.
        workflow_file (str): Workflow filename used to resolve the triggering
            actor.
        token (str, optional): GitHub API token.
        session: Requests-compatible session object for dependency injection.

    Returns:
        str | None: GitHub username to request as reviewer, or ``None`` if
        none could be determined.
    """
    actor = (
        None
        if reviewer
        else get_last_workflow_run_actor(
            repo, workflow_file, token=token, session=session
        )
    )
    codeowner = None
    if not reviewer and not actor:
        codeowners_content = get_codeowners_content(repo, token=token, session=session)
        owners = match_codeowners(codeowners_content, "") if codeowners_content else []
        codeowner = owners[0] if owners else None
    return reviewer or actor or codeowner


def _collect_failure_reasons(
    is_post_release, release, only_allowed_files, only_valid_bumps, approval_error
):
    """
    Build a list of human-readable reasons a post-release PR needs review.

    Args:
        is_post_release (bool): Whether the PR matches the post-release
            cleanup pattern.
        release (dict | None): The matching GitHub release, or ``None``.
        only_allowed_files (bool): Whether only allowed files were changed.
        only_valid_bumps (bool): Whether all changes were valid version/date
            bumps.
        approval_error (Exception | None): The error raised while attempting
            automatic approval, if any.

    Returns:
        list[str]: Human-readable reasons, in the order they should be
        reported.
    """
    reasons = []
    if not is_post_release:
        reasons.append(
            "the PR title/sender do not match the expected post-release cleanup pattern"
        )
    if release is None:
        reasons.append("no matching GitHub release tag could be found for this PR")
    if release is not None and not only_allowed_files:
        reasons.append(
            "only the version, citation, codemeta, changelog, news, and "
            "readme files should be changed, but other files were modified"
        )
    if release is not None and only_allowed_files and not only_valid_bumps:
        reasons.append(
            "the changes must be limited to version/date bumps matching the "
            "release tag, but other modifications were found"
        )
    if approval_error is not None:
        reasons.append(
            "automatic approval could not be completed because of a GitHub "
            f"API error: {approval_error}"
        )
    return reasons


def _enable_merge_or_comment(repo, pr_number, reviewer, token=None, session=None):
    """
    Enable auto-merge, or post a comment explaining why it could not be enabled.

    Args:
        repo (str): Repository full name (e.g. ``"CCBR/actions"``).
        pr_number (int | str): Pull request number.
        reviewer (str, optional): Reviewer to mention in the failure comment.
        token (str, optional): GitHub API token.
        session: Requests-compatible session object for dependency injection.
    """
    try:
        enable_auto_merge(repo, pr_number, token=token, session=session)
        print("Squash auto-merge enabled successfully")
    except (KeyError, requests.exceptions.RequestException, RuntimeError) as exc:
        reviewer_mention = f"@{reviewer} " if reviewer else ""
        comment = (
            f"{reviewer_mention}CCBR-bot approved this post-release cleanup "
            "PR, but could not enable auto-merge because of a GitHub API "
            f"error: {exc}"
        )
        try:
            post_pr_comment(repo, pr_number, comment, token=token, session=session)
            print("Posted a comment explaining that auto-merge could not be enabled")
        except (requests.exceptions.RequestException, RuntimeError) as comment_exc:
            print(f"Could not post the auto-merge failure comment: {comment_exc}")
            warnings.warn(f"Could not post auto-merge failure comment: {comment_exc}")


def _request_human_review(
    repo, pr_number, reviewer, failed_reasons, token=None, session=None
):
    """
    Post a comment explaining failed conditions and request a human reviewer.

    Args:
        repo (str): Repository full name (e.g. ``"CCBR/actions"``).
        pr_number (int | str): Pull request number.
        reviewer (str, optional): Explicit reviewer override.
        failed_reasons (list[str]): Reasons the PR needs human review, from
            [](`~ccbr_actions.post_release_pr._collect_failure_reasons`).
        token (str, optional): GitHub API token.
        session: Requests-compatible session object for dependency injection.
    """
    reasons_text = "\n".join(f"- {r}" for r in failed_reasons)
    print(f"Reasons requiring human review: {reasons_text.replace(chr(10), '; ')}")
    resolved_reviewer = determine_post_release_reviewer(
        repo, reviewer=reviewer, token=token, session=session
    )
    reviewer_mention = f"@{resolved_reviewer} " if resolved_reviewer else ""
    comment = (
        f"{reviewer_mention}This post-release cleanup PR requires human "
        "review. The changes were too complex for CCBR-bot to automatically "
        f"approve because the following conditions were not met:\n{reasons_text}"
    )
    try:
        response = post_pr_comment(
            repo, pr_number, comment, token=token, session=session
        )
        print(f"Posted human-review comment (HTTP {response.status_code})")
    except (requests.exceptions.RequestException, RuntimeError) as exc:
        print(f"Could not post human-review comment: {exc}")
        warnings.warn(f"Could not post human-review comment: {exc}")
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
            warnings.warn(f"Could not request reviewer {resolved_reviewer!r}: {exc}")
    else:
        print("No reviewer could be resolved")


def _review_post_release_pr(
    repo,
    pr_number,
    reviewer,
    token,
    session,
    version_filepath,
    citation_filepath,
    changelog_filepath,
    description_filepath,
):
    """
    Evaluate and review a post-release cleanup PR that isn't already approved.

    See [](`~ccbr_actions.post_release_pr.review_post_release_pr`) for the
    full policy description.

    Returns:
        bool: ``True`` if the PR was automatically approved, ``False`` if
        human review was requested.
    """
    pr_data = github_api_get(
        url=f"{GITHUB_API_URL}/repos/{repo}/pulls/{pr_number}",
        token=token,
        session=session,
    )
    pr_title = pr_data.get("title", "")
    pr_sender_type = pr_data.get("user", {}).get("type", "")
    head_ref = pr_data.get("head", {}).get("ref", "")
    is_post_release = is_post_release_pr(pr_title, pr_sender_type)
    release_tag = extract_release_tag(pr_title)
    release = (
        get_release_by_tag(repo, release_tag, token=token, session=session)
        if release_tag
        else None
    )

    pr_files = get_pr_files(repo, pr_number, token=token, session=session)
    filenames = [f.get("filename", "<unknown>") for f in pr_files]
    print(f"PR title: {pr_title!r}")
    print(f"PR sender type: {pr_sender_type!r}")
    print(f"Changed files ({len(filenames)}): {', '.join(filenames) or '<none>'}")
    print(f"Matches post-release cleanup PR: {is_post_release}")
    print(f"Release tag from title: {release_tag!r}")
    print(f"Release found on GitHub: {release is not None}")

    allowed_basenames = _allowed_basenames(
        version_filepath, citation_filepath, changelog_filepath, description_filepath
    )
    only_allowed_files = check_only_allowed_files_changed(pr_files, allowed_basenames)
    only_valid_bumps = False
    if only_allowed_files and release is not None:
        valid_values = _release_bump_values(release_tag, release)
        only_valid_bumps = check_version_date_bumps(
            pr_files, valid_values, release_tag.lstrip("v")
        )
    print(f"Only allowed files changed: {only_allowed_files}")
    print(f"Only version/date bumps found: {only_valid_bumps}")

    eligible = (
        is_post_release
        and release is not None
        and only_allowed_files
        and only_valid_bumps
    )
    approval_error = None
    was_auto_approved = False
    if eligible:
        print("Policy result: eligible for automatic approval")
        try:
            approve_pending_workflow_runs(repo, head_ref, token=token, session=session)
            print("Approved pending workflow runs (if any)")
        except (KeyError, requests.exceptions.RequestException, RuntimeError) as exc:
            print(f"Could not approve pending workflow runs: {exc}")
            warnings.warn(f"Could not approve pending workflow runs: {exc}")
        try:
            response = approve_pr(repo, pr_number, token=token, session=session)
            was_auto_approved = True
            print(f"Approval submitted successfully (HTTP {response.status_code})")
        except (KeyError, requests.exceptions.RequestException, RuntimeError) as exc:
            approval_error = exc
            print(f"Approval failed: {exc}")
        if was_auto_approved:
            _enable_merge_or_comment(
                repo, pr_number, reviewer, token=token, session=session
            )

    if not was_auto_approved:
        print("Policy result: automatic approval not performed")
        failed_reasons = _collect_failure_reasons(
            is_post_release,
            release,
            only_allowed_files,
            only_valid_bumps,
            approval_error,
        )
        _request_human_review(
            repo, pr_number, reviewer, failed_reasons, token=token, session=session
        )
        print("Result: human review requested")
    else:
        print("Result: automatically approved")

    return was_auto_approved


def review_post_release_pr(
    repo,
    pr_number,
    reviewer=None,
    token=None,
    session=None,
    force_review=False,
    version_filepath="VERSION",
    citation_filepath="CITATION.cff",
    changelog_filepath="CHANGELOG.md",
    description_filepath="DESCRIPTION",
):
    """
    Evaluate and review a post-release cleanup pull request.

    Checks whether the PR satisfies three conditions:

    - **Condition 1** – the PR title matches the post-release cleanup
      pattern (``chore: post-release cleanup for <tag>``) and *<tag>*
      corresponds to an actual GitHub release.
    - **Condition 2** – only the version file, citation file, ``codemeta.json``,
      changelog file, news file, and/or readme files were changed.
    - **Condition 3** – every change in those files is a version/date bump
      matching the release tag (or a re-rendered citation snippet in a
      readme file, which is validated the same way).

    When all conditions are met the function approves any pending workflow
    runs on the PR's head branch, approves the PR, and attempts to enable
    squash auto-merge. If auto-merge cannot be enabled, it leaves a comment
    with the GitHub API error. Otherwise it posts a comment explaining why
    the PR needs manual review and requests a human reviewer, resolved via
    [](`~ccbr_actions.post_release_pr.determine_post_release_reviewer`).

    If the PR already has an APPROVED review, no new review is submitted and
    the function returns ``True`` immediately unless *force_review* is true.

    Args:
        repo (str): Repository full name (e.g. ``"CCBR/actions"``).
        pr_number (int | str): Pull request number.
        reviewer (str, optional): GitHub username to request when human
            review is required. If omitted, a reviewer is resolved
            automatically.
        token (str, optional): GitHub API token.
        session: Requests-compatible session object for dependency injection.
        force_review (bool, optional): Re-submit the review and reviewer
            request even when the PR already has an approval. Defaults to
            ``False``.
        version_filepath (str): Path to the version file. Defaults to
            ``"VERSION"``.
        citation_filepath (str): Path to the citation file. Defaults to
            ``"CITATION.cff"``.
        changelog_filepath (str): Path to the changelog file. Defaults to
            ``"CHANGELOG.md"``.
        description_filepath (str): Path to the R DESCRIPTION file, used when
            an R package's version file is the DESCRIPTION file. Defaults to
            ``"DESCRIPTION"``.

    Returns:
        bool: ``True`` if the PR was already approved or was automatically
        approved, ``False`` if human review was requested.
    """
    print(f"Reviewing post-release cleanup PR {repo}#{pr_number}")
    already_approved = not force_review and is_pr_approved(
        repo, pr_number, token=token, session=session
    )
    if already_approved:
        print("Result: PR already has an APPROVED review; no action was taken")
        result = True
    else:
        result = _review_post_release_pr(
            repo,
            pr_number,
            reviewer,
            token,
            session,
            version_filepath,
            citation_filepath,
            changelog_filepath,
            description_filepath,
        )
    return result
