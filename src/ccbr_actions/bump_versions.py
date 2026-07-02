"""
Bump GitHub Actions versions in workflow files.
"""

import os
import pathlib
import re
from typing import Optional

import requests

from .github import GITHUB_API_URL, github_api_get

LOCK_COMMENT = "ccbr_actions:lock-version"

# Matches a `uses:` line in a workflow YAML file.
# Captures the leading indent/dash, the full action reference, and any trailing comment.
_USES_PATTERN = re.compile(
    r"^(?P<indent>\s*(?:-\s+)?)uses:\s*(?P<action>[^\s#]+@[^\s#]+)(?P<comment>\s*#.*)?\s*$"
)

# Tag classification patterns
_MAJOR_ONLY = re.compile(r"^(v?)(\d+)$")
_MAJOR_MINOR = re.compile(r"^(v?)(\d+)\.(\d+)$")
_FULL_SEMVER = re.compile(r"^(v?)(\d+)\.(\d+)\.(\d+)(?:[.\-+].+)?$")
_GIT_SHA = re.compile(r"^[0-9a-f]{7,40}$", re.IGNORECASE)


def get_latest_release_tag_api(
    repo: str,
    token: Optional[str] = None,
    session=requests,
) -> Optional[str]:
    """
    Get the latest release tag for a GitHub repository using the GitHub API.

    Args:
        repo (str): The GitHub repository in the format ``owner/repo``.
        token (str, optional): GitHub API token for authenticated requests.
        session: Requests-compatible session object.

    Returns:
        str or None: The latest release tag name, or ``None`` if not found.

    Examples:
        >>> get_latest_release_tag_api('actions/checkout')  # doctest: +SKIP
        'v4.2.2'
    """
    url = f"{GITHUB_API_URL}/repos/{repo}/releases/latest"
    try:
        data = github_api_get(url=url, token=token, session=session)
        return data.get("tag_name")
    except (requests.exceptions.RequestException, RuntimeError, KeyError):
        return None


def parse_action_ref(action_str: str) -> tuple:
    """
    Parse an action string into a ``(repo, ref)`` tuple.

    The action string must contain ``@`` separating the repository path from the
    ref. For nested actions such as ``CCBR/actions/draft-release@v0.7``, the
    repository is taken as the first two path segments.

    Args:
        action_str (str): Action string, e.g. ``actions/checkout@v4``.

    Returns:
        tuple: A ``(repo, ref)`` pair where *repo* is ``owner/repo`` and *ref*
            is the version tag or SHA.

    Raises:
        ValueError: If ``action_str`` does not contain ``@``.

    Examples:
        >>> parse_action_ref('actions/checkout@v4')
        ('actions/checkout', 'v4')
        >>> parse_action_ref('CCBR/actions/draft-release@v0.7')
        ('CCBR/actions', 'v0.7')
    """
    if "@" not in action_str:
        raise ValueError(f"No '@' found in action string: {action_str!r}")
    at_idx = action_str.index("@")
    ref = action_str[at_idx + 1 :]
    repo_part = action_str[:at_idx]
    parts = repo_part.split("/")
    repo = "/".join(parts[:2]) if len(parts) >= 2 else repo_part  # abs-path:ignore
    return repo, ref


def classify_ref(ref: str) -> str:
    """
    Classify a git ref as one of several tag types.

    Args:
        ref (str): The ref string to classify.

    Returns:
        str: One of ``'sha'``, ``'major'``, ``'major_minor'``, ``'semver'``,
            or ``'named'``.

    Examples:
        >>> classify_ref('abc1234')
        'sha'
        >>> classify_ref('v4')
        'major'
        >>> classify_ref('v0.7')
        'major_minor'
        >>> classify_ref('v4.1.0')
        'semver'
        >>> classify_ref('latest')
        'named'
        >>> classify_ref('stable')
        'named'
    """
    if _GIT_SHA.match(ref):
        return "sha"
    if _MAJOR_ONLY.match(ref):
        return "major"
    if _MAJOR_MINOR.match(ref):
        return "major_minor"
    if _FULL_SEMVER.match(ref):
        return "semver"
    return "named"


