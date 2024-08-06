import json
import os
import re
import warnings

from .util import shell_run


def get_releases(limit=1, args=""):
    releases = shell_run(
        f"gh release list --limit {limit} --json name,tagName,isLatest,publishedAt {args}"
    )
    return json.loads(releases)


def get_latest_release_tag(args=""):
    releases = get_releases(limit=1, args=args)
    return releases[0]["tagName"] if releases and releases[0]["isLatest"] else None


def get_latest_release_hash():
    tag_name = get_latest_release_tag()
    tag_hash = shell_run(f"git rev-list -n 1 {tag_name}")
    if "fatal: ambiguous argument" in tag_hash:
        raise ValueError(f"Tag {tag_name} not found in repository commit history")
    return tag_hash


def get_current_hash():
    return shell_run("git rev-parse HEAD")


def match_semver(version_str):
    semver_pattern = "(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)(?:-(?P<prerelease>(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?(?:\+(?P<buildmetadata>[0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?"
    return re.match(semver_pattern, version_str)


def get_major_minor_version(version_str):
    semver_match = match_semver(version_str)
    return (
        f"{semver_match.group('major')}.{semver_match.group('minor')}"
        if semver_match
        else None
    )


def is_ancestor(ancestor, descendant):
    return bool(
        shell_run(
            f"git merge-base --is-ancestor {ancestor} {descendant}  && echo True || echo False"
        ).strip()
    )
