"""
Module for interacting with GitHub releases and tags.

This module provides functions to retrieve and process release information from GitHub using the GitHub CLI.

Examples
--------
>>> get_current_hash()
'def456ghi789'

>>> match_semver("1.0.0")
<re.Match object; span=(0, 5), match='1.0.0'>

>>> get_major_minor_version("1.2.3")
'1.2'

>>> is_ancestor("abc123def456", "def456ghi789")
True
"""

import re

from .util import shell_run


def get_current_hash():
    """
    Get the current commit hash.

    Uses git rev-parse HEAD to get the current commit hash.

    Returns
    -------
    str
        The current commit hash.

    See Also
    --------
    get_latest_release_hash : Get the commit hash of the latest release.

    Examples
    --------
    >>> get_current_hash()
    'abc123def4567890abcdef1234567890abcdef12'
    """
    return shell_run("git rev-parse HEAD")


def match_semver(version_str, with_leading_v=False):
    """
    Match a version string against the semantic versioning pattern.

    This function uses a regular expression to check if a given version string
    adheres to the semantic versioning (SemVer) specification.
    See the semantic versioning guidelines: <https://semver.org/>

    Parameters
    ----------
    version_str : str
        The version string to match.

    Returns
    -------
    re.Match or None
        The match object if the version string matches the semantic versioning pattern, otherwise None.

    See Also
    --------
    get_major_minor_version : Extract the major and minor version from a semantic versioning string.

    Examples
    --------
    >>> match_semver("1.0.0")
    <re.Match object; span=(0, 5), match='1.0.0'>
    >>> match_semver("1.0.0-alpha+001")
    <re.Match object; span=(0, 13), match='1.0.0-alpha+001'>
    >>> match_semver("invalid_version")
    None
    """
    semver_pattern = "(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)(?:-(?P<prerelease>(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?(?:\+(?P<buildmetadata>[0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?"
    if with_leading_v:
        semver_pattern = f"v{semver_pattern}"
    return re.match(semver_pattern, version_str)


def get_major_minor_version(version_str):
    """
    Extract the major and minor version from a semantic versioning string.

    See the semantic versioning guidelines: <https://semver.org/>

    Parameters
    ----------
    version_str : str
        The version string to extract from.

    Returns
    -------
    str or None
        The major and minor version in the format 'major.minor', or None if the version string is invalid.

    See Also
    --------
    match_semver : Match a version string against the semantic versioning pattern.

    Examples
    --------
    >>> get_major_minor_version("1.0.0")
    '1.0'
    >>> get_major_minor_version("2.1.3-alpha")
    '2.1'
    >>> get_major_minor_version("invalid_version")
    None
    """
    semver_match = match_semver(version_str)
    return (
        f"{semver_match.group('major')}.{semver_match.group('minor')}"
        if semver_match
        else None
    )


def check_version_increments_by_one(
    current_version, next_version, with_leading_v=False
):
    # assert semantic version pattern
    next_semver = match_semver(next_version, with_leading_v=with_leading_v)
    if not next_semver:
        extra_msg = ""
        if with_leading_v and not next_version.startswith("v"):
            extra_msg = "The tag does not start with 'v'."
        raise ValueError(
            f"Tag {next_version} does not match semantic versioning guidelines. {extra_msg}\nView the guidelines here: https://semver.org/"
        )

    # assert next version is only 1 greater than current
    current_semver = match_semver(current_version, with_leading_v=with_leading_v)
    greater = sum(
        [
            next_semver.group(grp) > current_semver.group(grp)
            for grp in ["major", "minor", "patch"]
        ]
    )
    if not (greater == 1):
        raise ValueError(
            f"Next version must only increment one number at a time. Current version: {current_version}. Proposed next version: {next_version}"
        )


def is_ancestor(ancestor, descendant):
    """
    Check if one commit is an ancestor of another.

    Uses git merge-base --is-ancestor to determine if the ancestor is an ancestor of the descendant.

    Parameters
    ----------
    ancestor : str
        The commit hash of the potential ancestor.
    descendant : str
        The commit hash of the potential descendant.

    Returns
    -------
    bool
        True if the ancestor is an ancestor of the descendant, otherwise False.

    See Also
    --------
    get_latest_release_hash : Get the commit hash of the latest release.
    get_current_hash : Get the commit hash of the current.

    Examples
    --------
    >>> is_ancestor("abc123", "def456")
    True
    >>> is_ancestor("abc123", "ghi789")
    False
    """
    return bool(
        shell_run(
            f"git merge-base --is-ancestor {ancestor} {descendant}  && echo True || echo False"
        ).strip()
    )
