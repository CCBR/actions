"""
Helpers for reviewing post-release cleanup pull requests opened by the
``post-release`` action.
"""

import base64
import json
import os
import re
import warnings

import requests
import yaml

from .github import GITHUB_API_URL, github_api_get
from .pr_review import (
    approve_pending_workflow_runs,
    approve_pr,
    enable_auto_merge,
    get_codeowners_content,
    get_last_workflow_run_actor,
    get_pr_comments,
    get_pr_files,
    is_pr_approved_for_commit,
    match_codeowners,
    post_pr_comment,
    request_reviewer,
)
from .release import get_r_dev_version

POST_RELEASE_PR_TITLE_PATTERN = re.compile(r"^chore: post-release cleanup for (\S+)$")
DRAFT_RELEASE_WORKFLOW_FILE = "draft-release.yml"
_VERSION_TOKEN_PATTERN = re.compile(r"\d+(?:[.\-]\d+)*")


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


def _file_roles(
    version_filepath, citation_filepath, changelog_filepath, description_filepath
):
    """
    Map allowed file basenames to the validator role used to check their bump.

    Args:
        version_filepath (str): Path to the version file.
        citation_filepath (str): Path to the citation file.
        changelog_filepath (str): Path to the changelog file.
        description_filepath (str): Path to the R DESCRIPTION file.

    Returns:
        dict[str, str]: Basename to role (``"version"``, ``"citation"``,
        ``"codemeta"``, ``"changelog"``, or ``"description"``). README files
        are matched separately by prefix and default to the ``"readme"``
        role.
    """
    return {
        os.path.basename(version_filepath): "version",
        os.path.basename(citation_filepath): "citation",
        "codemeta.json": "codemeta",
        os.path.basename(changelog_filepath): "changelog",
        "NEWS.md": "changelog",
        "NEWS": "changelog",
        os.path.basename(description_filepath): "description",
    }


def is_allowed_filename(filename, roles):
    """
    Check whether a changed file is allowed in a post-release cleanup PR.

    Args:
        filename (str): Changed file's path, relative to the repo root.
        roles (dict[str, str]): Allowed file basenames mapped to validator
            roles, from [](`~ccbr_actions.post_release_pr._file_roles`).

    Returns:
        bool: ``True`` if *filename*'s basename is allowed, including any
        README file (matched case-insensitively by prefix).
    """
    basename = os.path.basename(filename)
    return basename in roles or basename.lower().startswith("readme")


def check_only_allowed_files_changed(pr_files, roles):
    """
    Check that every changed file in the PR is an allowed post-release file.

    Args:
        pr_files (list[dict]): File objects as returned by
            [](`~ccbr_actions.pr_review.get_pr_files`).
        roles (dict[str, str]): Allowed file basenames mapped to validator
            roles, from [](`~ccbr_actions.post_release_pr._file_roles`).

    Returns:
        bool: ``True`` if *pr_files* is non-empty and every file is allowed.
    """
    return bool(pr_files) and all(
        is_allowed_filename(f.get("filename", ""), roles) for f in pr_files
    )


def _release_bump_values(release_tag, release):
    """
    Build the set of token values allowed as a version/date bump target.

    Used only for the lenient, prose-oriented readme validator.

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
        line (str): A single line of file content.

    Returns:
        tuple[list[str], list[str]]: The text segments surrounding each
        numeric/version-like token, and the tokens themselves.
    """
    return _VERSION_TOKEN_PATTERN.split(line), _VERSION_TOKEN_PATTERN.findall(line)