def determine_new_ref(current_ref: str, latest_tag: Optional[str]) -> str:
    """
    Determine the new ref to use given the current ref and the latest release tag.

    Sliding tags (e.g. ``v4``, ``v0.7``) are preserved in style—only the
    version numbers are updated. Named refs (``latest``, ``stable``) and commit
    SHAs are returned unchanged.

    Args:
        current_ref (str): The currently pinned ref string.
        latest_tag (str or None): The latest release tag fetched from GitHub.
            If ``None``, *current_ref* is returned as-is.

    Returns:
        str: The new ref to use (may equal *current_ref* when no update is needed).

    Examples:
        >>> determine_new_ref('v7', 'v8.0.0')
        'v8'
        >>> determine_new_ref('v7', 'v7.3.0')
        'v7'
        >>> determine_new_ref('v0.7', 'v0.8.1')
        'v0.8'
        >>> determine_new_ref('v0.7', 'v0.7.5')
        'v0.7'
        >>> determine_new_ref('v4.1.0', 'v4.2.0')
        'v4.2.0'
        >>> determine_new_ref('v4.1.0', 'v4.1.0')
        'v4.1.0'
        >>> determine_new_ref('latest', 'v4.2.0')
        'latest'
        >>> determine_new_ref('stable', 'v4.2.0')
        'stable'
        >>> determine_new_ref('v4', None)
        'v4'
    """
    if latest_tag is None:
        return current_ref

    ref_type = classify_ref(current_ref)
    if ref_type in ("sha", "named"):
        return current_ref

    latest_major = latest_minor = latest_patch = None

    m_full = _FULL_SEMVER.match(latest_tag)
    m_mm = _MAJOR_MINOR.match(latest_tag)
    m_maj = _MAJOR_ONLY.match(latest_tag)

    if m_full:
        latest_major = int(m_full.group(2))
        latest_minor = int(m_full.group(3))
        latest_patch = int(m_full.group(4))
    elif m_mm:
        latest_major = int(m_mm.group(2))
        latest_minor = int(m_mm.group(3))
        latest_patch = 0
    elif m_maj:
        latest_major = int(m_maj.group(2))
        latest_minor = 0
        latest_patch = 0
    else:
        return current_ref

    if ref_type == "major":
        m = _MAJOR_ONLY.match(current_ref)
        prefix = m.group(1)
        current_major = int(m.group(2))
        if latest_major > current_major:
            return f"{prefix}{latest_major}"
        return current_ref

    if ref_type == "major_minor":
        m = _MAJOR_MINOR.match(current_ref)
        prefix = m.group(1)
        current_major = int(m.group(2))
        current_minor = int(m.group(3))
        if latest_major > current_major or (
            latest_major == current_major and latest_minor > current_minor
        ):
            return f"{prefix}{latest_major}.{latest_minor}"
        return current_ref

    if ref_type == "semver":
        m = _FULL_SEMVER.match(current_ref)
        prefix = m.group(1)
        current_major = int(m.group(2))
        current_minor = int(m.group(3))
        current_patch = int(m.group(4))
        if (
            latest_major > current_major
            or (latest_major == current_major and latest_minor > current_minor)
            or (
                latest_major == current_major
                and latest_minor == current_minor
                and latest_patch > current_patch
            )
        ):
            return f"{prefix}{latest_major}.{latest_minor}.{latest_patch}"
        return current_ref

    return current_ref


def bump_workflow_file(
    filepath,
    token: Optional[str] = None,
    session=requests,
    debug: bool = False,
) -> list:
    """
    Bump action versions in a single workflow YAML file.

    Lines containing ``# ccbr_actions:lock-version`` are skipped.
    Local actions (``uses: ./path/to/action``) are ignored because they contain
    no ``@`` separator.

    Args:
        filepath: Path to the workflow file to update.
        token (str, optional): GitHub API token.
        session: Requests-compatible session object.
        debug (bool): If ``True``, print proposed changes without writing to disk.

    Returns:
        list[str]: Descriptions of each substitution made (empty when nothing
            changed).

    Examples:
        >>> bump_workflow_file('path/to/workflow.yml', debug=True)  # doctest: +SKIP
        []
    """
    filepath = pathlib.Path(filepath)
    lines = filepath.read_text().splitlines(keepends=True)
    new_lines = []
    changes = []
    tag_cache: dict = {}

    for line in lines:
        new_line = line
        m = _USES_PATTERN.match(line.rstrip())
        comment = m.group("comment") or "" if m else ""

        if m and LOCK_COMMENT not in comment:
            action_str = m.group("action")
            try:
                repo, current_ref = parse_action_ref(action_str)
                if repo not in tag_cache:
                    tag_cache[repo] = get_latest_release_tag_api(
                        repo=repo, token=token, session=session
                    )
                latest_tag = tag_cache[repo]
                new_ref = determine_new_ref(current_ref, latest_tag)
                if new_ref != current_ref:
                    new_action_str = f"{action_str[: action_str.index('@')]}@{new_ref}"
                    new_line = line.replace(action_str, new_action_str, 1)
                    changes.append(f"{filepath}: {action_str} → {new_action_str}")
            except ValueError:
                pass

        new_lines.append(new_line)

    if changes:
        if debug:
            for change in changes:
                print(f"Would update: {change}")
        else:
            filepath.write_text("".join(new_lines))

    return changes


def bump_workflows(
    workflows_dir=".github/workflows",
    token: Optional[str] = None,
    session=requests,
    debug: bool = False,
) -> list:
    """
    Bump action versions in all ``*.yml`` files found in *workflows_dir*.

    Args:
        workflows_dir: Path to the directory containing workflow files.
            Defaults to ``.github/workflows``.
        token (str, optional): GitHub API token.
        session: Requests-compatible session object.
        debug (bool): If ``True``, print proposed changes without writing to disk.

    Returns:
        list[str]: Descriptions of all substitutions made across every file.

    Examples:
        >>> bump_workflows(debug=True)  # doctest: +SKIP
        []
    """
    workflows_dir = pathlib.Path(workflows_dir)
    all_changes = []
    for filepath in sorted(
        {*workflows_dir.glob("*.yml"), *workflows_dir.glob("*.yaml")}
    ):
        file_changes = bump_workflow_file(
            filepath=filepath, token=token, session=session, debug=debug
        )
        all_changes.extend(file_changes)
    return all_changes


def main(
    workflows_dir: str = ".github/workflows",
    debug: bool = False,
) -> list:
    """
    Bump action versions in all workflow files, using ``GH_TOKEN`` from the environment.

    Args:
        workflows_dir (str): Directory containing workflow YAML files.
        debug (bool): If ``True``, print changes without writing files.

    Returns:
        list[str]: Descriptions of all substitutions made.
    """
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    return bump_workflows(workflows_dir=workflows_dir, token=token, debug=debug)