def _is_valid_bump_line(old_line, new_line, valid_values):
    """
    Check whether a modified line is only a version/date bump.

    Args:
        old_line (str): The line's previous content.
        new_line (str): The line's new content.
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


def _get_file_content(repo, path, ref, token=None, session=None):
    """
    Fetch a file's decoded text content at a specific git ref.

    Args:
        repo (str): Repository full name (e.g. ``"CCBR/actions"``).
        path (str): File path, relative to the repo root.
        ref (str): Git ref (commit SHA, branch, or tag) to read the file at.
        token (str, optional): GitHub API token.
        session: Requests-compatible session object for dependency injection.

    Returns:
        str | None: Decoded file content, or ``None`` if the file doesn't
        exist at *ref* or its content couldn't be decoded.
    """
    url = f"{GITHUB_API_URL}/repos/{repo}/contents/{path}"
    try:
        data = github_api_get(
            url=url, token=token, session=session, params={"ref": ref}
        )
    except requests.exceptions.RequestException:
        data = None
    content = None
    if isinstance(data, dict) and isinstance(data.get("content"), str):
        try:
            content = base64.b64decode(data["content"]).decode("utf-8")
        except (ValueError, UnicodeDecodeError):
            content = None
    return content


def _validate_version_file(new_content, release_version):
    """
    Check that a plain version file was bumped to the expected dev version.

    Args:
        new_content (str | None): The file's content at the PR's head.
        release_version (str): The release version (without leading ``v``).

    Returns:
        bool: ``True`` if *new_content* is exactly ``"{release_version}-dev"``.
    """
    return (
        isinstance(new_content, str) and new_content.strip() == f"{release_version}-dev"
    )


def _validate_description_file(old_content, new_content, release_version):
    """
    Check that an R ``DESCRIPTION`` file's ``Version:`` field was bumped.

    Args:
        old_content (str | None): The file's content at the PR's base.
        new_content (str | None): The file's content at the PR's head.
        release_version (str): The release version (without leading ``v``).

    Returns:
        bool: ``True`` if the only change is the ``Version:`` line, bumped to
        the R development version (``X.Y.Z.9000``).
    """
    if not isinstance(old_content, str) or not isinstance(new_content, str):
        result = False
    else:
        try:
            expected_version = get_r_dev_version(release_version)
        except ValueError:
            expected_version = None
        old_lines = old_content.splitlines()
        new_lines = new_content.splitlines()
        if expected_version is None or len(old_lines) != len(new_lines):
            result = False
        else:
            diffs = [
                (old_line, new_line)
                for old_line, new_line in zip(old_lines, new_lines)
                if old_line != new_line
            ]
            result = (
                len(diffs) == 1
                and diffs[0][0].startswith("Version:")
                and diffs[0][1] == f"Version: {expected_version}"
            )
    return result


def _validate_citation_file(old_content, new_content, release_tag):
    """
    Check that a ``CITATION.cff`` file's version/date fields were bumped.

    Args:
        old_content (str | None): The file's content at the PR's base.
        new_content (str | None): The file's content at the PR's head.
        release_tag (str): The release tag (e.g. ``"v0.7.1"``).

    Returns:
        bool: ``True`` if only ``version``/``date-released`` changed, the new
        version equals *release_tag*, and the new date is a valid
        ``YYYY-MM-DD`` string.
    """
    try:
        old_data = yaml.safe_load(old_content) if old_content else {}
        new_data = yaml.safe_load(new_content) if new_content else {}
    except yaml.YAMLError:
        old_data, new_data = None, None
    if not isinstance(old_data, dict) or not isinstance(new_data, dict):
        result = False
    else:
        exempt_keys = {"version", "date-released"}
        unchanged_keys = (set(old_data) | set(new_data)) - exempt_keys
        fields_unchanged = all(
            old_data.get(k) == new_data.get(k) for k in unchanged_keys
        )
        new_date = new_data.get("date-released")
        version_ok = new_data.get("version") == release_tag
        date_ok = bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(new_date)))
        result = fields_unchanged and version_ok and date_ok
    return result


def _validate_codemeta_file(new_content, release_version, release_tag):
    """
    Check that ``codemeta.json``'s version field (if present) matches the release.

    Args:
        new_content (str | None): The file's content at the PR's head.
        release_version (str): The release version (without leading ``v``).
        release_tag (str): The release tag (e.g. ``"v0.7.1"``).

    Returns:
        bool: ``True`` if *new_content* is valid JSON and its ``version``
        field (if any) matches the release.
    """
    try:
        new_data = json.loads(new_content) if new_content else None
    except (json.JSONDecodeError, TypeError):
        new_data = None
    if not isinstance(new_data, dict):
        result = False
    else:
        version_field = new_data.get("version")
        result = version_field is None or version_field in (
            release_version,
            release_tag,
            f"v{release_version}",
        )
    return result


def _validate_changelog_file(old_content, new_content, release_version, dev_header):
    """
    Check that a changelog/news file only gained a new release heading.

    The only allowed change is a two-line insertion (a heading referencing
    *release_version*, followed by a blank line) placed immediately after the
    development-version header; everything else must be unchanged.

    Args:
        old_content (str | None): The file's content at the PR's base.
        new_content (str | None): The file's content at the PR's head.
        release_version (str): The release version (without leading ``v``).
        dev_header (str): Development-version header text to locate (matched
            case-insensitively).

    Returns:
        bool: ``True`` if the only change is the expected heading insertion.
    """
    if not isinstance(old_content, str) or not isinstance(new_content, str):
        result = False
    else:
        old_lines = old_content.splitlines(keepends=True)
        new_lines = new_content.splitlines(keepends=True)
        dev_header_index = next(
            (
                i
                for i, line in enumerate(old_lines)
                if line.lstrip().startswith("#") and dev_header.lower() in line.lower()
            ),
            None,
        )
        if dev_header_index is None:
            result = False
        else:
            insert_at = dev_header_index + 1
            if insert_at < len(old_lines) and not old_lines[insert_at].strip():
                insert_at += 1
            inserted = new_lines[insert_at : insert_at + 2]
            heading_pattern = re.compile(
                r"^#+\s+\S.*\b" + re.escape(release_version) + r"\b.*$"
            )
            rebuilt = old_lines[:insert_at] + inserted + old_lines[insert_at:]
            result = (
                len(new_lines) == len(old_lines) + 2
                and len(inserted) == 2
                and bool(heading_pattern.match(inserted[0].rstrip("\n")))
                and not inserted[1].strip()
                and rebuilt == new_lines
            )
    return result


def _validate_readme_file(old_content, new_content, valid_values):
    """
    Check that a readme file's changes are only version/date token bumps.

    No lines may be inserted or removed; each changed line must differ from
    its previous content only in numeric/version-like tokens.

    Args:
        old_content (str | None): The file's content at the PR's base.
        new_content (str | None): The file's content at the PR's head.
        valid_values (set[str]): Acceptable new token values, from
            [](`~ccbr_actions.post_release_pr._release_bump_values`).

    Returns:
        bool: ``True`` if every line is unchanged or a valid token bump.
    """
    if not isinstance(old_content, str) or not isinstance(new_content, str):
        result = False
    else:
        old_lines = old_content.splitlines()
        new_lines = new_content.splitlines()
        result = len(old_lines) == len(new_lines) and all(
            old_line == new_line
            or _is_valid_bump_line(old_line, new_line, valid_values)
            for old_line, new_line in zip(old_lines, new_lines)
        )
    return result


def _validate_file_bump(
    role,
    old_content,
    new_content,
    release_tag,
    release_version,
    dev_header,
    valid_values,
):
    """
    Dispatch to the validator for an allowed file's role.

    Args:
        role (str): One of ``"version"``, ``"description"``, ``"citation"``,
            ``"codemeta"``, ``"changelog"``, or ``"readme"``.
        old_content (str | None): The file's content at the PR's base.
        new_content (str | None): The file's content at the PR's head.
        release_tag (str): The release tag (e.g. ``"v0.7.1"``).
        release_version (str): The release version (without leading ``v``).
        dev_header (str): Development-version header text for changelog files.
        valid_values (set[str]): Acceptable new token values for readme files.

    Returns:
        bool: ``True`` if the file's change is a valid bump for its role.
    """
    if role == "version":
        result = _validate_version_file(new_content, release_version)
    elif role == "description":
        result = _validate_description_file(old_content, new_content, release_version)
    elif role == "citation":
        result = _validate_citation_file(old_content, new_content, release_tag)
    elif role == "codemeta":
        result = _validate_codemeta_file(new_content, release_version, release_tag)
    elif role == "changelog":
        result = _validate_changelog_file(
            old_content, new_content, release_version, dev_header
        )
    else:
        result = _validate_readme_file(old_content, new_content, valid_values)
    return result


def check_files_are_valid_bumps(
    repo,
    filenames,
    roles,
    release_tag,
    release,
    dev_header,
    base_sha,
    head_sha,
    token=None,
    session=None,
):
    """
    Verify every changed file is a valid bump, and that the version file
    itself was actually changed.

    This directly audits that the ``post-release`` action did its job: a PR
    that only touches, say, a readme file without also bumping the version
    file is rejected.

    Args:
        repo (str): Repository full name (e.g. ``"CCBR/actions"``).
        filenames (list[str]): Changed file paths from the PR.
        roles (dict[str, str]): Basename to validator role, from
            [](`~ccbr_actions.post_release_pr._file_roles`).
        release_tag (str): The release tag (e.g. ``"v0.7.1"``).
        release (dict): Release object from
            [](`~ccbr_actions.post_release_pr.get_release_by_tag`).
        dev_header (str): Development-version header text for changelog files.
        base_sha (str): Commit SHA to read "old" file contents at.
        head_sha (str): Commit SHA to read "new" file contents at.
        token (str, optional): GitHub API token.
        session: Requests-compatible session object for dependency injection.

    Returns:
        bool: ``True`` if the version file was among the changed files and
        every changed file's new content is a valid bump for its role.
    """
    release_version = release_tag.lstrip("v")
    valid_values = _release_bump_values(release_tag, release)
    version_basename = next(
        (basename for basename, role in roles.items() if role == "version"), None
    )
    version_bumped = any(
        os.path.basename(filename) == version_basename for filename in filenames
    )
    files_valid = True
    for filename in filenames:
        role = roles.get(os.path.basename(filename), "readme")
        old_content = _get_file_content(
            repo, filename, base_sha, token=token, session=session
        )
        new_content = _get_file_content(
            repo, filename, head_sha, token=token, session=session
        )
        files_valid = (
            _validate_file_bump(
                role,
                old_content,
                new_content,
                release_tag,
                release_version,
                dev_header,
                valid_values,
            )
            and files_valid
        )
    return version_bumped and files_valid


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
    is_post_release,
    release,
    files_complete,
    only_allowed_files,
    only_valid_bumps,
    approval_error,
):
    """
    Build a list of human-readable reasons a post-release PR needs review.

    Args:
        is_post_release (bool): Whether the PR matches the post-release
            cleanup pattern.
        release (dict | None): The matching GitHub release, or ``None``.
        files_complete (bool): Whether the full list of changed files could
            be retrieved (fails closed on a pagination mismatch).
        only_allowed_files (bool): Whether only allowed files were changed.
        only_valid_bumps (bool): Whether the version file was bumped and all
            changes were valid bumps.
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
    if release is not None and not files_complete:
        reasons.append(
            "the full list of changed files could not be verified (a "
            "pagination mismatch was detected), so the PR was not approved"
        )
    if release is not None and files_complete and not only_allowed_files:
        reasons.append(
            "only the version, citation, codemeta, changelog, news, and "
            "readme files should be changed, but other files were modified"
        )
    if release is not None and only_allowed_files and not only_valid_bumps:
        reasons.append(
            "the version file must be bumped and every change must be a "
            "valid version/date bump matching the release tag, but "
            "validation failed"
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


def _human_review_marker(head_sha):
    """
    Build the hidden marker used to detect a prior human-review comment.

    Args:
        head_sha (str): Commit SHA the comment applies to.

    Returns:
        str: An HTML comment embedding *head_sha*, invisible when rendered.
    """
    return f"<!-- ccbr-actions:review-post-release-pr:needs-human-review:{head_sha} -->"


def _has_pending_human_review_comment(
    repo, pr_number, head_sha, token=None, session=None
):
    """
    Check whether a human-review comment was already posted for *head_sha*.

    Args:
        repo (str): Repository full name (e.g. ``"CCBR/actions"``).
        pr_number (int | str): Pull request number.
        head_sha (str): Commit SHA to check for a prior comment.
        token (str, optional): GitHub API token.
        session: Requests-compatible session object for dependency injection.

    Returns:
        bool: ``True`` if an existing comment already carries the marker for
        *head_sha*.
    """
    try:
        comments = get_pr_comments(repo, pr_number, token=token, session=session)
    except requests.exceptions.RequestException:
        comments = []
    marker = _human_review_marker(head_sha)
    return any(marker in (comment.get("body") or "") for comment in comments)


def _request_human_review(
    repo, pr_number, reviewer, failed_reasons, head_sha, token=None, session=None
):
    """
    Post a comment explaining failed conditions and request a human reviewer.

    Args:
        repo (str): Repository full name (e.g. ``"CCBR/actions"``).
        pr_number (int | str): Pull request number.
        reviewer (str, optional): Explicit reviewer override.
        failed_reasons (list[str]): Reasons the PR needs human review, from
            [](`~ccbr_actions.post_release_pr._collect_failure_reasons`).
        head_sha (str): The PR's current head commit SHA, embedded as a
            hidden marker so a later run can detect this comment and avoid
            posting a duplicate for the same commit.
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
        f"\n\n{_human_review_marker(head_sha)}"
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
    dev_header,
    force_review,
    pr_data,
):
    """
    Evaluate and review a post-release cleanup PR that isn't already approved.

    See [](`~ccbr_actions.post_release_pr.review_post_release_pr`) for the
    full policy description.

    Returns:
        bool: ``True`` if the PR was automatically approved, ``False`` if
        human review was requested.
    """
    pr_title = pr_data.get("title", "")
    pr_sender_type = pr_data.get("user", {}).get("type", "")
    head_ref = pr_data.get("head", {}).get("ref", "")
    head_sha = pr_data.get("head", {}).get("sha", "")
    base_sha = pr_data.get("base", {}).get("sha", "")
    expected_file_count = pr_data.get("changed_files")
    is_post_release = is_post_release_pr(pr_title, pr_sender_type)
    release_tag = extract_release_tag(pr_title)
    release = (
        get_release_by_tag(repo, release_tag, token=token, session=session)
        if release_tag
        else None
    )

    pr_files = get_pr_files(repo, pr_number, token=token, session=session)
    filenames = [f.get("filename", "<unknown>") for f in pr_files]
    files_complete = expected_file_count is None or len(pr_files) == expected_file_count
    print(f"PR title: {pr_title!r}")
    print(f"PR sender type: {pr_sender_type!r}")
    print(f"Changed files ({len(filenames)}): {', '.join(filenames) or '<none>'}")
    print(f"Matches post-release cleanup PR: {is_post_release}")
    print(f"Release tag from title: {release_tag!r}")
    print(f"Release found on GitHub: {release is not None}")
    print(f"Full file list retrieved: {files_complete}")

    roles = _file_roles(
        version_filepath, citation_filepath, changelog_filepath, description_filepath
    )
    only_allowed_files = files_complete and check_only_allowed_files_changed(
        pr_files, roles
    )
    only_valid_bumps = False
    if only_allowed_files and release is not None and head_sha and base_sha:
        only_valid_bumps = check_files_are_valid_bumps(
            repo,
            filenames,
            roles,
            release_tag,
            release,
            dev_header,
            base_sha,
            head_sha,
            token=token,
            session=session,
        )
    print(f"Only allowed files changed: {only_allowed_files}")
    print(f"Version bumped and all changes valid: {only_valid_bumps}")

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

        current_pr_data = github_api_get(
            url=f"{GITHUB_API_URL}/repos/{repo}/pulls/{pr_number}",
            token=token,
            session=session,
        )
        current_head_sha = current_pr_data.get("head", {}).get("sha", "")
        if current_head_sha and current_head_sha != head_sha:
            approval_error = RuntimeError(
                "the pull request's head commit changed during review; "
                "aborting automatic approval to avoid approving unreviewed "
                "changes"
            )
            print(f"Aborting approval: {approval_error}")
        else:
            try:
                response = approve_pr(
                    repo, pr_number, token=token, session=session, commit_id=head_sha
                )
                was_auto_approved = True
                print(f"Approval submitted successfully (HTTP {response.status_code})")
            except (
                KeyError,
                requests.exceptions.RequestException,
                RuntimeError,
            ) as exc:
                approval_error = exc
                print(f"Approval failed: {exc}")
        if was_auto_approved:
            _enable_merge_or_comment(
                repo, pr_number, reviewer, token=token, session=session
            )

    if not was_auto_approved:
        print("Policy result: automatic approval not performed")
        already_notified = (
            bool(head_sha)
            and not force_review
            and _has_pending_human_review_comment(
                repo, pr_number, head_sha, token=token, session=session
            )
        )
        if already_notified:
            print(
                "Result: human review was already requested for this commit; "
                "skipping duplicate comment"
            )
        else:
            failed_reasons = _collect_failure_reasons(
                is_post_release,
                release,
                files_complete,
                only_allowed_files,
                only_valid_bumps,
                approval_error,
            )
            _request_human_review(
                repo,
                pr_number,
                reviewer,
                failed_reasons,
                head_sha,
                token=token,
                session=session,
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
    dev_header="development version",
):
    """
    Evaluate and review a post-release cleanup pull request.

    Checks whether the PR satisfies four conditions:

    - **Condition 1** – the PR title matches the post-release cleanup
      pattern (``chore: post-release cleanup for <tag>``) and *<tag>*
      corresponds to an actual GitHub release.
    - **Condition 2** – the full list of changed files could be retrieved
      (fails closed if a pagination mismatch is detected), and only the
      version file, citation file, ``codemeta.json``, changelog file, news
      file, and/or readme files were changed.
    - **Condition 3** – the version file was actually changed, auditing that
      the ``post-release`` action did its job.
    - **Condition 4** – every changed file's new content is a valid bump for
      its role: the version file matches the expected dev version exactly;
      ``CITATION.cff`` and ``codemeta.json`` match the release tag/version
      with no other fields changed; the changelog/news file only gained the
      expected release heading; and readme files only had existing
      version/date tokens replaced (no inserted lines), matching a
      re-rendered citation snippet from the ``auto-format`` action.

    When all conditions are met the function approves any pending workflow
    runs on the PR's head branch, re-checks the PR's head commit immediately
    before approving (aborting if it changed since validation), approves the
    PR pinned to that commit, and attempts to enable squash auto-merge. If
    auto-merge cannot be enabled, it leaves a comment with the GitHub API
    error. Otherwise it posts a comment explaining why the PR needs manual
    review and requests a human reviewer, resolved via
    [](`~ccbr_actions.post_release_pr.determine_post_release_reviewer`).

    If the PR already has an APPROVED review tied to its current head commit,
    no new review is submitted and the function returns ``True`` immediately
    unless *force_review* is true. A stale approval left on an earlier commit
    (e.g. after the ``auto-format`` action pushes a citation rerender) does
    not count, so the PR is re-validated. Likewise, if a human-review comment
    was already posted for the current head commit, no duplicate comment or
    reviewer request is submitted (unless *force_review* is true) — this keeps
    a `synchronize`-triggered workflow from spamming the PR while the same
    unresolved commit is repeatedly re-evaluated.

    Args:
        repo (str): Repository full name (e.g. ``"CCBR/actions"``).
        pr_number (int | str): Pull request number.
        reviewer (str, optional): GitHub username to request when human
            review is required. If omitted, a reviewer is resolved
            automatically.
        token (str, optional): GitHub API token.
        session: Requests-compatible session object for dependency injection.
        force_review (bool, optional): Re-submit the review and reviewer
            request even when the PR already has an approval or was already
            notified for the current commit. Defaults to ``False``.
        version_filepath (str): Path to the version file. Defaults to
            ``"VERSION"``.
        citation_filepath (str): Path to the citation file. Defaults to
            ``"CITATION.cff"``.
        changelog_filepath (str): Path to the changelog file. Defaults to
            ``"CHANGELOG.md"``.
        description_filepath (str): Path to the R DESCRIPTION file, used when
            an R package's version file is the DESCRIPTION file. Defaults to
            ``"DESCRIPTION"``.
        dev_header (str): Development-version header text to locate in the
            changelog file (matched case-insensitively). Defaults to
            ``"development version"``.

    Returns:
        bool: ``True`` if the PR was already approved or was automatically
        approved, ``False`` if human review was requested.
    """
    print(f"Reviewing post-release cleanup PR {repo}#{pr_number}")
    pr_data = github_api_get(
        url=f"{GITHUB_API_URL}/repos/{repo}/pulls/{pr_number}",
        token=token,
        session=session,
    )
    head_sha = pr_data.get("head", {}).get("sha", "")
    already_approved = not force_review and is_pr_approved_for_commit(
        repo, pr_number, head_sha, token=token, session=session
    )
    if already_approved:
        print("Result: PR already has an APPROVED review for the current head commit")
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
            dev_header,
            force_review,
            pr_data,
        )
    return result
